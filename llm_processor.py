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

COVER_HEADLINE = "오늘도 당신의 알고리즘은\n반대편 뉴스를 숨겼습니다"
COVER_SUBLINES = [
    "편향의 시대를 향한 평범한 저항",
    "오늘 하루, 좌우 언론의 엇갈린 메인 뉴스를",
    "Purple People이 대조해드립니다",
]
CLOSING_TITLE = "편향이 느껴지시나요?"
CLOSING_FOOTER = "여러분의 생각을 적어주세요"


class NewsCard(BaseModel):
    title: str = Field(description="기사 제목처럼 쓴 우리만의 헤드라인. 언론사명 금지.")
    lines: List[str] = Field(description="본문 5줄.", min_length=5, max_length=5)


class Script(BaseModel):
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

left_cards / right_cards (각 3장, 입력 순서 그대로)
- title: 기사 제목처럼 압축한 우리만의 헤드라인. 12~18자. 마침표 없음.
- lines: 정확히 5줄. 한 줄은 '한 문장'입니다. 한 문장을 여러 줄에 쪼개 담지 마세요.
  * 각 줄은 공백 포함 20~28자입니다. 18자 미만이면 실패로 간주합니다.
  * 각 줄은 반드시 서술어로 끝납니다. 명사나 조사로 끝나면 안 됩니다.
    (…했다 / …된다 / …않다 / …이다 / …지만 / …으며 처럼 끝내세요.)
  * 줄 끝에 마침표를 찍지 않습니다.
  * 5줄을 위에서 아래로 읽으면 하나의 완결된 글이 되어야 합니다.
    1줄은 무슨 일인지, 2~3줄은 '이로 인해', '그러나', '반면' 같은 연결어로 배경과 반응을 잇고,
    4~5줄은 앞을 받아 쟁점이나 전망으로 닫습니다.
  * 같은 말을 되풀이하거나 사실을 뚝뚝 끊어 나열하지 마세요.

  나쁜 예 (한 문장을 세 줄로 쪼갬, 명사로 끝남)
    "김승원 후보자가 동물" / "실험 자료 조작 의혹에" / "문과 출신이라 해명했다"
  좋은 예 (줄마다 한 문장이 끝남)
    "김승원 후보자가 동물실험 자료 조작 의혹에 휩싸였다"
    "그는 문과 출신이라 성능을 알 수 없었다고 해명했다"

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
        "side": "Left" if side == "left" else "Right",
        "title": card.title,
        "lines": card.lines,
    }


def _short_lines(script: "Script") -> List[str]:
    """한 문장을 여러 줄로 쪼개면 줄이 짧아진다. 그런 줄을 모아 재작성을 요청한다."""
    return [
        line
        for card in script.left_cards + script.right_cards
        for line in card.lines
        if len(line) < 18
    ]


def generate_script(news_data: Dict[str, List[Dict[str, str]]]) -> List[Dict[str, Any]]:
    """좌/우 메인 뉴스를 받아 카드뉴스 8장 렌더링 데이터를 만든다."""
    logger.info("Generating script with LLM...")

    user_prompt = (
        f"오늘 날짜: {date.today().isoformat()}\n\n"
        f"[좌파 매체 메인 뉴스]\n{_format_side(news_data['left'])}\n\n"
        f"[우파 매체 메인 뉴스]\n{_format_side(news_data['right'])}"
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    script = None
    for attempt in range(2):
        try:
            completion = client.beta.chat.completions.parse(
                model="gpt-4o-2024-08-06",
                messages=messages,
                response_format=Script,
            )
        except Exception as exc:
            logger.error(f"Error during LLM processing: {exc}")
            return []

        script = completion.choices[0].message.parsed
        short_lines = _short_lines(script)
        if not short_lines:
            break

        logger.info(f"Retrying: {len(short_lines)} lines are too short (attempt {attempt + 1})")
        messages += [
            {"role": "assistant", "content": completion.choices[0].message.content},
            {
                "role": "user",
                "content": (
                    "아래 줄들이 18자 미만이라 한 문장을 여러 줄로 쪼갠 상태입니다:\n"
                    + "\n".join(f"- {line}" for line in short_lines)
                    + "\n\n모든 줄을 20~28자의 완결된 문장으로 다시 써서 전체를 새로 출력하세요."
                ),
            },
        ]

    cards: List[Dict[str, Any]] = [
        {
            "kind": "cover",
            "page": 1,
            "bg": PURPLE,
            "headline": COVER_HEADLINE,
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
