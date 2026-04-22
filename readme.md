# Market WatchDog

CP, ABCP, ABSTB 데이터를 기반으로 시장 상태를 보는 Flask 대시보드입니다.

이 저장소는 현재 `2026년 2월` 기준 데이터 스냅샷으로 바로 화면을 확인할 수 있게 정리되어 있습니다.

## 빠른 실행

권장 환경은 `Python 3.12`입니다.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python app.py
```

브라우저에서 `http://127.0.0.1:5000` 으로 접속하면 됩니다.

## 기본 설정

- `MARKET_DB`: Flask가 읽는 메인 SQLite 파일 경로
- `MSI_ROOT`: MSI sqlite 폴더 경로
- `FLASK_HOST`: 기본 `127.0.0.1`
- `FLASK_PORT`: 기본 `5000`
- `FLASK_DEBUG`: 기본 `0`

`.env` 경로는 상대경로로 적어도 되고, 필요하면 절대경로를 써도 됩니다.

## 현재 포함된 데이터

- 메인 DB: `market_watchdog.db`
- MSI sqlite: `master set/msi/26년2월`
- Flask 화면은 현재 기준으로 `2026년 2월`까지 보이도록 맞춰져 있습니다.

## 3월 데이터 업데이트 순서

유지보수용 로컬 PC에서 아래 순서로 갱신하면 됩니다.

```bash
python "Siebro crawler.py"
python "Seibro balance crawler.py"
python monthly_preprocess_automation.py
python rollover_auto.py
python init_db.py --month "26년3월"
python MSI_v562_sqlite.py
```

입력 단계에서 다음 값을 쓰면 됩니다.

- `monthly_preprocess_automation.py`: 대상 월 `26년3월`, 기준 월 `26년2월`
- `rollover_auto.py`: 대상 월 `26년3월`

## 참고

- 크롤링 스크립트는 Chrome, Selenium, `webdriver-manager`, `pandas`가 필요합니다.
- 크롤링 종료월은 현재 날짜 기준 `지난달 말`까지 보도록 바꿔두었습니다. 지금 날짜 기준이면 `2026년 3월`까지 대상입니다.
- 전처리/크롤링 스크립트는 아직 유지보수용 로컬 경로 구조를 전제로 한 부분이 남아 있습니다. Flask 화면만 공유하려면 현재 스냅샷만으로도 충분합니다.
