# -*- coding: utf-8 -*-
"""
init_db.py
----------
기존 전처리 CSV 파일들을 SQLite DB로 일괄 적재.
최초 1회 실행 또는 DB 재구축 시 사용.

사용법:
    python init_db.py
    python init_db.py --month "26년2월"   # 특정 월 폴더 지정
"""

from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path

import pandas as pd

# =========================================================
# 경로 설정 (monthly_preprocess_automation.py 와 동일하게)
# =========================================================
PROJECT_ROOT = Path(r"E:\PROJECT\Market-WatchDog")
OUT_ROOT     = PROJECT_ROOT / "master set" / "전처리"
DB_PATH      = PROJECT_ROOT / "market_watchdog.db"


# =========================================================
# 유틸
# =========================================================
def read_csv_flex(path: Path, **kwargs) -> pd.DataFrame:
    for enc in ["utf-8-sig", "cp949", "utf-8"]:
        try:
            return pd.read_csv(path, encoding=enc, **kwargs)
        except Exception:
            pass
    raise RuntimeError(f"CSV 읽기 실패: {path}")


def latest_month_dir() -> Path:
    """전처리 폴더 중 가장 최신 월 폴더 자동 탐색."""
    pattern = re.compile(r"(\d{2})년\s*(\d{1,2})월")
    candidates = []
    for d in OUT_ROOT.iterdir():
        if not d.is_dir():
            continue
        m = pattern.fullmatch(d.name.strip())
        if m:
            yyyymm = int(f"20{m.group(1)}{int(m.group(2)):02d}")
            candidates.append((yyyymm, d))
    if not candidates:
        raise FileNotFoundError(f"전처리 폴더를 찾을 수 없음: {OUT_ROOT}")
    return max(candidates, key=lambda x: x[0])[1]


# =========================================================
# 테이블 생성
# =========================================================
CREATE_SQLS = """
CREATE TABLE IF NOT EXISTS cp_balance (
    yyyymm      INTEGER PRIMARY KEY,
    balance_amt REAL
);
CREATE TABLE IF NOT EXISTS cp_issue (
    yyyymm    INTEGER PRIMARY KEY,
    issue_amt REAL
);
CREATE TABLE IF NOT EXISTS cp_tenor (
    yyyymm         INTEGER PRIMARY KEY,
    ultra          REAL, short REAL, mid REAL,
    main           REAL, long  REAL, xlong REAL
);
CREATE TABLE IF NOT EXISTS cp_grade_iss (
    yyyymm      INTEGER PRIMARY KEY,
    top REAL, high REAL, mid REAL, low REAL, dist REAL,
    a1  REAL, a2  REAL, a2p REAL, a2m  REAL,
    a3  REAL, a3p REAL, a3m REAL,
    b   REAL, bp  REAL, bm  REAL,
    c   REAL, other REAL
);
CREATE TABLE IF NOT EXISTS cp_grade_bal (
    yyyymm  INTEGER PRIMARY KEY,
    top     REAL, highmid REAL, low REAL, dist REAL
);

CREATE TABLE IF NOT EXISTS abcp_balance (
    yyyymm      INTEGER PRIMARY KEY,
    balance_amt REAL
);
CREATE TABLE IF NOT EXISTS abcp_issue (
    yyyymm    INTEGER PRIMARY KEY,
    issue_amt REAL
);
CREATE TABLE IF NOT EXISTS abcp_tenor (
    yyyymm INTEGER PRIMARY KEY,
    ultra  REAL, short REAL, mid REAL,
    main   REAL, long  REAL, xlong REAL
);
CREATE TABLE IF NOT EXISTS abcp_grade_iss (
    yyyymm INTEGER PRIMARY KEY,
    top REAL, high REAL, mid REAL, low REAL, dist REAL,
    a1  REAL, a2  REAL, a2p REAL, a2m  REAL,
    a3  REAL, a3p REAL, a3m REAL,
    bp  REAL, c   REAL, d   REAL
);
CREATE TABLE IF NOT EXISTS abcp_grade_bal (
    yyyymm  INTEGER PRIMARY KEY,
    top     REAL, highmid REAL, low REAL, dist REAL
);

CREATE TABLE IF NOT EXISTS ab_balance (
    yyyymm      INTEGER PRIMARY KEY,
    balance_amt REAL
);
CREATE TABLE IF NOT EXISTS ab_issue (
    yyyymm    INTEGER PRIMARY KEY,
    issue_amt REAL
);
CREATE TABLE IF NOT EXISTS ab_tenor (
    yyyymm INTEGER PRIMARY KEY,
    ultra  REAL, short REAL, mid REAL,
    main   REAL, long  REAL, xlong REAL
);
CREATE TABLE IF NOT EXISTS ab_grade_iss (
    yyyymm INTEGER PRIMARY KEY,
    top REAL, high REAL, mid REAL, low REAL, dist REAL,
    a1  REAL, a2  REAL, a2p REAL, a2m  REAL,
    a3  REAL, a3p REAL, a3m REAL,
    b   REAL, bp  REAL, bm  REAL,
    c   REAL, d   REAL
);
CREATE TABLE IF NOT EXISTS ab_grade_bal (
    yyyymm  INTEGER PRIMARY KEY,
    top     REAL, highmid REAL, low REAL, dist REAL
);
"""


def init_tables(conn: sqlite3.Connection) -> None:
    for sql in CREATE_SQLS.strip().split(";"):
        sql = sql.strip()
        if sql:
            conn.execute(sql)
    conn.commit()
    print("[DB] 테이블 생성 완료")


# =========================================================
# CSV → DB 적재 함수들
# =========================================================
def upsert(conn: sqlite3.Connection, table: str, df: pd.DataFrame) -> int:
    """DataFrame을 테이블에 UPSERT (INSERT OR REPLACE)."""
    if df.empty:
        return 0
    cols = ", ".join(df.columns)
    placeholders = ", ".join(["?"] * len(df.columns))
    sql = f"INSERT OR REPLACE INTO {table} ({cols}) VALUES ({placeholders})"
    rows = [tuple(r) for r in df.itertuples(index=False)]
    conn.executemany(sql, rows)
    conn.commit()
    return len(rows)


def load_cp(conn: sqlite3.Connection, base_dir: Path) -> None:
    cp_dir = base_dir / "1 CP"

    # 잔액
    f = cp_dir / "1-2 CP월별잔액 합.csv"
    df = read_csv_flex(f)[["YYYYMM", "balance_amt"]].rename(columns={"YYYYMM": "yyyymm"})
    n = upsert(conn, "cp_balance", df)
    print(f"  cp_balance: {n}행")

    # 발행액
    f = cp_dir / "1-1 CP월별발행액 합.csv"
    df = read_csv_flex(f)[["YYYYMM", "issue_amt"]].rename(columns={"YYYYMM": "yyyymm"})
    n = upsert(conn, "cp_issue", df)
    print(f"  cp_issue: {n}행")

    # 만기구조
    f = cp_dir / "1-4 CP_발행종합_마스터_V4.csv"
    raw = read_csv_flex(f)
    df = pd.DataFrame({
        "yyyymm": raw["YYYYMM"],
        "ultra":  raw["tenor_share_ultra"],
        "short":  raw["tenor_share_short"],
        "mid":    raw["tenor_share_mid"],
        "main":   raw["tenor_share_main"],
        "long":   raw["tenor_share_long"],
        "xlong":  raw["tenor_share_xlong"],
    })
    n = upsert(conn, "cp_tenor", df)
    print(f"  cp_tenor: {n}행")

    # 신용등급 발행비중
    f = cp_dir / "1-3 CP_등급비중_V4.csv"
    raw = read_csv_flex(f)
    df = pd.DataFrame({
        "yyyymm": raw["YYYYMM"],
        "top":  raw["issue_share_top"],
        "high": raw["issue_share_high"],
        "mid":  raw["issue_share_mid"],
        "low":  raw["issue_share_low"],
        "dist": raw["issue_share_distress"],
        "a1":   raw["issue_detail_a1"],
        "a2":   raw["issue_detail_a2"],
        "a2p":  raw["issue_detail_a2+"],
        "a2m":  raw["issue_detail_a2-"],
        "a3":   raw["issue_detail_a3"],
        "a3p":  raw["issue_detail_a3+"],
        "a3m":  raw["issue_detail_a3-"],
        "b":    raw.get("issue_detail_b",   pd.Series(0, index=raw.index)),
        "bp":   raw.get("issue_detail_b+",  pd.Series(0, index=raw.index)),
        "bm":   raw.get("issue_detail_b-",  pd.Series(0, index=raw.index)),
        "c":    raw.get("issue_detail_c",   pd.Series(0, index=raw.index)),
        "other":raw.get("issue_detail_other", pd.Series(0, index=raw.index)),
    })
    n = upsert(conn, "cp_grade_iss", df)
    print(f"  cp_grade_iss: {n}행")

    # 신용등급 잔액비중
    f = cp_dir / "1-5 CP_신용도별_잔액.csv"
    raw = read_csv_flex(f)
    df = pd.DataFrame({
        "yyyymm":  raw["YYYYMM"],
        "top":     raw["bal_share_top"],
        "highmid": raw["bal_share_high_mid"],
        "low":     raw["bal_share_low"],
        "dist":    raw["bal_share_distress"],
    })
    n = upsert(conn, "cp_grade_bal", df)
    print(f"  cp_grade_bal: {n}행")


def load_abcp(conn: sqlite3.Connection, base_dir: Path) -> None:
    abcp_dir = base_dir / "2 ABCP"

    f = abcp_dir / "2-2 ABCP_2_월별잔액 합.csv"
    df = read_csv_flex(f)[["YYYYMM", "balance_amt"]].rename(columns={"YYYYMM": "yyyymm"})
    n = upsert(conn, "abcp_balance", df)
    print(f"  abcp_balance: {n}행")

    f = abcp_dir / "2-5 ABCP 월별 발행액합.csv"
    df = read_csv_flex(f)[["YYYYMM", "issue_amt"]].rename(columns={"YYYYMM": "yyyymm"})
    n = upsert(conn, "abcp_issue", df)
    print(f"  abcp_issue: {n}행")

    f = abcp_dir / "2-1 ABCP_만기비중_통합_V4.csv"
    raw = read_csv_flex(f)
    df = pd.DataFrame({
        "yyyymm": raw["YYYYMM"],
        "ultra":  raw["tenor_share_ultra"],
        "short":  raw["tenor_share_short"],
        "mid":    raw["tenor_share_mid"],
        "main":   raw["tenor_share_main"],
        "long":   raw["tenor_share_long"],
        "xlong":  raw["tenor_share_xlong"],
    })
    n = upsert(conn, "abcp_tenor", df)
    print(f"  abcp_tenor: {n}행")

    f = abcp_dir / "2-4 ABCP_신용등급비중_통합_V4.csv"
    raw = read_csv_flex(f)
    df = pd.DataFrame({
        "yyyymm": raw["YYYYMM"],
        "top":  raw["issue_share_top"],
        "high": raw["issue_share_high"],
        "mid":  raw["issue_share_mid"],
        "low":  raw["issue_share_low"],
        "dist": raw["issue_share_distress"],
        "a1":   raw["issue_detail_a1"],
        "a2":   raw["issue_detail_a2"],
        "a2p":  raw["issue_detail_a2+"],
        "a2m":  raw["issue_detail_a2-"],
        "a3":   raw["issue_detail_a3"],
        "a3p":  raw["issue_detail_a3+"],
        "a3m":  raw["issue_detail_a3-"],
        "bp":   raw.get("issue_detail_b+", pd.Series(0, index=raw.index)),
        "c":    raw.get("issue_detail_c",  pd.Series(0, index=raw.index)),
        "d":    raw.get("issue_detail_d",  pd.Series(0, index=raw.index)),
    })
    n = upsert(conn, "abcp_grade_iss", df)
    print(f"  abcp_grade_iss: {n}행")

    f = abcp_dir / "2-3 ABCP 신용등급별(4버킷) 잔액 비중.csv"
    raw = read_csv_flex(f)
    df = pd.DataFrame({
        "yyyymm":  raw["YYYYMM"],
        "top":     raw["bal_share_top"],
        "highmid": raw["bal_share_high_mid"],
        "low":     raw["bal_share_low"],
        "dist":    raw["bal_share_distress"],
    })
    n = upsert(conn, "abcp_grade_bal", df)
    print(f"  abcp_grade_bal: {n}행")


def load_ab(conn: sqlite3.Connection, base_dir: Path) -> None:
    ab_dir = base_dir / "3 ABSTB"

    f = ab_dir / "3-4 AB단기사채_2_월별잔액 합.csv"
    df = read_csv_flex(f)[["YYYYMM", "balance_amt"]].rename(columns={"YYYYMM": "yyyymm"})
    n = upsert(conn, "ab_balance", df)
    print(f"  ab_balance: {n}행")

    f = ab_dir / "3-3 AB단기사채 월별 발행액합.csv"
    df = read_csv_flex(f)[["YYYYMM", "issue_amt"]].rename(columns={"YYYYMM": "yyyymm"})
    n = upsert(conn, "ab_issue", df)
    print(f"  ab_issue: {n}행")

    f = ab_dir / "3-5AB단기사채_만기비중_통합_V4.csv"
    raw = read_csv_flex(f)
    df = pd.DataFrame({
        "yyyymm": raw["YYYYMM"],
        "ultra":  raw["tenor_share_ultra"],
        "short":  raw["tenor_share_short"],
        "mid":    raw["tenor_share_mid"],
        "main":   raw["tenor_share_main"],
        "long":   raw["tenor_share_long"],
        "xlong":  raw["tenor_share_xlong"],
    })
    n = upsert(conn, "ab_tenor", df)
    print(f"  ab_tenor: {n}행")

    f = ab_dir / "3-1 AB단기사채_신용등급비중_통합_V4.csv"
    raw = read_csv_flex(f)
    df = pd.DataFrame({
        "yyyymm": raw["YYYYMM"],
        "top":  raw["issue_share_top"],
        "high": raw["issue_share_high"],
        "mid":  raw["issue_share_mid"],
        "low":  raw["issue_share_low"],
        "dist": raw["issue_share_distress"],
        "a1":   raw["issue_detail_a1"],
        "a2":   raw["issue_detail_a2"],
        "a2p":  raw["issue_detail_a2+"],
        "a2m":  raw["issue_detail_a2-"],
        "a3":   raw["issue_detail_a3"],
        "a3p":  raw["issue_detail_a3+"],
        "a3m":  raw["issue_detail_a3-"],
        "b":    raw.get("issue_detail_b",  pd.Series(0, index=raw.index)),
        "bp":   raw.get("issue_detail_b+", pd.Series(0, index=raw.index)),
        "bm":   raw.get("issue_detail_b-", pd.Series(0, index=raw.index)),
        "c":    raw.get("issue_detail_c",  pd.Series(0, index=raw.index)),
        "d":    raw.get("issue_detail_d",  pd.Series(0, index=raw.index)),
    })
    n = upsert(conn, "ab_grade_iss", df)
    print(f"  ab_grade_iss: {n}행")

    f = ab_dir / "3-2 AB단기사채 신용등급별(4버킷) 잔액 비중.csv"
    raw = read_csv_flex(f)
    df = pd.DataFrame({
        "yyyymm":  raw["YYYYMM"],
        "top":     raw["bal_share_top"],
        "highmid": raw["bal_share_high_mid"],
        "low":     raw["bal_share_low"],
        "dist":    raw["bal_share_distress"],
    })
    n = upsert(conn, "ab_grade_bal", df)
    print(f"  ab_grade_bal: {n}행")


# =========================================================
# 메인
# =========================================================
def main(month_dir: Path) -> None:
    print(f"[DB 경로] {DB_PATH}")
    print(f"[데이터 폴더] {month_dir}")

    conn = sqlite3.connect(DB_PATH)
    try:
        init_tables(conn)
        print("\n[CP 적재]")
        load_cp(conn, month_dir)
        print("\n[ABCP 적재]")
        load_abcp(conn, month_dir)
        print("\n[AB 적재]")
        load_ab(conn, month_dir)
        print(f"\n[완료] {DB_PATH}")
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", type=str, default=None,
                        help="전처리 폴더명 (예: '26년2월'). 생략 시 최신 폴더 자동 탐색")
    args = parser.parse_args()

    if args.month:
        target_dir = OUT_ROOT / args.month
        if not target_dir.exists():
            raise FileNotFoundError(f"폴더 없음: {target_dir}")
    else:
        target_dir = latest_month_dir()

    main(target_dir)