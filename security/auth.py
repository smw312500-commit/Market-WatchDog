# -*- coding: utf-8 -*-
"""
auth.py
데모용 JWT 인증.

실제 운영 시에는 PyJWT + bcrypt + 사용자 DB로 교체 필요.
데모에서는 고정 토큰으로 정상/비정상 접근 시뮬레이션.
"""

import os
import hmac
import hashlib
import json
import base64
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify

# 환경변수에서 시크릿 로드 (없으면 데모용 기본값)
SECRET_KEY  = os.getenv("JWT_SECRET", "market-watchdog-demo-secret-2026")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "admin-demo-token-2026")

# 데모용 사용자 테이블
DEMO_USERS = {
    "admin": {"password": "admin1234", "role": "admin"},
    "viewer": {"password": "viewer1234", "role": "viewer"},
}


# ── 토큰 생성/검증 (HMAC-SHA256 기반 간이 JWT) ────────────────
def _b64(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")


def _sign(payload: dict, expires_hours: int = 24) -> str:
    """간이 JWT 생성."""
    payload = {**payload, "exp": (datetime.utcnow() + timedelta(hours=expires_hours)).isoformat()}
    header  = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}))
    body    = _b64(json.dumps(payload))
    sig     = hmac.new(SECRET_KEY.encode(), f"{header}.{body}".encode(), hashlib.sha256).hexdigest()
    return f"{header}.{body}.{sig}"


def _verify(token: str) -> dict | None:
    """토큰 검증. 실패 시 None 반환."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header, body, sig = parts
        expected = hmac.new(SECRET_KEY.encode(), f"{header}.{body}".encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        padding  = "=" * (4 - len(body) % 4)
        payload  = json.loads(base64.urlsafe_b64decode(body + padding))
        if datetime.fromisoformat(payload["exp"]) < datetime.utcnow():
            return None
        return payload
    except Exception:
        return None


def issue_token(user_id: str, role: str) -> str:
    return _sign({"sub": user_id, "role": role})


def login(user_id: str, password: str) -> str | None:
    """로그인 — 성공 시 토큰, 실패 시 None."""
    user = DEMO_USERS.get(user_id)
    if user and user["password"] == password:
        return issue_token(user_id, user["role"])
    return None


# ── 요청에서 토큰 추출 ────────────────────────────────────────
def get_token_from_request() -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return request.args.get("token") or request.cookies.get("token")


def get_current_user() -> dict | None:
    """현재 요청의 인증 정보. 비인증이면 None."""
    token = get_token_from_request()
    if not token:
        return None
    return _verify(token)


def is_admin() -> bool:
    user = get_current_user()
    return user is not None and user.get("role") == "admin"


# ── 데코레이터 ────────────────────────────────────────────────
def require_admin(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not is_admin():
            return jsonify({"error": "관리자 권한 필요"}), 403
        return f(*args, **kwargs)
    return wrapper
