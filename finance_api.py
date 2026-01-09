

import requests
import pandas as pd
from datetime import datetime
import os
import re

ECOS_KEY = "WHBQAV87QHCLYN0XIC02"
DATA_DIR = r"C:\Users\smw31\PycharmProjects\Market-WatchDog\data"

ECOS_INDICATORS = {
    # [1] 시장 금리
    "MSB_91D": {"table": "721Y001", "item_code1": "6010300", "freq_list": ["A", "M", "Q"], "unit_type": "rate", "name": "통안증권91일", "group": "시장금리"},
    "CORP_BOND_3Y_AA_MINUS": {"table": "721Y001", "item_code1": "7020000", "freq_list": ["A", "M", "Q"], "unit_type": "rate", "name": "회사채(3년, AA-)", "group": "시장금리"},
    "CORP_BOND_3Y_BBB_MINUS": {"table": "721Y001", "item_code1": "7030000", "freq_list": ["A", "M", "Q"], "unit_type": "rate", "name": "회사채(3년, BBB-)", "group": "시장금리"},
    "CORP_BOND_3Y_AA_MINUS_PV": {"table": "721Y001", "item_code1": "8010000", "freq_list": ["A", "M", "Q"], "unit_type": "rate", "name": "회사채(3년, AA- 민평)", "group": "시장금리"},
    "KOR_CP_91D": {"table": "721Y001", "item_code1": "4020000", "freq_list": ["A", "M", "Q"], "unit_type": "rate", "name": "CP(91일)", "group": "시장금리"},

    # [2] 비은행금융기관 여신 (항목 10개 생략 없이 꽉 채움)
    "TOTAL_NON_BANK": {"table": "111Y009", "item_code1": "1000000", "freq_list": ["A", "M", "Q"], "unit_type": "money", "name": "비은행 여신 합계", "group": "비은행금융기관 여신"},
    "SAVINGS_BANK": {"table": "111Y009", "item_code1": "1120600", "freq_list": ["A", "M", "Q"], "unit_type": "money", "name": "상호저축은행 여신", "group": "비은행금융기관 여신"},
    "COMMUNITY_CREDIT_COOP": {"table": "111Y009", "item_code1": "1121000", "freq_list": ["A", "M", "Q"], "unit_type": "money", "name": "새마을금고 여신", "group": "비은행금융기관 여신"},
    "MERCHANT_BANKING": {"table": "111Y009", "item_code1": "1120300", "freq_list": ["A", "M", "Q"], "unit_type": "money", "name": "종합금융회사 여신", "group": "비은행금융기관 여신"},
    "ASSET_MANAGEMENT": {"table": "111Y009", "item_code1": "1120400", "freq_list": ["A", "M", "Q"], "unit_type": "money", "name": "자산운용회사 여신", "group": "비은행금융기관 여신"},
    "TRUST_ACCOUNTS": {"table": "111Y009", "item_code1": "1120500", "freq_list": ["A", "M", "Q"], "unit_type": "money", "name": "신탁회사 여신", "group": "비은행금융기관 여신"},
    "CREDIT_UNIONS": {"table": "111Y009", "item_code1": "1120700", "freq_list": ["A", "M", "Q"], "unit_type": "money", "name": "신용협동조합 여신", "group": "비은행금융기관 여신"},
    "MUTUAL_CREDITS": {"table": "111Y009", "item_code1": "1120800", "freq_list": ["A", "M", "Q"], "unit_type": "money", "name": "상호금융 여신", "group": "비은행금융기관 여신"},
    "LIFE_INSURANCE": {"table": "111Y009", "item_code1": "1250000", "freq_list": ["A", "M", "Q"], "unit_type": "money", "name": "생명보험 여신", "group": "비은행금융기관 여신"},
    "OTHER_FINANCIAL": {"table": "111Y009", "item_code1": "1290000", "freq_list": ["A", "M", "Q"], "unit_type": "money", "name": "기타 비은행 여신", "group": "비은행금융기관 여신"},

    # [3] 금융자산부채잔액표 (형이 준 CP/유동화 코드로 완전 세분화)
    "FIN_CP_ASSET": {"table": "281Y002", "item_code1": "S12", "item_code2": "F043SZB", "item_code3": "A", "freq_list": ["A", "Q"], "unit_type": "money", "name": "금융법인 CP자산", "group": "금융자산부채잔액표"},
    "FIN_CP_LIAB": {"table": "281Y002", "item_code1": "S12", "item_code2": "F043SZB", "item_code3": "L", "freq_list": ["A", "Q"], "unit_type": "money", "name": "금융법인 CP부채", "group": "금융자산부채잔액표"},
    "FIN_ABS_ASSET": {"table": "281Y002", "item_code1": "S12", "item_code2": "F046SZB", "item_code3": "A", "freq_list": ["A", "Q"], "unit_type": "money", "name": "금융법인 유동화자산", "group": "금융자산부채잔액표"},
    "FIN_ABS_LIAB": {"table": "281Y002", "item_code1": "S12", "item_code2": "F046SZB", "item_code3": "L", "freq_list": ["A", "Q"], "unit_type": "money", "name": "금융법인 유동화부채", "group": "금융자산부채잔액표"},
    "NON_FIN_CP_ASSET": {"table": "281Y002", "item_code1": "S11", "item_code2": "F043SZB", "item_code3": "A", "freq_list": ["A", "Q"], "unit_type": "money", "name": "비금융법인 CP자산", "group": "금융자산부채잔액표"},
    "NON_FIN_CP_LIAB": {"table": "281Y002", "item_code1": "S11", "item_code2": "F043SZB", "item_code3": "L", "freq_list": ["A", "Q"], "unit_type": "money", "name": "비금융법인 CP부채", "group": "금융자산부채잔액표"},
    "NON_FIN_ABS_ASSET": {"table": "281Y002", "item_code1": "S11", "item_code2": "F046SZB", "item_code3": "A", "freq_list": ["A", "Q"], "unit_type": "money", "name": "비금융법인 유동화자산", "group": "금융자산부채잔액표"},
    "NON_FIN_ABS_LIAB": {"table": "281Y002", "item_code1": "S11", "item_code2": "F046SZB", "item_code3": "L", "freq_list": ["A", "Q"], "unit_type": "money", "name": "비금융법인 유동화부채", "group": "금융자산부채잔액표"},

    # [4] cp발행실적,만기별,단기사채 지표
# 1. cp만기별 발행현황 (6개)
    "LOC_TENOR_3M": {"source": "LOCAL", "file": "CP만기별 발행현황.xlsx", "item": "3개월이하", "name": "CP만기(3M이하)", "group": "cp만기별 발행현황", "unit_type": "money"},
    "LOC_TENOR_6M": {"source": "LOCAL", "file": "CP만기별 발행현황.xlsx", "item": "3~6개월이하", "name": "CP만기(3~6M)", "group": "cp만기별 발행현황", "unit_type": "money"},
    "LOC_TENOR_9M": {"source": "LOCAL", "file": "CP만기별 발행현황.xlsx", "item": "6~9개월이하", "name": "CP만기(6~9M)", "group": "cp만기별 발행현황", "unit_type": "money"},
    "LOC_TENOR_12M": {"source": "LOCAL", "file": "CP만기별 발행현황.xlsx", "item": "9~12개월 미만", "name": "CP만기(9~12M)", "group": "cp만기별 발행현황", "unit_type": "money"},
    "LOC_TENOR_1Y": {"source": "LOCAL", "file": "CP만기별 발행현황.xlsx", "item": "1년 이상", "name": "CP만기(1Y이상)", "group": "cp만기별 발행현황", "unit_type": "money"},
    "LOC_TENOR_TOTAL": {"source": "LOCAL", "file": "CP만기별 발행현황.xlsx", "item": "총합계", "name": "CP만기 총합계", "group": "cp만기별 발행현황", "unit_type": "money"},

    # 2. cp발행실적 (4개)
    "LOC_CP_ABCP": {"source": "LOCAL", "file": "CP발행실적.xlsx", "item": "ABCP", "name": "ABCP 발행", "group": "cp발행실적", "unit_type": "money"},
    "LOC_CP_PF": {"source": "LOCAL", "file": "CP발행실적.xlsx", "item": "PF ABCP", "name": "PF ABCP 발행", "group": "cp발행실적", "unit_type": "money"},
    "LOC_CP_GEN": {"source": "LOCAL", "file": "CP발행실적.xlsx", "item": "일반CP", "name": "일반CP 발행", "group": "cp발행실적", "unit_type": "money"},
    "LOC_CP_TOTAL": {"source": "LOCAL", "file": "CP발행실적.xlsx", "item": "총합계", "name": "CP 총발행", "group": "cp발행실적", "unit_type": "money"},

    # 3. 단기사채발행실적 (4개)
    "LOC_ST_AB": {"source": "LOCAL", "file": "단기사채 발행실적.xlsx", "item": "AB단기사채", "name": "AB단기사채 발행", "group": "단기사채발행실적", "unit_type": "money"},
    "LOC_ST_PF": {"source": "LOCAL", "file": "단기사채 발행실적.xlsx", "item": "PF단기사채", "name": "PF단기사채 발행", "group": "단기사채발행실적", "unit_type": "money"},
    "LOC_ST_GEN": {"source": "LOCAL", "file": "단기사채 발행실적.xlsx", "item": "일반단기사채", "name": "일반단기사채 발행", "group": "단기사채발행실적", "unit_type": "money"},
    "LOC_ST_TOTAL": {"source": "LOCAL", "file": "단기사채 발행실적.xlsx", "item": "총합계", "name": "단기사채 총발행", "group": "단기사채발행실적", "unit_type": "money"}
}


def get_ecos_data(table_code, item_code1, freq, start_date, end_date, item_code2=None, item_code3=None):
    s_date = str(start_date or "20150101").replace('-', '')
    e_date = str(end_date or datetime.now().strftime('%Y%m%d')).replace('-', '')
    try:
        if freq == 'A':
            s_date, e_date = s_date[:4], e_date[:4]
        elif freq == 'M':
            s_date, e_date = s_date[:6], e_date[:6]
        elif freq == 'Q':
            s_month = int(s_date[4:6]) if len(s_date) >= 6 else 1
            e_month = int(e_date[4:6]) if len(e_date) >= 6 else 12
            s_date, e_date = f"{s_date[:4]}Q{(s_month - 1) // 3 + 1}", f"{e_date[:4]}Q{(e_month - 1) // 3 + 1}"

        path_elements = [item_code1]
        if item_code2: path_elements.append(item_code2)
        if item_code3: path_elements.append(item_code3)
        item_path = "/".join(path_elements)

        url = f"http://ecos.bok.or.kr/api/StatisticSearch/{ECOS_KEY}/json/kr/1/100/{table_code}/{freq}/{s_date}/{e_date}/{item_path}/"
        res = requests.get(url)
        data = res.json()
        return data['StatisticSearch']['row'] if 'StatisticSearch' in data else []
    except:
        return []


def get_local_data(config, freq):
    file_path = os.path.join(DATA_DIR, config['file'])
    if not os.path.exists(file_path):
        print(f"엑셀 파일 못 찾음: {file_path}")
        return []

    try:
        # [수정] read_csv가 아니라 read_excel을 사용!
        # 형이 준 파일은 첫 줄이 제목이라 skiprows=1 사용
        df = pd.read_excel(file_path, skiprows=1, engine='openpyxl')

        target_row = df[df['항목'] == config['item']]
        if target_row.empty: return []

        data_list = []
        for col in df.columns:
            # "2024년 03월" 같은 날짜 패턴 찾기
            match = re.search(r'(\d{4})년\s*(\d{2})월', str(col))
            if match:
                year, month = match.group(1), match.group(2)
                val = target_row[col].values[0]

                if pd.isna(val) or val == '': continue

                # 주기(M, Q, A)에 따라 타임스탬프 변환
                if freq == 'M':
                    t_key = f"{year}{month}"
                elif freq == 'Q':
                    t_key = f"{year}Q{(int(month) - 1) // 3 + 1}"
                else:
                    t_key = year

                # 엑셀은 숫자에 콤마(,)가 있어도 숫자로 잘 인식하지만, 안전하게 처리
                data_list.append({"TIME": t_key, "DATA_VALUE": float(val)})

        if not data_list: return []

        # 중복된 날짜 합산 (분기/연별 처리용)
        res_df = pd.DataFrame(data_list).groupby('TIME')['DATA_VALUE'].sum().reset_index()
        return res_df.to_dict('records')

    except Exception as e:
        print(f"엑셀 로딩 중 에러 발생: {e}")
        return []