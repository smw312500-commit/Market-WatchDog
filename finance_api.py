import requests
import pandas as pd

ECOS_KEY = "WHBQAV87QHCLYN0XIC02"

ECOS_INDICATORS = {
    # 1. 시장금리 (721Y001 - 월, 분기, 연)
    "cp_91d": {"table": "721Y001", "item": "4020000", "freq_list": ["A", "M", "Q"], "name": "CP(91일) 금리"},
    "MSB": {"table": "721Y001", "item": "6010300", "freq_list": ["A", "M", "Q"], "name": "통안증권(91일)"},
    "corp_bond_aa": {"table": "721Y001", "item": "7020000", "freq_list": ["A", "M", "Q"], "name": "회사채(3년, AA-)"},
    "corp_bond_bbb": {"table": "721Y001", "item": "7030000", "freq_list": ["A", "M", "Q"], "name": "회사채(3년, BBB-)"},
    "corp_bond_aa_private": {"table": "721Y001", "item": "8010000", "freq_list": ["A", "M", "Q"], "name": "회사채(3년, AA-, 민평)"},

    # 2. 비은행금융기관 여신 (005Y003 - 월, 분기, 연)
    "loan_savings_bank": {"table": "005Y003", "item": "0000001", "freq_list": ["A", "M", "Q"], "name": "상호저축은행 여신"},
    "loan_credit_coop": {"table": "005Y003", "item": "0000002", "freq_list": ["A", "M", "Q"], "name": "신용협동조합 여신"},
    "loan_mutual_credit": {"table": "005Y003", "item": "0000003", "freq_list": ["A", "M", "Q"], "name": "상호금융 여신"},
    "loan_community_credit": {"table": "005Y003", "item": "0000004", "freq_list": ["A", "M", "Q"], "name": "새마을금고 여신"},

    # 3. 비은행금융기관 자산 (141Y007 - 월, 분기, 연)
    "asset_savings_bank": {"table": "141Y007", "item": "0520", "freq_list": ["A", "M", "Q"], "name": "상호저축은행 자산"},
    "asset_merchant_bank": {"table": "141Y007", "item": "0920", "freq_list": ["A", "M", "Q"], "name": "종합금융회사 자산"},
    "asset_credit_coop": {"table": "141Y007", "item": "1120", "freq_list": ["A", "M", "Q"], "name": "신용협동기구 자산"},
    "asset_mutual_credit": {"table": "141Y007", "item": "1220", "freq_list": ["A", "M", "Q"], "name": "상호금융 자산"},
    "asset_community_credit": {"table": "141Y007", "item": "1320", "freq_list": ["A", "M", "Q"], "name": "새마을금고 자산"},
    "asset_credit_card": {"table": "141Y007", "item": "1420", "freq_list": ["A", "M", "Q"], "name": "신용카드회사 자산"},
    "asset_installment_fin": {"table": "141Y007", "item": "1520", "freq_list": ["A", "M", "Q"], "name": "할부금융회사 자산"},
    "asset_leasing": {"table": "141Y007", "item": "1620", "freq_list": ["A", "M", "Q"], "name": "리스회사 자산"},
    "asset_venture_cap": {"table": "141Y007", "item": "1720", "freq_list": ["A", "M", "Q"], "name": "신기술사업금융회사 자산"},
    "asset_life_ins": {"table": "141Y007", "item": "2120", "freq_list": ["A", "M", "Q"], "name": "생명보험회사 자산"},
    "asset_nonlife_ins": {"table": "141Y007", "item": "2220", "freq_list": ["A", "M", "Q"], "name": "손해보험회사 자산"},
    "asset_post_ins": {"table": "141Y007", "item": "2320", "freq_list": ["A", "M", "Q"], "name": "우체국보험 자산"},
    "asset_securities": {"table": "141Y007", "item": "3120", "freq_list": ["A", "M", "Q"], "name": "증권회사 자산"},
    "asset_management": {"table": "141Y007", "item": "3320", "freq_list": ["A", "M", "Q"], "name": "자산운용회사 자산"},

    # 4. 금융자산부채잔액표 (041Y001 - 분기, 연)
    "cp_asset_finance": {
        "table": "041Y001", "item": "1040000", "item2": "1030200", "item3": "1",
        "freq_list": ["A", "Q"], "name": "금융법인 CP(자산)"
    },
    "cp_debt_corp": {
        "table": "041Y001", "item": "1020000", "item2": "1030200", "item3": "2",
        "freq_list": ["A", "Q"], "name": "비금융법인 CP(부채)"
    },
    "household_asset": {
        "table": "041Y001", "item": "1010000", "freq_list": ["A", "Q"], "name": "가계 및 비영리단체 금융자산"
    },
    "household_debt": {
        "table": "041Y001", "item": "2010000", "freq_list": ["A", "Q"], "name": "가계 및 비영리단체 금융부채"
    }
}


def get_ecos_data_by_id(indicator_id, freq, start_date, end_date):
    info = ECOS_INDICATORS[indicator_id]

    # 아이템 코드 조합 (item2, item3이 있으면 붙여줌)
    item_path = info['item']
    if 'item2' in info: item_path += f"/{info['item2']}"
    if 'item3' in info: item_path += f"/{info['item3']}"

    # ... 기존 날짜 처리 로직 동일 ...

def get_ecos_data(table_code, item_code1, freq, start_date, end_date):
    s_date = start_date.replace('-', '')
    e_date = end_date.replace('-', '')

    if freq == 'M':
        s_date, e_date = s_date[:6], e_date[:6]
    elif freq == 'Q':
        s_month = int(s_date[4:6])
        e_month = int(e_date[4:6])
        s_date = f"{s_date[:4]}{(s_month - 1) // 3 + 1}"
        e_date = f"{e_date[:4]}{(e_month - 1) // 3 + 1}"

    url = f"http://ecos.bok.or.kr/api/StatisticSearch/{ECOS_KEY}/json/kr/1/100/{table_code}/{freq}/{s_date}/{e_date}/{item_code1}/"

    # [진단] 요청하는 URL을 터미널에 출력
    print(f"DEBUG: 요청 URL -> {url}")

    try:
        res = requests.get(url)
        data = res.json()

        if 'StatisticSearch' in data:
            rows = data['StatisticSearch']['row']
            print(f"DEBUG: 데이터 가져오기 성공! ({len(rows)}건)")
            df = pd.DataFrame(rows)
            df['DATA_VALUE'] = pd.to_numeric(df['DATA_VALUE'])
            return df[['TIME', 'DATA_VALUE']].to_dict(orient='records')
        else:
            # [진단] 에러가 났을 때 한은이 뭐라고 하는지 출력
            print(f"DEBUG: 한은 응답 에러 -> {data}")
            return []
    except Exception as e:
        print(f"DEBUG: 시스템 에러 -> {e}")
        return []