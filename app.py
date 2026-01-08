import os
from flask import Flask, render_template, jsonify, request, redirect, url_for, session
from models import db, User  # models.py에서 가져옴
from crawler import get_multiple_keywords_news  # crawler.py에서 가져옴
from finance_api import get_ecos_data, ECOS_INDICATORS


app = Flask(__name__)
app.secret_key = "watchdog_secret"

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
    # group 정보까지 같이 보내서 프론트에서 필터링 가능하게 함
    list_data = [{"id": k, "name": v['name'], "group": v['group']} for k, v in ECOS_INDICATORS.items()]
    return jsonify(list_data)

@app.route('/api/ecos_custom')
def ecos_custom():
    indicator_id = request.args.get('id')
    freq = request.args.get('freq', 'Q')
    start = request.args.get('start', '')
    end = request.args.get('end', '')

    config = ECOS_INDICATORS.get(indicator_id.upper() if indicator_id else "")
    if not config: return jsonify([])

    data = get_ecos_data(
        config['table'], config['item_code1'], freq, start, end,
        config.get('item_code2'), config.get('item_code3')
    )
    # 그래프를 그리기 위해 unit_type(rate인지 money인지) 정보도 살짝 끼워줌
    return jsonify({"data": data, "unit_type": config['unit_type'], "name": config['name']})

if __name__ == '__main__':
    print(f"[{PROJECT_NAME}] 서버 가동 시작...")
    app.run(debug=True, port=5000)