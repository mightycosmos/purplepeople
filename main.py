import argparse
import logging
import sys
import os
from scraper import scrape_news
from llm_processor import generate_script
from image_gen import generate_images
from notifier import send_to_telegram

def main():
    parser = argparse.ArgumentParser(description="Purple People Card News Generator")
    parser.add_argument("keyword", type=str, help="뉴스 검색을 위한 키워드 (예: '부동산', '의료파업')")
    parser.add_argument("--keep-images", action="store_true", help="텔레그램 전송 후 로컬 이미지를 삭제하지 않음")
    args = parser.parse_args()

    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    logger = logging.getLogger("PurplePeople")
    
    logger.info(f"Starting Purple People pipeline for keyword: '{args.keyword}'")
    
    # 1. News Scraper
    logger.info("--- [STEP 1] Scraping News ---")
    news_data = scrape_news(args.keyword)
    if not news_data['left'] and not news_data['right']:
        logger.error("No news found for the given keyword. Aborting.")
        return
    logger.info(f"Found {len(news_data['left'])} left-wing and {len(news_data['right'])} right-wing articles.")
        
    # 2. LLM Processor
    logger.info("--- [STEP 2] Generating Script with LLM ---")
    if not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "your_openai_api_key_here":
        logger.error("OPENAI_API_KEY is missing or invalid. Please check your .env file.")
        return
        
    script = generate_script(args.keyword, news_data)
    if not script or len(script) != 8:
        logger.error(f"Failed to generate correct 8-card script (got {len(script)}). Aborting.")
        return
    logger.info("Successfully generated 8-card script.")
        
    # 3. Image Generator
    logger.info("--- [STEP 3] Generating Images with Playwright ---")
    image_paths = generate_images(script, output_dir="output")
    if len(image_paths) != 8:
        logger.error(f"Failed to generate 8 images (got {len(image_paths)}). Aborting.")
        return
    logger.info("Successfully generated 8 images.")
        
    # 4. Telegram Sender
    logger.info("--- [STEP 4] Sending to Telegram ---")
    send_to_telegram(image_paths, delete_after=not args.keep_images)
    
    logger.info("=== Pipeline completed successfully ===")

if __name__ == "__main__":
    main()
