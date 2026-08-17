import os
import requests
import logging
import asyncio
from telegram import Bot
from telegram.error import TelegramError

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Конфигурация
NASA_API_KEY = os.getenv('NASA_API_KEY')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHANNEL_ID = os.getenv('TELEGRAM_CHANNEL_ID')

# NASA API endpoints
APOD_URL = 'https://api.nasa.gov/planetary/apod'


def get_apod():
    """Получить Astronomy Picture of the Day"""
    try:
        params = {
            'api_key': NASA_API_KEY
            # Мы убрали 'count': 1, чтобы API возвращал словарь, а не список
        }
        response = requests.get(APOD_URL, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        # Дополнительная защита: если API вдруг вернет список, берем первый элемент
        if isinstance(data, list):
            return data[0]
            
        return data
    except requests.RequestException as e:
        logger.error(f"Ошибка получения APOD: {e}")
        return None


def format_apod_message(data):
    """Форматировать сообщение для APOD"""
    if data.get('media_type') == 'image':
        caption = f"🌌 <b>{data.get('title', 'Без названия')}</b>\n\n"
        caption += f"{data.get('explanation', '')}\n\n"
        caption += f"📅 {data.get('date', '')}"
        
        if 'copyright' in data:
            caption += f"\n© {data.get('copyright')}"
        
        return data.get('url'), caption
    else:
        # Видео или другой тип медиа
        caption = f"🎬 <b>{data.get('title', 'Без названия')}</b>\n\n"
        caption += f"{data.get('explanation', '')}\n\n"
        caption += f"🔗 <a href='{data.get('url', '')}'>Смотреть</a>\n"
        caption += f"📅 {data.get('date', '')}"
        
        return None, caption


async def send_to_telegram(image_url, caption, is_video=False):
    """Отправить сообщение в Telegram"""
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        
        if is_video or image_url is None:
            await bot.send_message(
                chat_id=TELEGRAM_CHANNEL_ID,
                text=caption,
                parse_mode='HTML'
            )
        else:
            await bot.send_photo(
                chat_id=TELEGRAM_CHANNEL_ID,
                photo=image_url,
                caption=caption,
                parse_mode='HTML'
            )
        
        logger.info("✅ Сообщение успешно отправлено в Telegram")
        return True
        
    except TelegramError as e:
        logger.error(f"Ошибка Telegram: {e}")
        return False


def main():
    """Основная функция"""
    logger.info("🚀 Запуск NASA Telegram бота")
    
    if not all([NASA_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID]):
        logger.error("❌ Не все переменные окружения установлены")
        return False
    
    apod_data = get_apod()
    
    if apod_data:
        logger.info(f"📸 Получено APOD: {apod_data.get('title', 'Без названия')}")
        
        image_url, caption = format_apod_message(apod_data)
        is_video = apod_data.get('media_type') == 'video'
        
        success = asyncio.run(send_to_telegram(image_url, caption, is_video))
        
        if success:
            logger.info("✅ APOD успешно отправлен")
            return True
    
    logger.error("❌ Не удалось отправить APOD")
    return False


if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)
