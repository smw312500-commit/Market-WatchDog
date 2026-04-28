# -*- coding: utf-8 -*-
"""
run_pipeline.py
월 입력 한 번으로 전체 파이프라인 자동 실행.

    발행 크롤링 → 잔액 크롤링 → 전처리 → DB upsert → MSI 재계산

사용법:
    python run_pipeline.py 26년4월
    python run_pipeline.py          (프롬프트로 입력)

환경변수 오버라이드:
    SKIP_CRAWL=1   크롤링 건너뜀 (원천 파일이 이미 있을 때)
"""

from __future__ import annotations

import os
import re
import sys
import calendar
import subprocess
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

MONTH_PAT = re.compile(r"(\d{2})년\s*(\d{1,2})월")


# =========================================================
# 유틸
# =========================================================
def parse_month(s: str) -> tuple[str, date, date]:
    """'26년4월' → (정규화된_이름, 시작일, 말일)"""
    s = s.strip().replace(" ", "")
    m = MONTH_PAT.fullmatch(s)
    if not m:
        raise ValueError(f"형식 오류: 예) 26년4월  입력값: {s!r}")
    yy, mm = int(m.group(1)), int(m.group(2))
    year = 2000 + yy
    last_day = calendar.monthrange(year, mm)[1]
    name = f"{yy}년{mm}월"
    return name, date(year, mm, 1), date(year, mm, last_day)


def header(step: str, total: int, current: int) -> None:
    print(f"\n{'='*60}")
    print(f"  [{current}/{total}] {step}")
    print(f"{'='*60}")


# =========================================================
# 단계별 실행
# =========================================================
def step_crawl_issue(start: date, end: date) -> None:
    env = {
        **os.environ,
        "CRAWL_START": start.isoformat(),
        "CRAWL_END":   end.isoformat(),
    }
    script = str(PROJECT_ROOT / "Siebro crawler.py")
    subprocess.run([sys.executable, script], env=env, cwd=str(PROJECT_ROOT), check=True)


def step_crawl_balance(start: date, end: date) -> None:
    env = {
        **os.environ,
        "CRAWL_START": start.isoformat(),
        "CRAWL_END":   end.isoformat(),
    }
    script = str(PROJECT_ROOT / "Seibro balance crawler.py")
    subprocess.run([sys.executable, script], env=env, cwd=str(PROJECT_ROOT), check=True)


def step_preprocess(month_name: str):
    from monthly_preprocess_automation import build_one_month_output
    return build_one_month_output(month_name)


def step_db_upsert(yyyymm, cp_result, abcp_result, abstb_result) -> None:
    from db_upsert_patch import upsert_month_to_db
    upsert_month_to_db(yyyymm, cp_result, abcp_result, abstb_result)


def step_msi() -> None:
    import MSI_v562_sqlite
    MSI_v562_sqlite.main()


# =========================================================
# 메인
# =========================================================
def main() -> None:
    raw = sys.argv[1] if len(sys.argv) > 1 else input("대상 월 입력 (예: 26년4월): ").strip()
    month_name, start_date, end_date = parse_month(raw)
    skip_crawl = os.getenv("SKIP_CRAWL", "0").strip().lower() in {"1", "true", "yes"}

    total = 4 if skip_crawl else 5
    step  = 0

    print(f"\n{'#'*60}")
    print(f"  Market WatchDog 파이프라인 — {month_name}")
    print(f"  범위: {start_date} ~ {end_date}")
    if skip_crawl:
        print("  ※ SKIP_CRAWL=1 → 크롤링 건너뜀")
    print(f"{'#'*60}")

    if not skip_crawl:
        step += 1
        header("발행 크롤링 (Siebro crawler)", total, step)
        step_crawl_issue(start_date, end_date)

        step += 1
        header("잔액 크롤링 (Seibro balance crawler)", total, step)
        step_crawl_balance(start_date, end_date)

    step += 1
    header("전처리", total, step)
    yyyymm, cp_result, abcp_result, abstb_result = step_preprocess(month_name)

    step += 1
    header("DB upsert", total, step)
    step_db_upsert(yyyymm, cp_result, abcp_result, abstb_result)

    step += 1
    header("MSI 재계산", total, step)
    step_msi()

    print(f"\n{'#'*60}")
    print(f"  완료: {month_name} 파이프라인 전체 종료")
    print(f"{'#'*60}\n")


if __name__ == "__main__":
    main()
