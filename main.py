import os
import requests
import logging
import asyncio
import time
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

# 🌍 Инициализация переводчика (английский -> русский)
translator = GoogleTranslator(source='en', target='ru')


def translate_text(text, max_length=4500):
    """Перевести текст на русский с защитой от лимитов API"""
    if not text:
        return ""
    
    try:
        if len(text) > max_length:
            # Если текст очень длинный, разбиваем его на части
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
            
            # Переводим каждую часть и соединяем
            translated_parts = [translator.translate(part) for part in parts]
            return ' '.join(translated_parts)
        else:
            # Обычный перевод
            return translator.translate(text)
            
    except Exception as e:
        logger.warning(f"⚠️ Ошибка перевода: {e}. Используем оригинальный текст.")
        return text


def get_apod_with_retry(max_retries=3, delay=5):
    """Получить APOD с механизмом повторных попыток при сбоях сети или 503 ошибке"""
    for attempt in range(max_retries):
        try:
            logger.info(f"🔄 Попытка {attempt + 1} из {max_retries} получить данные APOD...")
            params = {'api_key': NASA_API_KEY}
            
            # Увеличенный таймаут 60 секунд
            response = requests.get(APOD_URL, params=params, timeout=60)
            response.raise_for_status()
            data = response.json()
            
            if isinstance(data, list):
                return data[0]
            return data
            
        except requests.exceptions.Timeout:
            logger.warning(f"⏱️ Таймаут. Ждем {delay} секунд...")
            time.sleep(delay)
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Ошибка сети или сервера NASA: {e}")
            time.sleep(delay)
            
    logger.error("❌ Не удалось получить данные APOD после всех попыток.")
    return None


def main():
    logger.info("🚀 Запуск NASA Telegram бота (строго фото + перевод)")
    
    if not all([NASA_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID]):
        logger.error("❌ Не все переменные окружения установлены")
        return False
    
    apod_data = get_apod_with_retry()
    if not apod_data:
        logger.warning("⚠️ Не удалось получить данные APOD. Возможно, сервер NASA временно недоступен.")
        return False  # Вернем False, но в конце скрипта это обработается как мягкий выход

    # Проверяем, что сегодня именно фотография
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

    # 🌍 ПЕРЕВОД НА РУССКИЙ ЯЗЫК
    title_ru = translate_text(title_en)
    explanation_ru = translate_text(explanation_en)
    logger.info(f"✅ Перевод выполнен: {title_ru}")

    # Формируем пост на русском
    caption = f"🌌 <b>{title_ru}</b>\n\n"
    
    # Защита от превышения лимита Telegram (1024 символа для подписи к фото)
    max_len = 900
    if len(explanation_ru) > max_len:
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
    if success:
        exit(0)
    else:
        # Возвращаем 0 (успех), чтобы GitHub Actions не помечал день красным крестиком, 
        # если NASA просто недоступен. Это нормальная ситуация для ежедневных ботов.
        logger.warning("⚠️ Завершаем работу. Завтра попробуем снова!")
        exit(0)
