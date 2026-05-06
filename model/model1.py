"""
Model 1: 12개월 슬라이딩 윈도우 트렌드 모델
CP / ABCP / ABSTB 각각 독립적으로 발행/잔액 비율의 이탈 감지
"""
import re
import pandas as pd
import numpy as np
from pathlib import Path

ROOT = Path(__file__).parent.parent

def _find_latest_prep_dir() -> Path:
    prep_root = ROOT / "master set" / "전처리"
    pattern = re.compile(r'(\d{2})년(\d{1,2})월')
    candidates = []
    for d in prep_root.iterdir():
        if not d.is_dir():
            continue
        m = pattern.fullmatch(d.name.strip())
        if m:
            yyyymm = int(f"20{m.group(1)}{int(m.group(2)):02d}")
            candidates.append((yyyymm, d))
    if not candidates:
        raise FileNotFoundError(f"전처리 폴더 없음: {prep_root}")
    return max(candidates, key=lambda x: x[0])[1]

BASE = _find_latest_prep_dir()

TRAIN_START = 201601
WINDOW      = 12

DATA_PATHS = {
    'cp': {
        'issue':   BASE / '1 CP' / '1-4 CP_발행종합_마스터_V4.csv',
        'balance': BASE / '1 CP' / '1-2 CP월별잔액 합.csv',
    },
    'abcp': {
        'issue':   BASE / '2 ABCP' / '2-5 ABCP 월별 발행액합.csv',
        'balance': BASE / '2 ABCP' / '2-2 ABCP_2_월별잔액 합.csv',
        'grade':   BASE / '2 ABCP' / '2-4 ABCP_신용등급비중_통합_V4.csv',
        'tenor':   BASE / '2 ABCP' / '2-1 ABCP_만기비중_통합_V4.csv',
    },
    'abstb': {
        'issue':   BASE / '3 ABSTB' / '3-3 AB단기사채 월별 발행액합.csv',
        'balance': BASE / '3 ABSTB' / '3-4 AB단기사채_2_월별잔액 합.csv',
        'grade':   BASE / '3 ABSTB' / '3-1 AB단기사채_신용등급비중_통합_V4.csv',
        'tenor':   BASE / '3 ABSTB' / '3-5AB단기사채_만기비중_통합_V4.csv',
    },
}


def _read(path, cols=None):
    df = pd.read_csv(path, encoding='utf-8-sig')
    if cols:
        df = df[cols]
    return df


def load_instrument(name: str) -> pd.DataFrame:
    p = DATA_PATHS[name]

    if name == 'cp':
        issue = _read(p['issue'], ['YYYYMM', 'issue_amt', 'issue_share_high',
                                    'tenor_share_ultra', 'tenor_share_short'])
        bal   = _read(p['balance'], ['YYYYMM', 'balance_amt'])
        df = issue.merge(bal, on='YYYYMM')
    else:
        issue = _read(p['issue'],   ['YYYYMM', 'issue_amt'])
        bal   = _read(p['balance'], ['YYYYMM', 'balance_amt'])
        grade = _read(p['grade'],   ['YYYYMM', 'issue_share_high'])
        tenor = _read(p['tenor'],   ['YYYYMM', 'tenor_share_ultra', 'tenor_share_short'])
        df = issue.merge(bal, on='YYYYMM').merge(grade, on='YYYYMM').merge(tenor, on='YYYYMM')

    df = df[df['YYYYMM'] >= TRAIN_START].copy()
    df = df.sort_values('YYYYMM').reset_index(drop=True)

    df['rollover_ratio'] = df['issue_amt'] / df['balance_amt']
    df['short_tenor']    = df['tenor_share_ultra'] + df['tenor_share_short']

    return df


def compute_sliding_window(df: pd.DataFrame, window: int = WINDOW) -> pd.DataFrame:
    df = df.copy()

    # 직전 window개월 기준선 (현재 월 미포함)
    roll = df['rollover_ratio'].rolling(window)
    df['sw_mean'] = roll.mean().shift(1)
    df['sw_std']  = roll.std().shift(1)

    # 이탈 크기: z-score
    df['sw_z'] = (df['rollover_ratio'] - df['sw_mean']) / df['sw_std'].replace(0, np.nan)

    # 방향 구분: 음수 = 롤오버 급감(위기), 양수 = 과열(전조)
    df['sw_signal'] = df['sw_z'].apply(_classify)

    return df


def _classify(z):
    if pd.isna(z):
        return '-'
    if z < -2.0:
        return '경고(급감)'
    if z < -1.5:
        return '주의(감소)'
    if z >  2.0:
        return '경고(과열)'
    if z >  1.5:
        return '주의(증가)'
    return '정상'


def run(verbose: bool = True) -> dict:
    results = {}
    crisis_months = {'202210', '202209', '202211', '202003', '202004'}

    for name in ['cp', 'abcp', 'abstb']:
        df = load_instrument(name)
        df = compute_sliding_window(df)
        results[name] = df

        if not verbose:
            continue

        print(f'\n{"="*55}')
        print(f'  {name.upper()} - Model 1 Sliding Window (12M)')
        print(f'{"="*55}')
        print(f'{"월":>8}  {"비율":>7}  {"기준평균":>8}  {"Z스코어":>8}  {"신호"}')
        print('-' * 55)

        for _, row in df.iterrows():
            if pd.isna(row['sw_mean']):
                continue
            ym     = str(row['YYYYMM'])
            marker = ' <<<' if ym in crisis_months else ''
            sig    = row['sw_signal']
            print(f"{ym:>8}  {row['rollover_ratio']:>7.4f}  "
                  f"{row['sw_mean']:>8.4f}  {row['sw_z']:>8.3f}  "
                  f"{sig}{marker}")

    return results


if __name__ == '__main__':
    results = run()

    print('\n\n=== 경고/주의 구간 요약 ===')
    for name, df in results.items():
        alerts = df[df['sw_signal'].str.contains('경고|주의', na=False)]
        if not alerts.empty:
            print(f'\n[{name.upper()}]')
            for _, row in alerts.iterrows():
                print(f"  {row['YYYYMM']}  z={row['sw_z']:+.3f}  {row['sw_signal']}")
