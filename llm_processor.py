import os
import json
import logging
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from openai import OpenAI
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class CardNews(BaseModel):
    bg_color: str = Field(description="Background color for the card: 'purple', 'blue', or 'red'.")
    title: List[str] = Field(description="Core summary title, exactly 2 strings (2 lines).", min_length=2, max_length=2)
    details: List[str] = Field(description="Detailed summary points for the bottom section, 3 to 4 strings.", min_length=3, max_length=4)

class CardNewsList(BaseModel):
    cards: List[CardNews] = Field(description="List of exactly 8 cards.", min_length=8, max_length=8)

def generate_script(keyword: str, news_data: Dict[str, List[Dict[str, str]]]) -> List[Dict[str, Any]]:
    """
    뉴스 데이터를 받아 OpenAI GPT-4o를 이용해 카드뉴스 8장 분량의 스크립트를 생성합니다.
    """
    logger.info("Generating script with LLM...")
    
    # 좌/우파 뉴스 데이터를 프롬프트용 텍스트로 변환
    left_news_text = "\n".join([f"[{n['media']}] {n['title']}: {n['content']}" for n in news_data.get('left', [])])
    right_news_text = "\n".join([f"[{n['media']}] {n['title']}: {n['content']}" for n in news_data.get('right', [])])
    
    system_prompt = f"""
    당신은 전문적인 인스타그램 카드뉴스 에디터입니다.
    오늘의 주제는 '{keyword}'입니다.
    
    제공된 좌파 및 우파 언론 기사를 바탕으로, 반드시 8장의 카드뉴스 스크립트를 작성해야 합니다.
    각 카드는 아래의 규칙을 엄격하게 따라야 합니다.
    
    [카드 구성 규칙]
    Card 1 (bg_color: "purple"): 주제 '{keyword}'에 대한 흥미를 끄는 강렬한 도입부 (후킹 멘트)
    Card 2 (bg_color: "blue"): 좌파 기사 1 요약 및 핵심 논조
    Card 3 (bg_color: "blue"): 좌파 기사 2 요약 및 핵심 논조
    Card 4 (bg_color: "blue"): 좌파 기사 3 요약 및 핵심 논조
    Card 5 (bg_color: "red"): 우파 기사 1 요약 및 핵심 논조
    Card 6 (bg_color: "red"): 우파 기사 2 요약 및 핵심 논조
    Card 7 (bg_color: "red"): 우파 기사 3 요약 및 핵심 논조
    Card 8 (bg_color: "purple"): "여러분의 생각은 어떠신가요?"와 같은 질문 형태의 결론 및 CTA 문구
    
    [데이터 형식 규칙]
    - title: 반드시 두 개의 문자열을 리스트로 반환하여 2줄로 표현될 수 있도록 하세요. 
    - details: 3~4개의 문자열을 리스트로 반환하여 상세 내용을 표현하세요.
    - bg_color: 반드시 "purple", "blue", "red" 중 하나를 사용하세요.
    """
    
    user_prompt = f"""
    [좌파 매체 뉴스]
    {left_news_text}
    
    [우파 매체 뉴스]
    {right_news_text}
    """
    
    try:
        completion = client.beta.chat.completions.parse(
            model="gpt-4o-2024-08-06",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format=CardNewsList,
        )
        
        result = completion.choices[0].message.parsed
        return [card.model_dump() for card in result.cards]
        
    except Exception as e:
        logger.error(f"Error during LLM processing: {e}")
        return []

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    dummy_data = {
        'left': [{'media': '한겨레', 'title': '부동산 가격 폭등, 서민 고통', 'content': '집값이 계속해서 오르며...'}],
        'right': [{'media': '조선일보', 'title': '부동산 규제 완화 필요', 'content': '시장 활성화를 위해...'}]
    }
    script = generate_script("부동산", dummy_data)
    print(json.dumps(script, ensure_ascii=False, indent=2))
