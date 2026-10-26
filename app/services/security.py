import hashlib
import hmac
import re
import secrets

from fastapi import HTTPException

from app.config import settings
from app.models import Audit


def password_hash(password):
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1).hex()
    return f"scrypt${salt}${digest}"


def password_valid(password, encoded):
    try:
        _, salt, expected = encoded.split("$")
        actual = hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def token_hash(token):
    return hmac.new(settings().session_secret.encode(), token.encode(), hashlib.sha256).hexdigest()


def text_hash(draft):
    return hashlib.sha256(f"{draft.conversation_id}|{draft.revision}|{draft.edited_answer}".encode()).hexdigest()


def audit(db, user, action, target, **details):
    db.add(Audit(organization_id=user.organization_id, actor_id=user.id,
                 action=action, target_id=target, details=details))


PRIVATE_PATTERN = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|(?<!\d)1[3-9]\d{9}(?!\d)|"
                             r"(?:sk-|AKIA)[A-Za-z0-9_-]{8,}|(?:password|密码|token|secret)\s*[:=]\s*\S+", re.I)


def redact(text):
    return PRIVATE_PATTERN.sub("[已脱敏]", text)


def check_outbound(text):
    if PRIVATE_PATTERN.search(text) or re.search(r"https?://|wecom://|feishu://|lark://", text, re.I):
        raise HTTPException(422, "外发文本包含链接或疑似敏感信息；请删除后重新确认")
    if re.search(r"<[^>]*>", text):
        raise HTTPException(422, "外发文本不接受 HTML 标记")
