# Market WatchDog

한국 단기금융시장(CP·ABCP·AB단기사채)의 발행·잔액·신용·만기 데이터를 월별로 수집·가공해,
머신러닝 기반 이상탐지 모델로 시장 스트레스를 정량화하고 실시간으로 시각화하는 Flask 기반 대시보드입니다.

---

## 주요 기능

**INDICATORS** — 시계열 지표 대시보드  
CP·ABCP·AB단기사채 3개 시장의 잔액·발행액·만기구조·신용등급 비중을 2016년부터 월별 누적 차트로 제공합니다. 전체·24·12·6·3개월 기간 선택 및 커스텀 범위 조회를 지원합니다.

**시장감시** — ML 이상탐지 대시보드  
Sliding Window(Model 1) + Isolation Forest(Model 2) 두 모델을 결합해 시장 스트레스를 탐지합니다. CP·ABCP·AB단기사채 각각의 현재 레벨(정상/주의/경고/위험)을 카드로 표시하고, 시장 스트레스·추세 이탈 시계열 차트를 제공합니다.

**AI 시장 해석** — GPT-4o-mini 자동 요약  
파이프라인 실행 또는 버튼 클릭 시 현재 시장 데이터를 기반으로 비전문가 언어의 시장 요약을 생성합니다.

**AI 시장 도우미** — 실시간 채팅  
현재 시장 데이터가 자동으로 컨텍스트에 포함된 OpenAI 기반 채팅 기능입니다.

**보안 레이어** — Date-Based Dynamic Decoy Security Layer  
에니그마 암호 컨셉을 적용한 자체 설계 보안 레이어입니다. 비인증 API 접근 시 원본 대신 날짜·Seed 문서 기반으로 치환된 Decoy 데이터를 반환합니다. `/demo`에서 시연, `/admin`에서 Seed 관리 및 접근 로그를 확인할 수 있습니다.

---

## 빠른 실행

Python 3.12 권장.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# .env 파일을 열어 OPENAI_API_KEY 입력
python app.py
```

브라우저에서 `http://127.0.0.1:5000` 으로 접속합니다.

---

## 환경변수 설정 (.env)

`.env.example`을 복사해서 `.env`로 만들고 아래 항목을 채웁니다.

| 변수 | 설명 |
|---|---|
| `OPENAI_API_KEY` | OpenAI API 키 (AI 요약·채팅 기능에 필요) |
| `FLASK_SECRET` | Flask 세션 암호화 키 (임의 문자열로 변경 권장) |
| `ADMIN_ID` | 관리자 로그인 아이디 (기본: admin) |
| `ADMIN_PW` | 관리자 로그인 비밀번호 |
| `FLASK_HOST` | 기본 `127.0.0.1` |
| `FLASK_PORT` | 기본 `5000` |

---

## 월별 데이터 업데이트

`run_pipeline.py`를 실행하면 크롤링 → 전처리 → DB 업데이트 → ML 모델 적용 → AI 요약 생성이 한 번에 됩니다.

```bash
python run_pipeline.py 26년5월
```

원천 파일이 이미 있으면 크롤링을 건너뛸 수 있습니다.

```bash
SKIP_CRAWL=1 python run_pipeline.py 26년5월
```

---

## 관리자 콘솔

`http://127.0.0.1:5000/admin` 에서 관리자 로그인 후 사용합니다.

- **Seed 문서 선택**: `mail_archive/` 폴더의 업무 메일 12개 중 하나를 Decoy 암호화 Seed로 지정
- **접근 로그**: 정상 접근(NORMAL_ACCESS) / Decoy 반환(DECOY_RETURNED) 이력 확인
- **Seed 이력**: 버전별 Seed 변경 이력 조회

---

## Decoy 보안 레이어 시연

`http://127.0.0.1:5000/demo` 에서 인증 여부에 따라 원본 데이터와 Decoy 데이터가 어떻게 달라지는지 확인할 수 있습니다.

---

## 포트폴리오 문서 생성

```bash
python make_portfolio.py
```

`screenshots/` 폴더에 스크린샷을 저장해두면 문서에 자동 삽입됩니다.

| 파일명 | 내용 |
|---|---|
| `cover.png` | 대시보드 전체 화면 |
| `indicators.png` | INDICATORS 차트 |
| `analysis_stress.png` | 시장감시 — 스트레스 차트 |
| `analysis_trend.png` | 시장감시 — 추세 이탈 탭 |
| `ai_chat.png` | AI 채팅 화면 |
| `decoy_demo.png` | Decoy 데모 비교 |
| `admin.png` | 관리자 콘솔 |

---

## 참고

- 크롤링은 Chrome + Selenium + `webdriver-manager`가 필요합니다.
- ML 모델 pkl 파일(`model/*.pkl`)은 저장소에 포함되지 않습니다. 최초 실행 시 `model/model2.py`로 학습이 필요합니다.
- `market_watchdog.db`는 저장소에 포함되지 않습니다. 전처리 CSV가 있으면 `db_upsert_patch.py`로 생성할 수 있습니다.
- 전처리·크롤링 스크립트는 로컬 경로 구조를 전제로 합니다. Flask 화면만 확인하려면 현재 스냅샷 DB만으로 충분합니다.
