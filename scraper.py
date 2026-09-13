import requests
from bs4 import BeautifulSoup
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

# 언론사 OID 매핑
MEDIA_OIDS = {
    'left': {
        '한겨레': '028',
        '경향신문': '032',
        '오마이뉴스': '047'
    },
    'right': {
        '조선일보': '023',
        '중앙일보': '025',
        '동아일보': '020'
    }
}

def get_articles_by_oid(keyword: str, oid: str, max_articles: int = 3) -> List[Dict[str, str]]:
    """특정 언론사(oid)에서 키워드로 최신 기사를 검색하고 제목/본문을 가져옵니다."""
    url = f"https://search.naver.com/search.naver?where=news&query={keyword}&pd=1&sort=1&ds=&de=&nso=so:dd,p:1w,a:all&mynews=1&office_type=1&office_section_code=1&news_office_checked={oid}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    articles = []
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 네이버 뉴스 검색 결과 리스트
        news_items = soup.select('.news_area')
        
        for item in news_items:
            if len(articles) >= max_articles:
                break
                
            title_tag = item.select_one('.news_tit')
            desc_tag = item.select_one('.api_txt_lines.dsc_txt_wrap')
            
            if title_tag and desc_tag:
                title = title_tag.get('title') or title_tag.text
                desc = desc_tag.text
                link = title_tag.get('href')
                
                articles.append({
                    'title': title.strip(),
                    'content': desc.strip(),
                    'link': link
                })
                
    except Exception as e:
        logger.error(f"Error scraping articles for oid {oid}: {e}")
        
    return articles

def scrape_news(keyword: str) -> Dict[str, List[Dict[str, str]]]:
    """좌파 및 우파 언론사에서 키워드에 대한 기사를 수집합니다."""
    logger.info(f"Scraping news for keyword: {keyword}")
    results = {'left': [], 'right': []}
    
    # 좌파 매체 수집
    for media_name, oid in MEDIA_OIDS['left'].items():
        logger.info(f"Scraping {media_name} (Left)...")
        articles = get_articles_by_oid(keyword, oid, max_articles=1)
        if articles:
            article = articles[0]
            article['media'] = media_name
            results['left'].append(article)
            
    # 우파 매체 수집
    for media_name, oid in MEDIA_OIDS['right'].items():
        logger.info(f"Scraping {media_name} (Right)...")
        articles = get_articles_by_oid(keyword, oid, max_articles=1)
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
                print(f"[{a['media']}] {a['title']}\n{a['content']}\n")
