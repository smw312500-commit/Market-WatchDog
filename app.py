import os
import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, jsonify, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = "watchdog_secret"

# [1] 프로젝트 설정 및 DB 준비 (최상단으로 배치)
PROJECT_NAME = "Market WatchDog"
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'market_watchdog.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    user_type = db.Column(db.String(20), nullable=False)
    company_name = db.Column(db.String(100), nullable=True)
    biz_number = db.Column(db.String(20), nullable=True)


with app.app_context():
    db.create_all()



def crawl_infomax_search(query):
    """특정 키워드로 검색해서 최신 뉴스 가져오기"""
    # 인포맥스 검색 URL (최신순 정렬)
    url = f"https://news.einfomax.co.kr/news/articleList.html?sc_area=A&view_type=sm&sc_word={query}"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        articles = soup.select("ul.type2 li")

        results = []
        for art in articles[:5]:  # 슬롯당 최신 5개면 충분함
            title_tag = art.select_one("h4.titles a")
            if not title_tag: continue
            results.append({
                "title": title_tag.text.strip(),
                "link": "https://news.einfomax.co.kr" + title_tag['href']
            })
        return results
    except Exception as e:
        print(f"❌ {query} 검색 에러: {e}")
        return []


# [3] 페이지 라우팅 (경로 및 변수 정리)
@app.route('/')
def index():
    return render_template('index.html', project_name=PROJECT_NAME)


@app.route('/login')
def login():
    return render_template('login.html', project_name=PROJECT_NAME)


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
        return redirect(url_for('index'))
    return render_template('login.html', project_name=PROJECT_NAME)


@app.route('/indicators')
def indicators():
    return render_template('indicators.html', project_name=PROJECT_NAME)


@app.route('/analysis')
def analysis():
    return render_template('analysis.html', project_name=PROJECT_NAME)


# [4] API 엔드포인트

def get_multiple_keywords_news(keyword_list):
    """여러 키워드를 각각 검색해서 결과를 하나로 합침 (중복 제거)"""
    combined_results = []
    seen_links = set()  # 중복 기사 방지용

    for kw in keyword_list:
        # 각 키워드별로 검색 실행
        news_list = crawl_infomax_search(kw)
        for news in news_list:
            if news['link'] not in seen_links:
                combined_results.append(news)
                seen_links.add(news['link'])

    # 최신 기사 순으로 보여주고 싶으면 여기서 정렬하거나,
    # 그냥 앞에서부터 끊어서 7개만 반환
    return combined_results[:7]


@app.route('/api/infomax_news')
def get_infomax_news():
    # 이제 형이 원하는 대로 키워드를 리스트로 콤마(,) 찍어서 나열해
    data = {
        # 1번 슬롯: "CP 발행", "단기자금", "발행량" 중 하나라도 걸리면 다 가져와
        "slot1": get_multiple_keywords_news(["CP 발행", "단기자금", "발행량"]),

        # 2번 슬롯: 금리, 유동성 관련
        "slot2": get_multiple_keywords_news(["금리", "유동성", "레포"]),

        # 3번 슬롯: 리스크 관련
        "slot3": get_multiple_keywords_news(["신용위험", "PF", "부도"])
    }
    return jsonify(data)


if __name__ == '__main__':
    print(f"[{PROJECT_NAME}] 서버 가동 시작...")
    app.run(debug=True, port=5000)