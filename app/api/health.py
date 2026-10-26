from fastapi.routing import APIRouter
from sqlalchemy import text

from app.db import engine
from app.models import Customer

router = APIRouter(tags=["health"])


@router.get("/health/live")
def live():
    return {"status": "alive"}


@router.get("/health/ready")
def ready():
    """就绪探针：确认数据库连接与演示数据都已可用。"""
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    from app.db import SessionLocal
    with SessionLocal() as db:
        customers = db.query(Customer).count()
    return {"status": "ready", "customers": customers}
