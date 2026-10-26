import hmac
from datetime import timedelta
from secrets import token_urlsafe

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select

from app.db import get_db
from app.models import LoginSession, User, now
from app.repositories.access import Access
from app.services.security import token_hash


def principal(request: Request, db=Depends(get_db)):
    token = request.cookies.get("copilot_session", "")
    session = db.scalar(select(LoginSession).where(LoginSession.token_hash == token_hash(token),
                                                   LoginSession.expires_at > now()))
    user = db.get(User, session.user_id) if session else None
    if not user or not user.active:
        raise HTTPException(401, "请先登录")
    request.state.session = session
    return user


def access(db=Depends(get_db), user=Depends(principal)):
    return Access(db, user)


async def csrf(request: Request, user=Depends(principal)):
    form = await request.form()
    supplied = request.headers.get("X-CSRF-Token") or str(form.get("csrf_token", ""))
    if not hmac.compare_digest(supplied, request.state.session.csrf):
        raise HTTPException(403, "CSRF 校验失败，请刷新页面后重试")
    return user


def create_session(db, user):
    token = token_urlsafe(32)
    row = LoginSession(user_id=user.id, token_hash=token_hash(token), csrf=token_urlsafe(32),
                       expires_at=now() + timedelta(hours=8))
    db.add(row)
    return token
