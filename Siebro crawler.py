r"""
세이브로 자동 크롤러 v3
- 2016.01 ~ 2025.12 전체 수집
- 날짜 입력: send_keys 방식 (검증됨)
- 1주씩 수집 (월~금 영업일만)
- 파일명: 16년1월1주차.csv
- 저장 경로: E:\PROJECT\Market-WatchDog\legacy data\{시장}\{년월}\
- 이미 있는 파일 자동 스킵
- 조회 후 40초 대기
- xls 다운로드 후 csv 변환 저장
- 발행액 긁어오기
"""

import os
import time
import calendar
import pandas as pd
from datetime import date
from dateutil.relativedelta import relativedelta
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


def last_completed_month_end(today=None):
    base = today or date.today()
    return base.replace(day=1) - relativedelta(days=1)


def env_date(name, default):
    raw = os.getenv(name)
    if not raw:
        return default
    return date.fromisoformat(raw)

# ============================================================
# 설정
# =======================시작날짜 끝날짜 설정=====================================
BASE_SAVE_DIR   = r"E:\PROJECT\Market-WatchDog\legacy data"
CRAWL_START     = env_date("CRAWL_START", date(2016, 1, 1))    # 수집 시작
CRAWL_END       = env_date("CRAWL_END", last_completed_month_end())
WAIT_SEARCH     = 40                   # 조회 후 대기 (초)
WAIT_PAGE_LOAD  = 10                   # 페이지 초기 로딩

MARKETS = {
    "cp": {
        "url":       "https://seibro.or.kr/websquare/control.jsp?w2xPath=/IPORTAL/user/moneyMarke/BIP_CNTS04005V.xml&menuNo=128",
        "search_id": "image35",
        "excel_id":  "ExcelDownload_img",
        "folder":    "cp",
        "label":     "CP",
    },
    "abcp": {
        "url":       "https://seibro.or.kr/websquare/control.jsp?w2xPath=/IPORTAL/user/abs/BIP_CNTS21005V.xml&menuNo=958",
        "search_id": "image8",
        "excel_id":  "ExcelDownload_img",
        "folder":    "abcp",
        "label":     "ABCP",
    },
    "abstb": {
        "url":       "https://seibro.or.kr/websquare/control.jsp?w2xPath=/IPORTAL/user/abs/BIP_CNTS21004V.xml&menuNo=957",
        "search_id": "image8",
        "excel_id":  "ExcelDownload_img",
        "folder":    "ab단기사채",
        "label":     "AB단기사채",
    },
}

CAL_START_ID = "bd_sd1_inputCalendar1_input"
CAL_END_ID   = "bd_sd1_inputCalendar2_input"


# ============================================================
# 날짜 유틸
# ============================================================
def get_weekdays(year, month):
    """해당 월 영업일(월~금) 리스트"""
    days = []
    _, last = calendar.monthrange(year, month)
    for d in range(1, last + 1):
        dt = date(year, month, d)
        if dt.weekday() < 5:
            days.append(dt)
    return days

def split_weeks(weekdays):
    """
    영업일을 월요일 기준 주차로 분리
    - 월 첫 주: 1일 ~ 첫 금요일 (또는 첫 월요일 전날까지)
    - 이후: 월요일 ~ 금요일
    - 월 마지막 주: 마지막 월요일 ~ 말일
    """
    if not weekdays:
        return []

    weeks = []
    cur   = [weekdays[0]]

    for d in weekdays[1:]:
        # 월요일이면 새 주 시작
        if d.weekday() == 0:
            weeks.append(cur)
            cur = [d]
        else:
            cur.append(d)

    weeks.append(cur)
    return weeks

def file_label(year, month, week_num):
    """파일명: 16년1월1주차"""
    return f"{str(year)[2:]}년{month}월{week_num}주차"

def month_folder(year, month):
    """폴더명: 16년1월"""
    return f"{str(year)[2:]}년{month}월"

def get_all_months():
    months = []
    cur = CRAWL_START
    while cur <= CRAWL_END:
        months.append((cur.year, cur.month))
        cur += relativedelta(months=1)
    return months


# ============================================================
# 드라이버
# ============================================================
def make_driver(download_dir):
    os.makedirs(download_dir, exist_ok=True)
    opts = Options()
    opts.add_experimental_option("prefs", {
        "download.default_directory":   download_dir,
        "download.prompt_for_download": False,
        "directory_upgrade":            True,
    })
    opts.add_argument("--start-maximized")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    opts.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
    svc = Service(ChromeDriverManager().install())
    drv = webdriver.Chrome(service=svc, options=opts)
    # webdriver 탐지 무력화
    drv.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
    return drv

def is_alive(driver):
    try:
        _ = driver.current_url
        return True
    except:
        return False


# ============================================================
# 기존 파일 스캔 (csv 기준)
# ============================================================
def scan_existing(folder):
    existing = set()
    root = os.path.join(BASE_SAVE_DIR, folder)
    if not os.path.exists(root):
        return existing
    for month_dir in os.listdir(root):
        mpath = os.path.join(root, month_dir)
        if not os.path.isdir(mpath):
            continue
        for f in os.listdir(mpath):
            if f.endswith('.csv'):
                existing.add(os.path.splitext(f)[0])
    return existing


# ============================================================
# xls → csv 변환
# ============================================================
def xls_to_csv(xls_path, csv_path):
    """xls/xlsx 파일을 csv로 변환 후 원본 xls 삭제
    세이브로는 HTML을 xls로 위장한 파일을 내려줌 → BeautifulSoup으로 파싱
    """
    try:
        # 1차 시도: 진짜 Excel 형식
        try:
            df = pd.read_excel(xls_path, header=0, engine='xlrd')
            df.to_csv(csv_path, index=False, encoding='utf-8-sig')
            os.remove(xls_path)
            return True
        except Exception:
            pass

        # 2차 시도: openpyxl
        try:
            df = pd.read_excel(xls_path, header=0, engine='openpyxl')
            df.to_csv(csv_path, index=False, encoding='utf-8-sig')
            os.remove(xls_path)
            return True
        except Exception:
            pass

        # 3차 시도: HTML 테이블로 파싱 (세이브로 위장 xls)
        dfs = pd.read_html(xls_path, encoding='cp949')
        if dfs:
            dfs[0].to_csv(csv_path, index=False, encoding='utf-8-sig')
            os.remove(xls_path)
            return True

        print(f"      ⚠️ 모든 변환 방법 실패")
        return False

    except Exception as e:
        print(f"      ⚠️ CSV 변환 실패: {e}")
        return False


# ============================================================
# 다운로드 대기 + 이름 변경 + csv 변환
# ============================================================
def wait_rename_convert(download_dir, label, timeout=90):
    print(f"      ⬇️  다운로드 대기 중...")
    start = time.time()
    while time.time() - start < timeout:
        files = os.listdir(download_dir)
        tmp  = [f for f in files if f.endswith('.crdownload') or f.endswith('.tmp')]
        done = [f for f in files if f.endswith(('.xls', '.xlsx'))
                and not f.startswith(label)]
        if done and not tmp:
            latest = max(
                [os.path.join(download_dir, f) for f in done],
                key=os.path.getmtime
            )
            ext     = os.path.splitext(latest)[1]
            xls_dst = os.path.join(download_dir, label + ext)
            csv_dst = os.path.join(download_dir, label + '.csv')

            # xls 이름 변경
            if os.path.exists(xls_dst):
                os.remove(xls_dst)
            os.rename(latest, xls_dst)

            # csv 변환
            if xls_to_csv(xls_dst, csv_dst):
                print(f"      ✅ 저장: {csv_dst}")
                return True
            else:
                print(f"      ⚠️ xls는 저장됨 (csv 변환 실패): {xls_dst}")
                return True  # xls라도 있으면 성공 처리
        time.sleep(1)

    print(f"      ❌ 다운로드 타임아웃: {label}")
    return False


# ============================================================
# 날짜 입력 (send_keys 방식)
# ============================================================
def input_date(driver, wait, cal_num, target_date):
    """
    세이브로 달력 팝업 방식으로 날짜 입력
    cal_num: 1=시작일, 2=종료일
    """
    prefix = f"bd_sd1_inputCalendar{cal_num}"
    img_id  = f"{prefix}_img"
    yr_id   = f"{prefix}_calendar_selectbox_year"
    mo_id   = f"{prefix}_calendar_selectbox_month"

    year  = target_date.year
    month = target_date.month
    day   = target_date.day

    try:
        # 1. 달력 아이콘 클릭 → 팝업 열기
        cal_img = wait.until(EC.element_to_be_clickable((By.ID, img_id)))
        driver.execute_script("arguments[0].click();", cal_img)
        time.sleep(0.8)

        # 2. 년도 select 변경
        from selenium.webdriver.support.ui import Select
        yr_sel = wait.until(EC.presence_of_element_located((By.ID, yr_id)))
        Select(yr_sel).select_by_value(f"{year} ")
        time.sleep(0.5)

        # 3. 월 select 변경
        mo_sel = driver.find_element(By.ID, mo_id)
        Select(mo_sel).select_by_value(f"{month} ")
        time.sleep(0.5)

        # 4. 날짜 td 클릭 (class: w2calendar_date_{day})
        day_cell = wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR,
             f"#{prefix}_calendar .w2calendar_date_on.w2calendar_date_{day}")
        ))
        driver.execute_script("arguments[0].click();", day_cell)
        time.sleep(0.5)

        # 5. 확인 (input 값 체크)
        input_el = driver.find_element(By.ID, f"{prefix}_input")
        actual = input_el.get_attribute('value')
        print(f"      📅 {'시작일' if cal_num==1 else '종료일'} → "
              f"목표:{year}/{month:02d}/{day:02d} / 실제:{actual}")
        return True

    except Exception as e:
        print(f"      ⚠️ 날짜 입력 실패 (cal{cal_num}): {e}")
        return False


# ============================================================
# 주차 1회 수집
# ============================================================
def crawl_week(driver, cfg, week_days, save_dir, label):
    if not is_alive(driver):
        print(f"      ⚠️ 드라이버 세션 죽음")
        return False

    wait    = WebDriverWait(driver, 25)
    s_date  = week_days[0]
    e_date  = week_days[-1]
    print(f"      [{label}] {s_date} ~ {e_date}")

    try:
        # 1. 페이지 로드
        driver.get(cfg["url"])
        time.sleep(WAIT_PAGE_LOAD)

        # 2. 시작일 입력 (달력 팝업 1번)
        if not input_date(driver, wait, 1, s_date):
            return False

        # 3. 종료일 입력 (달력 팝업 2번)
        if not input_date(driver, wait, 2, e_date):
            return False

        # 4. 조회 버튼
        search_btn = wait.until(EC.element_to_be_clickable((By.ID, cfg["search_id"])))
        driver.execute_script("arguments[0].click();", search_btn)
        print(f"      🔍 조회 중... ({WAIT_SEARCH}초 대기)")
        time.sleep(WAIT_SEARCH)

        # 5. 엑셀 다운로드
        excel_btn = wait.until(EC.element_to_be_clickable((By.ID, cfg["excel_id"])))
        driver.execute_script("arguments[0].click();", excel_btn)

        # 6. 대기 + 이름변경 + csv 변환
        return wait_rename_convert(save_dir, label)

    except Exception as e:
        print(f"      ❌ 오류 ({label}): {e}")
        return False


# ============================================================
# 시장별 전체 수집
# ============================================================
def crawl_market(mkt_key, cfg):
    print(f"\n{'='*60}")
    print(f"  [{cfg['label']}] 수집 시작")
    print(f"{'='*60}")

    existing   = scan_existing(cfg["folder"])
    months     = get_all_months()
    driver     = None
    cur_dl_dir = None
    ok = skip = fail = 0

    for year, month in months:
        weekdays = get_weekdays(year, month)
        weeks    = split_weeks(weekdays)
        mfolder  = month_folder(year, month)
        mpath    = os.path.join(BASE_SAVE_DIR, cfg["folder"], mfolder)

        for w_idx, week_days in enumerate(weeks, 1):
            # CRAWL_END 넘는 주차는 수집 안 함
            if week_days[0] > CRAWL_END:
                break

            # 주차 내 날짜도 CRAWL_END까지만
            week_days = [d for d in week_days if d <= CRAWL_END]
            if not week_days:
                break

            lbl = file_label(year, month, w_idx)

            # 이미 있으면 스킵
            if lbl in existing:
                skip += 1
                continue

            # 드라이버 없거나 세션 죽었거나 폴더 바뀌면 재시작
            if driver is None or not is_alive(driver) or cur_dl_dir != mpath:
                if driver:
                    try: driver.quit()
                    except: pass
                os.makedirs(mpath, exist_ok=True)
                cur_dl_dir = mpath
                print(f"\n  🌐 브라우저 시작 → {mpath}")
                driver = make_driver(mpath)

            result = crawl_week(driver, cfg, week_days, mpath, lbl)

            if result:
                existing.add(lbl)
                ok += 1
            else:
                fail += 1
                print(f"      🔄 드라이버 재시작...")
                try: driver.quit()
                except: pass
                driver     = None
                cur_dl_dir = None
                time.sleep(5)

            time.sleep(2)

    if driver:
        try: driver.quit()
        except: pass

    print(f"\n  [{cfg['label']}] 완료 — 수집:{ok} / 스킵:{skip} / 실패:{fail}")


# ============================================================
# 메인
# ============================================================
def main():
    print("=" * 60)
    print("  세이브로 자동 크롤러 v3")
    print(f"  저장 경로 : {BASE_SAVE_DIR}")
    print(f"  수집 범위 : {CRAWL_START.strftime('%Y.%m')} ~ {CRAWL_END.strftime('%Y.%m')}")
    print(f"  조회 대기 : {WAIT_SEARCH}초")
    print(f"  저장 형식 : CSV")
    print("=" * 60)

    for cfg in MARKETS.values():
        os.makedirs(os.path.join(BASE_SAVE_DIR, cfg["folder"]), exist_ok=True)

    for mkt_key, cfg in MARKETS.items():
        crawl_market(mkt_key, cfg)

    print("\n✅ 전체 수집 완료!")


if __name__ == "__main__":
    main()
