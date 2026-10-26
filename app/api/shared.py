from fastapi import Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.routing import APIRouter
from sqlalchemy import select

from app.models import Customer, Draft, LoginSession, Message, ReplyAction, User, now
from app.repositories.access import Access
from app.services.security import token_hash

router = APIRouter()


def session_user(request: Request, db):
    """读取登录态。页面用它做跳转判断，写操作用它做身份校验。"""
    token = request.cookies.get("copilot_session", "")
    if not token:
        return None
    row = db.scalar(select(LoginSession).where(LoginSession.token_hash == token_hash(token),
                                               LoginSession.expires_at > now()))
    user = db.get(User, row.user_id) if row else None
    if not user or not user.active:
        return None
    request.state.session = row
    return user


def require(request: Request, db) -> User:
    """未登录时抛 401，由 main.py 的统一处理器跳转登录页。"""
    user = session_user(request, db)
    if not user:
        raise HTTPException(401, "请先登录")
    return user


def access_of(request: Request, db) -> Access:
    return Access(db, require(request, db))


def drafts_of(db, conversation_id):
    return list(db.scalars(select(Draft).where(Draft.conversation_id == conversation_id)
                           .order_by(Draft.created_at.desc())))


def latest_actions(db, draft_ids):
    """每个草稿最近的回复动作。按创建时间升序取最后一条，直接给模板用，避免在模板里做作用域副作用。"""
    if not draft_ids:
        return {}
    rows = list(db.scalars(select(ReplyAction).where(ReplyAction.draft_id.in_(draft_ids))
                           .order_by(ReplyAction.created_at)))
    return {row.draft_id: row for row in rows}


def messages_of(db, conversation_id):
    return list(db.scalars(select(Message).where(Message.conversation_id == conversation_id)
                           .order_by(Message.created_at)))


def customer_name(db, cid):
    row = db.get(Customer, cid)
    return row.name if row else "未知客户"


def redirect_to(path: str) -> RedirectResponse:
    return RedirectResponse(path, status_code=303)
