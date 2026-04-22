try:
    import requests
except ModuleNotFoundError:
    requests = None

try:
    from bs4 import BeautifulSoup
except ModuleNotFoundError:
    BeautifulSoup = None

def crawl_infomax_search(query):
    """특정 키워드로 검색해서 최신 뉴스 가져오기"""
    if requests is None or BeautifulSoup is None:
        print(f"[news disabled] missing dependency while searching: {query}")
        return []

    url = f"https://news.einfomax.co.kr/news/articleList.html?sc_area=A&view_type=sm&sc_word={query}"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        articles = soup.select("ul.type2 li")

        results = []
        for art in articles[:5]:
            title_tag = art.select_one("h4.titles a")
            if not title_tag: continue
            results.append({
                "title": title_tag.text.strip(),
                "link": "https://news.einfomax.co.kr" + title_tag['href']
            })
        return results
    except Exception as e:
        print(f"❌ {query} 검색 에러: {e}")
        return []

def get_multiple_keywords_news(keyword_list):
    """여러 키워드를 각각 검색해서 결과를 하나로 합침 (중복 제거)"""
    combined_results = []
    seen_links = set()

    for kw in keyword_list:
        news_list = crawl_infomax_search(kw)
        for news in news_list:
            if news['link'] not in seen_links:
                combined_results.append(news)
                seen_links.add(news['link'])

    return combined_results[:7]
