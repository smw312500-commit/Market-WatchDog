# -*- coding: utf-8 -*-
"""
db_upsert_patch.py
------------------
monthly_preprocess_automation.py 에 추가할 DB upsert 로직.

사용법:
  1) 이 파일을 monthly_preprocess_automation.py 와 같은 폴더에 둔다.
  2) monthly_preprocess_automation.py 상단에 import 추가:
        from db_upsert_patch import upsert_month_to_db
  3) build_one_month_output() 함수 맨 끝에 한 줄 추가:
        upsert_month_to_db(yyyymm, cp_result, abcp_result, abstb_result)
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict

import pandas as pd

PROJECT_ROOT = Path(r"E:\PROJECT\Market-WatchDog")
DB_PATH      = PROJECT_ROOT / "market_watchdog.db"


def _upsert(conn: sqlite3.Connection, table: str, df: pd.DataFrame) -> None:
    if df.empty:
        return
    cols = ", ".join(df.columns)
    ph   = ", ".join(["?"] * len(df.columns))
    sql  = f"INSERT OR REPLACE INTO {table} ({cols}) VALUES ({ph})"
    conn.executemany(sql, [tuple(r) for r in df.itertuples(index=False)])


def _row(d: dict) -> pd.DataFrame:
    return pd.DataFrame([d])


def upsert_month_to_db(
    yyyymm:       int,
    cp_result:    Dict[str, pd.DataFrame],
    abcp_result:  Dict[str, pd.DataFrame],
    abstb_result: Dict[str, pd.DataFrame],
) -> None:
    """
    전처리 결과 Dict 에서 필요한 컬럼만 뽑아 DB에 upsert.
    monthly_preprocess_automation.py 의 build_one_month_output() 끝에서 호출.
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        # ── CP ──────────────────────────────────────────
        df = cp_result["1-2 CP월별잔액 합.csv"]
        _upsert(conn, "cp_balance",
                _row({"yyyymm": yyyymm, "balance_amt": float(df["balance_amt"].iloc[0])}))

        df = cp_result["1-1 CP월별발행액 합.csv"]
        _upsert(conn, "cp_issue",
                _row({"yyyymm": yyyymm, "issue_amt": float(df["issue_amt"].iloc[0])}))

        df = cp_result["1-4 CP_발행종합_마스터_V4.csv"]
        _upsert(conn, "cp_tenor", _row({
            "yyyymm": yyyymm,
            "ultra": float(df["tenor_share_ultra"].iloc[0]),
            "short": float(df["tenor_share_short"].iloc[0]),
            "mid":   float(df["tenor_share_mid"].iloc[0]),
            "main":  float(df["tenor_share_main"].iloc[0]),
            "long":  float(df["tenor_share_long"].iloc[0]),
            "xlong": float(df["tenor_share_xlong"].iloc[0]),
        }))

        df = cp_result["1-3 CP_등급비중_V4.csv"]
        _upsert(conn, "cp_grade_iss", _row({
            "yyyymm": yyyymm,
            "top":  float(df["issue_share_top"].iloc[0]),
            "high": float(df["issue_share_high"].iloc[0]),
            "mid":  float(df["issue_share_mid"].iloc[0]),
            "low":  float(df["issue_share_low"].iloc[0]),
            "dist": float(df["issue_share_distress"].iloc[0]),
            "a1":   float(df.get("issue_detail_a1",  [0]).iloc[0]),
            "a2":   float(df.get("issue_detail_a2",  [0]).iloc[0]),
            "a2p":  float(df["issue_detail_a2+"].iloc[0]),
            "a2m":  float(df["issue_detail_a2-"].iloc[0]),
            "a3":   float(df.get("issue_detail_a3",  [0]).iloc[0]),
            "a3p":  float(df["issue_detail_a3+"].iloc[0]),
            "a3m":  float(df["issue_detail_a3-"].iloc[0]),
            "b":    float(df.get("issue_detail_b",   [0]).iloc[0]),
            "bp":   float(df.get("issue_detail_b+",  [0]).iloc[0]),
            "bm":   float(df.get("issue_detail_b-",  [0]).iloc[0]),
            "c":    float(df.get("issue_detail_c",   [0]).iloc[0]),
            "other":float(df.get("issue_detail_other",[0]).iloc[0]),
        }))

        df = cp_result["1-5 CP_신용도별_잔액.csv"]
        _upsert(conn, "cp_grade_bal", _row({
            "yyyymm":  yyyymm,
            "top":     float(df["bal_share_top"].iloc[0]),
            "highmid": float(df["bal_share_high_mid"].iloc[0]),
            "low":     float(df["bal_share_low"].iloc[0]),
            "dist":    float(df["bal_share_distress"].iloc[0]),
        }))

        # ── ABCP ────────────────────────────────────────
        df = abcp_result["2-2 ABCP_2_월별잔액 합.csv"]
        _upsert(conn, "abcp_balance",
                _row({"yyyymm": yyyymm, "balance_amt": float(df["balance_amt"].iloc[0])}))

        df = abcp_result["2-5 ABCP 월별 발행액합.csv"]
        _upsert(conn, "abcp_issue",
                _row({"yyyymm": yyyymm, "issue_amt": float(df["issue_amt"].iloc[0])}))

        df = abcp_result["2-1 ABCP_만기비중_통합_V4.csv"]
        _upsert(conn, "abcp_tenor", _row({
            "yyyymm": yyyymm,
            "ultra": float(df["tenor_share_ultra"].iloc[0]),
            "short": float(df["tenor_share_short"].iloc[0]),
            "mid":   float(df["tenor_share_mid"].iloc[0]),
            "main":  float(df["tenor_share_main"].iloc[0]),
            "long":  float(df["tenor_share_long"].iloc[0]),
            "xlong": float(df["tenor_share_xlong"].iloc[0]),
        }))

        df = abcp_result["2-4 ABCP_신용등급비중_통합_V4.csv"]
        _upsert(conn, "abcp_grade_iss", _row({
            "yyyymm": yyyymm,
            "top":  float(df["issue_share_top"].iloc[0]),
            "high": float(df["issue_share_high"].iloc[0]),
            "mid":  float(df["issue_share_mid"].iloc[0]),
            "low":  float(df["issue_share_low"].iloc[0]),
            "dist": float(df["issue_share_distress"].iloc[0]),
            "a1":   float(df.get("issue_detail_a1",  [0]).iloc[0]),
            "a2":   float(df.get("issue_detail_a2",  [0]).iloc[0]),
            "a2p":  float(df["issue_detail_a2+"].iloc[0]),
            "a2m":  float(df["issue_detail_a2-"].iloc[0]),
            "a3":   float(df.get("issue_detail_a3",  [0]).iloc[0]),
            "a3p":  float(df["issue_detail_a3+"].iloc[0]),
            "a3m":  float(df["issue_detail_a3-"].iloc[0]),
            "bp":   float(df.get("issue_detail_b+",  [0]).iloc[0]),
            "c":    float(df.get("issue_detail_c",   [0]).iloc[0]),
            "d":    float(df.get("issue_detail_d",   [0]).iloc[0]),
        }))

        df = abcp_result["2-3 ABCP 신용등급별(4버킷) 잔액 비중.csv"]
        _upsert(conn, "abcp_grade_bal", _row({
            "yyyymm":  yyyymm,
            "top":     float(df["bal_share_top"].iloc[0]),
            "highmid": float(df["bal_share_high_mid"].iloc[0]),
            "low":     float(df["bal_share_low"].iloc[0]),
            "dist":    float(df["bal_share_distress"].iloc[0]),
        }))

        # ── AB단기사채 ───────────────────────────────────
        df = abstb_result["3-4 AB단기사채_2_월별잔액 합.csv"]
        _upsert(conn, "ab_balance",
                _row({"yyyymm": yyyymm, "balance_amt": float(df["balance_amt"].iloc[0])}))

        df = abstb_result["3-3 AB단기사채 월별 발행액합.csv"]
        _upsert(conn, "ab_issue",
                _row({"yyyymm": yyyymm, "issue_amt": float(df["issue_amt"].iloc[0])}))

        df = abstb_result["3-5AB단기사채_만기비중_통합_V4.csv"]
        _upsert(conn, "ab_tenor", _row({
            "yyyymm": yyyymm,
            "ultra": float(df["tenor_share_ultra"].iloc[0]),
            "short": float(df["tenor_share_short"].iloc[0]),
            "mid":   float(df["tenor_share_mid"].iloc[0]),
            "main":  float(df["tenor_share_main"].iloc[0]),
            "long":  float(df["tenor_share_long"].iloc[0]),
            "xlong": float(df["tenor_share_xlong"].iloc[0]),
        }))

        df = abstb_result["3-1 AB단기사채_신용등급비중_통합_V4.csv"]
        _upsert(conn, "ab_grade_iss", _row({
            "yyyymm": yyyymm,
            "top":  float(df["issue_share_top"].iloc[0]),
            "high": float(df["issue_share_high"].iloc[0]),
            "mid":  float(df["issue_share_mid"].iloc[0]),
            "low":  float(df["issue_share_low"].iloc[0]),
            "dist": float(df["issue_share_distress"].iloc[0]),
            "a1":   float(df.get("issue_detail_a1",  [0]).iloc[0]),
            "a2":   float(df.get("issue_detail_a2",  [0]).iloc[0]),
            "a2p":  float(df["issue_detail_a2+"].iloc[0]),
            "a2m":  float(df["issue_detail_a2-"].iloc[0]),
            "a3":   float(df.get("issue_detail_a3",  [0]).iloc[0]),
            "a3p":  float(df["issue_detail_a3+"].iloc[0]),
            "a3m":  float(df["issue_detail_a3-"].iloc[0]),
            "b":    float(df.get("issue_detail_b",   [0]).iloc[0]),
            "bp":   float(df.get("issue_detail_b+",  [0]).iloc[0]),
            "bm":   float(df.get("issue_detail_b-",  [0]).iloc[0]),
            "c":    float(df.get("issue_detail_c",   [0]).iloc[0]),
            "d":    float(df.get("issue_detail_d",   [0]).iloc[0]),
        }))

        df = abstb_result["3-2 AB단기사채 신용등급별(4버킷) 잔액 비중.csv"]
        _upsert(conn, "ab_grade_bal", _row({
            "yyyymm":  yyyymm,
            "top":     float(df["bal_share_top"].iloc[0]),
            "highmid": float(df["bal_share_high_mid"].iloc[0]),
            "low":     float(df["bal_share_low"].iloc[0]),
            "dist":    float(df["bal_share_distress"].iloc[0]),
        }))

        conn.commit()
        print(f"[DB] {yyyymm} upsert 완료")

    except Exception as e:
        conn.rollback()
        print(f"[DB] upsert 실패: {e}")
    finally:
        conn.close()
