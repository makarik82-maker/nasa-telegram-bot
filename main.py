import os
import requests
import logging
import asyncio
from telegram import Bot
from telegram.error import TelegramError
from deep_translator import GoogleTranslator

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Конфигурация из переменных окружения
NASA_API_KEY = os.getenv('NASA_API_KEY')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHANNEL_ID = os.getenv('TELEGRAM_CHANNEL_ID')

APOD_URL = 'https://api.nasa.gov/planetary/apod'

# Инициализация переводчика
translator = GoogleTranslator(source='en', target='ru')


def translate_text(text, max_length=4500):
    """Перевести текст на русский с защитой от лимитов"""
    if not text:
        return ""
    
    try:
        # Google Translate имеет лимит ~5000 символов за раз
        if len(text) > max_length:
            # Разбиваем на части и переводим по частям
            parts = []
            current_part = ""
            
            for sentence in text.replace('\n', ' ').split('. '):
                if len(current_part) + len(sentence) < max_length:
                    current_part += sentence + '. '
                else:
                    if current_part:
                        parts.append(current_part.strip())
                    current_part = sentence + '. '
            
            if current_part:
                parts.append(current_part.strip())
            
            # Переводим каждую часть
            translated_parts = [translator.translate(part) for part in parts]
            return ' '.join(translated_parts)
        else:
            return translator.translate(text)
            
    except Exception as e:
        logger.warning(f"⚠️ Ошибка перевода: {e}. Используем оригинальный текст.")
        return text


def get_apod():
    """Получить Astronomy Picture of the Day"""
    try:
        params = {'api_key': NASA_API_KEY}
        response = requests.get(APOD_URL, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        # Защита: если API вернет список, берем первый элемент
        if isinstance(data, list):
            return data[0]
        return data
    except requests.RequestException as e:
        logger.error(f"Ошибка получения APOD: {e}")
        return None


def main():
    logger.info("🚀 Запуск NASA Telegram бота (строго фото + перевод)")
    
    # Проверка наличия всех ключей
    if not all([NASA_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID]):
        logger.error("❌ Не все переменные окружения установлены")
        return False
    
    apod_data = get_apod()
    if not apod_data:
        logger.error("❌ Не удалось получить данные APOD")
        return False

    # Строго проверяем, что сегодня именно фотография
    if apod_data.get('media_type') != 'image':
        logger.warning(f"⚠️ Сегодняшний APOD не является фото (тип: {apod_data.get('media_type')}). Пропускаем.")
        return False
    
    # Получаем оригинальные данные
    title_en = apod_data.get('title', 'Без названия')
    explanation_en = apod_data.get('explanation', '')
    date = apod_data.get('date', '')
    image_url = apod_data.get('url')
    copyright_info = apod_data.get('copyright')

    logger.info(f"📸 Получено фото APOD: {title_en}")

    # Переводим на русский
    title_ru = translate_text(title_en)
    explanation_ru = translate_text(explanation_en)

    logger.info(f"🔄 Переведено: {title_ru}")

    # Формируем пост на русском
    caption = f"🌌 <b>{title_ru}</b>\n\n"
    
    # Защита от превышения лимита Telegram (1024 символа для подписи к фото)
    max_len = 900
    if len(explanation_ru) > max_len:
        # Обрезаем по последнему пробелу, чтобы не резать слово
        explanation_ru = explanation_ru[:max_len].rsplit(' ', 1)[0] + "..."
    
    caption += f"{explanation_ru}\n\n"
    caption += f"📅 {date}"
    
    if copyright_info:
        caption += f"\n© {copyright_info}"

    # Отправка в Telegram
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        asyncio.run(bot.send_photo(
            chat_id=TELEGRAM_CHANNEL_ID,
            photo=image_url,
            caption=caption,
            parse_mode='HTML'
        ))
        logger.info("✅ Фото успешно отправлено в Telegram")
        return True
        
    except TelegramError as e:
        logger.error(f"Ошибка Telegram: {e}")
        return False


if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)
