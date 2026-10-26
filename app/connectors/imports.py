import csv
import io
import json
from datetime import datetime
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import select

from app.models import ImportedMessage, PlatformBinding, Source
from app.services.security import audit

MAX_SIZE = 1024 * 1024


class ImportMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    platform: Literal["wecom", "feishu"]
    platform_tenant: str = Field(min_length=1, max_length=100)
    application_id: str = Field(min_length=1, max_length=100)
    chat_id: str = Field(min_length=1, max_length=100)
    message_id: str = Field(min_length=1, max_length=100)
    sender: str = Field(min_length=1, max_length=100)
    timestamp: datetime
    reply_to: str | None = Field(default=None, max_length=100)
    content: str = Field(min_length=1, max_length=10000)

    @field_validator("timestamp")
    @classmethod
    def timezone_required(cls, value):
        if value.tzinfo is None:
            raise ValueError("timestamp 必须包含时区")
        return value


def parse(data, filename):
    if len(data) > MAX_SIZE:
        raise HTTPException(413, "文件不得超过 1 MiB")
    try:
        text = data.decode("utf-8-sig")
        if filename.lower().endswith(".json"):
            rows = json.loads(text)
        elif filename.lower().endswith(".csv"):
            rows = list(csv.DictReader(io.StringIO(text)))
        else:
            raise ValueError("只接受 UTF-8 JSON 或 CSV")
        if not isinstance(rows, list) or not 1 <= len(rows) <= 500:
            raise ValueError("每次导入 1 至 500 条消息")
        return [ImportMessage.model_validate({**r, "reply_to": r.get("reply_to") or None}) for r in rows]
    except (ValueError, TypeError, AttributeError, UnicodeDecodeError, ValidationError) as exc:
        raise HTTPException(422, "格式错误：检查必填字段、UTF-8、时区与消息长度（见导入格式文档）") from exc


def resolve_binding(access, row):
    binding = access.db.scalar(select(PlatformBinding).where(
        PlatformBinding.organization_id == access.user.organization_id,
        PlatformBinding.platform == row.platform, PlatformBinding.platform_tenant == row.platform_tenant,
        PlatformBinding.application_id == row.application_id, PlatformBinding.chat_id == row.chat_id,
        PlatformBinding.customer_account_id.in_(access.customer_ids())
    ))
    if not binding:
        raise HTTPException(403, "平台、应用与群的服务器绑定不存在或无权访问；文件不能自行指定客户")
    return binding


def import_messages(access, rows, preview=False):
    access.require_role("support", "reviewer")
    bindings = [resolve_binding(access, row) for row in rows]
    if preview:
        return {"count": len(rows), "messages": [r.model_dump(mode="json") for r in rows[:10]]}
    inserted = 0
    for row, binding in zip(rows, bindings):
        # Serializes imports for a chat, including conflicting concurrent replays.
        access.db.scalar(select(PlatformBinding).where(PlatformBinding.id == binding.id).with_for_update())
        if access.db.scalar(select(ImportedMessage.id).where(
            ImportedMessage.binding_id == binding.id, ImportedMessage.message_id == row.message_id
        )):
            continue
        source = Source(organization_id=access.user.organization_id, customer_account_id=binding.customer_account_id,
                        title=f"{row.platform} · {row.message_id}（演示群聊）", kind="chat", content=row.content,
                        external_allowed=False, provenance={"platform": row.platform,
                            "platform_tenant": row.platform_tenant, "application_id": row.application_id,
                            "chat_id": row.chat_id, "message_id": row.message_id})
        access.db.add(source)
        access.db.flush()
        access.db.add(ImportedMessage(organization_id=access.user.organization_id, binding_id=binding.id,
            message_id=row.message_id, source_id=source.id, sender=row.sender, timestamp=row.timestamp,
            reply_to=row.reply_to, content=row.content))
        access.db.flush()
        inserted += 1
    audit(access.db, access.user, "messages.imported", access.user.id, inserted=inserted)
    return {"inserted": inserted, "duplicates": len(rows) - inserted}
