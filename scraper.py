import json
import logging
import re
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
}

# 각 언론사 메인 뉴스 수집 경로. RSS가 없는 곳은 메인 페이지를 직접 파싱한다.
MEDIA_SOURCES = {
    "left": [
        {"name": "한겨레", "kind": "rss", "url": "https://www.hani.co.kr/rss/"},
        {"name": "경향신문", "kind": "rss", "url": "https://www.khan.co.kr/rss/rssdata/total_news.xml"},
        {"name": "오마이뉴스", "kind": "rss", "url": "https://rss.ohmynews.com/rss/ohmynews.xml"},
    ],
    "right": [
        {
            "name": "조선일보",
            "kind": "rss",
            "url": "https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml",
        },
        {
            "name": "중앙일보",
            "kind": "html",
            "url": "https://www.joongang.co.kr/",
            "link_pattern": r"^https://www\.joongang\.co\.kr/article/\d+$",
        },
        {"name": "동아일보", "kind": "rss", "url": "https://rss.donga.com/total.xml"},
    ],
}

BODY_SELECTORS = [
    "div.article-text",
    "div.text",
    "#articleBody",
    ".art_body",
    ".at_contents",
    "section.article-body",
    '[itemprop="articleBody"]',
    "#article_body",
    ".news_view",
    "#news_body_area",
    "article",
]

NOISE_PATTERNS = [
    r"무단\s*전재",
    r"재배포\s*금지",
    r"저작권자",
    r"기자\s*$",
    r"^\s*\[.*?\]\s*$",
    r"구독하기",
    r"관련기사",
    r"^\s*ⓒ",
]


def _fetch(url: str, timeout: int = 15) -> Optional[requests.Response]:
    try:
        response = requests.get(url, headers=HEADERS, timeout=timeout)
        response.raise_for_status()
        return response
    except Exception as exc:
        logger.warning(f"Fetch failed for {url}: {exc}")
        return None


def _clean_paragraphs(raw_text: str) -> str:
    """기사 본문에서 저작권 고지·기자 서명 등 잡음을 걷어내고 문단으로 다시 묶는다."""
    paragraphs = []
    for line in raw_text.split("\n"):
        line = re.sub(r"\s+", " ", line).strip()
        if len(line) < 20:
            continue
        if any(re.search(pattern, line) for pattern in NOISE_PATTERNS):
            continue
        paragraphs.append(line)
    return "\n".join(paragraphs)


def _extract_fusion_body(html: str) -> str:
    """조선일보 등 Arc Fusion 기반 사이트는 본문이 JS 전역 변수 안에 들어 있다."""
    match = re.search(r"Fusion\.globalContent\s*=\s*(\{.*?\});", html, re.S)
    if not match:
        return ""
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return ""
    texts = [
        BeautifulSoup(element.get("content", ""), "html.parser").get_text(" ", strip=True)
        for element in payload.get("content_elements", [])
        if element.get("type") == "text"
    ]
    return _clean_paragraphs("\n".join(texts))


def extract_article_body(url: str, max_chars: int = 4000) -> str:
    """기사 URL에서 본문 전문을 추출한다."""
    response = _fetch(url)
    if response is None:
        return ""

    fusion_body = _extract_fusion_body(response.text)
    if len(fusion_body) > 200:
        return fusion_body[:max_chars]

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "aside", "nav", "footer", "figcaption"]):
        tag.decompose()

    best = ""
    for selector in BODY_SELECTORS:
        for node in soup.select(selector):
            text = _clean_paragraphs(node.get_text(separator="\n"))
            if len(text) > len(best):
                best = text
        if len(best) > 400:
            break

    if len(best) < 200:
        fallback = "\n".join(p.get_text(separator=" ") for p in soup.find_all("p"))
        candidate = _clean_paragraphs(fallback)
        if len(candidate) > len(best):
            best = candidate

    return best[:max_chars]


# 메인 뉴스로 보기 어려운 연성 기사. 피드 최상단이 스포츠·연예면 다음 기사로 넘어간다.
SOFT_CATEGORIES = (
    "스포츠", "야구", "축구", "골프", "배구", "농구", "연예", "방송", "영화", "음악",
    "문화", "책", "만화", "웹툰", "게임", "여행", "음식", "패션", "사는이야기",
    "칼럼", "사설", "오피니언", "날씨", "포토", "사진",
)
SOFT_URL_PATTERN = re.compile(
    r"(star\.ohmynews|/sports?/|/entertainments?/|/culture/|/life/|/travel/|/photo/|/opinion/)",
    re.IGNORECASE,
)


def _is_hard_news(categories: List[str], link: str) -> bool:
    if SOFT_URL_PATTERN.search(link):
        return False
    return not any(soft in category for category in categories for soft in SOFT_CATEGORIES)


def _dedupe_title(title: str) -> str:
    """메인 페이지 링크는 썸네일용 제목과 본제목이 겹쳐 같은 문장이 두 번 잡힌다."""
    title = re.sub(r"\s+", " ", title).strip()
    half = len(title) // 2
    if len(title) % 2 == 1 and title[half] == " " and title[:half] == title[half + 1 :]:
        return title[:half]
    return title


def _top_link_from_rss(source: Dict[str, str]) -> Optional[Dict[str, str]]:
    response = _fetch(source["url"])
    if response is None:
        return None

    soup = BeautifulSoup(response.content, "xml")
    for item in soup.find_all("item"):
        link = item.link.get_text(strip=True) if item.link else ""
        if not link:
            continue
        categories = [tag.get_text(strip=True) for tag in item.find_all("category")]
        if not _is_hard_news(categories, link):
            continue
        return {"title": item.title.get_text(strip=True) if item.title else "", "link": link}
    return None


def _top_link_from_html(source: Dict[str, str]) -> Optional[Dict[str, str]]:
    response = _fetch(source["url"])
    if response is None:
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    pattern = re.compile(source["link_pattern"])
    for anchor in soup.find_all("a", href=True):
        if not pattern.match(anchor["href"]):
            continue
        title = _dedupe_title(anchor.get_text(separator=" ", strip=True))
        if len(title) < 8:
            continue
        return {"title": title, "link": anchor["href"]}
    return None


def fetch_main_article(source: Dict[str, str]) -> Optional[Dict[str, str]]:
    """한 언론사의 메인 뉴스 한 건을 제목·본문과 함께 가져온다."""
    head = _top_link_from_rss(source) if source["kind"] == "rss" else _top_link_from_html(source)
    if head is None:
        logger.warning(f"No main article found for {source['name']}")
        return None

    body = extract_article_body(head["link"])
    if len(body) < 150:
        logger.warning(f"Body too short for {source['name']} ({len(body)} chars)")

    return {
        "media": source["name"],
        "title": head["title"],
        "link": head["link"],
        "content": body,
    }


def scrape_main_news() -> Dict[str, List[Dict[str, str]]]:
    """좌/우 언론사의 메인 뉴스를 각각 수집한다."""
    results: Dict[str, List[Dict[str, str]]] = {"left": [], "right": []}
    for side, sources in MEDIA_SOURCES.items():
        for source in sources:
            logger.info(f"Fetching main news from {source['name']} ({side})")
            article = fetch_main_article(source)
            if article:
                results[side].append(article)
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    data = scrape_main_news()
    for side, articles in data.items():
        print(f"===== {side.upper()} =====")
        for article in articles:
            print(f"[{article['media']}] {article['title']}")
            print(f"  link: {article['link']}")
            print(f"  body({len(article['content'])}): {article['content'][:200]}...\n")
