import os
from flask import Flask, render_template, jsonify, request, redirect, url_for, session
from models import db, User  # models.py에서 가져옴
from crawler import get_multiple_keywords_news  # crawler.py에서 가져옴
from finance_api import get_ecos_data, get_local_data, ECOS_INDICATORS
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
import json

app = Flask(__name__)
app.secret_key = "watchdog_secret"
BASE_DIR = r"C:\Users\smw31\PycharmProjects\Market-WatchDog"
DATA_DIR = os.path.join(BASE_DIR, "data")
PREPROCESS_DIR = os.path.join(DATA_DIR, "전처리")

# 전처리 폴더가 없으면 생성
if not os.path.exists(PREPROCESS_DIR):
    os.makedirs(PREPROCESS_DIR)

# [1] 프로젝트 설정
PROJECT_NAME = "Market WatchDog"
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'market_watchdog.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# DB 초기화
db.init_app(app)

with app.app_context():
    db.create_all()

# [2] 페이지 라우팅
@app.route('/')
def index():
    return render_template('index.html', project_name=PROJECT_NAME)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session['user_id'] = user.id
            session['username'] = user.username
            return redirect(url_for('index'))
        else:
            return "로그인 실패! 아이디나 비번 확인."
    return render_template('login.html', project_name=PROJECT_NAME, mode='login')

@app.route('/logout')
def logout():
    session.clear()
    print(" 로그아웃 완료")
    return redirect(url_for('index'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        data = request.form
        new_user = User(
            username=data['username'],
            password=data['password'],
            email=data['email'],
            user_type=data['user_type'],
            company_name=data.get('company_name'),
            biz_number=data.get('biz_number')
        )
        db.session.add(new_user)
        db.session.commit()
        session['user_id'] = new_user.id
        session['username'] = new_user.username
        return redirect(url_for('index'))
    return render_template('login.html', project_name=PROJECT_NAME, mode='signup')

@app.route('/indicators')
def indicators():
    return render_template('indicators.html', project_name=PROJECT_NAME)

@app.route('/analysis')
def analysis():
    return render_template('analysis.html', project_name=PROJECT_NAME)


def process_cp_data():
    """
    원본 데이터셋에서 Success_Rate를 가져와 QoQ를 계산하고
    '전처리' 폴더에 저장하는 가공 함수
    """
    # 원본 데이터셋 경로 (Success_Rate가 들어있는 파일)
    source_path = os.path.join(DATA_DIR, 'Regime_EWS_Dataset_v3_Refined.csv')

    if not os.path.exists(source_path):
        return None

    # 데이터 읽기 및 가공 (형의 성공률 QoQ 로직)
    df = pd.read_csv(source_path, encoding='utf-8-sig')
    df.columns = df.columns.str.strip()

    # 가공: 분기와 성공률 추출 후 QoQ 계산
    # 구조 재현
    result = df[['분기', 'Success_Rate']].copy()
    result.rename(columns={'Success_Rate': '발행성공률(%)'}, inplace=True)

    # 성공률 QoQ 계산: (현재-이전)/이전 * 100
    result['성공률_QoQ(%)'] = result['발행성공률(%)'].pct_change() * 100

    # '전처리' 폴더에 저장
    save_path = os.path.join(PREPROCESS_DIR, 'cp_발행성공률_QoQ_결과.csv')
    result.to_csv(save_path, index=False, encoding='utf-8-sig')

    return result


def process_card2_data():
    """
    [카드 2번 엔진 - 단위: 조 원]
    1. CP만기별 발행현황.xlsx -> '3개월이하' 추출 (단위 변환: 억 -> 조)
    2. 단기사채 발행실적.xlsx -> '총합계' 추출 (단위 변환: 억 -> 조)
    3. 최근 5분기 데이터 결합
    """
    cp_path = os.path.join(DATA_DIR, 'CP만기별 발행현황.xlsx')
    st_path = os.path.join(DATA_DIR, '단기사채 발행실적.xlsx')

    if not os.path.exists(cp_path) or not os.path.exists(st_path):
        print("❌ 2번 카드용 파일이 부족해 형!")
        return None

    try:
        # 1. CP 3개월 이하 데이터 추출
        df_cp = pd.read_excel(cp_path, skiprows=1, engine='openpyxl')
        df_cp.columns = df_cp.columns.str.strip()
        cp_3m = df_cp[df_cp['항목'] == '3개월이하'].iloc[:, 2:].T
        cp_3m.columns = ['cp_under_3m']

        # 2. 단기사채 총합계 데이터 추출
        df_st = pd.read_excel(st_path, skiprows=1, engine='openpyxl')
        df_st.columns = df_st.columns.str.strip()
        st_total = df_st[df_st['항목'] == '총합계'].iloc[:, 2:].T
        st_total.columns = ['st_bond_total']

        # 3. 데이터 결합 및 단위 변환
        combined = pd.concat([cp_3m, st_total], axis=1).dropna()

        # [핵심] 숫자로 변환 후 10,000으로 나눠서 '조 원' 단위로 변경
        combined['cp_under_3m'] = pd.to_numeric(combined['cp_under_3m'], errors='coerce') / 10000
        combined['st_bond_total'] = pd.to_numeric(combined['st_bond_total'], errors='coerce') / 10000

        # 날짜 포맷 정리 (2024/Q4)
        combined.index = combined.index.str.replace('년 ', '/Q').str.replace('월', '').str.replace('03', '1').str.replace(
            '06', '2').str.replace('09', '3').str.replace('12', '4')

        # 4. 최근 5분기만 자르기
        result = combined.tail(5).reset_index().rename(columns={'index': '분기'})

        # 5. 저장
        save_path = os.path.join(PREPROCESS_DIR, 'cp_단기사채_결합_결과.csv')
        result.to_csv(save_path, index=False, encoding='utf-8-sig')

        print("✅ 2번 카드(CP 3M + 단기사채) 가공 성공! (단위: 조 원)")
        return result

    except Exception as e:
        print(f"🔥 2번 가공 에러: {e}")
        return None


def process_card3_data():
    """
    [카드 3번 엔진]
    비금융법인 CP 부채 '전체 잔액(절대액)'을 조 단위로 환산
    """
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=365 * 2)).strftime("%Y%m%d")

    try:
        c_non = ECOS_INDICATORS['NON_FIN_CP_LIAB']

        # API 호출
        non_fin_data = get_ecos_data(
            c_non['table'], c_non['item_code1'], 'Q', start_date, end_date,
            item_code2=c_non.get('item_code2'), item_code3=c_non.get('item_code3')
        )

        if not non_fin_data:
            return [0] * 5

        df = pd.DataFrame(non_fin_data).set_index('TIME')
        df['DATA_VALUE'] = pd.to_numeric(df['DATA_VALUE'], errors='coerce')

        # [수정] 증감량(diff) 계산을 삭제하고 '전체 잔액'을 조 단위로 환산
        # 십억 원 단위 -> 1,000으로 나누면 '조 원'
        df['total_balance_trillion'] = df['DATA_VALUE'] / 1000

        # 최근 5분기의 전체 잔액 리스트 반환
        return df['total_balance_trillion'].tail(5).tolist()

    except Exception as e:
        print(f"3번 가공 에러: {e}")
        return [0] * 5

def process_cp_proxy_data():
    """
    [카드 1번 최종 엔진]
    형의 get_ecos_data(table_code, item_code1, freq, start_date, end_date, item_code2, item_code3)
    규격에 100% 맞춰서 호출하도록 수정했어.
    """
    issuance_path = os.path.join(DATA_DIR, 'CP발행실적.xlsx')

    # 넉넉하게 최근 8분기치 가져와서 5분기 뽑아내기
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=365 * 2)).strftime("%Y%m%d")

    try:
        # [1] 분자: 엑셀 발행 실적
        df_iss = pd.read_excel(issuance_path, skiprows=1, engine='openpyxl')
        df_iss.columns = df_iss.columns.str.strip()
        iss_total = df_iss[df_iss['항목'] == '총합계'].iloc[:, 2:].T
        iss_total.columns = ['issuance']
        iss_total.index = iss_total.index.str.replace('년 ', 'Q').str.replace('월', '').str.replace('03',
                                                                                                  '1').str.replace('06',
                                                                                                                   '2').str.replace(
            '09', '3').str.replace('12', '4')

        # [2] 분모: 한은 API 데이터 (금융/비금융 합산)
        c_fin = ECOS_INDICATORS['FIN_CP_LIAB']
        c_non = ECOS_INDICATORS['NON_FIN_CP_LIAB']

        # ★ 형의 함수 규격에 맞춰서 인자 순서 정렬!
        # get_ecos_data(table_code, item_code1, freq, start_date, end_date, item_code2, item_code3)
        fin_data = get_ecos_data(
            c_fin['table'], c_fin['item_code1'], 'Q', start_date, end_date,
            item_code2=c_fin.get('item_code2'), item_code3=c_fin.get('item_code3')
        )
        non_fin_data = get_ecos_data(
            c_non['table'], c_non['item_code1'], 'Q', start_date, end_date,
            item_code2=c_non.get('item_code2'), item_code3=c_non.get('item_code3')
        )

        if not fin_data or not non_fin_data:
            print(" API 호출은 성공했으나 데이터가 비어있어 . 날짜나 코드를 확인해봐.")
            return None

        # [3] 가공 로직
        df_fin = pd.DataFrame(fin_data).set_index('TIME')  # 한은 결과는 대문자 'TIME'일 확률이 높음
        df_non = pd.DataFrame(non_fin_data).set_index('TIME')

        # 'DATA_VALUE' 컬럼을 숫자로 변환해서 합산
        df_fin['DATA_VALUE'] = pd.to_numeric(df_fin['DATA_VALUE'], errors='coerce')
        df_non['DATA_VALUE'] = pd.to_numeric(df_non['DATA_VALUE'], errors='coerce')

        stock_total = df_fin['DATA_VALUE'] + df_non['DATA_VALUE']
        stock_total.name = 'stock'

        # [4] 데이터 병합 및 성공률 계산
        final_df = pd.concat([iss_total, stock_total], axis=1).dropna()
        # 성공률 = (발행액 / 시장잔액) * 100  (단위 보정: 잔액 십억원 -> 원)
        final_df['발행성공률(%)'] = (final_df['issuance'] / (final_df['stock'] * 1000000000)) * 100
        final_df['성공률_QoQ(%)'] = final_df['발행성공률(%)'].pct_change() * 100

        # 보기 좋게 인덱스 정리
        final_df.index = [f"{str(x)[:4]}/{str(x)[4:]}" for x in final_df.index]
        final_df = final_df.reset_index().rename(columns={'index': '분기'})

        # [5] 저장 및 반환
        final_df = final_df.tail(5)
        save_path = os.path.join(PREPROCESS_DIR, 'cp_발행성공률_QoQ_결과.csv')
        final_df.to_csv(save_path, index=False, encoding='utf-8-sig')

        print("✅ 1번 카드 프록시 가공 성공!")
        return final_df

    except Exception as e:
        print(f"🔥 가공 중 에러 발생: {e}")
        import traceback
        traceback.print_exc()
        return None


def load_ml_data():
    json_path = os.path.join(DATA_DIR, 'EWS_Final_Data.json')
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)

        parsed_rows = []
        for entry in raw_data:
            # 탭으로 구분된 키와 값을 분리
            key = list(entry.keys())[0]
            val = entry[key]
            # 컬럼명과 데이터를 결합하여 딕셔너리 생성
            cols = key.split('\t')
            vals = val.split('\t')
            parsed_rows.append(dict(zip(cols, vals)))

        df = pd.DataFrame(parsed_rows)

        # Explanation_Top3에서 S1, S2 수치 추출 (ML 피처로 활용)
        # 예: "S1_Accel: -7.46 | S1_Delta: -2.37 | S2_Delta: -7.73"
        df['S1_Delta'] = df['Explanation_Top3'].str.extract(r'S1_Delta: ([-]?\d+\.\d+)').astype(float)
        df['S2_Delta'] = df['Explanation_Top3'].str.extract(r'S2_Delta: ([-]?\d+\.\d+)').astype(float)

        return df
    except Exception as e:
        print(f"🔥 ML 데이터 로드 실패: {e}")
        return None

# 전역 변수로 ML 데이터 로드
ml_knowledge_base = load_ml_data()


def analyze_market_risk_ml(current_m1, current_m3):
    """
    현재 지표(m1, m3)와 가장 유사한 과거 패턴을 ML 데이터셋에서 찾아 진단합니다.
    """
    if ml_knowledge_base is None:
        return "Normal", 0.1, "데이터베이스를 로드할 수 없어 분석이 제한됩니다."

    # 유사도 계산 (Euclidean Distance)
    # 현재 데이터와 과거 데이터셋 간의 거리를 계산하여 가장 유사한 시점을 탐색합니다.
    distances = np.sqrt(
        (ml_knowledge_base['S1_Delta'] - current_m1) ** 2 +
        (ml_knowledge_base['S2_Delta'] - current_m3) ** 2
    )

    # 가장 유사한 과거 사례 매칭
    closest_idx = distances.idxmin()
    match = ml_knowledge_base.loc[closest_idx]

    state = match['EWS_Result_Status']
    p_risk = float(match['p_risk'])

    # [지표 해석 로직] 전문적인 용어로 변환
    raw_exp = match['Explanation_Top3']  # "S1_Accel: -9.28 | S1_Delta: -5.75 | S2_Delta: -1.46"

    try:
        # 문자열에서 수치 추출
        s1_a = float(raw_exp.split('S1_Accel: ')[1].split(' |')[0])
        s1_d = float(raw_exp.split('S1_Delta: ')[1].split(' |')[0])
        s2_d = float(raw_exp.split('S2_Delta: ')[1])

        # 수치에 따른 상태 정의
        accel_text = "급격한 위축세" if s1_a < 0 else "회복세 전환"
        delta_text = "하락" if s1_d < 0 else "상승"
        short_term_text = "심화" if s2_d > 0 else "완화"

        # 사용자용 최종 멘트 조립 (정중한 문체)
        explanation = (
            f"현재 시장 패턴은 과거 {match['분기']}의 위기 징후와 매우 유사한 것으로 분석되었습니다. "
            f"당시 발행 시장은 {accel_text}({s1_a})를 보였으며, "
            f"조달 성공률은 전분기 대비 {delta_text}({s1_d})하는 양상을 나타냈습니다. "
            f"특히 단기물 쏠림 현상이 {short_term_text}({s2_d})되었던 시기이므로, 리스크 관리에 만전을 기할 필요가 있습니다."
        )
    except Exception as e:
        explanation = f"현재 시장 상황은 {match['분기']}의 통계적 패턴과 유사성을 보이고 있습니다. 변동성 확대에 유의하시기 바랍니다."

    return state, p_risk, explanation


@app.route('/api/analysis_summary')
@app.route('/api/analysis_summary')
def get_analysis_summary():
    try:
        # [1] 기존 엔진들 호출 (변화 없음)
        df1 = process_cp_proxy_data()
        df2 = process_card2_data()
        delta3 = process_card3_data()    # 현재 '잔액' 리스트 (조 단위)

        if df1 is None or df2 is None or not delta3:
            return jsonify({"error": "Data failure"}), 500

        last_5_df1 = df1.tail(5)
        last_5_df2 = df2.tail(5)

        # ---------------------------------------------------------
        # [수정 포인트] ML 진단용 '변화량' 계산
        # ---------------------------------------------------------
        # 1. 1번 카드 성공률 (QoQ)
        current_m1 = last_5_df1['성공률_QoQ(%)'].iloc[-1]

        # 2. 3번 카드 변화량 계산 (최신 잔액 - 이전 분기 잔액)
        # delta3가 잔액 리스트이므로, 마지막 두 값의 차이를 구해야 'S2_Delta'와 매칭됨
        if len(delta3) >= 2:
            current_m3_delta = delta3[-1] - delta3[-2]
        else:
            current_m3_delta = 0  # 데이터가 부족할 경우 안전장치

        # ML 엔진 호출: 잔액이 아닌 '변화량(current_m3_delta)'을 넣어줌!
        state, p_risk, explanation = analyze_market_risk_ml(current_m1, current_m3_delta)
        # ---------------------------------------------------------

        return jsonify({
            "labels": last_5_df1['분기'].tolist(),
            "cp_issuance": last_5_df1['성공률_QoQ(%)'].fillna(0).tolist(),

            "maturity": {
                "cp_3m": last_5_df2['cp_3m'].tolist() if 'cp_3m' in last_5_df2 else last_5_df2['cp_under_3m'].tolist(),
                "st_bond": last_5_df2['st_bond'].tolist() if 'st_bond' in last_5_df2 else last_5_df2['st_bond_total'].tolist()
            },

            # 화면에는 형이 원하는 '잔액' 리스트 그대로 전달
            "non_bank_delta": delta3,

            "final_status": {
                "state": state,
                "p_risk": p_risk,
                "explanation": explanation
            }
        })
    except Exception as e:
        print(f"🔥 API 리턴 중 에러: {e}")
        return jsonify({"error": str(e)}), 500


# [3] API 엔드포인트
@app.route('/api/infomax_news')
def get_infomax_news():
    data = {
        "slot1": get_multiple_keywords_news(["CP 발행", "단기자금", "발행량"]),
        "slot2": get_multiple_keywords_news(["금리", "유동성", "레포"]),
        "slot3": get_multiple_keywords_news(["신용위험", "PF", "부도"])
    }
    return jsonify(data)

@app.route('/api/indicator_list')
def get_indicator_list():
    # source 정보를 포함해서 1번/4번 칸 분리 가능하게 전달
    list_data = [{"id": k, "name": v['name'], "group": v['group'], "source": v.get('source', 'API')} for k, v in ECOS_INDICATORS.items()]
    return jsonify(list_data)

@app.route('/api/ecos_custom')
def ecos_custom():
    indicator_id = request.args.get('id', '').upper()
    freq = request.args.get('freq', 'Q')
    start = request.args.get('start', '2023-01-01')
    end = request.args.get('end', '')

    config = ECOS_INDICATORS.get(indicator_id)
    if not config: return jsonify({"data": [], "name": "Unknown", "unit_type": "rate"})

    if config.get('source') == 'LOCAL':
        raw_data = get_local_data(config, freq)
    else:
        raw_data = get_ecos_data(config['table'], config['item_code1'], freq, start, end, config.get('item_code2'),
                                 config.get('item_code3'))

    return jsonify({"data": raw_data, "unit_type": config['unit_type'], "name": config['name']})

if __name__ == '__main__':
    print(f"[{PROJECT_NAME}] 서버 가동 시작...")
    app.run(debug=True, port=5000)