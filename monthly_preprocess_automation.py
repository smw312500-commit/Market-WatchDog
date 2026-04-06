# -*- coding: utf-8 -*-
r"""
v4 전처리 반자동 생성기 (월 1개씩 생성)

사용 예
- 실행 후: 26년1월 입력
- 결과:
  E:\PROJECT\Market-WatchDog\master set\전처리\26년1월\...

전제
- 기준본은 기본적으로:
  E:\PROJECT\Market-WatchDog\master set\전처리\25년 12월
- 즉 25년 12월 누적본 뒤에 입력월 1개를 이어붙여 새 폴더를 만든다.

원천 구조
1) 발행액
- CP:      legacy data\cp\26년1월\*.csv
- ABCP:    legacy data\abcp\26년1월\*.csv
- ABSTB:   legacy data\ab단기사채\26년1월\*.csv

2) 잔액
- CP:      legacy data2\cp\CP 26년1월.csv
- ABCP:    legacy data2\abcp\ABCP 26년1월.csv
- ABSTB:   legacy data2\ab단기사채\ABSTB 26년1월.csv

주의
- 잔액 원천 단위는 억원으로 가정하고, 코드에서 원으로 환산함
- 만기비중 계산 전 추가 제외 필터는 현재 미적용
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd


# =========================================================
# 경로 설정
# =========================================================
PROJECT_ROOT = Path(r"E:\PROJECT\Market-WatchDog")
#PROJECT_ROOT = Path(r"D:\project\Market-WatchDog")


ISSUE_ROOT = PROJECT_ROOT / "legacy data"
BAL_ROOT = PROJECT_ROOT / "legacy data2"
OUT_ROOT = PROJECT_ROOT / "master set" / "전처리"

# 기본 기준본
DEFAULT_BASE_MONTH_DIR = OUT_ROOT / "25년 12월"

# 잔액 원천 단위: 억원 -> 원 환산
BALANCE_UNIT_MULTIPLIER = 100_000_000


# =========================================================
# 공통 유틸
# =========================================================
def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def read_csv_flex(path: Path, **kwargs) -> pd.DataFrame:
    encodings = ["utf-8-sig", "cp949", "utf-8"]
    last_err = None
    for enc in encodings:
        try:
            return pd.read_csv(path, encoding=enc, **kwargs)
        except Exception as e:
            last_err = e
    raise last_err


def to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str).str.replace(",", "", regex=False).str.strip(),
        errors="coerce"
    ).fillna(0)


def parse_target_month(month_name: str) -> int:
    """
    '26년1월' -> 202601
    """
    s = str(month_name).strip().replace(" ", "")
    m = re.fullmatch(r"(\d{2})년(\d{1,2})월", s)
    if not m:
        raise ValueError("입력 형식 오류: 예) 26년1월")
    yy = int(m.group(1))
    mm = int(m.group(2))
    return int(f"{2000 + yy}{mm:02d}")


def yyyymm_from_text(text: str) -> Optional[int]:
    s = str(text).strip()

    m = re.search(r"(20\d{2})(0?[1-9]|1[0-2])$", s)
    if m:
        return int(m.group(1) + m.group(2).zfill(2))

    m = re.search(r"(\d{2,4})\s*년\s*(\d{1,2})\s*월", s)
    if m:
        y = int(m.group(1))
        mm = int(m.group(2))
        if y < 100:
            y += 2000
        return int(f"{y}{mm:02d}")

    m = re.search(r"(20\d{2})[-./ ]?(0?[1-9]|1[0-2])", s)
    if m:
        return int(m.group(1) + m.group(2).zfill(2))

    return None


def parse_date_yyyymmdd(series: pd.Series) -> pd.Series:
    s = series.astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    return pd.to_datetime(s, format="%Y%m%d", errors="coerce")


def choose_first_nonempty_rating(row: pd.Series, cols: List[str]) -> Optional[str]:
    for c in cols:
        val = row.get(c, np.nan)
        if pd.notna(val):
            t = str(val).strip()
            if t and t.lower() != "nan":
                return t
    return None


def normalize_rating(raw: Optional[str]) -> str:
    if raw is None:
        return "OTHER"

    s = str(raw).upper().strip()
    s = s.replace(" ", "")
    s = s.replace("Ｂ", "B").replace("Ａ", "A").replace("Ｃ", "C").replace("Ｄ", "D")
    s = s.replace("－", "-").replace("＋", "+")
    s = re.sub(r"[^A-Z0-9+\-]", "", s)

    allowed = {
        "A1", "A2+", "A2", "A2-", "A3+", "A3", "A3-",
        "B+", "B", "B-", "C", "D"
    }
    if s in allowed:
        return s

    if s.startswith("A1"):
        return "A1"
    if s.startswith("A2+"):
        return "A2+"
    if s.startswith("A2-"):
        return "A2-"
    if s.startswith("A2"):
        return "A2"
    if s.startswith("A3+"):
        return "A3+"
    if s.startswith("A3-"):
        return "A3-"
    if s.startswith("A3"):
        return "A3"
    if s.startswith("B+"):
        return "B+"
    if s.startswith("B-"):
        return "B-"
    if s.startswith("B"):
        return "B"
    if s.startswith("C"):
        return "C"
    if s.startswith("D"):
        return "D"

    return "OTHER"


def issue_bucket_5(rating: str) -> str:
    if rating == "A1":
        return "top"
    if rating in {"A2+", "A2", "A2-"}:
        return "high"
    if rating in {"A3+", "A3", "A3-"}:
        return "mid"
    if rating in {"B+", "B", "B-"}:
        return "low"
    if rating in {"C", "D"}:
        return "distress"
    return "other"


def tenor_bucket(days: float) -> Optional[str]:
    if pd.isna(days):
        return None
    d = int(days)
    if d <= 7:
        return "ultra"
    if 8 <= d <= 30:
        return "short"
    if 31 <= d <= 91:
        return "mid"
    if 92 <= d <= 183:
        return "main"
    if 184 <= d <= 365:
        return "long"
    if d >= 366:
        return "xlong"
    return None


def append_and_save(base_path: Path, out_path: Path, new_df: pd.DataFrame) -> None:
    base_df = read_csv_flex(base_path)
    base_cols = base_df.columns.tolist()

    for col in base_cols:
        if col not in new_df.columns:
            new_df[col] = 0

    extra_cols = [c for c in new_df.columns if c not in base_cols]
    merged = pd.concat([base_df, new_df[base_cols + extra_cols]], ignore_index=True)

    if "YYYYMM" in merged.columns:
        merged["YYYYMM"] = pd.to_numeric(merged["YYYYMM"], errors="coerce")
        merged = merged.drop_duplicates(subset=["YYYYMM"], keep="last").sort_values("YYYYMM")

    merged = merged[base_cols + extra_cols]
    ensure_dir(out_path.parent)
    merged.to_csv(out_path, index=False, encoding="utf-8-sig")


# =========================================================
# 발행액 원천 로더
# =========================================================
def load_issue_month_folder(month_dir: Path) -> pd.DataFrame:
    files = sorted(month_dir.glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"발행액 csv 없음: {month_dir}")

    frames = []
    for f in files:
        df = read_csv_flex(f)
        df["__source_file"] = f.name
        frames.append(df)

    out = pd.concat(frames, ignore_index=True)
    out.columns = [str(c).strip() for c in out.columns]
    return out


def prep_cp_issue(month_dir: Path, target_yyyymm: int) -> pd.DataFrame:
    df = load_issue_month_folder(month_dir).copy()

    if "발행년월" in df.columns:
        df["YYYYMM"] = df["발행년월"].astype(str).str.extract(r"(\d{6})")[0]
        df["YYYYMM"] = pd.to_numeric(df["YYYYMM"], errors="coerce")
    else:
        df["YYYYMM"] = target_yyyymm

    df["issue_amt"] = to_numeric(df["발행금액"]) if "발행금액" in df.columns else 0

    df["발행일_dt"] = parse_date_yyyymmdd(df["발행일"]) if "발행일" in df.columns else pd.NaT
    df["만기일_dt"] = parse_date_yyyymmdd(df["만기일"]) if "만기일" in df.columns else pd.NaT
    df["tenor_days"] = (df["만기일_dt"] - df["발행일_dt"]).dt.days

    df["rating_norm"] = df["신용등급"].apply(normalize_rating) if "신용등급" in df.columns else "OTHER"
    df["bucket_5"] = df["rating_norm"].apply(issue_bucket_5)
    df["tenor_bucket"] = df["tenor_days"].apply(tenor_bucket)

    df = df[df["YYYYMM"] == target_yyyymm].copy()
    return df


def prep_ab_issue(month_dir: Path, target_yyyymm: int) -> pd.DataFrame:
    df = load_issue_month_folder(month_dir).copy()

    if "발행월" in df.columns:
        ym = df["발행월"].apply(yyyymm_from_text)
        df["YYYYMM"] = pd.to_numeric(ym, errors="coerce")
    else:
        df["YYYYMM"] = target_yyyymm

    if "원화환산발행금액" in df.columns:
        amt_krw = to_numeric(df["원화환산발행금액"])
        if "발행금액" in df.columns:
            amt_raw = to_numeric(df["발행금액"])
            df["issue_amt"] = np.where(amt_krw > 0, amt_krw, amt_raw)
        else:
            df["issue_amt"] = amt_krw
    elif "발행금액" in df.columns:
        df["issue_amt"] = to_numeric(df["발행금액"])
    else:
        df["issue_amt"] = 0

    df["발행일_dt"] = parse_date_yyyymmdd(df["발행일"]) if "발행일" in df.columns else pd.NaT
    df["만기일_dt"] = parse_date_yyyymmdd(df["만기일"]) if "만기일" in df.columns else pd.NaT
    df["tenor_days"] = (df["만기일_dt"] - df["발행일_dt"]).dt.days

    rating_cols = ["한국신용평가", "한국기업평가", "NICE신용평가", "서울신용평가"]
    existing = [c for c in rating_cols if c in df.columns]
    df["chosen_rating"] = df.apply(lambda r: choose_first_nonempty_rating(r, existing), axis=1)
    df["rating_norm"] = df["chosen_rating"].apply(normalize_rating)
    df["bucket_5"] = df["rating_norm"].apply(issue_bucket_5)
    df["tenor_bucket"] = df["tenor_days"].apply(tenor_bucket)

    df = df[df["YYYYMM"] == target_yyyymm].copy()
    return df


# =========================================================
# 잔액 원천 로더
# =========================================================
def find_balance_file(balance_dir: Path, target_yyyymm: int, prefix: str) -> Path:
    yy = str(target_yyyymm)[2:4]
    mm = int(str(target_yyyymm)[4:6])

    candidates = list(balance_dir.glob("*.csv"))
    for f in candidates:
        name = f.name.replace(" ", "")
        if prefix.replace(" ", "") in name and f"{yy}년{mm}월" in name:
            return f

    raise FileNotFoundError(
        f"잔액 파일 못 찾음: dir={balance_dir}, prefix={prefix}, yyyymm={target_yyyymm}"
    )


def parse_balance_summary(balance_file: Path, target_yyyymm: int) -> Dict[str, float]:
    """
    잔액 원천은 억원 단위라고 가정하고, 여기서 원 단위로 환산한다.
    """
    df = read_csv_flex(balance_file)
    df.columns = [str(c).strip() for c in df.columns]

    body = df.iloc[2:].copy().reset_index(drop=True)
    sum_row = body[body.iloc[:, 0].astype(str).str.strip() == "합계"]
    if sum_row.empty:
        sum_row = body.tail(1)

    row = sum_row.iloc[0]

    def get_idx(i: int) -> float:
        try:
            return float(pd.to_numeric(str(row.iloc[i]).replace(",", "").strip(), errors="coerce") or 0)
        except Exception:
            return 0.0

    # 원천 금액: 억원
    amt_top_eok = get_idx(2)
    amt_high_mid_eok = get_idx(4)
    amt_low_eok = get_idx(6)
    amt_distress_eok = get_idx(8)
    amt_total_eok = get_idx(10)

    # 원 단위 환산
    amt_top = amt_top_eok * BALANCE_UNIT_MULTIPLIER
    amt_high_mid = amt_high_mid_eok * BALANCE_UNIT_MULTIPLIER
    amt_low = amt_low_eok * BALANCE_UNIT_MULTIPLIER
    amt_distress = amt_distress_eok * BALANCE_UNIT_MULTIPLIER
    amt_total = amt_total_eok * BALANCE_UNIT_MULTIPLIER

    return {
        "YYYYMM": target_yyyymm,
        "balance_total_amt": amt_total,
        "bal_amt_top": amt_top,
        "bal_amt_high_mid": amt_high_mid,
        "bal_amt_low": amt_low,
        "bal_amt_distress": amt_distress,
        "bal_share_top": amt_top / amt_total if amt_total else 0,
        "bal_share_high_mid": amt_high_mid / amt_total if amt_total else 0,
        "bal_share_low": amt_low / amt_total if amt_total else 0,
        "bal_share_distress": amt_distress / amt_total if amt_total else 0,
        "balance_amt": amt_total,
    }


# =========================================================
# 집계 로직
# =========================================================
def make_issue_amt(df: pd.DataFrame) -> pd.DataFrame:
    return df.groupby("YYYYMM", as_index=False)["issue_amt"].sum()


def make_issue_rating_cp(df: pd.DataFrame) -> pd.DataFrame:
    detail_order = [
        "A1", "A2", "A2+", "A2-", "A3", "A3+", "A3-", "B", "B+", "B-", "C", "OTHER"
    ]
    out = {"YYYYMM": [int(df["YYYYMM"].iloc[0])]}
    total_amt = df["issue_amt"].sum()

    detail_map = {}
    for r in detail_order:
        amt = df.loc[df["rating_norm"] == r, "issue_amt"].sum()
        key = "issue_detail_other" if r == "OTHER" else f"issue_detail_{r.lower()}"
        detail_map[key] = amt / total_amt if total_amt else 0

    out.update({k: [v] for k, v in detail_map.items()})

    out.update({
        "issue_share_distress": [detail_map.get("issue_detail_c", 0) + detail_map.get("issue_detail_other", 0)],
        "issue_share_high": [sum(detail_map.get(k, 0) for k in ["issue_detail_a2", "issue_detail_a2+", "issue_detail_a2-"])],
        "issue_share_low": [sum(detail_map.get(k, 0) for k in ["issue_detail_b", "issue_detail_b+", "issue_detail_b-"])],
        "issue_share_mid": [sum(detail_map.get(k, 0) for k in ["issue_detail_a3", "issue_detail_a3+", "issue_detail_a3-"])],
        "issue_share_top": [detail_map.get("issue_detail_a1", 0)],
    })

    col_order = [
        "YYYYMM",
        "issue_share_distress", "issue_share_high", "issue_share_low", "issue_share_mid", "issue_share_top",
        "issue_detail_a1", "issue_detail_a2", "issue_detail_a2+", "issue_detail_a2-",
        "issue_detail_a3", "issue_detail_a3+", "issue_detail_a3-",
        "issue_detail_b", "issue_detail_b+", "issue_detail_b-",
        "issue_detail_c", "issue_detail_other",
    ]
    return pd.DataFrame(out)[col_order]


def make_issue_rating_ab(df: pd.DataFrame, include_b=True, include_bminus=True) -> pd.DataFrame:
    detail_order = ["A1", "A2", "A2+", "A2-", "A3", "A3+", "A3-"]
    if include_b:
        detail_order.append("B")
    detail_order.append("B+")
    if include_bminus:
        detail_order.append("B-")
    detail_order.extend(["C", "D"])

    out = {"YYYYMM": [int(df["YYYYMM"].iloc[0])]}
    total_amt = df["issue_amt"].sum()

    detail_map = {}
    for r in detail_order:
        amt = df.loc[df["rating_norm"] == r, "issue_amt"].sum()
        detail_map[f"issue_detail_{r.lower()}"] = amt / total_amt if total_amt else 0

    out.update({k: [v] for k, v in detail_map.items()})

    out.update({
        "issue_share_distress": [detail_map.get("issue_detail_c", 0) + detail_map.get("issue_detail_d", 0)],
        "issue_share_high": [sum(detail_map.get(k, 0) for k in ["issue_detail_a2", "issue_detail_a2+", "issue_detail_a2-"])],
        "issue_share_low": [sum(detail_map.get(k, 0) for k in ["issue_detail_b", "issue_detail_b+", "issue_detail_b-"])],
        "issue_share_mid": [sum(detail_map.get(k, 0) for k in ["issue_detail_a3", "issue_detail_a3+", "issue_detail_a3-"])],
        "issue_share_top": [detail_map.get("issue_detail_a1", 0)],
    })

    front = [
        "YYYYMM",
        "issue_share_distress", "issue_share_high", "issue_share_low", "issue_share_mid", "issue_share_top",
    ]
    detail_cols = [c for c in [
        "issue_detail_a1", "issue_detail_a2", "issue_detail_a2+", "issue_detail_a2-",
        "issue_detail_a3", "issue_detail_a3+", "issue_detail_a3-",
        "issue_detail_b", "issue_detail_b+", "issue_detail_b-",
        "issue_detail_c", "issue_detail_d"
    ] if c in out]
    return pd.DataFrame(out)[front + detail_cols]


def make_tenor(df: pd.DataFrame) -> pd.DataFrame:
    yyyymm = int(df["YYYYMM"].iloc[0])
    total_amt = df["issue_amt"].sum()

    out = {
        "YYYYMM": yyyymm,
        "tenor_total_amt": total_amt,
    }
    for b in ["ultra", "short", "mid", "main", "long", "xlong"]:
        amt = df.loc[df["tenor_bucket"] == b, "issue_amt"].sum()
        out[f"tenor_amt_{b}"] = amt
        out[f"tenor_share_{b}"] = amt / total_amt if total_amt else 0

    return pd.DataFrame([out])


def make_cp_master(issue_amt_df: pd.DataFrame, rating_df: pd.DataFrame, tenor_df: pd.DataFrame) -> pd.DataFrame:
    return issue_amt_df.merge(
        rating_df[["YYYYMM", "issue_share_distress", "issue_share_high", "issue_share_low", "issue_share_mid", "issue_share_top"]],
        on="YYYYMM", how="left"
    ).merge(
        tenor_df[[
            "YYYYMM",
            "tenor_share_long", "tenor_share_main", "tenor_share_mid",
            "tenor_share_short", "tenor_share_ultra", "tenor_share_xlong"
        ]],
        on="YYYYMM", how="left"
    )


# =========================================================
# 자산군별 월 처리
# =========================================================
def process_cp_month(month_name: str, yyyymm: int) -> Dict[str, pd.DataFrame]:
    issue_dir = ISSUE_ROOT / "cp" / month_name
    bal_dir = BAL_ROOT / "cp"

    issue_df = prep_cp_issue(issue_dir, yyyymm)
    bal_file = find_balance_file(bal_dir, yyyymm, "CP")
    bal_summary = parse_balance_summary(bal_file, yyyymm)

    return {
        "1-1 CP월별발행액 합.csv": make_issue_amt(issue_df),
        "1-2 CP월별잔액 합.csv": pd.DataFrame([{"YYYYMM": yyyymm, "balance_amt": bal_summary["balance_amt"]}]),
        "1-3 CP_등급비중_V4.csv": make_issue_rating_cp(issue_df),
        "1-4 CP_발행종합_마스터_V4.csv": make_cp_master(make_issue_amt(issue_df), make_issue_rating_cp(issue_df), make_tenor(issue_df)),
        "1-5 CP_신용도별_잔액.csv": pd.DataFrame([{
            "YYYYMM": yyyymm,
            "balance_total_amt": bal_summary["balance_total_amt"],
            "bal_amt_top": bal_summary["bal_amt_top"],
            "bal_share_top": bal_summary["bal_share_top"],
            "bal_amt_high_mid": bal_summary["bal_amt_high_mid"],
            "bal_share_high_mid": bal_summary["bal_share_high_mid"],
            "bal_amt_low": bal_summary["bal_amt_low"],
            "bal_share_low": bal_summary["bal_share_low"],
            "bal_amt_distress": bal_summary["bal_amt_distress"],
            "bal_share_distress": bal_summary["bal_share_distress"],
        }]),
    }


def process_abcp_month(month_name: str, yyyymm: int) -> Dict[str, pd.DataFrame]:
    issue_dir = ISSUE_ROOT / "abcp" / month_name
    bal_dir = BAL_ROOT / "abcp"

    issue_df = prep_ab_issue(issue_dir, yyyymm)
    bal_file = find_balance_file(bal_dir, yyyymm, "ABCP")
    bal_summary = parse_balance_summary(bal_file, yyyymm)

    return {
        "2-1 ABCP_만기비중_통합_V4.csv": make_tenor(issue_df),
        "2-2 ABCP_2_월별잔액 합.csv": pd.DataFrame([{"YYYYMM": yyyymm, "balance_amt": bal_summary["balance_amt"]}]),
        "2-3 ABCP 신용등급별(4버킷) 잔액 비중.csv": pd.DataFrame([{
            "YYYYMM": yyyymm,
            "balance_total_amt": bal_summary["balance_total_amt"],
            "bal_share_top": bal_summary["bal_share_top"],
            "bal_share_high_mid": bal_summary["bal_share_high_mid"],
            "bal_share_low": bal_summary["bal_share_low"],
            "bal_share_distress": bal_summary["bal_share_distress"],
            "bal_amt_top": bal_summary["bal_amt_top"],
            "bal_amt_high_mid": bal_summary["bal_amt_high_mid"],
            "bal_amt_low": bal_summary["bal_amt_low"],
            "bal_amt_distress": bal_summary["bal_amt_distress"],
        }]),
        "2-4 ABCP_신용등급비중_통합_V4.csv": make_issue_rating_ab(issue_df, include_b=False, include_bminus=False),
        "2-5 ABCP 월별 발행액합.csv": make_issue_amt(issue_df),
    }


def process_abstb_month(month_name: str, yyyymm: int) -> Dict[str, pd.DataFrame]:
    issue_dir = ISSUE_ROOT / "ab단기사채" / month_name
    bal_dir = BAL_ROOT / "ab단기사채"

    issue_df = prep_ab_issue(issue_dir, yyyymm)
    bal_file = find_balance_file(bal_dir, yyyymm, "ABSTB")
    bal_summary = parse_balance_summary(bal_file, yyyymm)

    return {
        "3-1 AB단기사채_신용등급비중_통합_V4.csv": make_issue_rating_ab(issue_df, include_b=True, include_bminus=True),
        "3-2 AB단기사채 신용등급별(4버킷) 잔액 비중.csv": pd.DataFrame([{
            "YYYYMM": yyyymm,
            "balance_total_amt": bal_summary["balance_total_amt"],
            "bal_share_top": bal_summary["bal_share_top"],
            "bal_share_high_mid": bal_summary["bal_share_high_mid"],
            "bal_share_low": bal_summary["bal_share_low"],
            "bal_share_distress": bal_summary["bal_share_distress"],
            "bal_amt_top": bal_summary["bal_amt_top"],
            "bal_amt_high_mid": bal_summary["bal_amt_high_mid"],
            "bal_amt_low": bal_summary["bal_amt_low"],
            "bal_amt_distress": bal_summary["bal_amt_distress"],
        }]),
        "3-3 AB단기사채 월별 발행액합.csv": make_issue_amt(issue_df),
        "3-4 AB단기사채_2_월별잔액 합.csv": pd.DataFrame([{"YYYYMM": yyyymm, "balance_amt": bal_summary["balance_amt"]}]),
        "3-5AB단기사채_만기비중_통합_V4.csv": make_tenor(issue_df),
    }


# =========================================================
# 저장
# =========================================================
def save_month_output(month_name: str, month_results: Dict[str, pd.DataFrame], subfolder: str, base_month_dir: Path) -> None:
    base_dir = base_month_dir / subfolder
    out_dir = OUT_ROOT / month_name / subfolder
    ensure_dir(out_dir)

    for file_name, new_df in month_results.items():
        base_file = base_dir / file_name
        out_file = out_dir / file_name
        append_and_save(base_file, out_file, new_df)


def build_one_month_output(month_name: str, base_month_dir: Path) -> None:
    yyyymm = parse_target_month(month_name)

    print(f"[시작] 대상월: {month_name} / {yyyymm}")
    print(f"[기준본] {base_month_dir}")
    print(f"[잔액 단위 환산] 억원 -> 원 (x {BALANCE_UNIT_MULTIPLIER:,})")

    cp_result = process_cp_month(month_name, yyyymm)
    print("[완료] CP")

    abcp_result = process_abcp_month(month_name, yyyymm)
    print("[완료] ABCP")

    abstb_result = process_abstb_month(month_name, yyyymm)
    print("[완료] ABSTB")

    save_month_output(month_name, cp_result, "1 CP", base_month_dir)
    save_month_output(month_name, abcp_result, "2 ABCP", base_month_dir)
    save_month_output(month_name, abstb_result, "3 ABSTB", base_month_dir)

    print(f"[완료] 산출 폴더 생성: {OUT_ROOT / month_name}")


# =========================================================
# 실행부
# =========================================================
if __name__ == "__main__":
    target_month = input("생성할 대상 월 입력 (예: 26년1월): ").strip()
    base_input = input("기준본 월 폴더명 입력 (엔터 시 '25년 12월'): ").strip()

    base_month_dir = OUT_ROOT / base_input if base_input else DEFAULT_BASE_MONTH_DIR

    if not base_month_dir.exists():
        raise FileNotFoundError(f"기준본 폴더 없음: {base_month_dir}")

    build_one_month_output(target_month, base_month_dir)
