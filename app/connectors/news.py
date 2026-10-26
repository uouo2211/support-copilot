import hashlib
import json
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import httpx
from defusedxml import ElementTree

FEEDS = {
    "postgresql": "https://www.postgresql.org/news.rss",
    "aws-security": "https://aws.amazon.com/security/security-bulletins/rss/feed/",
}


class NewsFailure(Exception):
    def __init__(self, code, recoverable=False):
        self.code = code
        self.recoverable = recoverable
        super().__init__(code)


def canonical(url):
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in {"www.postgresql.org", "aws.amazon.com"}:
        raise NewsFailure("链接不在白名单")
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path.rstrip("/") + "/", "", ""))


def normalized(item, source):
    title = re.sub(r"<[^>]+>", "", item["title"]).strip()
    summary = re.sub(r"<[^>]+>", "", item.get("summary", "")).strip()[:1500]
    return {"source": source, "guid": item.get("guid") or item["url"],
            "canonical_url": canonical(item["url"]), "title": title, "summary": summary,
            "category": "安全" if source == "aws-security" else "数据库",
            "content_hash": hashlib.sha256((title + "\n" + summary).encode()).hexdigest(),
            "published_at": item.get("published_at")}


def replay(snapshot):
    if snapshot not in {"A", "B"}:
        raise NewsFailure("无效模拟快照")
    items = json.loads((Path(__file__).resolve().parents[2] / "fixtures" / "news.json").read_text())
    return [normalized(i, i["source"]) for i in items[:2 if snapshot == "A" else 3]]


def live(source):
    if source not in FEEDS:
        raise NewsFailure("来源不在白名单")
    try:
        with httpx.Client(timeout=20, follow_redirects=False) as client:
            with client.stream("GET", FEEDS[source], headers={"User-Agent": "support-copilot-demo/0.1 (RSS; daily)"}) as response:
                if response.status_code != 200:
                    raise NewsFailure(f"HTTP {response.status_code}", response.status_code in {408, 429, 500, 502, 503, 504})
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > 2 * 1024 * 1024:
                        raise NewsFailure("RSS 超出 2 MiB 上限")
        root = ElementTree.fromstring(bytes(body))
        result = []
        for entry in root.findall(".//item")[:100]:
            published = None
            date = entry.findtext("pubDate")
            if date:
                try:
                    published = parsedate_to_datetime(date)
                    if not published.tzinfo:
                        published = published.replace(tzinfo=timezone.utc)
                except (ValueError, TypeError):
                    pass
            result.append(normalized({"title": entry.findtext("title") or "无标题",
                "guid": entry.findtext("guid"), "url": entry.findtext("link") or "",
                "summary": entry.findtext("description") or "", "published_at": published}, source))
        return result
    except httpx.TransportError as exc:
        raise NewsFailure("网络或超时错误", True) from exc
    except NewsFailure:
        raise
    except Exception as exc:
        raise NewsFailure("RSS 格式无效") from exc


def parse_date(value):
    return datetime.fromisoformat(value) if isinstance(value, str) else value
