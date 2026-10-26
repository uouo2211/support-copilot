"""演示数据种子脚本。

复用项目原有的知识提取、群聊导入解析、发布等业务逻辑写入演示数据，保证 demo 行为与原设计一致。
幂等：重复执行不会产生重复数据。使用 --reset 可先清空演示库。

    python -m scripts.seed_demo
    python -m scripts.seed_demo --reset
"""

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.config import settings
from app.connectors.imports import import_messages, parse
from app.db import Base, SessionLocal, engine
from app.models import (Assignment, Conversation, Customer, ImportedMessage, Knowledge, Message,
                        NewsItem, Organization, PlatformBinding, Revision, Source, User, now)
from app.repositories.access import Access
from app.services import knowledge as ksvc
from app.services.security import password_hash

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "fixtures"
ORG = "org-demo"
PASSWORD = settings().demo_password


def ensure(db, model, row_id, **fields):
    """按主键幂等写入。Assignment 为 (user_id, customer_account_id) 复合主键，需传元组。"""
    key = row_id if isinstance(row_id, tuple) else (row_id,)
    if len(key) == 1 and db.get(model, row_id):
        return db.get(model, row_id)
    if len(key) > 1 and db.get(model, row_id):
        return db.get(model, row_id)
    row = model(**fields) if len(key) > 1 else model(id=row_id, **fields)
    db.add(row)
    db.flush()
    return row


def bootstrap(db):
    ensure(db, Organization, ORG, name="DataPilot 演示组织", index_version=1)
    ensure(db, Customer, "customer-a", organization_id=ORG, name="客户 A（演示）", product_version="3.2")
    ensure(db, Customer, "customer-b", organization_id=ORG, name="客户 B（演示）", product_version="3.1")
    for slug, display, role in [("staff-a", "客服小林", "support"), ("reviewer", "审核员李岚", "reviewer"),
                                ("tech", "技术支持王栋", "technical")]:
        ensure(db, User, slug, organization_id=ORG, username=slug, display_name=display,
               password_hash=password_hash(PASSWORD), role=role)
    for user in ("staff-a", "reviewer", "tech"):
        for cid in ("customer-a", "customer-b"):
            ensure(db, Assignment, (user, cid), user_id=user, customer_account_id=cid)
    ensure(db, PlatformBinding, "bind-wecom-a", organization_id=ORG, platform="wecom",
           platform_tenant="demo-corp", application_id="archive-demo", chat_id="group-a",
           customer_account_id="customer-a")
    ensure(db, PlatformBinding, "bind-feishu-b", organization_id=ORG, platform="feishu",
           platform_tenant="demo-tenant", application_id="knowledge-demo", chat_id="group-b",
           customer_account_id="customer-b")
    db.commit()


def load_documents(db):
    """产品文档：正式导入即 published。

    注意访问权限规则：面向全部客户的公共知识必须同时满足
    visibility=public、public_approved=True、customer_account_id 为空，三者缺一不可。
    """
    docs = json.loads((FIXTURES / "documents.json").read_text(encoding="utf-8"))
    created = 0
    for doc in docs:
        if db.get(Source, f"s-{doc['id']}"):
            continue
        private = doc.get("customer")
        source = Source(id=f"s-{doc['id']}", organization_id=ORG, customer_account_id=private,
                        title=doc["title"], kind="doc", content=doc["content"],
                        external_allowed=False, provenance={"fixture": doc["id"]})
        db.add(source)
        db.flush()

        kid = f"k-{doc['id']}"
        knowledge = Knowledge(id=kid, organization_id=ORG, customer_account_id=private,
                              title=doc["title"], status="published")
        db.add(knowledge)
        db.flush()

        rev = Revision(id=f"r-{doc['id']}", organization_id=ORG, knowledge_id=kid, source_id=source.id,
                       content=doc["content"], customer_account_id=private,
                       visibility="customer" if private else "public",
                       public_approved=private is None,
                       version_min=doc.get("min", "3.1"), version_max=doc.get("max", "3.2"),
                       authority=3 if doc.get("claim_key") else 2, topic=doc["topic"],
                       claim_key=doc.get("claim_key"), claim_value=doc.get("claim_value"),
                       valid_until=now() if doc.get("expired") else None,
                       verification="演示产品文档库，随版本发布同步更新", reviewed_by="reviewer")
        db.add(rev)
        db.flush()
        knowledge.current_revision_id = rev.id
        db.flush()
        ksvc.build_chunks(db, rev)
        created += 1
    db.commit()
    return created


def load_chats(db, access):
    """群聊导入走真实 connectors.imports 解析与服务器绑定校验，客户归属不能由文件决定。"""
    inserted = 0
    for name in ("wecom.json", "feishu.csv"):
        rows = parse((FIXTURES / name).read_bytes(), name)
        inserted += import_messages(access, rows)["inserted"]
    db.commit()
    return inserted


def extract_pending(db, access, message_id):
    """未核验的群聊结论只能成为待审核候选，审核前不进入正式索引。"""
    row = db.scalar(select(ImportedMessage).where(ImportedMessage.message_id == message_id))
    if not row:
        return None
    if db.scalar(select(Revision).where(Revision.source_id == row.source_id)):
        return None
    access.user = db.get(User, "reviewer")
    knowledge = ksvc.extract_candidate(access, row.source_id)
    knowledge.status = "pending_review"
    db.commit()
    return knowledge


def load_conversations(db):
    cases = [
        ("conv-a-alert", "customer-a", "3.2", "3.2 告警恢复后没有通知",
         ["我们 DataPilot 3.2 告警恢复了，但是一条通知都没收到，怎么排查？"]),
        ("conv-a-backup", "customer-a", "3.2", "3.2 备份对象找不到",
         ["DataPilot 3.2 备份对象找不到，任务却显示成功，到底有没有成功？"]),
        ("conv-a-noversion", "customer-a", None, "版本未知：监控看不到数据",
         ["我们的监控面板最近看不到数据了，帮我看看是什么问题？"]),
        ("conv-b-alert", "customer-b", "3.1", "3.1 告警通知路由咨询",
         ["DataPilot 3.1 的告警通知是怎么配的？接收组在哪里设置？"]),
    ]
    for cid, account, version, title, questions in cases:
        if db.get(Conversation, cid):
            continue
        db.add(Conversation(id=cid, organization_id=ORG, customer_account_id=account,
                            title=title, product_version=version, platform="wecom", status="open"))
        db.flush()
        for index, question in enumerate(questions):
            db.add(Message(id=f"{cid}-m{index}", organization_id=ORG, conversation_id=cid,
                           sender="客户（演示）", content=question, created_at=now()))
        db.flush()
    db.commit()


def load_news(db):
    """replay 快照 A（2 条）与 B（3 条），用于验证幂等去重：A→B→B 记录数为 2→3→3。"""
    items = json.loads((FIXTURES / "news.json").read_text(encoding="utf-8"))
    for mode, rows in {"A": items[:2], "B": items}.items():
        for item in rows:
            guid = f"{item['source']}:{item['guid']}"
            if db.scalar(select(NewsItem.id).where(NewsItem.mode == mode, NewsItem.guid == guid)):
                continue
            published = (datetime.fromisoformat(item["published_at"]).astimezone(timezone.utc)
                         if item["published_at"] else None)
            db.add(NewsItem(mode=mode, source=item["source"], guid=guid,
                            canonical_url=item["url"],
                            content_hash=hashlib.sha256(item["title"].encode()).hexdigest(),
                            title=item["title"], summary=item["summary"], category=item["source"],
                            status="collected", published_at=published, collected_at=now()))
        db.flush()
    db.commit()


def main():
    if "--reset" in sys.argv:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        bootstrap(db)
        access = Access(db, db.get(User, "staff-a"))
        docs = load_documents(db)
        chats = load_chats(db, access)
        pending = extract_pending(db, access, "backup-102")
        load_conversations(db)
        load_news(db)
        print("演示数据就绪")
        print(f"  产品文档知识：{docs} 条新增")
        print(f"  群聊消息导入：{chats} 条新增")
        print(f"  待审核候选：{pending.title if pending else '（已存在）'}")
        print("  会话：4 个 · replay 快照：A=2 条 / B=3 条")
        print(f"  演示账号：staff-a / reviewer / tech，统一密码 {PASSWORD}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
