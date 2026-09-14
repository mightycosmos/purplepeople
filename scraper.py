import requests
from bs4 import BeautifulSoup
import logging
import urllib.parse
from typing import List, Dict

logger = logging.getLogger(__name__)

# 언론사 구글 검색 사이트 매핑
MEDIA_SITES = {
    'left': {
        '한겨레': 'hani.co.kr',
        '경향신문': 'khan.co.kr',
        '오마이뉴스': 'ohmynews.com'
    },
    'right': {
        '조선일보': 'chosun.com',
        '중앙일보': 'joongang.co.kr',
        '동아일보': 'donga.com'
    }
}

def get_article_by_site(keyword: str, site: str, max_articles: int = 1) -> List[Dict[str, str]]:
    """Google News RSS를 통해 특정 사이트에서 키워드 검색 후 최신 기사를 가져옵니다."""
    query = f"{keyword} site:{site}"
    encoded_query = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
    
    articles = []
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'xml')
        
        items = soup.find_all('item')
        for item in items:
            if len(articles) >= max_articles:
                break
                
            title = item.title.text if item.title else ''
            # 구글 뉴스는 title 끝에 " - 언론사명" 이 붙는 경우가 많음
            if " - " in title:
                title = title.rsplit(" - ", 1)[0]
                
            link = item.link.text if item.link else ''
            desc = item.description.text if item.description else title
            
            # HTML 태그 제거
            desc_soup = BeautifulSoup(desc, 'html.parser')
            clean_desc = desc_soup.get_text(separator=' ', strip=True)
            
            articles.append({
                'title': title.strip(),
                'content': clean_desc,
                'link': link
            })
    except Exception as e:
        logger.error(f"Error scraping articles for site {site}: {e}")
        
    return articles

def scrape_news(keyword: str) -> Dict[str, List[Dict[str, str]]]:
    """좌파 및 우파 언론사에서 키워드에 대한 기사를 수집합니다."""
    logger.info(f"Scraping news for keyword: {keyword} using Google News RSS")
    results = {'left': [], 'right': []}
    
    # 좌파 매체 수집
    for media_name, site in MEDIA_SITES['left'].items():
        logger.info(f"Scraping {media_name} (Left)...")
        articles = get_article_by_site(keyword, site, max_articles=1)
        if articles:
            article = articles[0]
            article['media'] = media_name
            results['left'].append(article)
            
    # 우파 매체 수집
    for media_name, site in MEDIA_SITES['right'].items():
        logger.info(f"Scraping {media_name} (Right)...")
        articles = get_article_by_site(keyword, site, max_articles=1)
        if articles:
            article = articles[0]
            article['media'] = media_name
            results['right'].append(article)
            
    return results

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) > 1:
        keyword = sys.argv[1]
        data = scrape_news(keyword)
        for side, side_articles in data.items():
            print(f"--- {side.upper()} ---")
            for a in side_articles:
                print(f"[{a['media']}] {a['title']}\n{a['content'][:100]}...\n")
