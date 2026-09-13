import os
import logging
import asyncio
from telegram import Bot, InputMediaPhoto
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

async def send_media_group_async(image_paths: list, delete_after: bool = True):
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id or token == "your_telegram_bot_token_here":
        logger.error("Telegram credentials missing or invalid in .env")
        return
        
    bot = Bot(token=token)
    media_group = []
    
    try:
        # 사진 데이터를 읽어서 InputMediaPhoto 리스트 생성
        for path in image_paths:
            if os.path.exists(path):
                with open(path, 'rb') as f:
                    media_group.append(InputMediaPhoto(media=f.read()))
            else:
                logger.warning(f"File not found: {path}")
                
        if not media_group:
            logger.error("No valid images to send.")
            return

        logger.info(f"Sending {len(media_group)} images to Telegram...")
        await bot.send_media_group(chat_id=chat_id, media=media_group)
        logger.info("Successfully sent images to Telegram.")
        
    except Exception as e:
        logger.error(f"Error sending to Telegram: {e}")
        
    finally:
        if delete_after:
            for path in image_paths:
                if os.path.exists(path):
                    os.remove(path)
                    logger.info(f"Deleted {path}")
            
            # output 디렉토리가 비어있으면 삭제 (선택적)
            output_dir = os.path.dirname(image_paths[0]) if image_paths else None
            if output_dir and os.path.exists(output_dir) and not os.listdir(output_dir):
                os.rmdir(output_dir)
                logger.info(f"Removed empty directory: {output_dir}")

def send_to_telegram(image_paths: list, delete_after: bool = True):
    """
    동기 코드에서 호출하기 위한 래퍼 함수
    """
    asyncio.run(send_media_group_async(image_paths, delete_after))

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # 테스트용
    # send_to_telegram(["output/card_1.png"], delete_after=False)
