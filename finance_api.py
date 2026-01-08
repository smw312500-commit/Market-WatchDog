import requests
import pandas as pd
from datetime import datetime

ECOS_KEY = "WHBQAV87QHCLYN0XIC02"

ECOS_INDICATORS = {
    # 시장 금리
    "KOR_BASE_RATE": {"table": "722Y001", "item_code1": "0101000", "freq_list": ["A", "M", "Q"], "unit_type": "rate",
                      "name": "한국은행 기준금리", "group": "시장금리"},
    "KOR_10Y_BOND": {"table": "102Y002", "item_code1": "010210000", "freq_list": ["A", "M", "Q", "D"],
                     "unit_type": "rate", "name": "국고채(10년)", "group": "시장금리"},
    "KOR_3Y_BOND": {"table": "102Y002", "item_code1": "010200000", "freq_list": ["A", "M", "Q", "D"],
                    "unit_type": "rate", "name": "국고채(3년)", "group": "시장금리"},
    "KOR_CP_91D": {"table": "102Y001", "item_code1": "010502000", "freq_list": ["A", "M", "Q", "D"],
                   "unit_type": "rate", "name": "CP(91일)", "group": "시장금리"},

    # 비은행금융기관 여신
    "TOTAL_NON_BANK": {"table": "111Y009", "item_code1": "1000000", "freq_list": ["A", "M", "Q"], "unit_type": "money", "name": "비은행 여신 합계", "group": "비은행금융기관 여신"},
    "MERCHANT_BANKING": {"table": "111Y009", "item_code1": "1120300", "freq_list": ["A", "M", "Q"], "unit_type": "money", "name": "종합금융회사 여신", "group": "비은행금융기관 여신"},
    "ASSET_MANAGEMENT": {"table": "111Y009", "item_code1": "1120400", "freq_list": ["A", "M", "Q"], "unit_type": "money", "name": "자산운용회사 여신", "group": "비은행금융기관 여신"},
    "TRUST_ACCOUNTS": {"table": "111Y009", "item_code1": "1120500", "freq_list": ["A", "M", "Q"], "unit_type": "money", "name": "신탁회사 여신", "group": "비은행금융기관 여신"},
    "SAVINGS_BANK": {"table": "111Y009", "item_code1": "1120600", "freq_list": ["A", "M", "Q"], "unit_type": "money", "name": "상호저축은행 여신", "group": "비은행금융기관 여신"},
    "CREDIT_UNIONS": {"table": "111Y009", "item_code1": "1120700", "freq_list": ["A", "M", "Q"], "unit_type": "money", "name": "신용협동조합 여신", "group": "비은행금융기관 여신"},
    "MUTUAL_CREDITS": {"table": "111Y009", "item_code1": "1120800", "freq_list": ["A", "M", "Q"], "unit_type": "money", "name": "상호금융 여신", "group": "비은행금융기관 여신"},
    "COMMUNITY_CREDIT_COOP": {"table": "111Y009", "item_code1": "1121000", "freq_list": ["A", "M", "Q"], "unit_type": "money", "name": "새마을금고 여신", "group": "비은행금융기관 여신"},
    "LIFE_INSURANCE": {"table": "111Y009", "item_code1": "1250000", "freq_list": ["A", "M", "Q"], "unit_type": "money", "name": "생명보험 여신", "group": "비은행금융기관 여신"},
    "OTHER_FINANCIAL": {"table": "111Y009", "item_code1": "1290000", "freq_list": ["A", "M", "Q"], "unit_type": "money", "name": "기타 비은행 여신", "group": "비은행금융기관 여신"},
    # (다른 비은행 지표들도 같은 방식으로 'group': '비은행금융기관 여신' 추가)

    # 금융자산부채잔액표
    "FINANCE_CORP_ASSET": {"table": "102Y004", "item_code1": "S12", "item_code2": "0000000", "item_code3": "FA",
                           "freq_list": ["A", "Q"], "unit_type": "money", "name": "금융법인 자산", "group": "금융자산부채잔액표"},
    "FINANCE_CORP_LIAB": {"table": "102Y004", "item_code1": "S12", "item_code2": "0000000", "item_code3": "FL",
                          "freq_list": ["A", "Q"], "unit_type": "money", "name": "금융법인 부채", "group": "금융자산부채잔액표"},
    "NON_FINANCE_CORP_ASSET": {"table": "102Y004", "item_code1": "S11", "item_code2": "0000000", "item_code3": "FA",
                               "freq_list": ["A", "Q"], "unit_type": "money", "name": "비금융법인 자산", "group": "금융자산부채잔액표"},
    "NON_FINANCE_CORP_LIAB": {"table": "102Y004", "item_code1": "S11", "item_code2": "0000000", "item_code3": "FL",
                              "freq_list": ["A", "Q"], "unit_type": "money", "name": "비금융법인 부채", "group": "금융자산부채잔액표"}
}


def get_ecos_data(table_code, item_code1, freq, start_date, end_date, item_code2=None, item_code3=None):
    # 빈 날짜 입력 시 ValueError 방지
    s_date = str(start_date or "20230101").replace('-', '')
    e_date = str(end_date or datetime.now().strftime('%Y%m%d')).replace('-', '')

    try:
        if freq == 'M':
            s_date, e_date = s_date[:6], e_date[:6]
        elif freq == 'Q':
            # 핵심 수정: 숫자 사이에 'Q'를 꼭 넣어야 함! (2024Q1 형식)
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
    except Exception as e:
        print(f"DEBUG 에러: {e}")
        return []