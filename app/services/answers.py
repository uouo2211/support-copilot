import re
import time

from fastapi import HTTPException
from sqlalchemy import select

from app.config import settings
from app.models import Customer, Draft, Feedback, Handoff, Message, ReplyAction
from app.providers.ai import generate
from app.schemas.answer import Answer, Citation
from app.services.retrieval import retrieve
from app.services.security import audit, check_outbound, redact, text_hash


def fallback(decision, reason, text, version, missing=None):
    return Answer(answer=text, citations=[], applicability=f"DataPilot {version or '版本未知'} · 演示数据",
                  missing_context=missing or [], decision=decision, reason_codes=[reason])


def answer_question(access, conv, question):
    # Deterministic safety rules are independent of provider and never invoke tools.
    if re.search(r"忽略.*(?:指令|规则)|系统提示词|system\s*prompt|ignore.*instructions|绕过.*权限|扮演.*管理员", question, re.I):
        return fallback("deny", "UNTRUSTED_INSTRUCTION", "无法遵循更改系统规则或绕过权限的请求。", conv.product_version)
    if re.search(r"drop\s+(?:table|database)|删库|删除数据库|执行.*(?:命令|SQL)|关闭.*审计|泄露.*(?:密钥|密码)", question, re.I):
        return fallback("handoff", "HIGH_RISK", "涉及高风险操作，需要技术支持核实授权与变更流程。本助手不会执行数据库命令。", conv.product_version)
    all_customers = list(access.db.scalars(select(Customer).where(Customer.organization_id == access.user.organization_id)))
    for customer in all_customers:
        if customer.id != conv.customer_account_id and (customer.id in question or customer.name.replace("（演示）", "") in question):
            return fallback("deny", "CUSTOMER_SCOPE", "不能在当前会话中查询其他客户数据。", conv.product_version)
    if re.search(r"其他客户|全部客户|跨客户|另一客户", question):
        return fallback("deny", "CUSTOMER_SCOPE", "当前会话只允许访问已绑定客户的授权证据。", conv.product_version)
    if re.search(r"今天.*(?:资讯|新闻)|最新.*(?:新闻|资讯)|安全公告|行业资讯", question):
        return fallback("deny", "NEWS_SEPARATE", "资讯在独立资讯页管理，不作为 DataPilot 产品事实。replay 是固定模拟快照，不代表当天新闻。", conv.product_version)
    rows, retrieval = retrieve(access, conv, question)
    if not rows:
        return fallback("deny", "NO_EVIDENCE", "当前授权范围内没有足够的已发布有效证据，不能据此编造答案。请补充正式文档或转技术核实。", conv.product_version)
    if not conv.product_version:
        return fallback("clarify", "VERSION_REQUIRED", "请先确认 DataPilot 产品版本（例如 3.1 或 3.2），不同版本的适用方案可能不同。",
                        None, ["DataPilot 产品版本"])
    claims = {}
    for row in rows:
        rev = row.Revision
        if rev.claim_key and rev.authority >= 3:
            claims.setdefault(rev.claim_key, set()).add(rev.claim_value)
    if any(len(values) > 1 for values in claims.values()):
        result = fallback("handoff", "EVIDENCE_CONFLICT", "同一适用版本的正式证据存在冲突，已停止给出操作结论，请转技术支持核实。", conv.product_version)
        result.citations = [citation(r) for r in rows]
        return result
    chosen = rows[:3]
    if settings().ai_mode == "mock":
        text = "\n\n".join(dict.fromkeys(redact(r.Chunk.text) for r in chosen))
        check_outbound(text)
        return Answer(answer=text, citations=[citation(r) for r in chosen],
                      applicability=f"DataPilot {conv.product_version} · 当前客户授权范围 · 演示数据",
                      missing_context=[], decision="suggest", reason_codes=["DETERMINISTIC_EVIDENCE_EXTRACT"], retrieval=retrieval)
    messages = list(access.db.scalars(select(Message).where(
        Message.conversation_id == conv.id, Message.organization_id == access.user.organization_id
    ).order_by(Message.created_at.desc()).limit(8)))
    model = generate(redact(question), [redact(m.content) for m in messages],
                     [{"id": r.Chunk.id, "text": redact(r.Chunk.text)} for r in chosen])
    allowed = {r.Chunk.id: r for r in chosen}
    if any(i not in allowed for i in model.evidence_ids) or (model.decision == "suggest" and not model.evidence_ids):
        raise HTTPException(502, "模型引用校验失败；输出未保存")
    check_outbound(model.answer)
    result = Answer(**model.model_dump(exclude={"evidence_ids"}),
                    citations=[citation(allowed[i]) for i in dict.fromkeys(model.evidence_ids)], retrieval=retrieval)
    # Customer names in generated output must not introduce another account.
    for customer in all_customers:
        if customer.id != conv.customer_account_id and customer.name.replace("（演示）", "") in result.answer:
            raise HTTPException(502, "模型输出隐私校验失败")
    return result


def citation(row):
    return Citation(evidence_id=row.Chunk.id, revision_id=row.Revision.id, source_id=row.Source.id,
                    title=row.Knowledge.title, excerpt=redact(row.Chunk.text),
                    external_allowed=row.Source.external_allowed and row.Revision.visibility == "public")


def create_draft(access, cid, question):
    access.require_role("support")
    conv = access.conversation(cid, lock=True)
    started = time.perf_counter()
    answer = answer_question(access, conv, question)
    row = Draft(organization_id=access.user.organization_id, conversation_id=conv.id,
                operator_id=access.user.id, question=question, original=answer.model_dump(),
                edited_answer=answer.answer, mode=settings().ai_mode,
                latency_ms=int((time.perf_counter() - started) * 1000))
    access.db.add(row)
    access.db.flush()
    audit(access.db, access.user, "draft.generated", row.id, decision=answer.decision, mode=row.mode)
    return row


def validate_evidence(access, draft):
    conv = access.conversation(draft.conversation_id)
    current = {r.Chunk.id: r.Revision.id for r in access.evidence(conv)}
    for c in draft.original["citations"]:
        if current.get(c["evidence_id"]) != c["revision_id"]:
            raise HTTPException(409, "引用已撤销、过期、变化或失去授权，请重新生成草稿")
    check_outbound(draft.edited_answer)


def edit_draft(access, did, revision, text):
    access.require_role("support")
    draft = access.draft(did, lock=True)
    if draft.revision != revision:
        raise HTTPException(409, "草稿已更新，请刷新后重试")
    if draft.edited_answer != text:
        draft.edited_answer = text
        draft.revision += 1
        draft.confirmed_hash = None
        audit(access.db, access.user, "draft.edited", draft.id, text_revision=draft.revision)
    return draft


def confirm(access, did, revision):
    access.require_role("support")
    draft = access.draft(did, lock=True)
    if draft.revision != revision:
        raise HTTPException(409, "确认文本版本不一致，请重新确认")
    validate_evidence(access, draft)
    digest = text_hash(draft)
    action = access.db.scalar(select(ReplyAction).where(ReplyAction.draft_id == did, ReplyAction.text_hash == digest))
    if not action:
        # Internal source links/excerpts are never appended to the customer-facing text.
        action = ReplyAction(organization_id=access.user.organization_id, draft_id=did,
                             conversation_id=draft.conversation_id, operator_id=access.user.id,
                             text_hash=digest, text=draft.edited_answer, citations=draft.original["citations"])
        access.db.add(action)
        access.db.flush()
        audit(access.db, access.user, "reply.confirmed", action.id, text_revision=revision)
    draft.confirmed_hash = digest
    return action


def mark_sent(access, did, action_id):
    access.require_role("support")
    draft = access.draft(did, lock=True)
    action = access.db.get(ReplyAction, action_id)
    if not action or action.draft_id != did or action.text_hash != draft.confirmed_hash or action.text_hash != text_hash(draft):
        raise HTTPException(409, "文本已改变或尚未确认，不能标记回复")
    validate_evidence(access, draft)
    action.status = "manually_replied"
    access.conversation(draft.conversation_id).status = "replied"
    audit(access.db, access.user, "reply.manually_replied", action.id)
    return action


def handoff(access, did, troubleshooting):
    access.require_role("support", "technical")
    draft = access.draft(did, lock=True)
    conv = access.conversation(draft.conversation_id)
    existing = access.db.scalar(select(Handoff).where(Handoff.draft_id == did))
    if existing:
        return existing
    current = {r.Chunk.id for r in access.evidence(conv)}
    row = Handoff(organization_id=access.user.organization_id, draft_id=did,
                  conversation_id=conv.id, operator_id=access.user.id,
                  payload={"question": draft.question, "version": conv.product_version,
                           "troubleshooting": redact(troubleshooting),
                           "citations": [c for c in draft.original["citations"] if c["evidence_id"] in current],
                           "missing_context": draft.original["missing_context"]})
    access.db.add(row)
    conv.status = "handoff"
    access.db.flush()
    audit(access.db, access.user, "technical.handoff", row.id)
    return row


def feedback(access, did, rating, note):
    access.require_role("support", "technical")
    access.draft(did)
    row = Feedback(organization_id=access.user.organization_id, draft_id=did,
                   operator_id=access.user.id, rating=rating, note=redact(note))
    access.db.add(row)
    audit(access.db, access.user, "feedback.recorded", did, rating=rating)
