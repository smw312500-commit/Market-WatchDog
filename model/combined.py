"""
Combined: Model 1 + Model 2 통합 신호
두 모델이 동시에 신호를 내면 더 강한 경고
"""
import pandas as pd
import joblib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from model1 import load_instrument, compute_sliding_window
from model2 import build_features, FEATURE_COLS

MODEL_DIR = Path(__file__).parent


# ── 최종 레벨 결정 규칙 ──────────────────────────────────────────
# Model1 signal (sw_z 기반)  x  Model2 anomaly_score
#
#  M1 경고  + M2 이상(score>=0.6)  → 위험
#  M1 경고  + M2 정상              → 경고
#  M1 주의  + M2 이상              → 경고
#  M1 주의  + M2 정상              → 주의
#  M1 정상  + M2 이상              → 주의
#  M1 정상  + M2 정상              → 정상

M2_THRESHOLD = 0.6   # anomaly_score 이상 판단 임계값


def _m1_level(signal: str) -> int:
    if '경고' in signal: return 2
    if '주의' in signal: return 1
    return 0


def _m2_level(score: float) -> int:
    if score >= M2_THRESHOLD: return 2
    if score >= 0.4:          return 1
    return 0


LEVEL_MAP = {
    (2, 2): '위험',
    (2, 1): '경고',
    (2, 0): '경고',
    (1, 2): '경고',
    (1, 1): '주의',
    (1, 0): '주의',
    (0, 2): '주의',
    (0, 1): '정상',
    (0, 0): '정상',
}


def apply_saved_model(name: str) -> pd.DataFrame:
    """저장된 모델(pkl)로 전체 데이터 점수 산출 - 재학습 없음"""
    model  = joblib.load(MODEL_DIR / f'if_{name}.pkl')
    scaler = joblib.load(MODEL_DIR / f'scaler_{name}.pkl')

    df = load_instrument(name)
    df = build_features(df)
    df = df.dropna(subset=FEATURE_COLS).copy()

    X   = scaler.transform(df[FEATURE_COLS].values)
    raw = model.decision_function(X)
    df['anomaly_score'] = 1 - (raw - raw.min()) / (raw.max() - raw.min())
    df['anomaly_label'] = model.predict(X)

    return df


def run_combined(verbose: bool = True) -> dict:
    results = {}
    crisis_months = {'202210', '202209', '202211', '202003', '202004',
                     '201907', '202106', '201707'}

    for name in ['cp', 'abcp', 'abstb']:
        # Model 1
        df = load_instrument(name)
        df = compute_sliding_window(df)

        # Model 2 (저장된 모델 적용)
        df2 = apply_saved_model(name)
        df2 = df2[['YYYYMM', 'anomaly_score', 'anomaly_label']].copy()

        # 병합
        df = df.merge(df2, on='YYYYMM', how='left')

        # 결합 레벨 산출
        def combined_level(row):
            if pd.isna(row['sw_signal']) or row['sw_signal'] == '-':
                return '-'
            m1 = _m1_level(row['sw_signal'])
            m2 = _m2_level(row['anomaly_score'] if pd.notna(row['anomaly_score']) else 0)
            return LEVEL_MAP[(m1, m2)]

        df['final_level'] = df.apply(combined_level, axis=1)
        results[name] = df

        if not verbose:
            continue

        print(f'\n{"="*65}')
        print(f'  {name.upper()} - Combined (Model1 + Model2)')
        print(f'{"="*65}')
        print(f'{"월":>8}  {"M1_z":>7}  {"M1신호":>12}  {"M2점수":>7}  {"최종레벨":>8}')
        print('-' * 60)

        for _, row in df.iterrows():
            if row['sw_signal'] == '-':
                continue
            ym     = str(int(row['YYYYMM']))
            marker = ' <<<' if ym in crisis_months else ''
            level  = row['final_level']
            score  = row['anomaly_score'] if pd.notna(row['anomaly_score']) else 0

            # 위험/경고만 강조
            if level in ('위험', '경고', '주의') or ym in crisis_months:
                print(f"{ym:>8}  {row['sw_z']:>7.3f}  {row['sw_signal']:>12}  "
                      f"{score:>7.4f}  {level:>8}{marker}")

    return results


def export_json(results: dict, out_path: Path = None) -> Path:
    import json
    from datetime import datetime

    if out_path is None:
        out_path = MODEL_DIR.parent / 'model_output.json'

    last_yyyymm = None
    payload = {}

    for name, df in results.items():
        records = []
        for _, row in df.iterrows():
            if row['sw_signal'] == '-':
                continue
            score = float(row['anomaly_score']) if pd.notna(row['anomaly_score']) else 0.0
            records.append({
                'YYYYMM':         int(row['YYYYMM']),
                'rollover_ratio': round(float(row['rollover_ratio']), 6),
                'sw_z':           round(float(row['sw_z']), 4),
                'sw_signal':      row['sw_signal'],
                'anomaly_score':  round(score, 4),
                'final_level':    row['final_level'],
            })
        payload[name] = records
        if records:
            last_yyyymm = records[-1]['YYYYMM']

    output = {
        'last_updated': last_yyyymm,
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        **payload,
    }

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    return out_path


if __name__ == '__main__':
    results = run_combined()

    print('\n\n=== 전체 기간 위험/경고 구간 요약 ===')
    for name, df in results.items():
        alerts = df[df['final_level'].isin(['위험', '경고', '주의'])]
        if alerts.empty:
            continue
        print(f'\n[{name.upper()}]')
        for _, row in alerts.iterrows():
            score = row['anomaly_score'] if pd.notna(row['anomaly_score']) else 0
            print(f"  {int(row['YYYYMM'])}  M1={row['sw_z']:+.3f}({row['sw_signal']})  "
                  f"M2={score:.3f}  → {row['final_level']}")
