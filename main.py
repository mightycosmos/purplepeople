import argparse
import logging
import os
import sys

from dotenv import load_dotenv

from image_gen import generate_images
from llm_processor import generate_script
from notifier import send_to_telegram
from scraper import scrape_main_news


def main():
    parser = argparse.ArgumentParser(description="Purple People Card News Generator")
    parser.add_argument("--keep-images", action="store_true", help="텔레그램 전송 후 로컬 이미지를 삭제하지 않음")
    parser.add_argument("--no-telegram", action="store_true", help="이미지만 생성하고 전송하지 않음")
    args = parser.parse_args()

    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    logger = logging.getLogger("PurplePeople")

    logger.info("Starting Purple People pipeline (main news of each outlet)")

    logger.info("--- [STEP 1] Scraping main news ---")
    news_data = scrape_main_news()
    logger.info(
        f"Collected {len(news_data['left'])} left and {len(news_data['right'])} right main articles."
    )
    if len(news_data["left"]) < 3 or len(news_data["right"]) < 3:
        logger.error("Need 3 main articles per side. Aborting.")
        return

    logger.info("--- [STEP 2] Generating script with LLM ---")
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY is missing. Please check your .env file.")
        return

    script = generate_script(news_data)
    if len(script) != 8:
        logger.error(f"Failed to generate 8-card script (got {len(script)}). Aborting.")
        return

    logger.info("--- [STEP 3] Generating images with Playwright ---")
    image_paths = generate_images(script, output_dir="output")
    if len(image_paths) != 8:
        logger.error(f"Failed to generate 8 images (got {len(image_paths)}). Aborting.")
        return

    if args.no_telegram:
        logger.info("Skipping Telegram delivery (--no-telegram).")
    else:
        logger.info("--- [STEP 4] Sending to Telegram ---")
        send_to_telegram(image_paths, delete_after=not args.keep_images)

    logger.info("=== Pipeline completed successfully ===")


if __name__ == "__main__":
    main()
