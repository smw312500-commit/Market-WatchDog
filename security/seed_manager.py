# -*- coding: utf-8 -*-
"""
seed_manager.py
seed 문서 DB 관리 + 치환표 조합 반환.
"""

import sqlite3
from datetime import date, datetime
from pathlib import Path

from security.cipher import build_table

DB_PATH = Path(__file__).resolve().parent.parent / "market_watchdog.db"

# 납기지연 메일 — 기본 seed (초기 등록용)
DEFAULT_SEED = """From: j.morrison@atlanticfreight.com
To: procurement@yourcompany.com
CC: operations@yourcompany.com
Date: May 4, 2026
Subject: URGENT - Shipment Delay Notification / PO #2026-0412

Dear Procurement Team,

I regret to inform you that MV Queensbury Star, carrying your cargo
under Bill of Lading No. QB-20260412, has experienced an unexpected
port congestion delay at the origin terminal in Busan.

The vessel's departure has been postponed from the originally
scheduled date of April 28, 2026. Based on current harbor authority
updates, we expect the ship to depart within the next 3 to 5 days,
subject to berth availability and weather clearance.

Once the vessel clears port and begins its voyage, standard transit
time of approximately 14 days applies. We will provide a revised
ETA immediately upon confirmed departure.

We sincerely apologize for any inconvenience this may cause to your
production schedule or downstream commitments. Please do not
hesitate to contact our operations desk if you require an official
delay certificate for your records or insurance purposes.

We will keep you updated with daily status reports until departure
is confirmed.

Best regards,

James Morrison
Senior Logistics Coordinator
Atlantic Freight Solutions
Tel: +1-213-847-2291
j.morrison@atlanticfreight.com"""


def _conn():
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    return c


def init_tables():
    """security_seed, access_logs 테이블 생성."""
    with _conn() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS security_seed (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                seed_phrase  TEXT    NOT NULL,
                seed_version INTEGER NOT NULL,
                active_from  TEXT    NOT NULL,
                active_to    TEXT,
                created_by   TEXT,
                created_at   TEXT    DEFAULT (datetime('now','localtime')),
                is_active    INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS access_logs (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      TEXT,
                request_path TEXT,
                access_type  TEXT,
                result_type  TEXT,
                seed_version INTEGER,
                ip_address   TEXT,
                user_agent   TEXT,
                created_at   TEXT DEFAULT (datetime('now','localtime')),
                note         TEXT
            );
        """)


def ensure_default_seed():
    """DB에 활성 seed가 없으면 기본 seed 등록."""
    with _conn() as c:
        row = c.execute(
            "SELECT id FROM security_seed WHERE is_active=1 LIMIT 1"
        ).fetchone()
        if not row:
            c.execute("""
                INSERT INTO security_seed
                  (seed_phrase, seed_version, active_from, created_by, is_active)
                VALUES (?, 1, ?, 'system', 1)
            """, (DEFAULT_SEED, datetime.now().isoformat(timespec='seconds')))


def get_active_seed() -> dict | None:
    """현재 활성 seed 반환."""
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM security_seed WHERE is_active=1 ORDER BY seed_version DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None


def register_seed(seed_text: str, created_by: str = "admin") -> dict:
    """새 seed 등록 — 기존 active seed 비활성화."""
    now = datetime.now().isoformat(timespec='seconds')
    with _conn() as c:
        # 기존 active 비활성화
        c.execute("""
            UPDATE security_seed
            SET is_active=0, active_to=?
            WHERE is_active=1
        """, (now,))

        # 새 버전 번호
        row = c.execute("SELECT MAX(seed_version) as mx FROM security_seed").fetchone()
        new_version = (row['mx'] or 0) + 1

        c.execute("""
            INSERT INTO security_seed
              (seed_phrase, seed_version, active_from, created_by, is_active)
            VALUES (?, ?, ?, ?, 1)
        """, (seed_text, new_version, now, created_by))

    return get_active_seed()


def get_table(d: date = None) -> dict | None:
    """현재 seed + 날짜로 최종 치환표 반환."""
    seed = get_active_seed()
    if not seed:
        return None
    return build_table(seed['seed_phrase'], d or date.today())


def log_access(
    request_path: str,
    access_type: str,
    result_type: str,
    user_id: str | None = None,
    seed_version: int | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    note: str | None = None,
):
    """접근 로그 기록."""
    with _conn() as c:
        c.execute("""
            INSERT INTO access_logs
              (user_id, request_path, access_type, result_type,
               seed_version, ip_address, user_agent, note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, request_path, access_type, result_type,
              seed_version, ip_address, user_agent, note))


def get_logs(limit: int = 100) -> list[dict]:
    """최근 접근 로그 조회."""
    with _conn() as c:
        rows = c.execute("""
            SELECT * FROM access_logs
            ORDER BY id DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]


def get_seed_history() -> list[dict]:
    """seed 변경 이력 전체 조회."""
    with _conn() as c:
        rows = c.execute(
            "SELECT id, seed_version, active_from, active_to, created_by, is_active "
            "FROM security_seed ORDER BY seed_version DESC"
        ).fetchall()
        return [dict(r) for r in rows]
