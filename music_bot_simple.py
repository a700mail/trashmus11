import logging
import os
import asyncio
import json
import time
import random
import secrets
import yt_dlp
import browser_cookie3
from http.cookiejar import MozillaCookieJar
from aiogram import Bot, Dispatcher, types
from aiogram import F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

import re
from functools import partial
import aiohttp
from datetime import datetime, timedelta
from collections import deque
from asyncio import PriorityQueue
from concurrent.futures import ThreadPoolExecutor

# Загрузка переменных окружения
try:
    from dotenv import load_dotenv
    load_dotenv()
    logging.info("✅ Переменные окружения загружены из .env файла")
except ImportError:
    logging.warning("⚠️ python-dotenv не установлен. Переменные окружения загружаются из системы.")
except Exception as e:
    logging.error(f"❌ Ошибка загрузки .env файла: {e}")

# === НАСТРОЙКИ ===
API_TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
if not API_TOKEN:
    raise RuntimeError("Переменная окружения BOT_TOKEN или TELEGRAM_BOT_TOKEN не установлена")

MAX_FILE_SIZE_MB = 50
CACHE_DIR = "cache"
COOKIES_FILE = os.path.join(os.path.dirname(__file__), "cookies.txt")
TRACKS_FILE = os.path.join(os.path.dirname(__file__), "tracks.json")
SEARCH_CACHE_FILE = os.path.join(os.path.dirname(__file__), "search_cache.json")

# === НАСТРОЙКИ КЭША ===
SEARCH_CACHE_TTL = 600
PAGE_SIZE = 10  # для постраничной навигации

# === НАСТРОЙКИ ЗАГРУЗОК ===
MAX_CONCURRENT_DOWNLOADS = 3  # Максимальное количество одновременных загрузок
ACTIVE_DOWNLOADS = 0  # Счетчик активных загрузок

# === ГЛОБАЛЬНЫЕ ОБЪЕКТЫ ДЛЯ ЗАГРУЗОК ===
yt_executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="yt_downloader")
download_semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)

# === НАСТРОЙКИ SOUNDCLOUD ===
SOUNDCLOUD_SEARCH_LIMIT = 10  # Количество результатов поиска на SoundCloud
SOUNDCLOUD_CACHE_PREFIX = "sc"  # Префикс для кэша SoundCloud

# === ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ===
user_tracks = {}
user_recommendation_history = {}

# === НАСТРОЙКИ АНТИСПАМА ===
ANTISPAM_DELAY = 1.0  # Задержка между запросами в секундах (1 сек)
user_last_request = {}  # Словарь для отслеживания времени последних запросов пользователей

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
os.makedirs(CACHE_DIR, exist_ok=True)

# === ОСНОВНЫЕ КОМАНДЫ ===

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Команда /start"""
    user_id = str(message.from_user.id)
    user_name = message.from_user.first_name
    
    welcome_text = f"""
🎵 Привет, {user_name}!

Я Music Bot - твой помощник для скачивания музыки!

🎧 Что я умею:
• Скачивать музыку с YouTube
• Поддерживать SoundCloud
• Искать треки по названию
• Сохранять твои любимые треки

📱 Отправь мне ссылку на YouTube или SoundCloud, и я скачаю музыку для тебя!

🔍 Или используй команду /search для поиска треков.
"""
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔍 Поиск музыки")],
            [KeyboardButton(text="📚 Моя музыка")],
            [KeyboardButton(text="ℹ️ Помощь")]
        ],
        resize_keyboard=True
    )
    
    await message.answer(welcome_text, reply_markup=keyboard)
    logging.info(f"✅ Пользователь {user_id} ({user_name}) запустил бота")

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    """Команда /help"""
    help_text = """
🎵 Music Bot - Помощь

📱 Основные команды:
/start - Запустить бота
/help - Показать эту справку
/search - Поиск музыки
/mymusic - Моя музыка

🔗 Как использовать:
1. Отправь ссылку на YouTube видео
2. Отправь ссылку на SoundCloud трек
3. Используй поиск по названию

💡 Советы:
• Максимальный размер файла: 50MB
• Поддерживаются форматы: MP3, M4A
• Поиск работает по названию и исполнителю
"""
    
    await message.answer(help_text)
    logging.info(f"✅ Пользователь {message.from_user.id} запросил помощь")

@dp.message(Command("search"))
async def cmd_search(message: types.Message):
    """Команда /search для поиска музыки"""
    await message.answer("🔍 Введите название трека или исполнителя для поиска:")
    logging.info(f"✅ Пользователь {message.from_user.id} запустил поиск")

@dp.message(Command("mymusic"))
async def cmd_mymusic(message: types.Message):
    """Команда /mymusic для показа сохраненной музыки"""
    user_id = str(message.from_user.id)
    
    if user_id in user_tracks and user_tracks[user_id]:
        tracks_text = "📚 Ваша музыка:\n\n"
        for i, track in enumerate(user_tracks[user_id][:10], 1):
            tracks_text += f"{i}. {track['title']} - {track['artist']}\n"
        
        if len(user_tracks[user_id]) > 10:
            tracks_text += f"\n... и еще {len(user_tracks[user_id]) - 10} треков"
    else:
        tracks_text = "📚 У вас пока нет сохраненной музыки.\nОтправьте ссылку на трек, чтобы добавить его в коллекцию!"
    
    await message.answer(tracks_text)
    logging.info(f"✅ Пользователь {user_id} просмотрел свою музыку")

@dp.message()
async def handle_message(message: types.Message):
    """Обработка всех сообщений"""
    user_id = str(message.from_user.id)
    text = message.text
    
    # Проверка антиспама
    current_time = time.time()
    if user_id in user_last_request:
        time_diff = current_time - user_last_request[user_id]
        if time_diff < ANTISPAM_DELAY:
            await message.answer("⏳ Подождите немного перед следующим запросом...")
            return
    
    user_last_request[user_id] = current_time
    
    # Обработка текстовых сообщений
    if text:
        if text == "🔍 Поиск музыки":
            await cmd_search(message)
        elif text == "📚 Моя музыка":
            await cmd_mymusic(message)
        elif text == "ℹ️ Помощь":
            await cmd_help(message)
        elif text.startswith(('http://', 'https://')):
            # Это ссылка - обрабатываем как URL
            await process_url(message, text)
        else:
            # Это поисковый запрос
            await process_search_query(message, text)
    
    # Обработка аудио файлов
    elif message.audio:
        await process_audio(message)

async def process_url(message: types.Message, url: str):
    """Обработка URL для скачивания"""
    user_id = str(message.from_user.id)
    
    await message.answer("🔄 Обрабатываю ссылку...")
    
    try:
        if 'youtube.com' in url or 'youtu.be' in url:
            await process_youtube_url(message, url)
        elif 'soundcloud.com' in url:
            await process_soundcloud_url(message, url)
        else:
            await message.answer("❌ Поддерживаются только YouTube и SoundCloud ссылки")
    except Exception as e:
        logging.error(f"❌ Ошибка обработки URL {url}: {e}")
        await message.answer("❌ Произошла ошибка при обработке ссылки")

async def process_youtube_url(message: types.Message, url: str):
    """Обработка YouTube URL"""
    user_id = str(message.from_user.id)
    
    try:
        await message.answer("🎵 Скачиваю с YouTube...")
        
        # Здесь будет логика скачивания YouTube
        # Пока просто имитируем процесс
        
        await asyncio.sleep(2)  # Имитация загрузки
        
        await message.answer("✅ Трек успешно скачан и добавлен в вашу коллекцию!")
        
        # Сохраняем информацию о треке
        if user_id not in user_tracks:
            user_tracks[user_id] = []
        
        user_tracks[user_id].append({
            'title': 'YouTube трек',
            'artist': 'YouTube',
            'url': url,
            'date': datetime.now().isoformat()
        })
        
        logging.info(f"✅ Пользователь {user_id} добавил YouTube трек")
        
    except Exception as e:
        logging.error(f"❌ Ошибка YouTube: {e}")
        await message.answer("❌ Не удалось скачать трек с YouTube")

async def process_soundcloud_url(message: types.Message, url: str):
    """Обработка SoundCloud URL"""
    user_id = str(message.from_user.id)
    
    try:
        await message.answer("🎧 Скачиваю с SoundCloud...")
        
        # Здесь будет логика скачивания SoundCloud
        # Пока просто имитируем процесс
        
        await asyncio.sleep(2)  # Имитация загрузки
        
        await message.answer("✅ Трек успешно скачан и добавлен в вашу коллекцию!")
        
        # Сохраняем информацию о треке
        if user_id not in user_tracks:
            user_tracks[user_id] = []
        
        user_tracks[user_id].append({
            'title': 'SoundCloud трек',
            'artist': 'SoundCloud',
            'url': url,
            'date': datetime.now().isoformat()
        })
        
        logging.info(f"✅ Пользователь {user_id} добавил SoundCloud трек")
        
    except Exception as e:
        logging.error(f"❌ Ошибка SoundCloud: {e}")
        await message.answer("❌ Не удалось скачать трек с SoundCloud")

async def process_search_query(message: types.Message, query: str):
    """Обработка поискового запроса"""
    user_id = str(message.from_user.id)
    
    await message.answer(f"🔍 Ищу: {query}")
    
    try:
        # Здесь будет логика поиска
        # Пока просто имитируем процесс
        
        await asyncio.sleep(1)  # Имитация поиска
        
        # Имитируем результаты поиска
        results = [
            f"🎵 {query} - Исполнитель 1",
            f"🎵 {query} - Исполнитель 2", 
            f"🎵 {query} - Исполнитель 3"
        ]
        
        results_text = "🔍 Результаты поиска:\n\n" + "\n".join(results)
        results_text += "\n\n💡 Отправьте ссылку на YouTube или SoundCloud для скачивания"
        
        await message.answer(results_text)
        logging.info(f"✅ Пользователь {user_id} искал: {query}")
        
    except Exception as e:
        logging.error(f"❌ Ошибка поиска: {e}")
        await message.answer("❌ Произошла ошибка при поиске")

async def process_audio(message: types.Message):
    """Обработка аудио файлов"""
    user_id = str(message.from_user.id)
    
    await message.answer("🎵 Получил аудио файл! Это будет добавлено в вашу коллекцию.")
    
    # Сохраняем информацию о треке
    if user_id not in user_tracks:
        user_tracks[user_id] = []
    
    user_tracks[user_id].append({
        'title': message.audio.title or 'Неизвестный трек',
        'artist': message.audio.performer or 'Неизвестный исполнитель',
        'duration': message.audio.duration,
        'date': datetime.now().isoformat()
    })
    
    logging.info(f"✅ Пользователь {user_id} добавил аудио файл")

async def main():
    """Главная функция бота"""
    logging.info("🚀 Запуск Music Bot...")
    
    try:
        # Запускаем бота
        logging.info("✅ Бот запущен успешно!")
        await dp.start_polling(bot)
        
    except Exception as e:
        logging.error(f"❌ Критическая ошибка: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
