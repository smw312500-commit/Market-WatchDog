import requests
import pandas as pd
from datetime import datetime

# API 키는 형이 발급받은 걸로 바꿔 끼워야 돼
ECOS_KEY = "WHBQAV87QHCLYN0XIC02"
FISIS_KEY = "1318ad6d5fc0e2fc8d8ede90da6e39f7"


def get_ecos_data(table_code, item_code1, start_date, end_date, freq='D'):
    """한국은행 ECOS 데이터 호출 함수"""
    url = f"http://ecos.bok.or.kr/api/StatisticSearch/{ECOS_KEY}/json/kr/1/100/{table_code}/{freq}/{start_date}/{end_date}/{item_code1}/"

    try:
        res = requests.get(url)
        data = res.json()
        if 'StatisticSearch' in data:
            rows = data['StatisticSearch']['row']
            df = pd.DataFrame(rows)
            # 수치 데이터는 숫자로 변환
            df['DATA_VALUE'] = pd.to_numeric(df['DATA_VALUE'])
            return df[['TIME', 'DATA_VALUE']].to_dict(orient='records')
        return []
    except Exception as e:
        print(f"ECOS Error: {e}")
        return []


def get_fisis_data(item_code, start_date, end_date):
    """금감원 FISIS 데이터 호출 (예시 구조)"""
    # FISIS는 API 구조가 조금 더 까다로우니 실제 문서의 URL 구조를 확인해야 돼
    # 아래는 일반적인 JSON 호출 예시야
    url = f"https://fisis.fss.or.kr/openapi/statisticsSearch.json?lang=kr&auth={FISIS_KEY}&itemId={item_code}&startTerm={start_date}&endTerm={end_date}"

    try:
        res = requests.get(url)
        data = res.json()
        # FISIS 데이터 구조에 맞춰서 파싱 (실제 호출 후 구조 확인 필요)
        if 'result' in data:
            return data['result']['list']
        return []
    except Exception as e:
        print(f"FISIS Error: {e}")
        return []


def get_market_watch_indicators():
    """형이 요청한 지표들 한꺼번에 모아서 정리"""
    today = datetime.now().strftime('%Y%m%d')
    three_months_ago = "20230101"  # 테스트용으로 일단 길게 잡음

    indicators = {
        # 1. 시장금리 (예: 국고채 3년, CP 91일물)
        "market_rates": get_ecos_data("028Y001", "010200000", three_months_ago, today),  # 국고채 3년
        "cp_rates": get_ecos_data("028Y001", "010300000", three_months_ago, today),  # CP 91일

        # 2. 비은행금융기관 여신 (예: 저축은행 대출금)
        "non_bank_loans": get_ecos_data("005Y003", "0000001", "202301", "202312", "M"),  # 월간 데이터

        # 3. 금융자산부채잔액 (분기 데이터)
        "fin_assets": get_ecos_data("041Y001", "1010000", "20231", "20234", "Q")
    }

    return indicators