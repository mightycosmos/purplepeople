import logging
import os

from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

CARD_WIDTH = 1080
CARD_HEIGHT = 1350


def generate_images(script: list, output_dir: str = "output") -> list:
    """카드 데이터를 템플릿에 넣고 Playwright로 캡처해 이미지를 만든다."""
    os.makedirs(output_dir, exist_ok=True)

    env = Environment(loader=FileSystemLoader("templates"))
    template = env.get_template("template.html")

    image_paths = []
    logger.info("Starting Playwright for image generation...")
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": CARD_WIDTH, "height": CARD_HEIGHT})

            for index, card in enumerate(script, start=1):
                page.set_content(template.render(**card), wait_until="networkidle")
                page.wait_for_timeout(600)

                output_path = os.path.join(output_dir, f"card_{index}.png")
                page.screenshot(path=output_path)
                image_paths.append(output_path)
                logger.info(f"Generated {output_path}")

            browser.close()
    except Exception as exc:
        logger.error(f"Error generating images: {exc}")

    return image_paths


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    generate_images(
        [
            {
                "kind": "cover",
                "page": 1,
                "bg": "#412C93",
                "headline": "오늘도 당신의 알고리즘은 반대편 뉴스를 숨겼습니다",
                "sublines": ["편향의 시대를 향한 평범한 저항", "오늘 하루, 좌우 언론의", "엇갈린 메인 뉴스를 대조해드립니다"],
            }
        ]
    )
