from fastapi import HTTPException
from packaging.version import InvalidVersion, Version
from sqlalchemy import or_, select

from app.models import Assignment, Chunk, Conversation, Customer, Draft, Knowledge, Revision, Source, now


def version_matches(version, lower, upper):
    try:
        return Version(lower) <= Version(version) <= Version(upper)
    except (InvalidVersion, TypeError):
        return False


class Access:
    """All customer-scoped reads share this policy, including staff roles."""

    def __init__(self, db, user):
        self.db = db
        self.user = user

    def require_role(self, *roles):
        if self.user.role not in roles:
            raise HTTPException(403, "当前角色无此权限")

    def customer_ids(self):
        return list(self.db.scalars(select(Customer.id).join(
            Assignment, Assignment.customer_account_id == Customer.id
        ).where(Assignment.user_id == self.user.id, Customer.organization_id == self.user.organization_id)))

    def scope(self, model, public=False):
        customer = model.customer_account_id.in_(self.customer_ids())
        if public:
            customer = or_(customer, model.customer_account_id.is_(None))
        return (model.organization_id == self.user.organization_id, customer)

    def customer(self, cid):
        """客户实体自身没有 customer_account_id，不能套用 scope()。

        授权语义不变：客户归属仍由服务器的客服分配关系决定，不信任调用方传入的任意客户标识。
        """
        row = self.db.scalar(select(Customer).where(
            Customer.id == cid, Customer.organization_id == self.user.organization_id,
            Customer.id.in_(self.customer_ids())))
        if not row:
            raise HTTPException(404, "资源不存在或不在授权范围")
        return row

    def conversations(self):
        return list(self.db.scalars(select(Conversation).where(*self.scope(Conversation)).order_by(Conversation.id)))

    def conversation(self, cid, lock=False):
        query = select(Conversation).where(Conversation.id == cid, *self.scope(Conversation))
        row = self.db.scalar(query.with_for_update() if lock else query)
        if not row:
            raise HTTPException(404, "会话不存在或不在授权范围")
        return row

    def draft(self, did, lock=False):
        query = select(Draft).join(Conversation).where(
            Draft.id == did, Draft.organization_id == self.user.organization_id, *self.scope(Conversation))
        row = self.db.scalar(query.with_for_update(of=Draft) if lock else query)
        if not row:
            raise HTTPException(404, "草稿不存在或不在授权范围")
        return row

    def source(self, sid):
        row = self.db.scalar(select(Source).where(Source.id == sid, *self.scope(Source, public=True)))
        if not row or not row.active:
            raise HTTPException(404, "来源不存在、已撤回或不在授权范围")
        return row

    def knowledge(self, kid, lock=False):
        query = select(Knowledge).where(Knowledge.id == kid, *self.scope(Knowledge, public=True))
        row = self.db.scalar(query.with_for_update() if lock else query)
        if not row:
            raise HTTPException(404, "知识不存在或不在授权范围")
        return row

    def knowledge_list(self):
        return list(self.db.scalars(select(Knowledge).where(*self.scope(Knowledge, public=True))
                                    .order_by(Knowledge.updated_at.desc())))

    def evidence(self, conversation, include_unknown=False):
        self.customer(conversation.customer_account_id)
        query = select(Chunk, Revision, Knowledge, Source).join(
            Revision, Chunk.revision_id == Revision.id
        ).join(Knowledge, Knowledge.current_revision_id == Revision.id).join(
            Source, Source.id == Revision.source_id
        ).where(
            Chunk.organization_id == self.user.organization_id,
            Revision.organization_id == self.user.organization_id,
            Knowledge.organization_id == self.user.organization_id,
            Source.organization_id == self.user.organization_id,
            Knowledge.status == "published", Source.active.is_(True),
            or_(Revision.valid_until.is_(None), Revision.valid_until > now()),
            or_(
                (Revision.visibility == "public") & Revision.public_approved.is_(True)
                & Revision.customer_account_id.is_(None) & Knowledge.customer_account_id.is_(None),
                (Revision.visibility == "customer")
                & (Revision.customer_account_id == conversation.customer_account_id)
                & (Knowledge.customer_account_id == conversation.customer_account_id),
            ),
            or_(Source.customer_account_id.is_(None),
                Source.customer_account_id == conversation.customer_account_id),
        )
        rows = list(self.db.execute(query))
        return [r for r in rows if (include_unknown and not conversation.product_version) or
                version_matches(conversation.product_version, r.Revision.version_min, r.Revision.version_max)]
