import os
import logging
from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

def generate_images(script: list, output_dir: str = 'output') -> list:
    """
    Jinja2를 이용해 템플릿에 데이터를 주입하고 Playwright로 캡처하여 이미지를 생성합니다.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Jinja2 환경 설정
    env = Environment(loader=FileSystemLoader('templates'))
    try:
        template = env.get_template('template.html')
    except Exception as e:
        logger.error(f"Error loading template: {e}")
        return []
        
    image_paths = []
    
    logger.info("Starting Playwright for image generation...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1080, 'height': 1080})
            
            for idx, card in enumerate(script):
                # Card 2~4(Left), Card 5~7(Right)
                side = ''
                if card.get('card_type', 'news') == 'news':
                    side = 'Left' if 1 <= idx <= 3 else 'Right' if 4 <= idx <= 6 else ''

                # HTML 렌더링
                html_content = template.render(
                    bg_color=card.get('bg_color', 'light'),
                    card_type=card.get('card_type', 'news'),
                    content=card.get('content', ''),
                    media=card.get('media', ''),
                    title=card.get('title', ''),
                    desc=card.get('desc', ''),
                    side=side,
                    page=idx + 1
                )
                
                # 페이지 로드 및 스크린샷 캡처
                # networkidle 이벤트를 기다려 외부 리소스(폰트, CSS)가 로드되도록 함
                page.set_content(html_content, wait_until='networkidle')
                
                # 추가로 폰트 렌더링을 위해 약간의 대기
                page.wait_for_timeout(1000)
                
                output_path = os.path.join(output_dir, f"card_{idx+1}.png")
                page.screenshot(path=output_path)
                image_paths.append(output_path)
                
                logger.info(f"Generated {output_path}")
                
            browser.close()
    except Exception as e:
        logger.error(f"Error generating images: {e}")
        
    return image_paths

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    dummy_script = [
        {
            "bg_color": "black",
            "card_type": "cover",
            "content": "대통령 지지율 급락, 도대체 왜?"
        }
    ]
    generate_images(dummy_script)
