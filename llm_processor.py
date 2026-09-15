import json
import logging
import os
from datetime import date
from typing import Any, Dict, List

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

PURPLE = "#412C93"
BLUE = "#1A3A8C"
RED = "#9B1B21"

COVER_SUBLINES = [
    "편향의 시대를 향한 평범한 저항",
    "오늘 하루, 좌우 언론의",
    "엇갈린 메인 뉴스를 대조해드립니다",
]
CLOSING_TITLE = "편향이 느껴지시나요?"
CLOSING_FOOTER = "여러분의 생각을 적어주세요"


class NewsCard(BaseModel):
    title: str = Field(description="기사 제목처럼 쓴 우리만의 헤드라인. 언론사명 금지.")
    lines: List[str] = Field(description="본문 5줄.", min_length=5, max_length=5)


class Script(BaseModel):
    cover_headline: str = Field(description="표지 후킹 문구.")
    left_cards: List[NewsCard] = Field(min_length=3, max_length=3)
    right_cards: List[NewsCard] = Field(min_length=3, max_length=3)
    closing_left: List[str] = Field(description="좌측 매체들이 오늘 무엇에 주목했는지 2줄.", min_length=2, max_length=2)
    closing_right: List[str] = Field(description="우측 매체들이 오늘 무엇에 주목했는지 2줄.", min_length=2, max_length=2)


SYSTEM_PROMPT = """당신은 시사 카드뉴스 'Purple People'의 에디터입니다.
좌파 성향 매체 3곳과 우파 성향 매체 3곳이 오늘 메인에 올린 기사를 그대로 받았습니다.
검색 키워드는 없습니다. 각 진영이 오늘 무엇을 앞세웠는지 나란히 보여주는 것이 목적입니다.

절대 규칙
- 언론사 이름을 어디에도 쓰지 마세요. 카드에는 매체명이 드러나지 않습니다.
- 원 기사 제목을 그대로 베끼지 마세요. 같은 사실을 우리 말로 다시 쓴 헤드라인을 만듭니다.
- 좌우 어느 쪽도 편들지 말고, 해당 기사가 실제로 말한 내용만 씁니다. 없는 사실을 지어내지 마세요.

cover_headline
- 오늘 양 진영 메인 뉴스를 관통하는 한 줄 후킹 문구. 20~26자.
- 예: "오늘도 당신의 알고리즘은 반대편 뉴스를 숨겼습니다"

left_cards / right_cards (각 3장, 입력 순서 그대로)
- title: 기사 제목처럼 압축한 우리만의 헤드라인. 12~18자. 마침표 없음.
- lines: 정확히 5줄.
  * 각 줄은 14~22자의 짧은 문장이며 줄 끝에 마침표를 찍지 않습니다.
  * 5줄을 위에서 아래로 읽으면 하나의 완결된 글이 되어야 합니다.
    1줄은 무슨 일인지, 2~3줄은 '이로 인해', '그러나', '반면' 같은 연결어로 배경과 반응을 잇고,
    4~5줄은 앞을 받아 쟁점이나 전망으로 닫습니다.
  * 같은 말을 되풀이하거나 사실을 뚝뚝 끊어 나열하지 마세요.

closing_left / closing_right
- 각 2줄. 그 진영 3개 기사가 오늘 무엇에 무게를 실었는지 요약합니다. 줄당 18~26자.
- 실제 인물명과 사건명을 넣어 구체적으로 씁니다. 줄 끝에 마침표를 찍지 않습니다.
- '좌파 매체는', '우파 언론은' 같은 주어를 쓰지 말고 바로 내용으로 시작합니다.
- 예: "용혜인 사퇴와 교육부 서버 먹통 논란에 주목했다\""""


def _format_side(articles: List[Dict[str, str]]) -> str:
    return "\n\n".join(
        f"({index}) 제목: {article['title']}\n본문:\n{article['content']}"
        for index, article in enumerate(articles, start=1)
    )


def _news_card(card: NewsCard, page: int, side: str) -> Dict[str, Any]:
    return {
        "kind": "news",
        "page": page,
        "bg": BLUE if side == "left" else RED,
        "title": card.title,
        "lines": card.lines,
    }


def generate_script(news_data: Dict[str, List[Dict[str, str]]]) -> List[Dict[str, Any]]:
    """좌/우 메인 뉴스를 받아 카드뉴스 8장 렌더링 데이터를 만든다."""
    logger.info("Generating script with LLM...")

    user_prompt = (
        f"오늘 날짜: {date.today().isoformat()}\n\n"
        f"[좌파 매체 메인 뉴스]\n{_format_side(news_data['left'])}\n\n"
        f"[우파 매체 메인 뉴스]\n{_format_side(news_data['right'])}"
    )

    try:
        completion = client.beta.chat.completions.parse(
            model="gpt-4o-2024-08-06",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format=Script,
        )
    except Exception as exc:
        logger.error(f"Error during LLM processing: {exc}")
        return []

    script = completion.choices[0].message.parsed

    cards: List[Dict[str, Any]] = [
        {
            "kind": "cover",
            "page": 1,
            "bg": PURPLE,
            "headline": script.cover_headline,
            "sublines": COVER_SUBLINES,
        }
    ]
    for offset, card in enumerate(script.left_cards):
        cards.append(_news_card(card, page=2 + offset, side="left"))
    for offset, card in enumerate(script.right_cards):
        cards.append(_news_card(card, page=5 + offset, side="right"))
    cards.append(
        {
            "kind": "closing",
            "page": 8,
            "bg": PURPLE,
            "title": CLOSING_TITLE,
            "left_lines": script.closing_left,
            "right_lines": script.closing_right,
            "footer": CLOSING_FOOTER,
        }
    )
    return cards


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from scraper import scrape_main_news

    print(json.dumps(generate_script(scrape_main_news()), ensure_ascii=False, indent=2))
