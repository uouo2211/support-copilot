"""应用入口。Dockerfile 与 compose 原本引用 app.main:app，此处补全该模块。"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import health, web
from app.db import Base, engine

ROOT = Path(__file__).resolve().parent

app = FastAPI(title="DataPilot 客服助手 · 演示", version="demo")
app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")
app.include_router(health.router)
app.include_router(web.router)


@app.on_event("startup")
def startup():
    Base.metadata.create_all(engine)


@app.exception_handler(StarletteHTTPException)
async def handle_http_error(request: Request, exc: StarletteHTTPException):
    """浏览器请求返回可读的错误页，接口请求继续返回 JSON。"""
    wants_html = "text/html" in request.headers.get("accept", "")
    if exc.status_code == 401 and wants_html:
        return RedirectResponse("/login", status_code=303)
    if wants_html:
        return web.templates.TemplateResponse(
            "error.html", {"request": request, "status": exc.status_code, "detail": exc.detail},
            status_code=exc.status_code)
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


@app.exception_handler(Exception)
async def handle_error(request: Request, exc: Exception):
    if "text/html" in request.headers.get("accept", ""):
        return web.templates.TemplateResponse(
            "error.html", {"request": request, "status": 500, "detail": str(exc)}, status_code=500)
    raise exc
