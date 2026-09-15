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
    body: str = Field(
        description=(
            "줄바꿈 없는 한 문단. 문장 3~5개가 자연스럽게 이어지며 전체 110~130자다. "
            "모든 문장은 '~함', '~됨', '~있음' 같은 명사형으로 끝낸다. 줄을 직접 나누지 않는다."
        )
    )


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
- body: 줄바꿈 없는 한 문단으로 씁니다. 카드에서 줄은 알아서 나뉘므로 직접 끊지 마세요.
  * 공백 포함 110~130자. 문장 3~5개가 모여 하나의 문단이 됩니다.
  * 무슨 일이 있었는지로 시작해 '이로 인해', '그러나', '반면' 같은 연결어로 배경과 반응을 잇고,
    쟁점이나 전망으로 닫습니다. 읽으면 처음부터 끝까지 한 호흡으로 흘러야 합니다.
  * 모든 문장은 명사형 어미로 끝냅니다. '~했다/~된다/~있다'가 아니라 '~했음/~됨/~있음'입니다.
    (발견됐다→발견됐음, 밝혔다→밝힘, 커지고 있다→커지고 있음, 전망이다→전망임)
  * 문장과 문장 사이에는 마침표를 찍고, 맨 마지막 문장 끝에는 마침표를 찍지 않습니다.
  * 짧은 문장을 툭툭 나열하지 마세요. 앞 문장을 받아 다음 문장이 이어지게 씁니다.

  나쁜 예 (짧은 문장이 끊어져 나열되고 '~다'로 끝남)
    "서울 중랑구에서 지적장애 가족이 숨진 채 발견됐다. 이웃도 몰랐다. 복지 사각지대가 드러났다"
  좋은 예 (한 문단으로 이어지고 명사형으로 끝남)
    "서울 중랑구의 한 빌라에서 지적장애를 가진 형제가 숨진 채 발견됐는데, 이웃도 가족도
    몇 달째 이상을 알아채지 못했음. 기초생활수급 신청 이력조차 남아 있지 않아 행정의 손길이
    닿지 않았고, 복지 사각지대를 어떻게 메울지가 다시 과제로 남음"

closing_left / closing_right
- 각 2줄. 그 진영 3개 기사가 오늘 무엇에 무게를 실었는지 요약합니다. 줄당 18~26자.
- 실제 인물명과 사건명을 넣어 구체적으로 씁니다. 줄 끝에 마침표를 찍지 않습니다.
- 본문과 마찬가지로 명사형 어미로 끝냅니다. '주목했다'가 아니라 '주목했음'입니다.
  단 서술어를 빼고 명사만 나열하면 안 됩니다. 반드시 동사에서 온 '~했음', '~임', '~짐'으로 끝냅니다.
  나쁜 예: "메가특구 노동 특례와 사회적 대화" (서술어가 없음)
  좋은 예: "메가특구 노동 특례를 둘러싼 사회적 대화를 다뤘음"
- '좌파 매체는', '우파 언론은' 같은 주어를 쓰지 말고 바로 내용으로 시작합니다.
- 예: "용혜인 사퇴와 교육부 서버 먹통 논란에 주목했음\""""


def _format_side(articles: List[Dict[str, str]]) -> str:
    return "\n\n".join(
        f"({index}) 제목: {article['title']}\n본문:\n{article['content']}"
        for index, article in enumerate(articles, start=1)
    )


def _news_card(card: NewsCard, index: int, side: str) -> Dict[str, Any]:
    return {
        "kind": "news",
        "bg": BLUE if side == "left" else RED,
        "side": "Left" if side == "left" else "Right",
        "index": index,
        "title": card.title,
        "body": card.body.rstrip().rstrip("."),
    }


BODY_MIN = 100
BODY_MAX = 165


def _bad_bodies(script: "Script") -> List[str]:
    """분량이 어긋나거나 직접 줄을 나눈 본문을 모아 재작성을 요청한다."""
    return [
        f"{card.title} ({len(card.body)}자)"
        for card in script.left_cards + script.right_cards
        if not BODY_MIN <= len(card.body) <= BODY_MAX or "\n" in card.body
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
    for attempt in range(3):
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
        bad_bodies = _bad_bodies(script)
        if not bad_bodies:
            break

        logger.info(f"Retrying: {len(bad_bodies)} bodies are off-spec (attempt {attempt + 1})")
        messages += [
            {"role": "assistant", "content": completion.choices[0].message.content},
            {
                "role": "user",
                "content": (
                    f"아래 카드의 body가 규격을 벗어났습니다. body는 줄바꿈 없는 한 문단이고 "
                    f"공백 포함 {BODY_MIN}~{BODY_MAX}자여야 합니다.\n"
                    + "\n".join(f"- {line}" for line in bad_bodies)
                    + "\n\n짧으면 기사 본문에서 배경이나 반응을 더 가져와 채우고, 길면 곁가지를 덜어내세요. "
                    "문장을 토막내 나열하지 말고 연결어로 이어 한 문단으로 흐르게 쓰세요. 전체를 다시 출력하세요."
                ),
            },
        ]

    cards: List[Dict[str, Any]] = [
        {
            "kind": "cover",
            "bg": PURPLE,
            "headline": COVER_HEADLINE,
            "sublines": COVER_SUBLINES,
        }
    ]
    for index, card in enumerate(script.left_cards, start=1):
        cards.append(_news_card(card, index=index, side="left"))
    for index, card in enumerate(script.right_cards, start=1):
        cards.append(_news_card(card, index=index, side="right"))
    cards.append(
        {
            "kind": "closing",
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
