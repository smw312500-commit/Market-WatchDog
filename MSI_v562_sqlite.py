# -*- coding: utf-8 -*-
"""
MSI_v562_sqlite.py

MSI v56.2
- 잔액비중 level이 아니라 residual(추세선 대비 편차)을 메인으로 사용
- 신용도 / 만기구조를 보조축으로 사용
- 3개 축(balance / credit / tenor)의 avg + max 혼합
- precursor = 0.85 * avg + 0.15 * max
- trend     = 0.80 * avg + 0.20 * max
- 레고랜드 사건월(202210)을 anchor로 두고 target 1.00으로 후정규화
- CSV + SQLite 저장

출력
- CSV:
  E:\PROJECT\Market-WatchDog\master set\전처리\MSI_v562_지수.csv
- SQLite:
  D:\PROJECT\Market-WatchDog\master set\msi\{최신월폴더명}\MSI_v562_{최신월폴더명}.sqlite
- 테이블명:
  msi_v562_monthly
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd

#경로변경 필요
PROC_ROOT = Path(r"E:\PROJECT\Market-WatchDog\master set\전처리")
#PROC_ROOT = Path(r"D:\project\Market-WatchDog\master set\전처리")
CSV_OUT_FILE = PROC_ROOT / "MSI_v562_지수.csv"

#SQLITE_ROOT = Path(r"D:\PROJECT\Market-WatchDog\master set\msi")
SQLITE_ROOT = Path(r"E:\PROJECT\Market-WatchDog\master set\msi")
SQLITE_TABLE = "msi_v562_monthly"

FILE_MAP = {
    "cp_balance": "1-2 CP월별잔액 합.csv",
    "abcp_balance": "2-2 ABCP_2_월별잔액 합.csv",
    "ab_balance": "3-4 AB단기사채_2_월별잔액 합.csv",
    "cp_credit": "1-3 CP_등급비중_V4.csv",
    "ab_credit": "3-1 AB단기사채_신용등급비중_통합_V4.csv",
    "abcp_tenor": "2-1 ABCP_만기비중_통합_V4.csv",
    "ab_tenor": "3-5AB단기사채_만기비중_통합_V4.csv",
    "cp_master": "1-4 CP_발행종합_마스터_V4.csv",  # 선택
}

MONTH_DIR_PATTERN = re.compile(r"(?P<yy>\d{2})년\s*(?P<m>\d{1,2})월")


def read_csv_safely(path: Path) -> pd.DataFrame:
    for enc in ("utf-8-sig", "cp949", "euc-kr", "utf-8"):
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception:
            continue
    return pd.read_csv(path)


def find_latest_month_dir(proc_root: Path) -> Path:
    candidates = []
    for p in proc_root.iterdir():
        if not p.is_dir():
            continue
        m = MONTH_DIR_PATTERN.search(p.name)
        if not m:
            continue
        yy = int(m.group("yy"))
        mm = int(m.group("m"))
        candidates.append((yy, mm, p))
    if not candidates:
        raise FileNotFoundError(f"전처리 월 폴더를 찾지 못함: {proc_root}")
    candidates.sort()
    return candidates[-1][2]


def locate_file(base_dir: Path, filename: str) -> Path:
    p = base_dir / filename
    if p.exists():
        return p
    hits = list(base_dir.rglob(filename))
    if hits:
        return hits[0]
    raise FileNotFoundError(f"필수 파일 없음: {filename}")


def prep_month_col(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["YYYYMM"] = out["YYYYMM"].astype(int)
    out["date"] = pd.to_datetime(out["YYYYMM"].astype(str), format="%Y%m")
    return out.sort_values("YYYYMM").reset_index(drop=True)


def weighted_mean(df: pd.DataFrame, weights: Dict[str, float]) -> pd.Series:
    num = pd.Series(0.0, index=df.index)
    den = pd.Series(0.0, index=df.index)
    for col, w in weights.items():
        if col not in df.columns:
            continue
        valid = df[col].notna().astype(float)
        num += df[col].fillna(0) * w
        den += valid * w
    den = den.replace(0, np.nan)
    return num / den


def weighted_max(df: pd.DataFrame, weights: Dict[str, float]) -> pd.Series:
    cols = [c for c in weights if c in df.columns]
    if not cols:
        return pd.Series(np.nan, index=df.index)
    scaled = [df[c].fillna(0) * weights[c] for c in cols]
    arr = np.vstack([s.values for s in scaled])
    return pd.Series(arr.max(axis=0), index=df.index)


def stage(x: float) -> str:
    if pd.isna(x):
        return "-"
    if x >= 1.20:
        return "초위험"
    if x >= 1.00:
        return "위험"
    if x >= 0.75:
        return "경고"
    if x >= 0.50:
        return "주의"
    return "정상"


def make_sqlite_path(latest_month_dir: Path) -> Path:
    month_name = latest_month_dir.name
    target_dir = SQLITE_ROOT / month_name
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / f"MSI_v562_{month_name}.sqlite"


def save_to_sqlite(df: pd.DataFrame, db_path: Path, table_name: str = SQLITE_TABLE) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        save_df = df.copy()
        for c in save_df.columns:
            if pd.api.types.is_datetime64_any_dtype(save_df[c]):
                save_df[c] = save_df[c].dt.strftime("%Y-%m-%d")
        save_df.to_sql(table_name, conn, if_exists="replace", index=False)
        try:
            conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_yyyymm ON {table_name}(YYYYMM)")
        except Exception:
            pass
        conn.commit()


def rolling_linear_baseline(series: pd.Series, window: int = 24, min_periods: int = 12) -> pd.Series:
    values = series.astype(float).to_numpy()
    out = np.full(len(values), np.nan)
    for i in range(len(values)):
        start = max(0, i - window)
        end = i
        y = values[start:end]
        if len(y) < min_periods:
            continue
        valid = ~np.isnan(y)
        if valid.sum() < min_periods:
            continue
        x = np.arange(len(y))[valid]
        yv = y[valid]
        if len(np.unique(x)) < 2:
            continue
        slope, intercept = np.polyfit(x, yv, 1)
        out[i] = slope * len(y) + intercept
    return pd.Series(out, index=series.index)


def rolling_mad_of_residual(series: pd.Series, baseline: pd.Series, window: int = 24, min_periods: int = 12) -> pd.Series:
    resid = series - baseline
    return resid.shift(1).abs().rolling(window=window, min_periods=min_periods).median()


def residual_risk_score(
    series: pd.Series,
    higher_is_risk: bool,
    baseline_method: str = "linear",
    window: int = 24,
    min_periods: int = 12,
    center: float = 0.4,
    scale: float = 1.4,
    cap: float = 3.0,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    if baseline_method == "linear":
        baseline = rolling_linear_baseline(series, window=window, min_periods=min_periods)
    else:
        baseline = series.shift(1).rolling(window=window, min_periods=min_periods).median()
    mad = rolling_mad_of_residual(series, baseline, window=window, min_periods=min_periods)
    denom = 1.4826 * mad.replace(0, np.nan)
    z = (series - baseline) / denom
    if not higher_is_risk:
        z = -z
    score = ((z - center) / scale).clip(lower=0, upper=cap)
    return baseline, z, score


def load_inputs(base_dir: Path) -> Dict[str, Optional[pd.DataFrame]]:
    out: Dict[str, Optional[pd.DataFrame]] = {}
    for key, fname in FILE_MAP.items():
        try:
            out[key] = read_csv_safely(locate_file(base_dir, fname))
        except FileNotFoundError:
            if key == "cp_master":
                out[key] = None
            else:
                raise
    return out


def build_dataset(data: Dict[str, Optional[pd.DataFrame]]) -> pd.DataFrame:
    cp_bal = prep_month_col(data["cp_balance"])[["YYYYMM", "date", "balance_amt"]].rename(columns={"balance_amt": "cp_balance_amt"})
    abcp_bal = prep_month_col(data["abcp_balance"])[["YYYYMM", "balance_amt"]].rename(columns={"balance_amt": "abcp_balance_amt"})
    ab_bal = prep_month_col(data["ab_balance"])[["YYYYMM", "balance_amt"]].rename(columns={"balance_amt": "ab_balance_amt"})

    df = cp_bal.merge(abcp_bal, on="YYYYMM").merge(ab_bal, on="YYYYMM")

    df["total_balance_amt"] = df["cp_balance_amt"] + df["abcp_balance_amt"] + df["ab_balance_amt"]
    df["cp_balance_share"] = df["cp_balance_amt"] / df["total_balance_amt"]
    df["abcp_balance_share"] = df["abcp_balance_amt"] / df["total_balance_amt"]
    df["ab_balance_share"] = df["ab_balance_amt"] / df["total_balance_amt"]

    cp_credit = prep_month_col(data["cp_credit"])[["YYYYMM", "issue_share_top", "issue_share_high"]].rename(
        columns={"issue_share_top": "cp_issue_share_top", "issue_share_high": "cp_issue_share_high"}
    )
    ab_credit = prep_month_col(data["ab_credit"])[["YYYYMM", "issue_share_top", "issue_share_high"]].rename(
        columns={"issue_share_top": "ab_issue_share_top", "issue_share_high": "ab_issue_share_high"}
    )
    df = df.merge(cp_credit, on="YYYYMM", how="left").merge(ab_credit, on="YYYYMM", how="left")

    abcp_tenor = prep_month_col(data["abcp_tenor"])[["YYYYMM", "tenor_share_ultra", "tenor_share_short"]].copy()
    abcp_tenor["abcp_short_pressure"] = abcp_tenor["tenor_share_ultra"] + abcp_tenor["tenor_share_short"]
    df = df.merge(abcp_tenor[["YYYYMM", "abcp_short_pressure"]], on="YYYYMM", how="left")

    ab_tenor = prep_month_col(data["ab_tenor"])[["YYYYMM", "tenor_share_ultra", "tenor_share_short"]].copy()
    ab_tenor["ab_short_pressure"] = ab_tenor["tenor_share_ultra"] + ab_tenor["tenor_share_short"]
    df = df.merge(ab_tenor[["YYYYMM", "ab_short_pressure"]], on="YYYYMM", how="left")

    if data["cp_master"] is not None:
        cp_master = prep_month_col(data["cp_master"])
        if {"tenor_share_ultra", "tenor_share_short"}.issubset(cp_master.columns):
            cp_master["cp_short_pressure"] = cp_master["tenor_share_ultra"] + cp_master["tenor_share_short"]
            df = df.merge(cp_master[["YYYYMM", "cp_short_pressure"]], on="YYYYMM", how="left")

    return df


def build_v562(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    # residual risk with moderate caps
    out["cp_share_baseline"], out["cp_share_z"], out["cp_share_risk"] = residual_risk_score(
        out["cp_balance_share"], True, "linear", center=0.35, scale=1.25, cap=2.6
    )
    out["abcp_share_baseline"], out["abcp_share_z"], out["abcp_share_risk"] = residual_risk_score(
        out["abcp_balance_share"], False, "linear", center=0.35, scale=1.25, cap=2.6
    )
    out["ab_share_baseline"], out["ab_share_z"], out["ab_share_risk"] = residual_risk_score(
        out["ab_balance_share"], False, "linear", center=0.45, scale=1.45, cap=1.8
    )

    out["balance_core"] = weighted_mean(out, {
        "cp_share_risk": 0.45,
        "abcp_share_risk": 0.40,
        "ab_share_risk": 0.15,
    })

    _, out["cp_credit_top_z"], out["cp_credit_top_risk"] = residual_risk_score(
        out["cp_issue_share_top"], True, "median", center=0.35, scale=1.25, cap=1.9
    )
    _, out["cp_credit_high_z"], out["cp_credit_high_risk"] = residual_risk_score(
        out["cp_issue_share_high"], False, "median", center=0.35, scale=1.25, cap=1.9
    )
    out["cp_credit_core"] = weighted_mean(out, {
        "cp_credit_top_risk": 0.55,
        "cp_credit_high_risk": 0.45,
    })

    _, out["ab_credit_top_z"], out["ab_credit_top_risk"] = residual_risk_score(
        out["ab_issue_share_top"], True, "median", center=0.35, scale=1.25, cap=1.9
    )
    _, out["ab_credit_high_z"], out["ab_credit_high_risk"] = residual_risk_score(
        out["ab_issue_share_high"], False, "median", center=0.35, scale=1.25, cap=1.9
    )
    out["ab_credit_core"] = weighted_mean(out, {
        "ab_credit_top_risk": 0.55,
        "ab_credit_high_risk": 0.45,
    })
    out["credit_core"] = weighted_mean(out, {
        "cp_credit_core": 0.60,
        "ab_credit_core": 0.40,
    })

    _, out["abcp_tenor_z"], out["abcp_tenor_risk"] = residual_risk_score(
        out["abcp_short_pressure"], True, "median", center=0.35, scale=1.25, cap=2.1
    )
    _, out["ab_tenor_z"], out["ab_tenor_risk"] = residual_risk_score(
        out["ab_short_pressure"], True, "median", center=0.35, scale=1.25, cap=2.1
    )
    _, out["cp_tenor_z"], out["cp_tenor_risk"] = residual_risk_score(
        out["cp_short_pressure"], True, "median", center=0.45, scale=1.45, cap=1.5
    )
    out["tenor_core"] = weighted_mean(out, {
        "abcp_tenor_risk": 0.50,
        "ab_tenor_risk": 0.35,
        "cp_tenor_risk": 0.15,
    })

    core_weights = {"balance_core": 0.45, "credit_core": 0.30, "tenor_core": 0.25}
    trend_weights = {"balance_core": 0.50, "credit_core": 0.20, "tenor_core": 0.30}

    out["precursor_avg"] = weighted_mean(out, core_weights)
    out["precursor_max"] = weighted_max(out, core_weights)
    out["MSI_precursor_v562_raw"] = 0.85 * out["precursor_avg"] + 0.15 * out["precursor_max"]

    out["trend_avg"] = weighted_mean(out, trend_weights)
    out["trend_max"] = weighted_max(out, trend_weights)
    out["MSI_trend_v562_raw"] = 0.80 * out["trend_avg"] + 0.20 * out["trend_max"]

    out["MSI_total_v562_raw"] = 0.70 * out["MSI_precursor_v562_raw"] + 0.30 * out["MSI_trend_v562_raw"]
    out["MSI_total_v562_raw"] = np.maximum(out["MSI_total_v562_raw"], out["MSI_precursor_v562_raw"])

    out["hidden_risk_boost_v562"] = np.where(
        ((out["MSI_precursor_v562_raw"] >= 0.50) & (out["MSI_trend_v562_raw"] >= 0.58)) |
        ((out["balance_core"] >= 0.68) & (out["credit_core"] >= 0.42)),
        0.04, 0.0
    )
    out["MSI_total_v562_raw"] = out["MSI_total_v562_raw"] + out["hidden_risk_boost_v562"]

    anchor_month = 202210
    anchor_row = out.loc[out["YYYYMM"] == anchor_month, "MSI_total_v562_raw"]
    anchor_raw = float(anchor_row.iloc[0]) if len(anchor_row) else np.nan
    target_anchor = 1.00
    scale_factor = target_anchor / anchor_raw if pd.notna(anchor_raw) and anchor_raw > 0 else 1.0

    out["MSI_precursor_v562"] = out["MSI_precursor_v562_raw"] * scale_factor
    out["MSI_trend_v562"] = out["MSI_trend_v562_raw"] * scale_factor
    out["MSI_total_v562"] = out["MSI_total_v562_raw"] * scale_factor

    out["MSI_v562_상태"] = out["MSI_total_v562"].apply(stage)
    out["MSI_precursor_v562_상태"] = out["MSI_precursor_v562"].apply(stage)
    out["MSI_trend_v562_상태"] = out["MSI_trend_v562"].apply(stage)

    out["anchor_month_v562"] = anchor_month
    out["anchor_raw_v562"] = anchor_raw
    out["target_anchor_v562"] = target_anchor
    out["scale_factor_v562"] = scale_factor

    front = [
        "YYYYMM", "date",
        "cp_balance_amt", "abcp_balance_amt", "ab_balance_amt",
        "cp_balance_share", "abcp_balance_share", "ab_balance_share",
        "cp_share_baseline", "abcp_share_baseline", "ab_share_baseline",
        "cp_share_z", "abcp_share_z", "ab_share_z",
        "balance_core", "credit_core", "tenor_core",
        "precursor_avg", "precursor_max", "MSI_precursor_v562_raw",
        "trend_avg", "trend_max", "MSI_trend_v562_raw",
        "MSI_total_v562_raw", "hidden_risk_boost_v562",
        "MSI_precursor_v562", "MSI_trend_v562", "MSI_total_v562",
        "MSI_precursor_v562_상태", "MSI_trend_v562_상태", "MSI_v562_상태",
        "anchor_month_v562", "anchor_raw_v562", "target_anchor_v562", "scale_factor_v562",
    ]
    rest = [c for c in out.columns if c not in front]
    return out[front + rest]


def main() -> None:
    latest_month_dir = find_latest_month_dir(PROC_ROOT)
    print(f"[INFO] 입력 폴더: {latest_month_dir}")

    data = load_inputs(latest_month_dir)
    df = build_dataset(data)
    out = build_v562(df)

    out.to_csv(CSV_OUT_FILE, index=False, encoding="utf-8-sig")
    print(f"[DONE] CSV 저장 완료: {CSV_OUT_FILE}")

    sqlite_path = make_sqlite_path(latest_month_dir)
    save_to_sqlite(out, sqlite_path, SQLITE_TABLE)
    print(f"[DONE] SQLite 저장 완료: {sqlite_path}")
    print(f"[DONE] SQLite 테이블명: {SQLITE_TABLE}")


if __name__ == "__main__":
    main()
