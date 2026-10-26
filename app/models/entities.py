from datetime import datetime, timezone
from uuid import uuid4

# 演示运行时降级：原实现依赖 PostgreSQL + pgvector 的 Vector 列，本 demo 改用 SQLite 运行时，
# 该列退化为可空 JSON。MVP 默认 AI_MODE=mock、EMBEDDING_ENABLED=false，检索走 BM25，不使用此列；
# 检索、版本匹配、权限过滤与引用校验逻辑与原设计一致。线上版仍使用 PostgreSQL + pgvector。
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def now():
    return datetime.now(timezone.utc)


def uid():
    return str(uuid4())


class Identity:
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uid)


class Scoped:
    organization_id: Mapped[str] = mapped_column(String(64), index=True)


class Organization(Identity, Base):
    __tablename__ = "organizations"
    name: Mapped[str] = mapped_column(String(200))
    index_version: Mapped[int] = mapped_column(Integer, default=1)


class Customer(Identity, Scoped, Base):
    __tablename__ = "customers"
    name: Mapped[str] = mapped_column(String(200))
    product_version: Mapped[str | None] = mapped_column(String(30))


class User(Identity, Scoped, Base):
    __tablename__ = "users"
    username: Mapped[str] = mapped_column(String(80), unique=True)
    display_name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(30))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Assignment(Base):
    __tablename__ = "assignments"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    customer_account_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), primary_key=True)


class LoginSession(Identity, Base):
    __tablename__ = "login_sessions"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf: Mapped[str] = mapped_column(String(128))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PlatformBinding(Identity, Scoped, Base):
    __tablename__ = "platform_bindings"
    __table_args__ = (UniqueConstraint("platform", "platform_tenant", "application_id", "chat_id"),)
    platform: Mapped[str] = mapped_column(String(30))
    platform_tenant: Mapped[str] = mapped_column(String(100))
    application_id: Mapped[str] = mapped_column(String(100))
    chat_id: Mapped[str] = mapped_column(String(100))
    customer_account_id: Mapped[str] = mapped_column(ForeignKey("customers.id"))


class Conversation(Identity, Scoped, Base):
    __tablename__ = "conversations"
    customer_account_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    product_version: Mapped[str | None] = mapped_column(String(30))
    platform: Mapped[str] = mapped_column(String(30), default="wecom")
    status: Mapped[str] = mapped_column(String(30), default="open")


class Message(Identity, Scoped, Base):
    __tablename__ = "messages"
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    sender: Mapped[str] = mapped_column(String(100))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Source(Identity, Scoped, Base):
    __tablename__ = "sources"
    customer_account_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(30))
    content: Mapped[str] = mapped_column(Text)
    external_url: Mapped[str | None] = mapped_column(Text)
    external_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    provenance: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ImportedMessage(Identity, Scoped, Base):
    __tablename__ = "imported_messages"
    __table_args__ = (UniqueConstraint("binding_id", "message_id"),)
    binding_id: Mapped[str] = mapped_column(ForeignKey("platform_bindings.id"))
    message_id: Mapped[str] = mapped_column(String(100))
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"))
    sender: Mapped[str] = mapped_column(String(100))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reply_to: Mapped[str | None] = mapped_column(String(100))
    content: Mapped[str] = mapped_column(Text)


class Knowledge(Identity, Scoped, Base):
    __tablename__ = "knowledge"
    customer_account_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    current_revision_id: Mapped[str | None] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Revision(Identity, Scoped, Base):
    __tablename__ = "revisions"
    knowledge_id: Mapped[str] = mapped_column(ForeignKey("knowledge.id"), index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"))
    content: Mapped[str] = mapped_column(Text)
    customer_account_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id"))
    visibility: Mapped[str] = mapped_column(String(30), default="customer")
    version_min: Mapped[str] = mapped_column(String(30), default="3.1")
    version_max: Mapped[str] = mapped_column(String(30), default="3.2")
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    authority: Mapped[int] = mapped_column(Integer, default=2)
    topic: Mapped[str] = mapped_column(String(100))
    claim_key: Mapped[str | None] = mapped_column(String(100))
    claim_value: Mapped[str | None] = mapped_column(String(200))
    verification: Mapped[str] = mapped_column(Text, default="")
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    public_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Chunk(Identity, Scoped, Base):
    __tablename__ = "chunks"
    revision_id: Mapped[str] = mapped_column(ForeignKey("revisions.id"), index=True)
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)
    embedding_space: Mapped[str | None] = mapped_column(Text)


class Draft(Identity, Scoped, Base):
    __tablename__ = "drafts"
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    operator_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    question: Mapped[str] = mapped_column(Text)
    original: Mapped[dict] = mapped_column(JSON)
    edited_answer: Mapped[str] = mapped_column(Text)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    confirmed_hash: Mapped[str | None] = mapped_column(String(64))
    mode: Mapped[str] = mapped_column(String(20))
    latency_ms: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ReplyAction(Identity, Scoped, Base):
    __tablename__ = "reply_actions"
    __table_args__ = (UniqueConstraint("draft_id", "text_hash"),)
    draft_id: Mapped[str] = mapped_column(ForeignKey("drafts.id"))
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"))
    operator_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    text_hash: Mapped[str] = mapped_column(String(64))
    text: Mapped[str] = mapped_column(Text)
    citations: Mapped[list] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), default="confirmed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Feedback(Identity, Scoped, Base):
    __tablename__ = "feedback"
    draft_id: Mapped[str] = mapped_column(ForeignKey("drafts.id"))
    operator_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    rating: Mapped[str] = mapped_column(String(30))
    note: Mapped[str] = mapped_column(Text)


class Handoff(Identity, Scoped, Base):
    __tablename__ = "handoffs"
    __table_args__ = (UniqueConstraint("draft_id"),)
    draft_id: Mapped[str] = mapped_column(ForeignKey("drafts.id"))
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"))
    operator_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), default="open")


class NewsItem(Identity, Base):
    __tablename__ = "news_items"
    __table_args__ = (UniqueConstraint("mode", "source", "guid"), UniqueConstraint("mode", "canonical_url"),
                     UniqueConstraint("mode", "content_hash"))
    mode: Mapped[str] = mapped_column(String(20))
    source: Mapped[str] = mapped_column(String(50))
    guid: Mapped[str] = mapped_column(Text)
    canonical_url: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(30), default="collected")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Job(Identity, Base):
    __tablename__ = "jobs"
    task_key: Mapped[str] = mapped_column(String(200), unique=True)
    kind: Mapped[str] = mapped_column(String(30))
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    error: Mapped[str | None] = mapped_column(Text)


class Cursor(Base):
    __tablename__ = "cursors"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text)


class Audit(Identity, Scoped, Base):
    __tablename__ = "audits"
    actor_id: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(100))
    target_id: Mapped[str] = mapped_column(String(64))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
