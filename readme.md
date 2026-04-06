# Market WatchDog

한국 단기금융시장(CP·ABCP·AB단기사채) 스트레스 지수 모니터링 웹 대시보드

---

## 프로젝트 개요

단기채 시장의 잔액 추세, 신용도 구조, 만기구조 변화를 복합 분석해 시장 스트레스 수준을 지수화한 **MSI(Market Stress Index) v56.2** 기반 모니터링 시스템입니다.

예측 도구가 아닌 **현황 판단 보조 도구**로, 레고랜드 사태(2022.10) 등 과거 주요 사건을 학습해 현재 시장의 취약성 수준을 평가합니다.

---

## 주요 기능

- **실시간 뉴스** — 연합인포맥스 직접금융·단기자금·신용위험 3개 슬롯
- **지표 아카이브** — CP·ABCP·AB단기사채 잔액·발행·만기·신용도 전체 차트
- **MSI 분석 대시보드** — 현재 스트레스 수준, 사건별 비교 차트, 최근 24개월 테이블

---

## MSI v56.2 평가 구조

3개 축으로 구성됩니다.

| 축 | 지표 | 가중치 |
|----|------|--------|
| 잔액 | CP·ABCP·AB 잔액비중 추세 이탈 | 45% |
| 신용도 | CP·AB A1/A2 발행비중 쏠림 | 30% |
| 만기구조 | ABCP·AB·CP ultra+short 비중 | 25% |

레고랜드 사건월(2022.10)을 기준점(1.00)으로 정규화합니다.

| 점수 | 상태 |
|------|------|
| < 0.50 | 정상 |
| 0.50 ~ 0.75 | 주의 |
| 0.75 ~ 1.00 | 경고 |
| 1.00 ~ 1.20 | 위험 |
| ≥ 1.20 | 초위험 |

---

## 기술 스택

- **Backend** — Python 3.12, Flask
- **Database** — SQLite
- **Frontend** — HTML/CSS/JS, Chart.js
- **크롤링** — requests, BeautifulSoup

---

## 설치 및 실행

```bash
# 1. 의존성 설치
pip install flask requests beautifulsoup4 python-dotenv

# 2. 환경변수 설정
# dot_env.txt 파일을 .env 로 이름 변경 후 경로 수정
cp dot_env.txt .env

# 3. DB 초기화 (최초 1회)
python init_db.py

# 4. 서버 실행
python app.py
```

브라우저에서 `http://localhost:5000` 접속

---

## 프로젝트 구조

```
Market-WatchDog/
├── app.py                  # Flask 메인 서버
├── crawler.py              # 연합인포맥스 뉴스 크롤러
├── models.py               # DB 모델
├── templates/
│   ├── index.html          # 뉴스 페이지
│   ├── indicators.html     # 지표 아카이브
│   └── analysis.html       # MSI 분석 대시보드
├── dot_env.txt             # 환경변수 템플릿 (.env로 변경 후 사용)
└── README.md
```

---

## 주의사항

- `.env` 파일은 절대 깃에 올리지 마세요 (`.gitignore` 처리됨)
- MSI 계산 스크립트 및 데이터 파일은 별도 관리합니다
