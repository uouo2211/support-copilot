"""演示工作台的 HTTP 层。

这一层只负责取参数、调用既有 service、组织页面数据；权限判断统一走 repository 的 Access，
不在每个接口各写一套过滤，保证与 PostgreSQL 版本的行为一致。
"""

from pathlib import Path

from fastapi import Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.routing import APIRouter
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from app.api.deps import create_session
from app.api.shared import (access_of, customer_name, drafts_of, latest_actions, messages_of,
                            redirect_to, require, session_user)
from app.config import settings
from app.db import get_db
from app.models import Audit, Knowledge, NewsItem, Organization, Revision, User
from app.services import answers as answer_service
from app.services import knowledge as knowledge_service
from app.services.security import password_valid

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.get("/login")
def login_page(request: Request, db=Depends(get_db)):
    if session_user(request, db):
        return redirect_to("/workbench")
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...), db=Depends(get_db)):
    user = db.scalar(select(User).where(User.username == username, User.active.is_(True)))
    if not user or not password_valid(password, user.password_hash):
        return templates.TemplateResponse("login.html", {"request": request,
                                                         "error": "账号或密码不正确"}, status_code=401)
    token = create_session(db, user)
    db.flush()
    response = redirect_to("/workbench")
    cfg = settings()
    response.set_cookie("copilot_session", token, httponly=True, samesite="lax",
                        secure=cfg.cookie_secure, max_age=8 * 3600)
    return response


@router.post("/logout")
def logout(request: Request, db=Depends(get_db)):
    response = redirect_to("/login")
    response.delete_cookie("copilot_session")
    return response


@router.get("/")
def index(request: Request, db=Depends(get_db)):
    return redirect_to("/workbench" if session_user(request, db) else "/login")


@router.get("/workbench")
def workbench(request: Request, db=Depends(get_db)):
    access = access_of(request, db)
    rows = []
    for conv in access.conversations():
        drafts = drafts_of(db, conv.id)
        latest = drafts[0] if drafts else None
        rows.append({
            "id": conv.id, "title": conv.title, "customer": customer_name(db, conv.customer_account_id),
            "version": conv.product_version or "未确认", "status": conv.status,
            "draft_count": len(drafts),
            "decision": latest.original.get("decision") if latest else None,
        })
    return templates.TemplateResponse("workbench.html", {
        "request": request, "user": access.user, "rows": rows,
        "customer_count": len(access.customer_ids())})


@router.get("/c/{cid}")
def conversation(request: Request, cid: str, db=Depends(get_db)):
    access = access_of(request, db)
    conv = access.conversation(cid)
    drafts = drafts_of(db, cid)
    return templates.TemplateResponse("conversation.html", {
        "request": request, "user": access.user, "conv": conv,
        "customer": customer_name(db, conv.customer_account_id),
        "messages": messages_of(db, cid), "drafts": drafts,
        "actions": latest_actions(db, [d.id for d in drafts])})


@router.post("/c/{cid}/ask")
def ask(request: Request, cid: str, question: str = Form(...), db=Depends(get_db)):
    access = access_of(request, db)
    draft = answer_service.create_draft(access, cid, question)
    return redirect_to(f"/c/{cid}#draft-{draft.id}")


@router.post("/drafts/{did}/edit")
def edit(request: Request, did: str, text: str = Form(...), revision: int = Form(...), db=Depends(get_db)):
    access = access_of(request, db)
    draft = answer_service.edit_draft(access, did, revision, text)
    return redirect_to(f"/c/{draft.conversation_id}#draft-{did}")


@router.post("/drafts/{did}/confirm")
def confirm(request: Request, did: str, revision: int = Form(...), db=Depends(get_db)):
    access = access_of(request, db)
    action = answer_service.confirm(access, did, revision)
    return redirect_to(f"/c/{action.conversation_id}#draft-{did}")


@router.post("/drafts/{did}/sent")
def sent(request: Request, did: str, action_id: str = Form(...), db=Depends(get_db)):
    access = access_of(request, db)
    action = answer_service.mark_sent(access, did, action_id)
    return redirect_to(f"/c/{action.conversation_id}#draft-{did}")


@router.post("/drafts/{did}/handoff")
def handoff(request: Request, did: str, troubleshooting: str = Form(...), db=Depends(get_db)):
    access = access_of(request, db)
    row = answer_service.handoff(access, did, troubleshooting)
    return redirect_to(f"/c/{row.conversation_id}#draft-{did}")


@router.post("/drafts/{did}/feedback")
def feedback(request: Request, did: str, rating: str = Form(...), note: str = Form(""), db=Depends(get_db)):
    access = access_of(request, db)
    answer_service.feedback(access, did, rating, note)
    draft = access.draft(did)
    return redirect_to(f"/c/{draft.conversation_id}#draft-{did}")


@router.get("/knowledge")
def knowledge(request: Request, db=Depends(get_db)):
    access = access_of(request, db)
    rows = []
    for item in access.knowledge_list():
        rev = db.get(Revision, item.current_revision_id) if item.current_revision_id else None
        rows.append({
            "id": item.id, "title": item.title, "status": item.status,
            "category": item.customer_account_id and "客户私有" or "公共知识",
            "visibility": rev.visibility if rev else "-",
            "versions": f"{rev.version_min} ~ {rev.version_max}" if rev else "-",
            "topic": rev.topic if rev else "-",
            "content": rev.content if rev else "",
            "verification": rev.verification if rev else "",
            "min": rev.version_min if rev else "3.2", "max": rev.version_max if rev else "3.2",
            "expected_revision": rev.id if rev else "",
        })
    return templates.TemplateResponse("knowledge.html", {
        "request": request, "user": access.user, "rows": rows,
        "index_version": db.get(Organization, access.user.organization_id).index_version})


@router.post("/knowledge/{kid}/publish")
def publish(request: Request, kid: str, content: str = Form(...), lower: str = Form(...),
            upper: str = Form(...), verification: str = Form(...), public_approved: bool = Form(False),
            expected_revision: str = Form(""), db=Depends(get_db)):
    access = access_of(request, db)
    knowledge_service.publish(access, kid, content, lower, upper, verification,
                              public_approved, expected_revision or None)
    return redirect_to("/knowledge#k-" + kid)


@router.post("/knowledge/{kid}/revoke")
def revoke(request: Request, kid: str, db=Depends(get_db)):
    access = access_of(request, db)
    knowledge_service.change_status(access, kid, "revoked")
    return redirect_to("/knowledge#k-" + kid)


@router.get("/news")
def news(request: Request, db=Depends(get_db)):
    user = require(request, db)
    snapshots = {}
    for item in db.scalars(select(NewsItem).order_by(NewsItem.mode, NewsItem.published_at)):
        snapshots.setdefault(item.mode, []).append(item)
    return templates.TemplateResponse("news.html", {"request": request, "user": user,
                                                    "snapshots": snapshots})


@router.get("/audits")
def audits(request: Request, db=Depends(get_db)):
    user = require(request, db)
    rows = list(db.scalars(select(Audit).where(Audit.organization_id == user.organization_id)
                           .order_by(Audit.created_at.desc()).limit(60)))
    return templates.TemplateResponse("audits.html", {"request": request, "user": user, "rows": rows})
