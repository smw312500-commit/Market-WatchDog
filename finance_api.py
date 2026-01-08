# finance_api.py 전체 덮어쓰기!

import requests
import pandas as pd
from datetime import datetime

ECOS_KEY = "WHBQAV87QHCLYN0XIC02"

ECOS_INDICATORS = {
    # [1] 시장 금리
    "KOR_BASE_RATE": {"table": "722Y001", "item_code1": "0101000", "freq_list": ["A", "M", "Q"], "unit_type": "rate", "name": "한국은행 기준금리", "group": "시장금리"},
    "CORP_BOND_3Y_AA_MINUS": {"table": "721Y002", "item_code1": "7020000", "freq_list": ["A", "M", "Q"], "unit_type": "rate", "name": "회사채(3년, AA-)", "group": "시장금리"},
    "CORP_BOND_3Y_BBB_MINUS": {"table": "721Y002", "item_code1": "7030000", "freq_list": ["A", "M", "Q"], "unit_type": "rate", "name": "회사채(3년, BBB-)", "group": "시장금리"},
    "CORP_BOND_3Y_AA_MINUS_PV": {"table": "721Y002", "item_code1": "8010000", "freq_list": ["A", "M", "Q"], "unit_type": "rate", "name": "회사채(3년, AA- 민평)", "group": "시장금리"},
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
    "NON_FIN_ABS_LIAB": {"table": "281Y002", "item_code1": "S11", "item_code2": "F046SZB", "item_code3": "L", "freq_list": ["A", "Q"], "unit_type": "money", "name": "비금융법인 유동화부채", "group": "금융자산부채잔액표"}
}

def get_ecos_data(table_code, item_code1, freq, start_date, end_date, item_code2=None, item_code3=None):
    s_date = str(start_date or "20150101").replace('-', '')
    e_date = str(end_date or datetime.now().strftime('%Y%m%d')).replace('-', '')
    try:
        if freq == 'Q':
            s_month = int(s_date[4:6]) if len(s_date) >= 6 else 1
            e_month = int(e_date[4:6]) if len(e_date) >= 6 else 12
            s_date = f"{s_date[:4]}Q{(s_month - 1) // 3 + 1}"
            e_date = f"{e_date[:4]}Q{(e_month - 1) // 3 + 1}"
        item_path = item_code1
        if item_code2: item_path += f"/{item_code2}"
        if item_code3: item_path += f"/{item_code3}"
        url = f"http://ecos.bok.or.kr/api/StatisticSearch/{ECOS_KEY}/json/kr/1/100/{table_code}/{freq}/{s_date}/{e_date}/{item_path}/"
        res = requests.get(url)
        data = res.json()
        if 'StatisticSearch' in data:
            return data['StatisticSearch']['row']
        return []
    except: return []