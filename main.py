import os
import requests
import logging
import asyncio
import time
from telegram import Bot
from telegram.error import TelegramError
from deep_translator import GoogleTranslator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

NASA_API_KEY = os.getenv('NASA_API_KEY')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHANNEL_ID = os.getenv('TELEGRAM_CHANNEL_ID')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
GITHUB_REPOSITORY = os.getenv('GITHUB_REPOSITORY')
STATE_VAR_NAME = "LAST_APOD_DATE"

APOD_URL = 'https://api.nasa.gov/planetary/apod'
translator = GoogleTranslator(source='en', target='ru')


def get_last_sent_date():
    if not GITHUB_TOKEN or not GITHUB_REPOSITORY:
        return ""
    url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/actions/variables/{STATE_VAR_NAME}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()["value"]
        return ""
    except Exception as e:
        logger.warning(f"️ Не удалось получить последнюю дату: {e}")
        return ""


def set_last_sent_date(date_str):
    if not GITHUB_TOKEN or not GITHUB_REPOSITORY:
        return
    url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/actions/variables/{STATE_VAR_NAME}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    data = {"name": STATE_VAR_NAME, "value": date_str}
    try:
        response = requests.patch(url, headers=headers, json=data, timeout=10)
        if response.status_code == 404:
            create_url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/actions/variables"
            requests.post(create_url, headers=headers, json=data, timeout=10)
        logger.info(f"💾 Дата {date_str} сохранена.")
    except Exception as e:
        logger.error(f"❌ Не удалось сохранить дату: {e}")


def translate_text(text, max_length=4500):
    if not text:
        return ""
    try:
        if len(text) > max_length:
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
            translated_parts = [translator.translate(part) for part in parts]
            return ' '.join(translated_parts)
        else:
            translated = translator.translate(text)
            logger.info(f"🔄 Переведено: {text[:50]}... -> {translated[:50]}...")
            return translated
    except Exception as e:
        logger.warning(f"⚠️ Ошибка перевода: {e}. Используем оригинал.")
        return text


def get_apod_with_retry(max_retries=3, delay=5):
    for attempt in range(max_retries):
        try:
            logger.info(f"🔄 Попытка {attempt + 1} из {max_retries} получить данные APOD...")
            params = {'api_key': NASA_API_KEY}
            response = requests.get(APOD_URL, params=params, timeout=60)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list):
                return data[0]
            return data
        except requests.exceptions.Timeout:
            logger.warning(f"️ Таймаут. Ждем {delay} секунд...")
            time.sleep(delay)
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Ошибка сети или сервера NASA: {e}")
            time.sleep(delay)
    return None


def main():
    logger.info("🚀 Запуск NASA Telegram бота (с переводом и заголовком)")
    
    if not all([NASA_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID]):
        logger.error("❌ Не все переменные окружения установлены")
        return False
    
    apod_data = get_apod_with_retry()
    if not apod_data:
        logger.warning("⚠️ Не удалось получить данные APOD.")
        return False

    apod_date = apod_data.get('date', '')
    last_sent_date = get_last_sent_date()
    
    if last_sent_date == apod_date:
        logger.info(f"✅ Фото за {apod_date} УЖЕ отправлено. Пропускаем.")
        return True

    if apod_data.get('media_type') != 'image':
        logger.warning(f"⚠️ Сегодня не фото (тип: {apod_data.get('media_type')}). Пропускаем.")
        set_last_sent_date(apod_date)
        return True
    
    title_en = apod_data.get('title', 'Без названия')
    explanation_en = apod_data.get('explanation', '')
    image_url = apod_data.get('url')
    copyright_info = apod_data.get('copyright')

    logger.info(f"📸 Получено: {title_en}")

    # 🌍 ПЕРЕВОД
    title_ru = translate_text(title_en)
    explanation_ru = translate_text(explanation_en)
    logger.info(f"✅ Перевод завершён: {title_ru}")

    # 🌟 ФОРМИРОВАНИЕ ПОСТА С ЗАГОЛОВКОМ
    caption = "<b> Кадр дня от NASA</b>\n\n"
    caption += f"<b>{title_ru}</b>\n\n"
    
    max_len = 900
    if len(explanation_ru) > max_len:
        explanation_ru = explanation_ru[:max_len].rsplit(' ', 1)[0] + "..."
    
    caption += f"{explanation_ru}\n\n"
    caption += f"📅 {apod_date}"
    if copyright_info:
        caption += f"\n© {copyright_info}"

    logger.info(f" Финальный текст поста:\n{caption[:200]}...")

    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        asyncio.run(bot.send_photo(
            chat_id=TELEGRAM_CHANNEL_ID,
            photo=image_url,
            caption=caption,
            parse_mode='HTML'
        ))
        logger.info("✅ Фото отправлено в Telegram")
        set_last_sent_date(apod_date)
        return True
        
    except TelegramError as e:
        logger.error(f"Ошибка Telegram: {e}")
        return False


if __name__ == '__main__':
    success = main()
    exit(0 if success else 0)
