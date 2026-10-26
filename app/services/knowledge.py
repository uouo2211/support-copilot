import hashlib
import re
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import delete, select

from app.config import settings
from app.models import Chunk, Draft, ImportedMessage, Knowledge, Organization, Revision, Source, now
from app.providers.ai import embed
from app.repositories.access import version_matches
from app.services.security import audit, redact


def build_chunks(db, rev):
    texts = [p.strip() for p in re.split(r"\n\s*\n", rev.content) if p.strip()]
    if not texts:
        raise HTTPException(422, "知识内容不能为空")
    vectors = embed(texts)
    for i, text in enumerate(texts):
        db.add(Chunk(organization_id=rev.organization_id, revision_id=rev.id, text=text,
                     embedding=vectors[i] if vectors else None,
                     embedding_space=settings().embedding_space if vectors else None))
    db.flush()


def extract_candidate(access, source_id):
    access.require_role("support", "reviewer")
    source = access.source(source_id)
    if source.kind != "chat":
        raise HTTPException(422, "候选提取只适用于授权导入的聊天")
    existing = access.db.scalar(select(Revision).where(Revision.source_id == source_id))
    if existing:
        return access.knowledge(existing.knowledge_id)
    message = access.db.scalar(select(ImportedMessage).where(ImportedMessage.source_id == source_id))
    linked = [message]
    if message:
        candidates = list(access.db.scalars(select(ImportedMessage).where(
            ImportedMessage.binding_id == message.binding_id,
            ImportedMessage.timestamp.between(message.timestamp - timedelta(minutes=30), message.timestamp + timedelta(minutes=30))
        ).order_by(ImportedMessage.timestamp)))
        ids = {message.message_id}
        if message.reply_to:
            ids.add(message.reply_to)
        for _ in range(4):
            for item in candidates:
                if item.reply_to in ids:
                    ids.add(item.message_id)
        linked = [item for item in candidates if item.message_id in ids]
    content = redact("\n".join(item.content for item in linked)) if message else redact(source.content)
    fingerprint = hashlib.sha256(content.encode()).hexdigest()
    for revision in access.db.scalars(select(Revision).where(
        Revision.organization_id == access.user.organization_id,
        Revision.customer_account_id == source.customer_account_id
    )):
        if hashlib.sha256(revision.content.encode()).hexdigest() == fingerprint:
            return access.knowledge(revision.knowledge_id)
    category = "已验证方案" if "已验证" in content else "临时建议" if "建议" in content else "猜测"
    row = Knowledge(organization_id=access.user.organization_id, customer_account_id=source.customer_account_id,
                    title=f"{category} · {source.title}", status="pending_review")
    access.db.add(row)
    access.db.flush()
    rev = Revision(organization_id=row.organization_id, knowledge_id=row.id, source_id=source.id,
                   content=content, customer_account_id=row.customer_account_id, visibility="customer",
                   version_min="3.2", version_max="3.2", authority=1, topic="备份 prefix",
                   verification=f"候选分类：{category}；尚未由审核员核验")
    access.db.add(rev)
    access.db.flush()
    row.current_revision_id = rev.id
    audit(access.db, access.user, "knowledge.extracted", row.id, source_ids=[i.source_id for i in linked if i])
    return row


def publish(access, kid, content, lower, upper, verification, public_approved=False, expected_revision=None):
    access.require_role("reviewer")
    knowledge = access.knowledge(kid, lock=True)
    old = access.db.get(Revision, knowledge.current_revision_id)
    if expected_revision and old.id != expected_revision:
        raise HTTPException(409, "知识已变化，请刷新审核页面")
    source = access.source(old.source_id)
    if not version_matches(lower, lower, upper):
        raise HTTPException(422, "产品版本范围无效")
    if not verification.strip():
        raise HTTPException(422, "发布必须填写验证材料")
    if public_approved and source.customer_account_id:
        # Publish only a separately approved, sanitized source. Never expose the original chat.
        source = Source(organization_id=knowledge.organization_id, customer_account_id=None,
                        title=knowledge.title + " · 公开授权副本", kind="approved_excerpt", content=redact(content),
                        external_allowed=True, provenance={"dependency_source_id": old.source_id,
                                                           "public_approved_by": access.user.id})
        access.db.add(source)
        access.db.flush()
    scope = None if public_approved else knowledge.customer_account_id
    rev = Revision(organization_id=knowledge.organization_id, knowledge_id=kid, source_id=source.id,
                   content=redact(content), customer_account_id=scope,
                   visibility="public" if scope is None else "customer", public_approved=scope is None,
                   version_min=lower, version_max=upper, verification=verification,
                   authority=3, topic=old.topic, claim_key=old.claim_key, claim_value=old.claim_value,
                   valid_until=old.valid_until, reviewed_by=access.user.id)
    access.db.add(rev)
    access.db.flush()
    build_chunks(access.db, rev)
    # The pointer changes only after all snippets/vectors are prepared in this transaction.
    knowledge.current_revision_id = rev.id
    knowledge.customer_account_id = scope
    knowledge.status = "published"
    knowledge.updated_at = now()
    bump_index(access.db, knowledge.organization_id)
    audit(access.db, access.user, "knowledge.published", kid, revision_id=rev.id, public_approved=public_approved)
    return knowledge


def bump_index(db, oid):
    org = db.scalar(select(Organization).where(Organization.id == oid).with_for_update())
    org.index_version += 1


def change_status(access, kid, status):
    access.require_role("reviewer")
    knowledge = access.knowledge(kid, lock=True)
    if status not in {"revoked", "rejected", "pending_review", "superseded"}:
        raise HTTPException(422, "无效状态")
    knowledge.status = status
    knowledge.updated_at = now()
    bump_index(access.db, knowledge.organization_id)
    audit(access.db, access.user, f"knowledge.{status}", kid)
    return knowledge


def rollback(access, kid, revision_id):
    access.require_role("reviewer")
    knowledge = access.knowledge(kid, lock=True)
    rev = access.db.get(Revision, revision_id)
    if not rev or rev.knowledge_id != kid or not rev.reviewed_by:
        raise HTTPException(422, "只能回滚到已审核的同一知识修订")
    access.source(rev.source_id)
    if rev.valid_until and rev.valid_until <= now():
        raise HTTPException(409, "旧修订已过期，不能回滚")
    # Clone into a new immutable revision, retaining previous history.
    old_current = knowledge.current_revision_id
    knowledge.current_revision_id = rev.id
    result = publish(access, kid, rev.content, rev.version_min, rev.version_max,
                     f"回滚已验证修订 {rev.id}；{rev.verification}", rev.public_approved)
    audit(access.db, access.user, "knowledge.rollback", kid, previous_revision=old_current, restored_revision=rev.id)
    return result


def withdraw_source(access, sid, erase=False):
    access.require_role("reviewer")
    source = access.source(sid)
    affected = [source]
    for candidate in access.db.scalars(select(Source).where(Source.organization_id == access.user.organization_id)):
        if candidate.provenance.get("dependency_source_id") == sid:
            affected.append(candidate)
    source_ids = [s.id for s in affected]
    revisions = list(access.db.scalars(select(Revision).where(Revision.source_id.in_(source_ids))))
    kids = {r.knowledge_id for r in revisions}
    for k in access.db.scalars(select(Knowledge).where(Knowledge.id.in_(kids))):
        k.status = "pending_review"
    for s in affected:
        s.active = False
        if erase:
            s.content = "[已删除]"
            s.provenance = {}
            s.external_url = None
            s.title = "已删除来源"
    if erase:
        all_revs = list(access.db.scalars(select(Revision).where(Revision.knowledge_id.in_(kids))))
        ids = [r.id for r in all_revs]
        access.db.execute(delete(Chunk).where(Chunk.revision_id.in_(ids)))
        access.db.execute(delete(ImportedMessage).where(ImportedMessage.source_id.in_(source_ids)))
        for rev in all_revs:
            rev.content = "[已删除]"
            rev.verification = "[已删除]"
        # Remove derived draft text as well; minimal audit metadata remains.
        from app.models import Feedback, Handoff, ReplyAction
        for draft in access.db.scalars(select(Draft).where(Draft.organization_id == access.user.organization_id)):
            if any(c["revision_id"] in ids for c in draft.original["citations"]):
                draft.original = {**draft.original, "answer": "[来源已删除]", "citations": []}
                draft.edited_answer = "[来源已删除]"
                draft.question = "[已删除]"
                draft.confirmed_hash = None
                draft.revision += 1
                for action in access.db.scalars(select(ReplyAction).where(ReplyAction.draft_id == draft.id)):
                    action.text = "[来源已删除]"
                    action.citations = []
                for h in access.db.scalars(select(Handoff).where(Handoff.draft_id == draft.id)):
                    h.payload = {"deleted": True}
                for f in access.db.scalars(select(Feedback).where(Feedback.draft_id == draft.id)):
                    f.note = "[已删除]"
    bump_index(access.db, source.organization_id)
    audit(access.db, access.user, "source.erased" if erase else "source.withdrawn", sid)


def reindex(db):
    revisions = list(db.scalars(select(Revision).join(Knowledge, Knowledge.current_revision_id == Revision.id)
                               .where(Knowledge.status == "published")))
    for rev in revisions:
        db.execute(delete(Chunk).where(Chunk.revision_id == rev.id))
        build_chunks(db, rev)
    for org in db.scalars(select(Organization)):
        org.index_version += 1
