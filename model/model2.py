"""
Model 2: Isolation Forest 이상탐지 모델
CP / ABCP / ABSTB 각각 독립적으로 다변수 이상 점수 산출
학습 구간: 201601 ~ 202512

피처 (구조적 변화 흡수):
  sw_z          - Model1 슬라이딩윈도우 이탈 크기 (raw비율 대신)
  acceleration  - 롤오버 비율 가속도 (2차 미분)
  a2_diff       - A2 등급 비중의 전월 변화량
  tenor_diff    - 단기만기 비중의 전월 변화량
"""
import pandas as pd
from pathlib import Path
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import joblib

import sys
sys.path.insert(0, str(Path(__file__).parent))
from model1 import load_instrument, compute_sliding_window

MODEL_DIR     = Path(__file__).parent
CONTAMINATION = 0.05


FEATURE_COLS = ['sw_z', 'acceleration', 'a2_diff', 'tenor_diff']


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    df = compute_sliding_window(df).copy()

    # 가속도: 롤오버 비율 2차 미분
    df['velocity']     = df['rollover_ratio'].diff()
    df['acceleration'] = df['velocity'].diff()

    # A2 등급 비중 전월 변화량 (수준이 아니라 변화)
    df['a2_diff']    = df['issue_share_high'].diff()

    # 단기만기 비중 전월 변화량
    df['tenor_diff'] = df['short_tenor'].diff()

    return df


def train(name: str) -> tuple:
    df = load_instrument(name)
    df = build_features(df)

    # sw_z는 13번째 월부터 유효, acceleration은 추가 2행 필요 → 앞 14행 제거
    df_train = df.dropna(subset=FEATURE_COLS).copy()

    X = df_train[FEATURE_COLS].values

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = IsolationForest(
        n_estimators=200,
        contamination=CONTAMINATION,
        random_state=42
    )
    model.fit(X_scaled)

    raw_scores = model.decision_function(X_scaled)
    scores_01  = 1 - (raw_scores - raw_scores.min()) / (raw_scores.max() - raw_scores.min())

    df_train = df_train.copy()
    df_train['anomaly_score'] = scores_01
    df_train['anomaly_label'] = model.predict(X_scaled)

    joblib.dump(model,  MODEL_DIR / f'if_{name}.pkl')
    joblib.dump(scaler, MODEL_DIR / f'scaler_{name}.pkl')

    return model, scaler, df_train


def score_new(name: str, df_new: pd.DataFrame) -> pd.DataFrame:
    """학습된 모델로 새 데이터 점수 산출"""
    model  = joblib.load(MODEL_DIR / f'if_{name}.pkl')
    scaler = joblib.load(MODEL_DIR / f'scaler_{name}.pkl')

    df = build_features(df_new).dropna(subset=FEATURE_COLS).copy()
    X  = scaler.transform(df[FEATURE_COLS].values)

    raw = model.decision_function(X)
    df['anomaly_score'] = -raw
    df['anomaly_label'] = model.predict(X)
    return df


def run(verbose: bool = True) -> dict:
    results = {}
    crisis_months = {'202210', '202209', '202211', '202003', '202004'}

    for name in ['cp', 'abcp', 'abstb']:
        _, _, df = train(name)
        results[name] = df

        if not verbose:
            continue

        print(f'\n{"="*65}')
        print(f'  {name.upper()} - Model 2 Isolation Forest')
        print(f'{"="*65}')
        print(f'{"월":>8}  {"sw_z":>7}  {"가속도":>9}  {"A2변화":>8}  {"만기변화":>8}  {"이상점수":>8}  {"판정"}')
        print('-' * 70)

        for _, row in df.iterrows():
            ym     = str(int(row['YYYYMM']))
            marker = ' <<<' if ym in crisis_months else ''
            label  = '이상' if row['anomaly_label'] == -1 else '정상'
            print(f"{ym:>8}  {row['sw_z']:>7.3f}  "
                  f"{row['acceleration']:>9.5f}  {row['a2_diff']:>8.4f}  "
                  f"{row['tenor_diff']:>8.4f}  {row['anomaly_score']:>8.4f}  "
                  f"{label}{marker}")

    return results


if __name__ == '__main__':
    results = run()

    print('\n\n=== 이상 탐지 요약 (상위 10개 이상 점수) ===')
    for name, df in results.items():
        top = df.nlargest(10, 'anomaly_score')[['YYYYMM', 'anomaly_score', 'anomaly_label']]
        print(f'\n[{name.upper()}]')
        for _, row in top.iterrows():
            label = '이상' if row['anomaly_label'] == -1 else '정상'
            print(f"  {int(row['YYYYMM'])}  score={row['anomaly_score']:.4f}  {label}")
