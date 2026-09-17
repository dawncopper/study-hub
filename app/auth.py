"""会话登录（Cookie Session，内存表）。

- 密码：PBKDF2-SHA256，100000 轮，固定盐 studyhub（家庭场景足够）
- 会话：内存字典 token -> (parent_id, 过期时间)，cookie 存 studyhub_sid，7 天过期
"""
import hashlib
import secrets
import time

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from .models import Parent

SALT = "studyhub"
SESSION_DAYS = 7
_SESSIONS = {}  # token -> (parent_id, expires_ts)


def hash_password(password: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), SALT.encode("utf-8"), 100000
    ).hex()


def verify_password(password: str, password_hash: str) -> bool:
    return hash_password(password) == password_hash


def create_session(parent_id: int) -> str:
    token = secrets.token_hex(24)
    _SESSIONS[token] = (parent_id, time.time() + SESSION_DAYS * 86400)
    return token


def destroy_session(token: str | None) -> None:
    if token:
        _SESSIONS.pop(token, None)


def get_parent_id(request: Request) -> int | None:
    token = request.cookies.get("studyhub_sid")
    if not token:
        return None
    sess = _SESSIONS.get(token)
    if not sess:
        return None
    parent_id, expires = sess
    if time.time() > expires:
        _SESSIONS.pop(token, None)
        return None
    return parent_id


def get_current_parent(request: Request, db: Session) -> Parent:
    """页面/接口通用依赖：校验登录并返回当前家长。未登录 303 跳登录页。"""
    parent_id = get_parent_id(request)
    if parent_id is None:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    parent = db.query(Parent).get(parent_id)
    if parent is None:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return parent
