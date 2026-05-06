# -*- coding: utf-8 -*-
"""
run_pipeline.py
월 입력 한 번으로 전체 파이프라인 자동 실행.

    발행 크롤링 → 잔액 크롤링 → 전처리 → DB upsert → ML 모델 적용 → JSON 갱신

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


def step_model() -> Path:
    import json, os
    from datetime import datetime, date
    from model.combined import run_combined, export_json

    results = run_combined(verbose=False)
    path    = export_json(results)
    print(f"  JSON 저장: {path}")

    # 치환본 저장 (탈취 방어 레이어)
    try:
        from security.seed_manager import get_table, get_active_seed
        from security.cipher import encrypt
        table = get_table(date.today())
        if table:
            with open(path, encoding='utf-8') as f:
                plain = json.load(f)
            seed_info   = get_active_seed() or {}
            encrypted   = encrypt(plain, table)
            enc_path    = path.parent / 'model_output_enc.json'
            with open(enc_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'seed_version': seed_info.get('seed_version'),
                    'encrypted_at': datetime.now().isoformat(timespec='seconds'),
                    'data': encrypted,
                }, f, ensure_ascii=False, indent=2)
            print(f"  치환본 저장: {enc_path}")
    except Exception as e:
        print(f"  치환본 저장 건너뜀: {e}")

    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("  AI 요약 건너뜀 (OPENAI_API_KEY 미설정)")
        return path

    try:
        from openai import OpenAI

        with open(path, encoding='utf-8') as f:
            data = json.load(f)

        def interpret_row(r):
            s = r['anomaly_score']
            z = r['sw_z']
            stress = ("매우 안정적" if s < 0.2 else "안정적" if s < 0.4 else
                      "다소 불안" if s < 0.6 else "불안")
            trend  = ("자금이 빠르게 빠지는 중" if z < -2 else
                      "자금이 줄어드는 중"      if z < -1.5 else
                      "자금이 빠르게 몰리는 중" if z > 2 else
                      "자금이 늘어나는 중"      if z > 1.5 else
                      "발행량 평균 수준")
            return f"{r['final_level']} 상태 / {stress} / {trend}"

        cp   = data['cp'][-1]   if data['cp']   else {}
        abcp = data['abcp'][-1] if data['abcp'] else {}
        ab   = data['abstb'][-1] if data['abstb'] else {}

        situation = (
            f"기준 시점: {data['last_updated']}\n\n"
            f"기업어음:     {interpret_row(cp)}\n"
            f"자산담보어음: {interpret_row(abcp)}\n"
            f"AB단기사채:   {interpret_row(ab)}\n"
        )

        prompt = (
            f"{situation}\n"
            "위 세 가지 단기금융상품 현황을 금융을 전혀 모르는 사람에게 설명해줘.\n"
            "카톡으로 친한 친구한테 설명하듯 자연스럽게, 4~5문장으로.\n"
            "각 상품 상태를 구체적으로 언급하고, "
            "마지막 문장은 지금 전체적으로 어떻게 보면 되는지 결론으로 마무리해줘."
        )

        client   = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model='gpt-4o-mini',
            max_tokens=400,
            messages=[{'role': 'user', 'content': prompt}]
        )
        summary = response.choices[0].message.content or ''

        summary_path = path.parent / 'ai_summary.json'
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump({
                'summary':      summary,
                'last_updated': data['last_updated'],
                'generated_at': datetime.now().isoformat(timespec='seconds'),
            }, f, ensure_ascii=False, indent=2)

        print(f"  AI 요약 저장: {summary_path}")
    except Exception as e:
        print(f"  AI 요약 생성 실패 (건너뜀): {e}")

    return path


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
    print(f"  Market WatchDog 파이프라인 - {month_name}")
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
    header("ML 모델 적용 → JSON 갱신", total, step)
    step_model()

    print(f"\n{'#'*60}")
    print(f"  완료: {month_name} 파이프라인 전체 종료")
    print(f"{'#'*60}\n")


if __name__ == "__main__":
    main()
