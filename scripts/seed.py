import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.config import settings
from app.connectors.imports import import_messages, parse
from app.db import SessionLocal
from app.models import Assignment, Conversation, Customer, Knowledge, Message, Organization, PlatformBinding, Revision, Source, User
from app.repositories.access import Access
from app.services.knowledge import build_chunks
from app.services.security import password_hash


def seed(db):
    if settings().environment == "production":
        raise RuntimeError("生产环境禁止导入演示账号与数据")
    if not db.get(Organization, "demo-org"):
        db.add(Organization(id="demo-org", name="DataPilot 演示组织"))
        db.flush()
    for cid, name, version in [("customer-a", "客户 A（演示）", "3.2"), ("customer-b", "客户 B（演示）", "3.1")]:
        if not db.get(Customer, cid):
            db.add(Customer(id=cid, organization_id="demo-org", name=name, product_version=version))
    for username, role, name, customers in [
        ("agent_a", "support", "林悦 · 客服 A", ["customer-a"]),
        ("agent_b", "support", "周宁 · 客服 B", ["customer-b"]),
        ("reviewer", "reviewer", "陈知 · 知识审核员", ["customer-a", "customer-b"]),
        ("technical", "technical", "沈工 · 技术支持", ["customer-a", "customer-b"]),
    ]:
        if not db.get(User, username):
            db.add(User(id=username, organization_id="demo-org", username=username, display_name=name,
                        role=role, password_hash=password_hash(settings().demo_password)))
            db.flush()
        for cid in customers:
            if not db.get(Assignment, (username, cid)):
                db.add(Assignment(user_id=username, customer_account_id=cid))
    db.flush()
    for cid, customer, title, version, question in [
        ("conv-a", "customer-a", "告警没有恢复通知", "3.2", "DataPilot 3.2 告警恢复后没有通知，需要检查什么？"),
        ("conv-backup", "customer-a", "备份对象找不到", "3.2", "备份查看了错误 prefix 怎么排查？"),
        ("conv-unknown", "customer-a", "版本信息待补充", None, "支持 PostgreSQL 16 吗？"),
        ("conv-conflict", "customer-a", "自动重试次数核实", "3.2", "任务自动重试次数是多少？"),
        ("conv-b", "customer-b", "数据库兼容性确认", "3.1", "3.1 支持 PostgreSQL 15 吗？"),
    ]:
        if not db.get(Conversation, cid):
            db.add(Conversation(id=cid, organization_id="demo-org", customer_account_id=customer,
                                title=title, product_version=version))
            db.flush()
            db.add(Message(id="msg-" + cid, organization_id="demo-org", conversation_id=cid,
                           sender="客户运维（演示）", content=question))
    for bid, platform, tenant, app, chat, customer in [
        ("binding-a", "wecom", "demo-corp", "archive-demo", "group-a", "customer-a"),
        ("binding-b", "feishu", "demo-tenant", "knowledge-demo", "group-b", "customer-b"),
    ]:
        if not db.get(PlatformBinding, bid):
            db.add(PlatformBinding(id=bid, organization_id="demo-org", platform=platform, platform_tenant=tenant,
                                    application_id=app, chat_id=chat, customer_account_id=customer))
    db.flush()
    documents = json.loads(Path("fixtures/documents.json").read_text())
    for doc in documents:
        kid = doc["id"]
        if db.get(Knowledge, kid):
            continue
        customer = doc.get("customer")
        source = Source(id="src-" + kid, organization_id="demo-org", customer_account_id=customer,
                        title=doc["title"], kind="document", content=doc["content"], external_allowed=not customer)
        knowledge = Knowledge(id=kid, organization_id="demo-org", customer_account_id=customer,
                               title=doc["title"], status="published")
        db.add_all([source, knowledge])
        db.flush()
        rev = Revision(id="rev-" + kid, organization_id="demo-org", knowledge_id=kid, source_id=source.id,
                       content=doc["content"], customer_account_id=customer, visibility="customer" if customer else "public",
                       public_approved=not customer, version_min=doc.get("min", "3.1"), version_max=doc.get("max", "3.2"),
                       authority=3, topic=doc["topic"], verification="演示产品规格，非真实产品承诺",
                       reviewed_by="reviewer", claim_key=doc.get("claim_key"), claim_value=doc.get("claim_value"),
                       valid_until=datetime(2020, 1, 1, tzinfo=timezone.utc) if doc.get("expired") else None)
        db.add(rev)
        db.flush()
        build_chunks(db, rev)
        knowledge.current_revision_id = rev.id
    db.flush()
    reviewer = db.get(User, "reviewer")
    for filename in ["wecom.json", "feishu.csv"]:
        import_messages(Access(db, reviewer), parse(Path("fixtures", filename).read_bytes(), filename))


if __name__ == "__main__":
    with SessionLocal.begin() as db:
        seed(db)
    print("Demo fixtures seeded idempotently")
