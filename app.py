import os
from bs4 import BeautifulSoup
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = "watchdog_secret"

basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'market_watchdog.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)  # 아이디
    password = db.Column(db.String(100), nullable=False)  # 비밀번호
    email = db.Column(db.String(100), unique=True, nullable=False)  # 이메일
    user_type = db.Column(db.String(20), nullable=False)  # 'personal' or 'corporate'

    # 기업 회원 전용 필드 (개인일 경우 빈칸)
    company_name = db.Column(db.String(100), nullable=True)
    biz_number = db.Column(db.String(20), nullable=True)  # 사업자번호

with app.app_context():
    db.create_all()


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        data = request.form

        # 중복 체크 생략하고 바로 저장 (뼈대니까)
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
        print(f" 새 회원 가입 완료: {data['username']} ({data['user_type']})")
        return redirect(url_for('index'))

    return render_template('login.html')  # 가입 폼이 있는 페이지


def crawl_naver_news(keyword):
    """네이버에서 키워드로 뉴스 제목과 링크를 긁어오는 함수"""
    url = f"https://search.naver.com/search.naver?where=news&query={keyword}"
    headers = {"User-Agent": "Mozilla/5.0"}  # 차단 방지용

    response = request.get(url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')

    news_items = []
    # 네이버 뉴스 검색 결과의 제목 부분을 찾는 로직 (사이트 구조 바뀌면 수정 필요)
    articles = soup.select("ul.list_news > li")

    for art in articles[:5]:  # 딱 5개만 가져오자
        title = art.select_one("a.news_tit").text
        link = art.select_one("a.news_tit")['href']
        news_items.append({"title": title, "link": link})

    return news_items


# 프로젝트명 설정
PROJECT_NAME = "Market WatchDog"

@app.route('/')
def index():
    return render_template('index.html', project_name=PROJECT_NAME)

@app.route('/login')
def login():
    return render_template('login.html', project_name=PROJECT_NAME)

@app.route('/indicators')
def indicators():
    return render_template('indicators.html', project_name=PROJECT_NAME)

@app.route('/analysis')
def analysis():
    return render_template('analysis.html', project_name=PROJECT_NAME)

# --- 향후 구현할 API 껍데기들 ---
@app.route('/api/news')
def get_news():
    # "기업어음" 키워드로 뉴스 긁어오기
    news_data = crawl_naver_news("기업어음")
    return jsonify({"status": "success", "data": news_data})

if __name__ == '__main__':
    print(f"[{PROJECT_NAME}] 서버 가동 중... 시장 감시 시작한다.")
    app.run(debug=True, port=5000)