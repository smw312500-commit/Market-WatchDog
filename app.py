import os
from flask import Flask, render_template, jsonify, request, redirect, url_for, session
from models import db, User  # models.py에서 가져옴
from crawler import get_multiple_keywords_news  # crawler.py에서 가져옴
from finance_api import get_ecos_data, get_local_data, ECOS_INDICATORS
import pandas as pd

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


@app.route('/api/analysis_summary')
def get_analysis_summary():
    try:
        # [2] 가공 프로세스 실행 (파일이 없으면 만들고, 있으면 최신화)
        processed_df = process_cp_data()

        if processed_df is None:
            return jsonify({"error": "원본 데이터셋 파일을 찾을 수 없습니다."}), 404

        # [3] 가공된 데이터에서 최근 5분기 추출
        last_5 = processed_df.tail(5)
        labels = last_5['분기'].astype(str).tolist()
        cp_qoq_data = last_5['성공률_QoQ(%)'].fillna(0).tolist()

        # 최종 전송 데이터 (첫 번째 카드에 cp_qoq_data 주입)
        return jsonify({
            "labels": labels,
            "cp_issuance": cp_qoq_data,  # 첫 번째 카드 그래프 데이터
            "st_3m_ratio": [65, 68, 72, 70, 71],  # (추후 파일 연결)
            "non_bank_delta": [1, 2, -1, 3, 4],  # (추후 파일 연결)
            "final_status": {
                "state": "Caution (주의)",
                "p_risk": 0.58,
                "explanation": "전처리 엔진을 통해 CP 발행 성공률 QoQ 데이터가 가공되었습니다."
            }
        })

    except Exception as e:
        print(f"🔥 서버 에러: {str(e)}")
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