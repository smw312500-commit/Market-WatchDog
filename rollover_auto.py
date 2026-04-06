# -*- coding: utf-8 -*-
r"""
전처리 결과 폴더 -> 롤오버 자동 생성기 (반자동)

입력 재료 경로
E:\PROJECT\Market-WatchDog\master set\전처리\입력월

출력 경로
E:\PROJECT\Market-WatchDog\master set\rollover\입력월

생성 파일
- rollover_cp_v4.csv
- rollover_abcp_v4.csv
- rollover_abstb_v4.csv
- rollover_master_v4.csv
"""

from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd


# =========================================================
# 경로 설정
# =========================================================
PREP_ROOT = Path(r"E:\PROJECT\Market-WatchDog\master set\전처리")
ROLLOVER_ROOT = Path(r"E:\PROJECT\Market-WatchDog\master set\rollover")


# =========================================================
# 공통 유틸
# =========================================================
def read_csv_flex(path: Path, **kwargs) -> pd.DataFrame:
    encodings = ["utf-8-sig", "cp949", "utf-8"]
    last_err = None
    for enc in encodings:
        try:
            return pd.read_csv(path, encoding=enc, **kwargs)
        except Exception as e:
            last_err = e
    raise last_err


def safe_divide(num: pd.Series, den: pd.Series) -> pd.Series:
    out = num / den
    out = out.replace([np.inf, -np.inf], np.nan)
    return out


def prev_month_balance(balance_df: pd.DataFrame, y_col: str = "YYYYMM", v_col: str = "balance_total_amt") -> pd.DataFrame:
    df = balance_df[[y_col, v_col]].copy()
    df[y_col] = pd.to_numeric(df[y_col], errors="coerce")
    df[v_col] = pd.to_numeric(df[v_col], errors="coerce")
    df = df.sort_values(y_col).reset_index(drop=True)
    df["prev_balance_total_amt"] = df[v_col].shift(1)
    return df[[y_col, "prev_balance_total_amt"]]


# =========================================================
# CP 롤오버
# =========================================================
def build_cp_rollover(cp_master: pd.DataFrame, cp_balance_detail: pd.DataFrame) -> pd.DataFrame:
    m = cp_master.copy()
    b = cp_balance_detail.copy()

    m["YYYYMM"] = pd.to_numeric(m["YYYYMM"], errors="coerce")
    m["issue_amt"] = pd.to_numeric(m["issue_amt"], errors="coerce")

    share_cols = [
        "tenor_share_ultra",
        "tenor_share_short",
        "tenor_share_main",
        "tenor_share_mid",
        "tenor_share_long",
        "tenor_share_xlong",
    ]
    for c in share_cols:
        m[c] = pd.to_numeric(m[c], errors="coerce").fillna(0)

    prev_bal = prev_month_balance(b, v_col="balance_total_amt")

    out = m[["YYYYMM"]].copy()
    out = out.merge(prev_bal, on="YYYYMM", how="left")
    out = out.rename(columns={"prev_balance_total_amt": "cp_denom_prev_balance_total_amt"})

    out["cp_bucket_issue_amt_ultra"] = m["issue_amt"] * m["tenor_share_ultra"]
    out["cp_bucket_issue_amt_short"] = m["issue_amt"] * m["tenor_share_short"]
    out["cp_bucket_issue_amt_main"] = m["issue_amt"] * m["tenor_share_main"]
    out["cp_bucket_issue_amt_mid"] = m["issue_amt"] * m["tenor_share_mid"]
    out["cp_bucket_issue_amt_long"] = m["issue_amt"] * m["tenor_share_long"]
    out["cp_bucket_issue_amt_ultra_long"] = m["issue_amt"] * m["tenor_share_xlong"]

    denom = out["cp_denom_prev_balance_total_amt"]
    out["cp_rollover_ultra"] = safe_divide(out["cp_bucket_issue_amt_ultra"], denom)
    out["cp_rollover_short"] = safe_divide(out["cp_bucket_issue_amt_short"], denom)
    out["cp_rollover_main"] = safe_divide(out["cp_bucket_issue_amt_main"], denom)
    out["cp_rollover_mid"] = safe_divide(out["cp_bucket_issue_amt_mid"], denom)
    out["cp_rollover_long"] = safe_divide(out["cp_bucket_issue_amt_long"], denom)
    out["cp_rollover_ultra_long"] = safe_divide(out["cp_bucket_issue_amt_ultra_long"], denom)

    out = out.sort_values("YYYYMM").reset_index(drop=True)

    return out[
        [
            "YYYYMM",
            "cp_denom_prev_balance_total_amt",
            "cp_bucket_issue_amt_ultra", "cp_rollover_ultra",
            "cp_bucket_issue_amt_short", "cp_rollover_short",
            "cp_bucket_issue_amt_main", "cp_rollover_main",
            "cp_bucket_issue_amt_mid", "cp_rollover_mid",
            "cp_bucket_issue_amt_long", "cp_rollover_long",
            "cp_bucket_issue_amt_ultra_long", "cp_rollover_ultra_long",
        ]
    ]


# =========================================================
# ABCP / ABSTB 공통 롤오버
# =========================================================
def build_rollover_from_tenor(
    tenor_df: pd.DataFrame,
    balance_df: pd.DataFrame,
    prefix: str
) -> pd.DataFrame:
    t = tenor_df.copy()
    b = balance_df.copy()

    t["YYYYMM"] = pd.to_numeric(t["YYYYMM"], errors="coerce")

    tenor_amt_cols = [
        "tenor_amt_ultra",
        "tenor_amt_short",
        "tenor_amt_main",
        "tenor_amt_mid",
        "tenor_amt_long",
        "tenor_amt_xlong",
    ]
    for c in tenor_amt_cols:
        t[c] = pd.to_numeric(t[c], errors="coerce").fillna(0)

    prev_bal = prev_month_balance(b, v_col="balance_total_amt")

    out = t[["YYYYMM"]].copy()
    out = out.merge(prev_bal, on="YYYYMM", how="left")
    out = out.rename(columns={"prev_balance_total_amt": f"{prefix}_denom_prev_balance_total_amt"})

    out[f"{prefix}_bucket_issue_amt_ultra"] = t["tenor_amt_ultra"]
    out[f"{prefix}_bucket_issue_amt_short"] = t["tenor_amt_short"]
    out[f"{prefix}_bucket_issue_amt_main"] = t["tenor_amt_main"]
    out[f"{prefix}_bucket_issue_amt_mid"] = t["tenor_amt_mid"]
    out[f"{prefix}_bucket_issue_amt_long"] = t["tenor_amt_long"]
    out[f"{prefix}_bucket_issue_amt_ultra_long"] = t["tenor_amt_xlong"]

    denom = out[f"{prefix}_denom_prev_balance_total_amt"]
    out[f"{prefix}_rollover_ultra"] = safe_divide(out[f"{prefix}_bucket_issue_amt_ultra"], denom)
    out[f"{prefix}_rollover_short"] = safe_divide(out[f"{prefix}_bucket_issue_amt_short"], denom)
    out[f"{prefix}_rollover_main"] = safe_divide(out[f"{prefix}_bucket_issue_amt_main"], denom)
    out[f"{prefix}_rollover_mid"] = safe_divide(out[f"{prefix}_bucket_issue_amt_mid"], denom)
    out[f"{prefix}_rollover_long"] = safe_divide(out[f"{prefix}_bucket_issue_amt_long"], denom)
    out[f"{prefix}_rollover_ultra_long"] = safe_divide(out[f"{prefix}_bucket_issue_amt_ultra_long"], denom)

    out = out.sort_values("YYYYMM").reset_index(drop=True)

    return out[
        [
            "YYYYMM",
            f"{prefix}_denom_prev_balance_total_amt",
            f"{prefix}_bucket_issue_amt_ultra", f"{prefix}_rollover_ultra",
            f"{prefix}_bucket_issue_amt_short", f"{prefix}_rollover_short",
            f"{prefix}_bucket_issue_amt_main", f"{prefix}_rollover_main",
            f"{prefix}_bucket_issue_amt_mid", f"{prefix}_rollover_mid",
            f"{prefix}_bucket_issue_amt_long", f"{prefix}_rollover_long",
            f"{prefix}_bucket_issue_amt_ultra_long", f"{prefix}_rollover_ultra_long",
        ]
    ]


# =========================================================
# 마스터 병합
# =========================================================
def build_master(cp_df: pd.DataFrame, abcp_df: pd.DataFrame, abstb_df: pd.DataFrame) -> pd.DataFrame:
    cp_cols = [
        "YYYYMM",
        "cp_rollover_ultra", "cp_rollover_short", "cp_rollover_main",
        "cp_rollover_mid", "cp_rollover_long", "cp_rollover_ultra_long",
    ]
    abcp_cols = [
        "YYYYMM",
        "abcp_rollover_ultra", "abcp_rollover_short", "abcp_rollover_main",
        "abcp_rollover_mid", "abcp_rollover_long", "abcp_rollover_ultra_long",
    ]
    abstb_cols = [
        "YYYYMM",
        "abstb_rollover_ultra", "abstb_rollover_short", "abstb_rollover_main",
        "abstb_rollover_mid", "abstb_rollover_long", "abstb_rollover_ultra_long",
    ]

    out = cp_df[cp_cols].merge(abcp_df[abcp_cols], on="YYYYMM", how="outer")
    out = out.merge(abstb_df[abstb_cols], on="YYYYMM", how="outer")
    out = out.sort_values("YYYYMM").reset_index(drop=True)
    return out


# =========================================================
# 월 폴더 기준 파일 로드
# =========================================================
def load_month_inputs(target_month_folder: Path):
    cp_master_path = target_month_folder / "1 CP" / "1-4 CP_발행종합_마스터_V4.csv"
    cp_balance_path = target_month_folder / "1 CP" / "1-5 CP_신용도별_잔액.csv"

    abcp_tenor_path = target_month_folder / "2 ABCP" / "2-1 ABCP_만기비중_통합_V4.csv"
    abcp_balance_path = target_month_folder / "2 ABCP" / "2-3 ABCP 신용등급별(4버킷) 잔액 비중.csv"

    abstb_tenor_path = target_month_folder / "3 ABSTB" / "3-5AB단기사채_만기비중_통합_V4.csv"
    abstb_balance_path = target_month_folder / "3 ABSTB" / "3-2 AB단기사채 신용등급별(4버킷) 잔액 비중.csv"

    required = [
        cp_master_path, cp_balance_path,
        abcp_tenor_path, abcp_balance_path,
        abstb_tenor_path, abstb_balance_path,
    ]
    for p in required:
        if not p.exists():
            raise FileNotFoundError(f"필수 파일 없음: {p}")

    cp_master = read_csv_flex(cp_master_path)
    cp_balance = read_csv_flex(cp_balance_path)

    abcp_tenor = read_csv_flex(abcp_tenor_path)
    abcp_balance = read_csv_flex(abcp_balance_path)

    abstb_tenor = read_csv_flex(abstb_tenor_path)
    abstb_balance = read_csv_flex(abstb_balance_path)

    return cp_master, cp_balance, abcp_tenor, abcp_balance, abstb_tenor, abstb_balance


# =========================================================
# 실행
# =========================================================
def main():
    target_month = input("롤오버 생성 대상 월 입력 (예: 26년2월): ").strip()
    if not target_month:
        raise ValueError("대상 월이 비어있음")

    target_month_folder = PREP_ROOT / target_month
    if not target_month_folder.exists():
        raise FileNotFoundError(f"전처리 대상 월 폴더 없음: {target_month_folder}")

    out_dir = ROLLOVER_ROOT / target_month
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[입력] {target_month_folder}")
    print(f"[출력] {out_dir}")

    cp_master, cp_balance, abcp_tenor, abcp_balance, abstb_tenor, abstb_balance = load_month_inputs(target_month_folder)

    rollover_cp = build_cp_rollover(cp_master, cp_balance)
    print("[완료] rollover_cp")

    rollover_abcp = build_rollover_from_tenor(abcp_tenor, abcp_balance, "abcp")
    print("[완료] rollover_abcp")

    rollover_abstb = build_rollover_from_tenor(abstb_tenor, abstb_balance, "abstb")
    print("[완료] rollover_abstb")

    rollover_master = build_master(rollover_cp, rollover_abcp, rollover_abstb)
    print("[완료] rollover_master")

    rollover_cp.to_csv(out_dir / "rollover_cp_v4.csv", index=False, encoding="utf-8-sig")
    rollover_abcp.to_csv(out_dir / "rollover_abcp_v4.csv", index=False, encoding="utf-8-sig")
    rollover_abstb.to_csv(out_dir / "rollover_abstb_v4.csv", index=False, encoding="utf-8-sig")
    rollover_master.to_csv(out_dir / "rollover_master_v4.csv", index=False, encoding="utf-8-sig")

    print(f"[저장 완료] {out_dir}")
    print(out_dir / "rollover_cp_v4.csv")
    print(out_dir / "rollover_abcp_v4.csv")
    print(out_dir / "rollover_abstb_v4.csv")
    print(out_dir / "rollover_master_v4.csv")


if __name__ == "__main__":
    main()