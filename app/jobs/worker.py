import logging
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select, text
from sqlalchemy.dialects.postgresql import insert

from app.config import settings
from app.connectors.news import FEEDS, NewsFailure, live, parse_date, replay
from app.db import SessionLocal
from app.models import Cursor, Job, NewsItem, now

log = logging.getLogger(__name__)
RETRIES = [timedelta(minutes=5), timedelta(minutes=30), timedelta(hours=2)]


def enqueue(db, key, payload, run_at=None):
    db.execute(insert(Job).values(task_key=key, kind="news", payload=payload,
                                 run_at=run_at or now()).on_conflict_do_nothing(index_elements=["task_key"]))


def schedule(db, instant=None):
    instant = instant or now()
    if not db.scalar(text("SELECT pg_try_advisory_xact_lock(731202608)")):
        return
    local = instant.astimezone(ZoneInfo("Asia/Shanghai"))
    due = local.replace(hour=8, minute=0, second=0, microsecond=0)
    if local < due:
        due -= timedelta(days=1)
    key = f"schedule:{settings().news_mode}"
    cursor = db.get(Cursor, key)
    first = datetime.fromisoformat(cursor.value) + timedelta(days=1) if cursor else due
    while first <= due:
        for source in FEEDS:
            enqueue(db, f"daily:{settings().news_mode}:{source}:{first.date()}",
                    {"mode": settings().news_mode, "source": source, "snapshot": "A"}, instant)
        first += timedelta(days=1)
    if cursor:
        cursor.value = due.isoformat()
    else:
        db.add(Cursor(key=key, value=due.isoformat()))


def collect(db, payload):
    mode = payload["mode"]
    if mode == "replay":
        items = replay(payload.get("snapshot", "A"))
        if payload.get("source"):
            items = [i for i in items if i["source"] == payload["source"]]
    elif mode == "live":
        source = payload["source"]
        cursor = db.get(Cursor, "fetch:" + source)
        if cursor and now() - datetime.fromisoformat(cursor.value) < timedelta(minutes=5):
            raise NewsFailure("RSS 限频：至少间隔 5 分钟", True)
        items = live(source)
        if cursor:
            cursor.value = now().isoformat()
        else:
            db.add(Cursor(key="fetch:" + source, value=now().isoformat()))
    else:
        raise NewsFailure("无效资讯模式")
    added = 0
    for item in items:
        duplicate = db.scalar(select(NewsItem.id).where(NewsItem.mode == mode, or_(
            (NewsItem.source == item["source"]) & (NewsItem.guid == item["guid"]),
            NewsItem.canonical_url == item["canonical_url"], NewsItem.content_hash == item["content_hash"])))
        if not duplicate:
            result = db.execute(insert(NewsItem).values(**{**item, "published_at": parse_date(item["published_at"])},
                mode=mode).on_conflict_do_nothing().returning(NewsItem.id))
            added += int(result.scalar() is not None)
    return added


def run_one(db, instant=None):
    instant = instant or now()
    # Lock survives the bounded network call. Process death rolls back the claim automatically.
    job = db.scalar(select(Job).where(Job.status.in_(["pending", "retry"]), Job.run_at <= instant)
                    .order_by(Job.run_at).with_for_update(skip_locked=True).limit(1))
    if not job:
        return False
    job.attempts += 1
    try:
        collect(db, job.payload)
        job.status = "done"
        job.error = None
    except NewsFailure as exc:
        job.error = exc.code
        if exc.recoverable and job.attempts <= 3:
            job.status = "retry"
            job.run_at = instant + RETRIES[job.attempts - 1]
        else:
            job.status = "failed"
    return True


def main():
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            with SessionLocal.begin() as db:
                schedule(db)
            with SessionLocal.begin() as db:
                worked = run_one(db)
            if not worked:
                time.sleep(5)
        except Exception:
            log.error("Worker transaction failed; pending task retained", exc_info=False)
            time.sleep(5)


if __name__ == "__main__":
    main()
