r"""
세이브로 잔액 크롤러
- 월말일 하나만 조회 - 월 잔액
- 종목별 4개: 어음(일반)/어음AB/일반단기사채/AB단기사채
- 저장: legacy data2\{종류}\{년월}.csv
- 조회 후 40초 대기
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
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
#===============시작일 종료일===========================
BASE_SAVE_DIR = r"E:\PROJECT\Market-WatchDog\legacy data2"
CRAWL_START   = date(2026, 1, 1)
CRAWL_END     = date(2026, 3, 31)
WAIT_SEARCH   = 40
WAIT_PAGE     = 10

URL = "https://seibro.or.kr/websquare/control.jsp?w2xPath=/IPORTAL/user/moneyMarke/BIP_CNTS04004V.xml&menuNo=126"

CATEGORIES = [
    {"name": "어음(일반)",   "radio_id": "SF_RADIO1_input_0", "folder": "cp"},
    {"name": "어음AB",       "radio_id": "SF_RADIO1_input_1", "folder": "abcp"},
    {"name": "일반단기사채", "radio_id": "SF_RADIO1_input_2", "folder": "일반단기사채"},
    {"name": "AB단기사채",   "radio_id": "SF_RADIO1_input_3", "folder": "ab단기사채"},
]

CAL_IMG_ID   = "inputCalendar1_img"
CAL_YR_ID    = "inputCalendar1_calendar_selectbox_year"
CAL_MO_ID    = "inputCalendar1_calendar_selectbox_month"
CAL_INPUT_ID = "inputCalendar1_input"
SEARCH_ID    = "image36"
EXCEL_ID     = "ExcelDownload_img"


def month_last_weekday(year, month):
    _, last = calendar.monthrange(year, month)
    d = date(year, month, last)
    while d.weekday() > 4:
        d = d - relativedelta(days=1)
    return d

def file_label(year, month):
    return f"{str(year)[2:]}년{month}월"

def get_all_months():
    months = []
    cur = CRAWL_START
    while cur <= CRAWL_END:
        months.append((cur.year, cur.month))
        cur += relativedelta(months=1)
    return months

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
    opts.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
    svc = Service(ChromeDriverManager().install())
    drv = webdriver.Chrome(service=svc, options=opts)
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

def scan_existing(folder):
    existing = set()
    root = os.path.join(BASE_SAVE_DIR, folder)
    if not os.path.exists(root):
        return existing
    for f in os.listdir(root):
        if f.endswith('.csv'):
            existing.add(os.path.splitext(f)[0])
    return existing

def xls_to_csv(xls_path, csv_path):
    try:
        try:
            df = pd.read_excel(xls_path, header=0, engine='xlrd')
        except Exception:
            df = pd.read_excel(xls_path, header=0, engine='openpyxl')
        df.to_csv(csv_path, index=False, encoding='utf-8-sig')
        os.remove(xls_path)
        return True
    except Exception:
        pass
    try:
        dfs = pd.read_html(xls_path, encoding='cp949')
        if dfs:
            dfs[0].to_csv(csv_path, index=False, encoding='utf-8-sig')
            os.remove(xls_path)
            return True
    except Exception as e:
        print(f"      CSV 변환 실패: {e}")
    return False

def wait_rename_convert(download_dir, label, timeout=90):
    print(f"      다운로드 대기 중...")
    start = time.time()
    while time.time() - start < timeout:
        files = os.listdir(download_dir)
        tmp  = [f for f in files if f.endswith('.crdownload') or f.endswith('.tmp')]
        done = [f for f in files if f.endswith(('.xls', '.xlsx')) and not f.startswith(label)]
        if done and not tmp:
            latest  = max([os.path.join(download_dir, f) for f in done], key=os.path.getmtime)
            ext     = os.path.splitext(latest)[1]
            xls_dst = os.path.join(download_dir, label + ext)
            csv_dst = os.path.join(download_dir, label + '.csv')
            if os.path.exists(xls_dst):
                os.remove(xls_dst)
            os.rename(latest, xls_dst)
            if xls_to_csv(xls_dst, csv_dst):
                print(f"      저장: {csv_dst}")
                return True
            else:
                print(f"      xls 저장됨 (csv 변환 실패): {xls_dst}")
                return True
        time.sleep(1)
    print(f"      다운로드 타임아웃: {label}")
    return False

def input_date(driver, wait, target_date):
    year  = target_date.year
    month = target_date.month
    day   = target_date.day
    try:
        cal_img = wait.until(EC.element_to_be_clickable((By.ID, CAL_IMG_ID)))
        driver.execute_script("arguments[0].click();", cal_img)
        time.sleep(0.8)

        yr_sel = wait.until(EC.presence_of_element_located((By.ID, CAL_YR_ID)))
        Select(yr_sel).select_by_value(f"{year} ")
        time.sleep(0.5)

        mo_sel = driver.find_element(By.ID, CAL_MO_ID)
        Select(mo_sel).select_by_value(f"{month} ")
        time.sleep(0.5)

        day_cell = wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, f"#inputCalendar1_calendar .w2calendar_date_on.w2calendar_date_{day}")
        ))
        driver.execute_script("arguments[0].click();", day_cell)
        time.sleep(0.5)

        input_el = driver.find_element(By.ID, CAL_INPUT_ID)
        actual = input_el.get_attribute('value')
        print(f"      날짜 -> 목표:{year}/{month:02d}/{day:02d} / 실제:{actual}")
        return True
    except Exception as e:
        print(f"      날짜 입력 실패: {e}")
        return False

def select_category(driver, wait, radio_id):
    try:
        radio = wait.until(EC.presence_of_element_located((By.ID, radio_id)))
        driver.execute_script("arguments[0].click();", radio)
        time.sleep(0.5)
        return True
    except Exception as e:
        print(f"      종목 선택 실패 ({radio_id}): {e}")
        return False

def crawl_one(driver, cat, target_date, save_dir, label):
    if not is_alive(driver):
        return False

    wait = WebDriverWait(driver, 25)
    print(f"      [{label}] {cat['name']} / {target_date}")

    try:
        driver.get(URL)
        time.sleep(WAIT_PAGE)

        if not select_category(driver, wait, cat["radio_id"]):
            return False

        if not input_date(driver, wait, target_date):
            return False

        search_btn = wait.until(EC.element_to_be_clickable((By.ID, SEARCH_ID)))
        driver.execute_script("arguments[0].click();", search_btn)
        print(f"      조회 중... ({WAIT_SEARCH}초 대기)")
        time.sleep(WAIT_SEARCH)

        excel_btn = wait.until(EC.element_to_be_clickable((By.ID, EXCEL_ID)))
        driver.execute_script("arguments[0].click();", excel_btn)

        return wait_rename_convert(save_dir, label)

    except Exception as e:
        print(f"      오류 ({label}): {e}")
        return False

def crawl_category(cat):
    print(f"\n{'='*60}")
    print(f"  [{cat['name']}] 수집 시작")
    print(f"{'='*60}")

    save_dir = os.path.join(BASE_SAVE_DIR, cat["folder"])
    os.makedirs(save_dir, exist_ok=True)
    existing = scan_existing(cat["folder"])
    months   = get_all_months()
    driver   = None
    ok = skip = fail = 0

    for year, month in months:
        if date(year, month, 1) > CRAWL_END:
            break

        lbl         = file_label(year, month)
        target_date = month_last_weekday(year, month)

        if target_date > CRAWL_END:
            target_date = CRAWL_END

        if lbl in existing:
            skip += 1
            continue

        if driver is None or not is_alive(driver):
            print(f"\n  브라우저 시작")
            driver = make_driver(save_dir)

        result = crawl_one(driver, cat, target_date, save_dir, lbl)

        if result:
            existing.add(lbl)
            ok += 1
        else:
            fail += 1
            try: driver.quit()
            except: pass
            driver = None
            time.sleep(5)

        time.sleep(2)

    if driver:
        try: driver.quit()
        except: pass

    print(f"\n  [{cat['name']}] 완료 - 수집:{ok} / 스킵:{skip} / 실패:{fail}")

def main():
    print("=" * 60)
    print("  세이브로 잔액 크롤러")
    print(f"  저장 경로 : {BASE_SAVE_DIR}")
    print(f"  수집 범위 : {CRAWL_START.strftime('%Y.%m')} ~ {CRAWL_END.strftime('%Y.%m')}")
    print(f"  조회 대기 : {WAIT_SEARCH}초")
    print(f"  저장 형식 : CSV (월말 기준)")
    print("=" * 60)

    for cat in CATEGORIES:
        crawl_category(cat)

    print("\n전체 잔액 수집 완료!")

if __name__ == "__main__":
    main()