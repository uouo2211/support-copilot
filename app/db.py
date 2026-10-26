from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

_url = settings().database_url
_is_sqlite = _url.startswith("sqlite")


class Base(DeclarativeBase):
    pass


_demo_kw = {}
if _is_sqlite:
    # 演示运行时降级：SQLite 不支持 SELECT ... FOR UPDATE，原 SQL 中的行锁在此被忽略。
    # 并发保护语义仍由 PostgreSQL 版本保证，demo 单机演示不存在并发写入争抢。
    from sqlalchemy.dialects.sqlite.base import SQLiteDialect

    SQLiteDialect.for_update_clause = lambda self, select, **kw: ""
    _demo_kw["connect_args"] = {"check_same_thread": False}

engine = create_engine(_url, pool_pre_ping=not _is_sqlite, **_demo_kw)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_db():
    with SessionLocal() as db:
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
