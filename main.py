import os
import requests
import logging
from datetime import datetime
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
EPIC_URL = 'https://api.nasa.gov/EPIC/api/natural'
EPIC_IMAGE_URL = 'https://api.nasa.gov/EPIC/archive/natural'


def get_apod():
    """Получить Astronomy Picture of the Day"""
    try:
        params = {
            'api_key': NASA_API_KEY,
            'count': 1
        }
        response = requests.get(APOD_URL, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Ошибка получения APOD: {e}")
        return None


def get_epic():
    """Получить фото Земли с EPIC камеры"""
    try:
        params = {'api_key': NASA_API_KEY}
        response = requests.get(EPIC_URL, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if data and len(data) > 0:
            # Берём последнее фото
            latest = data[-1]
            date = latest['date'].split(' ')[0].replace('-', '/')
            image_name = latest['image']
            
            # Формируем URL изображения
            image_url = f"{EPIC_IMAGE_URL}/{date}/png/{image_name}.png?api_key={NASA_API_KEY}"
            
            return {
                'url': image_url,
                'title': f"🌍 Земля с расстояния 1.5 млн км",
                'date': latest['date'],
                'explanation': f"Фото сделано камерой EPIC на спутнике DSCOVR.\n\n"
                             f"Дата: {latest['date']}\n"
                             f"Координаты: {latest['centroid_coordinates']}"
            }
        return None
    except requests.RequestException as e:
        logger.error(f"Ошибка получения EPIC: {e}")
        return None


def format_apod_message(data):
    """Форматировать сообщение для APOD"""
    if data['media_type'] == 'image':
        caption = f"🌌 <b>{data['title']}</b>\n\n"
        caption += f"{data['explanation']}\n\n"
        caption += f"📅 {data['date']}"
        
        if 'copyright' in data:
            caption += f"\n© {data['copyright']}"
        
        return data['url'], caption
    else:
        # Видео
        caption = f"🎬 <b>{data['title']}</b>\n\n"
        caption += f"{data['explanation']}\n\n"
        caption += f"🔗 <a href='{data['url']}'>Смотреть видео</a>\n"
        caption += f"📅 {data['date']}"
        
        return None, caption


async def send_to_telegram(image_url, caption, is_video=False):
    """Отправить сообщение в Telegram"""
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        
        if is_video or image_url is None:
            # Отправляем как текст с ссылкой
            await bot.send_message(
                chat_id=TELEGRAM_CHANNEL_ID,
                text=caption,
                parse_mode='HTML'
            )
        else:
            # Отправляем фото
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
    
    # Проверяем переменные окружения
    if not all([NASA_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID]):
        logger.error("❌ Не все переменные окружения установлены")
        return False
    
    # Получаем APOD
    apod_data = get_apod()
    
    if apod_data:
        logger.info(f"📸 Получено APOD: {apod_data.get('title', 'Без названия')}")
        
        # Форматируем сообщение
        image_url, caption = format_apod_message(apod_data)
        is_video = apod_data.get('media_type') == 'video'
        
        # Отправляем в Telegram
        import asyncio
        success = asyncio.run(send_to_telegram(image_url, caption, is_video))
        
        if success:
            logger.info("✅ APOD успешно отправлен")
            return True
    
    logger.error("❌ Не удалось отправить APOD")
    return False


if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)
