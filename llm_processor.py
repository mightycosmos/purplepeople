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

CLOSING_TEXT = "편향이 느껴지시나요?\n여러분의 생각을 적어주세요"


class CardNews(BaseModel):
    bg_color: str = Field(description="Background color: 'black', 'light', or 'purple'.")
    card_type: str = Field(description="Type of card: 'cover', 'news', or 'closing'.")
    content: str = Field(default="", description="Text for cover or closing card.")
    media: str = Field(default="", description="Name of the media outlet.")
    title: str = Field(default="", description="Headline shown on the card.")
    desc: str = Field(default="", description="Body copy that reads as one connected paragraph.")


class CardNewsList(BaseModel):
    cards: List[CardNews] = Field(description="Exactly 8 cards.", min_length=8, max_length=8)


SYSTEM_PROMPT = """당신은 시사 카드뉴스 에디터입니다.
오늘 좌파 성향 매체 3곳과 우파 성향 매체 3곳의 '메인 뉴스'를 그대로 받았습니다.
검색 키워드는 없습니다. 각 매체가 오늘 무엇을 가장 앞세웠는지를 그대로 보여주는 것이 목적입니다.

반드시 8장을 만듭니다.
Card 1 (bg_color "black", card_type "cover"): content에 오늘 양쪽 메인 뉴스를 관통하는 한 줄 후킹 문구. 25자 이내.
Card 2~4 (bg_color "light", card_type "news"): 좌파 매체 3건을 입력된 순서 그대로.
Card 5~7 (bg_color "light", card_type "news"): 우파 매체 3건을 입력된 순서 그대로.
Card 8 (bg_color "purple", card_type "closing"): 고정 문구이므로 비워 두어도 됩니다.

뉴스 카드 작성 규칙
- media: 입력에 주어진 매체명을 그대로 씁니다.
- title: 원 기사 제목을 카드에서 읽기 좋게 다듬되 사실을 바꾸지 않습니다. 35자 이내.
- desc: 가장 중요합니다. 아래를 지키세요.
  * 기사 본문을 읽고 3~4개 문장으로 다시 씁니다. 분량은 공백 포함 150~200자.
  * 개별 사실을 나열해 "~했다. ~했다."로 끊어 붙이지 마세요.
  * 첫 문장은 무슨 일인지, 가운데 문장은 '그 배경에는', '이에 대해', '다만' 같은 연결어로 이유나 반응을 잇고,
    마지막 문장은 앞 내용을 받아 의미나 전망으로 닫습니다.
  * 처음부터 끝까지 하나의 완결된 문단으로 읽혀야 하며, 문장이 중간에 잘리면 안 됩니다.
  * 본문에 없는 사실을 지어내지 마세요. 본문이 짧으면 있는 내용만으로 짧은 문단을 완성하세요.
- 좌/우 어느 쪽도 편들지 말고, 해당 매체가 쓴 논조를 그대로 전달하세요."""


def _format_side(articles: List[Dict[str, str]]) -> str:
    blocks = []
    for index, article in enumerate(articles, start=1):
        blocks.append(
            f"({index}) 매체: {article['media']}\n"
            f"제목: {article['title']}\n"
            f"본문:\n{article['content']}"
        )
    return "\n\n".join(blocks) if blocks else "(수집된 기사 없음)"


def generate_script(news_data: Dict[str, List[Dict[str, str]]]) -> List[Dict[str, Any]]:
    """좌/우 메인 뉴스를 받아 카드뉴스 8장 스크립트를 생성한다."""
    logger.info("Generating script with LLM...")

    user_prompt = (
        f"오늘 날짜: {date.today().isoformat()}\n\n"
        f"[좌파 매체 메인 뉴스]\n{_format_side(news_data.get('left', []))}\n\n"
        f"[우파 매체 메인 뉴스]\n{_format_side(news_data.get('right', []))}"
    )

    try:
        completion = client.beta.chat.completions.parse(
            model="gpt-4o-2024-08-06",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format=CardNewsList,
        )
    except Exception as exc:
        logger.error(f"Error during LLM processing: {exc}")
        return []

    cards = [card.model_dump() for card in completion.choices[0].message.parsed.cards]
    cards[-1] = {
        "bg_color": "purple",
        "card_type": "closing",
        "content": CLOSING_TEXT,
        "media": "",
        "title": "",
        "desc": "",
    }
    return cards


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from scraper import scrape_main_news

    print(json.dumps(generate_script(scrape_main_news()), ensure_ascii=False, indent=2))
