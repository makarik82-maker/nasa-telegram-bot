import os
import requests
import logging
import asyncio
import time
from datetime import datetime, timedelta
from telegram import Bot
from telegram.error import TelegramError
from deep_translator import GoogleTranslator

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
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
GITHUB_REPOSITORY = os.getenv('GITHUB_REPOSITORY')

# Источники контента (в порядке ротации)
SOURCES = ['apod', 'epic', 'earth', 'history']
STATE_VAR_NAME = "LAST_CONTENT_INFO"

translator = GoogleTranslator(source='en', target='ru')


# ==================== NASA APOD ====================
def get_apod():
    """Получить Astronomy Picture of the Day с переводом"""
    try:
        logger.info("🌌 Запрос к NASA APOD API...")
        url = 'https://api.nasa.gov/planetary/apod'
        params = {'api_key': NASA_API_KEY}
        response = requests.get(url, params=params, timeout=60)
        response.raise_for_status()
        data = response.json()
        
        if isinstance(data, list):
            data = data[0]
        
        if data.get('media_type') != 'image':
            logger.warning(f"⚠️ APOD сегодня не фото (тип: {data.get('media_type')}). Пропускаем.")
            return None
        
        title_en = data.get('title', 'Без названия')
        explanation_en = data.get('explanation', '')
        image_url = data.get('url')
        copyright_info = data.get('copyright')
        apod_date = data.get('date', '')
        
        # Перевод
        title_ru = translator.translate(title_en) if len(title_en) > 5 else title_en
        explanation_ru = translator.translate(explanation_en) if len(explanation_en) > 10 else explanation_en
        
        logger.info(f"✅ Переведено: {title_ru}")
        
        # Формирование поста
        caption_parts = [
            "<b>🌌 Кадр дня от NASA</b>",
            "",
            f"<b>{title_ru}</b>",
            "",
            explanation_ru,
            "",
            f"📅 {apod_date}"
        ]
        
        if copyright_info:
            caption_parts.append(f"© {copyright_info}")
        
        caption = "\n".join(caption_parts)
        
        # Защита от превышения лимита Telegram
        if len(caption) > 1020:
            caption = caption[:1020].rsplit(' ', 1)[0] + "..."
        
        return {
            'type': 'photo',
            'url': image_url,
            'caption': caption,
            'date': apod_date
        }
    except Exception as e:
        logger.error(f"❌ Ошибка APOD API: {e}")
        return None


# ==================== NASA EPIC API ====================
def get_epic_photo():
    """Получить фото Земли с камеры EPIC (DSCOVR) с переводом"""
    try:
        logger.info(" Запрос к NASA EPIC API...")
        url = 'https://api.nasa.gov/EPIC/api/natural'
        params = {'api_key': NASA_API_KEY}
        response = requests.get(url, params=params, timeout=60)
        response.raise_for_status()
        data = response.json()
        
        if data and len(data) > 0:
            latest = data[-1]
            date = latest['date'].split(' ')[0].replace('-', '/')
            image_name = latest['image']
            
            image_url = f"https://api.nasa.gov/EPIC/archive/natural/{date}/png/{image_name}.png?api_key={NASA_API_KEY}"
            
            # Текст для перевода
            description_en = f"Снимок сделан камерой EPIC на борту спутника DSCOVR. Координаты центра: {latest['centroid_coordinates']}. Расстояние: примерно 1.5 миллиона километров от Земли."
            
            # Перевод
            description_ru = translator.translate(description_en) if len(description_en) > 10 else description_en
            logger.info(f"✅ EPIC текст переведён")
            
            # Формирование поста с заголовком "Кадр дня от NASA"
            caption_parts = [
                "<b>🌌 Кадр дня от NASA</b>",
                "",
                "<b>🌍 Земля из космоса</b>",
                "",
                description_ru,
                "",
                f"📅 Дата: {latest['date']}"
            ]
            
            caption = "\n".join(caption_parts)
            
            return {
                'type': 'photo',
                'url': image_url,
                'caption': caption,
                'date': latest['date'].split(' ')[0]
            }
        return None
    except Exception as e:
        logger.error(f" Ошибка EPIC API: {e}")
        return None


# ==================== NASA EARTH IMAGERY API ====================
def get_earth_imagery():
    """Получить спутниковый снимок Земли (Landsat 8) с переводом"""
    try:
        logger.info("🛰️ Запрос к NASA Earth Imagery API...")
        
        date = (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
        url = f'https://api.nasa.gov/planetary/earth/imagery'
        
        # Случайные координаты для разнообразия
        import random
        lon = random.uniform(-180, 180)
        lat = random.uniform(-60, 60)  # Избегаем полюсов
        
        params = {
            'api_key': NASA_API_KEY,
            'lon': lon,
            'lat': lat,
            'dim': 0.15,
            'date': date
        }
        
        response = requests.get(url, params=params, timeout=60)
        
        if response.status_code == 200:
            data = response.json()
            image_url = data.get('url')
            
            # Текст для перевода
            description_en = f"Спутник: Landsat 8. Дата съёмки: {data.get('date', 'Неизвестно')}. Координаты: {lat:.2f} градусов широты, {lon:.2f} градусов долготы. Многоспектральное изображение поверхности Земли."
            
            # Перевод
            description_ru = translator.translate(description_en) if len(description_en) > 10 else description_en
            logger.info(f"✅ Earth Imagery текст переведён")
            
            # Формирование поста с заголовком "Кадр дня от NASA"
            caption_parts = [
                "<b>🌌 Кадр дня от NASA</b>",
                "",
                "<b>🛰️ Спутниковый снимок Земли</b>",
                "",
                description_ru
            ]
            
            caption = "\n".join(caption_parts)
            
            return {
                'type': 'photo',
                'url': image_url,
                'caption': caption,
                'date': data.get('date', date)
            }
        
        return None
    except Exception as e:
        logger.error(f"❌ Ошибка Earth Imagery API: {e}")
        return None


# ==================== WIKIPEDIA / NASA HISTORY API ====================
def get_historical_event():
    """Получить историческое событие из истории космонавтики с переводом"""
    try:
        logger.info("📚 Запрос к Wikipedia API (история космонавтики)...")
        
        today = datetime.now()
        month_day = today.strftime('%m-%d')
        
        url = f'https://en.wikipedia.org/api/rest_v1/feed/onthisday/events/{month_day}'
        headers = {'User-Agent': 'NASA-Telegram-Bot/1.0'}
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        events = data.get('events', [])
        
        # Фильтруем события, связанные с космосом
        space_keywords = ['space', 'nasa', 'satellite', 'rocket', 'launch', 'astronaut', 
                         'cosmos', 'moon', 'mars', 'planet', 'telescope', 'orbit', 'cosmic']
        
        space_events = [e for e in events if any(kw in e.get('text', '').lower() for kw in space_keywords)]
        
        if space_events:
            import random
            event = random.choice(space_events)
            year = event.get('year', 'Неизвестно')
            text = event.get('text', '')
            
            # Перевод
            translated_text = translator.translate(text[:500]) if len(text) > 10 else text
            logger.info(f"✅ Историческое событие переведено")
            
            # Формирование поста БЕЗ заголовка "Кадр дня от NASA"
            caption_parts = [
                "<b>📚 В этот день в истории космоса</b>",
                "",
                f"🗓️ {year} год",
                "",
                translated_text,
                "",
                "Источник: Wikipedia"
            ]
            
            caption = "\n".join(caption_parts)
            
            return {
                'type': 'text',
                'url': None,
                'caption': caption,
                'date': f"{year}-{month_day}"
            }
        
        # Если нет событий по космосу, берём любое
        if events:
            event = events[0]
            year = event.get('year', 'Неизвестно')
            text = event.get('text', '')[:300]
            
            # Перевод
            translated_text = translator.translate(text) if len(text) > 10 else text
            logger.info(f"✅ Событие переведено")
            
            caption_parts = [
                "<b>📚 В этот день</b>",
                "",
                f"🗓️ {year} год",
                "",
                translated_text,
                "",
                "Источник: Wikipedia"
            ]
            
            caption = "\n".join(caption_parts)
            
            return {
                'type': 'text',
                'url': None,
                'caption': caption,
                'date': f"{year}-{month_day}"
            }
        
        return None
    except Exception as e:
        logger.error(f"❌ Ошибка Wikipedia API: {e}")
        return None


# ==================== УПРАВЛЕНИЕ СОСТОЯНИЕМ ====================
def get_last_content_info():
    """Получить информацию о последнем посте"""
    if not GITHUB_TOKEN or not GITHUB_REPOSITORY:
        return None, None
    
    url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/actions/variables/{STATE_VAR_NAME}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            value = response.json()["value"]
            parts = value.split(':')
            return parts[0], parts[1] if len(parts) > 1 else None
        return None, None
    except Exception as e:
        logger.warning(f"⚠️ Не удалось получить последнюю информацию: {e}")
        return None, None


def set_last_content_info(source, date):
    """Сохранить информацию о последнем посте"""
    if not GITHUB_TOKEN or not GITHUB_REPOSITORY:
        return
    
    url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/actions/variables/{STATE_VAR_NAME}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    data = {"name": STATE_VAR_NAME, "value": f"{source}:{date}"}
    
    try:
        response = requests.patch(url, headers=headers, json=data, timeout=10)
        if response.status_code == 404:
            create_url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/actions/variables"
            requests.post(create_url, headers=headers, json=data, timeout=10)
        logger.info(f"💾 Сохранено: {source}:{date}")
    except Exception as e:
        logger.error(f"❌ Не удалось сохранить информацию: {e}")


def get_next_source():
    """Определить следующий источник на основе последнего использованного"""
    last_source, _ = get_last_content_info()
    
    if last_source is None:
        return SOURCES[0]
    
    try:
        last_index = SOURCES.index(last_source)
        next_index = (last_index + 1) % len(SOURCES)
        return SOURCES[next_index]
    except ValueError:
        return SOURCES[0]


# ==================== ОСНОВНАЯ ФУНКЦИЯ ====================
def main():
    logger.info("🚀 Запуск NASA Telegram бота (ротация: APOD, EPIC, Earth, History)")
    
    if not all([NASA_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID]):
        logger.error("❌ Не все переменные окружения установлены")
        return False
    
    # Определяем следующий источник
    source = get_next_source()
    logger.info(f"🎯 Выбран источник: {source.upper()}")
    
    # Получаем контент
    if source == 'apod':
        content = get_apod()
    elif source == 'epic':
        content = get_epic_photo()
    elif source == 'earth':
        content = get_earth_imagery()
    elif source == 'history':
        content = get_historical_event()
    else:
        logger.error(f"❌ Неизвестный источник: {source}")
        return False
    
    if not content:
        logger.warning("⚠️ Не удалось получить контент. Пропускаем.")
        return False
    
    logger.info(f"✅ Получен контент от {source}")
    
    # Отправка в Telegram
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        
        if content['type'] == 'photo' and content['url']:
            asyncio.run(bot.send_photo(
                chat_id=TELEGRAM_CHANNEL_ID,
                photo=content['url'],
                caption=content['caption'],
                parse_mode='HTML'
            ))
        else:
            asyncio.run(bot.send_message(
                chat_id=TELEGRAM_CHANNEL_ID,
                text=content['caption'],
                parse_mode='HTML'
            ))
        
        logger.info("✅ Контент успешно отправлен в Telegram")
        set_last_content_info(source, content['date'])
        
        return True
        
    except TelegramError as e:
        logger.error(f"Ошибка Telegram: {e}")
        return False


if __name__ == '__main__':
    success = main()
    if success:
        exit(0)
    else:
        logger.warning("⚠️ Завершаем работу. Завтра попробуем снова!")
        exit(0)
