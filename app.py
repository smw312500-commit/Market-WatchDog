import os
from flask import Flask, render_template, jsonify, request, redirect, url_for, session
from models import db, User  # models.py에서 가져옴
from crawler import get_multiple_keywords_news  # crawler.py에서 가져옴
from finance_api import get_ecos_data, get_local_data, ECOS_INDICATORS
import pandas as pd
from datetime import datetime, timedelta

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
    [카드 2번 엔진]
    1. CP만기별 발행현황.xlsx -> '3개월이하' 추출
    2. 단기사채 발행실적.xlsx -> '총합계' 추출
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

        # 3. 데이터 결합 (날짜 맞추기)
        combined = pd.concat([cp_3m, st_total], axis=1).dropna()

        # 날짜 포맷 정리 (2024/Q4)
        combined.index = combined.index.str.replace('년 ', '/Q').str.replace('월', '').str.replace('03', '1').str.replace(
            '06', '2').str.replace('09', '3').str.replace('12', '4')

        # 숫자로 변환
        combined['cp_under_3m'] = pd.to_numeric(combined['cp_under_3m'], errors='coerce')
        combined['st_bond_total'] = pd.to_numeric(combined['st_bond_total'], errors='coerce')

        # 4. 최근 5분기만 자르기
        result = combined.tail(5).reset_index().rename(columns={'index': '분기'})

        # 5. 저장 (나중에 확인용)
        save_path = os.path.join(PREPROCESS_DIR, 'cp_단기사채_결합_결과.csv')
        result.to_csv(save_path, index=False, encoding='utf-8-sig')

        print("✅ 2번 카드(CP 3M + 단기사채) 가공 성공!")
        return result

    except Exception as e:
        print(f"🔥 2번 가공 에러: {e}")
        return None

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
            print("❌ API 호출은 성공했으나 데이터가 비어있어 형. 날짜나 코드를 확인해봐.")
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

    except Exception as e:
        print(f"🔥 프록시 가공 엔진 내부 에러: {e}")
        import traceback
        traceback.print_exc()  # 어디서 에러 났는지 상세히 찍어줌
        return None


@app.route('/api/analysis_summary')
def get_analysis_summary():
    try:
        # [1] 1번 카드 엔진: 프록시 성공률 가공
        df1 = process_cp_proxy_data()

        # [2] 2번 카드 엔진: CP 3개월물 + 단기사채 총합계 가공
        df2 = process_card2_data()

        if df1 is None or df2 is None:
            return jsonify({"error": "데이터 가공 중 에러가 발생했어 형. 터미널 확인해봐!"}), 500

        # 최근 5분기 데이터 추출
        last_5_df1 = df1.tail(5)
        last_5_df2 = df2.tail(5)

        # [3] JSON 리턴 (2번 카드 데이터 포함)
        return jsonify({
            "labels": last_5_df1['분기'].tolist(),  # X축 라벨
            "cp_issuance": last_5_df1['성공률_QoQ(%)'].fillna(0).tolist(),  # 1번 카드 데이터

            # 2번 카드: 두 개의 지표를 리스트로 전달
            "maturity": {
                "cp_3m": last_5_df2['cp_under_3m'].tolist(),  # 3개월 이하 CP
                "st_bond": last_5_df2['st_bond_total'].tolist()  # 단기사채 총합
            },

            # 3번은 아직 0으로 (다음 단계에서 작업)
            "non_bank_delta": [0] * 5,

            "final_status": {
                "state": "Analyzing",
                "p_risk": 0.45,
                "explanation": "1번(성공률)과 2번(단기물 발행규모) 지표 연동이 완료되었습니다."
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