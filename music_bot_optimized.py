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
from functools import partial, lru_cache
import aiohttp
from datetime import datetime, timedelta
from collections import deque
from asyncio import PriorityQueue
from concurrent.futures import ThreadPoolExecutor
import threading
from typing import Dict, List, Optional, Tuple
import weakref

# Загрузка переменных окружения
try:
    from dotenv import load_dotenv
    load_dotenv()
    logging.info("✅ Переменные окружения загружены из .env файла")
except ImportError:
    logging.warning("⚠️ python-dotenv не установлен. Переменные окружения загружаются из системы.")
except Exception as e:
    logging.error(f"❌ Ошибка загрузки .env файла: {e}")

# === ОПТИМИЗИРОВАННЫЕ НАСТРОЙКИ ===
API_TOKEN = os.getenv("BOT_TOKEN")
if not API_TOKEN:
    raise RuntimeError("Переменная окружения BOT_TOKEN не установлена")

MAX_FILE_SIZE_MB = 50
CACHE_DIR = "cache"
COOKIES_FILE = os.path.join(os.path.dirname(__file__), "cookies.txt")
TRACKS_FILE = os.path.join(os.path.dirname(__file__), "tracks.json")
SEARCH_CACHE_FILE = os.path.join(os.path.dirname(__file__), "search_cache.json")

# === ОПТИМИЗАЦИЯ ПРОИЗВОДИТЕЛЬНОСТИ ===
MAX_CONCURRENT_DOWNLOADS = 8  # Увеличили для лучшей производительности
MAX_CONCURRENT_DOWNLOADS_PER_USER = 3  # Больше загрузок на пользователя
MAX_CACHE_SIZE_MB = 1024  # 1GB кэш
CACHE_CLEANUP_THRESHOLD = 0.8  # Очистка при 80% заполнении
DOWNLOAD_TIMEOUT = 60  # Увеличили таймаут для стабильности
SEARCH_CACHE_TTL = 1800  # 30 минут кэш поиска
PAGE_SIZE = 15  # Увеличили размер страницы

# === ГЛОБАЛЬНЫЕ ОБЪЕКТЫ ===
user_tracks = {}
user_recommendation_history = {}
track_metadata_cache = {}
search_cache = {}

# === ОПТИМИЗИРОВАННЫЕ ОЧЕРЕДИ ===
PREMIUM_QUEUE = PriorityQueue()
REGULAR_QUEUE = deque(maxlen=1000)  # Ограничиваем размер очереди

# === ОПТИМИЗАЦИЯ ЗАГРУЗОК ===
yt_executor = ThreadPoolExecutor(
    max_workers=12,  # Увеличили количество потоков
    thread_name_prefix="yt_downloader",
    thread_name_prefix="yt_downloader"
)
download_semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)
user_download_semaphores = {}
ACTIVE_DOWNLOADS = 0

# === КЭШИРОВАНИЕ ===
@lru_cache(maxsize=1000)
def get_cached_metadata(url: str) -> Optional[dict]:
    """Кэширует метаданные треков в памяти"""
    return track_metadata_cache.get(url)

# === ОПТИМИЗИРОВАННОЕ ЛОГИРОВАНИЕ ===
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot_optimized.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# Инициализация бота
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
os.makedirs(CACHE_DIR, exist_ok=True)

# === ОПТИМИЗИРОВАННЫЕ ФУНКЦИИ ===

class DownloadManager:
    """Менеджер загрузок с оптимизацией производительности"""
    
    def __init__(self):
        self.active_downloads = 0
        self.download_history = deque(maxlen=100)
        self.failed_downloads = {}
        self.retry_delays = {}
    
    async def download_with_retry(self, url: str, user_id: str, max_retries: int = 3) -> Optional[str]:
        """Скачивание с автоматическими повторами и оптимизацией"""
        if url in self.failed_downloads:
            last_fail_time = self.failed_downloads[url].get('time', 0)
            if time.time() - last_fail_time < 300:  # 5 минут кэш ошибок
                return None
        
        for attempt in range(max_retries):
            try:
                result = await self._download_single(url, user_id)
                if result:
                    self.download_history.append({
                        'url': url,
                        'user_id': user_id,
                        'success': True,
                        'timestamp': time.time()
                    })
                    return result
            except Exception as e:
                logging.warning(f"Попытка {attempt + 1} не удалась для {url}: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Экспоненциальная задержка
        
        # Запоминаем неудачную попытку
        self.failed_downloads[url] = {
            'time': time.time(),
            'user_id': user_id,
            'attempts': max_retries
        }
        return None
    
    async def _download_single(self, url: str, user_id: str) -> Optional[str]:
        """Одиночная попытка скачивания"""
        async with download_semaphore:
            self.active_downloads += 1
            try:
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(
                    yt_executor, 
                    self._download_blocking, 
                    url, 
                    user_id
                )
                return result
            finally:
                self.active_downloads -= 1
    
    def _download_blocking(self, url: str, user_id: str) -> Optional[str]:
        """Блокирующее скачивание в отдельном потоке"""
        try:
            ydl_opts = {
                'format': 'bestaudio/best',
                'quiet': True,
                'no_warnings': True,
                'ignoreerrors': True,
                'timeout': DOWNLOAD_TIMEOUT,
                'retries': 2,
                'nocheckcertificate': True,
                'extractaudio': True,
                'audioformat': 'mp3',
                'audioquality': '192K',
                'outtmpl': os.path.join(CACHE_DIR, f'{user_id}_%(title)s_%(epoch)s.%(ext)s'),
            }
            
            if os.path.exists(COOKIES_FILE):
                ydl_opts['cookiefile'] = COOKIES_FILE
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if info and 'requested_downloads' in info:
                    downloaded_file = info['requested_downloads'][0]['filepath']
                    return downloaded_file
            
            return None
        except Exception as e:
            logging.error(f"Ошибка скачивания {url}: {e}")
            return None

# Создаем глобальный менеджер загрузок
download_manager = DownloadManager()

class CacheManager:
    """Менеджер кэша с автоматической очисткой"""
    
    def __init__(self, max_size_mb: int = MAX_CACHE_SIZE_MB):
        self.max_size_mb = max_size_mb
        self.cache_info = {}
        self.last_cleanup = time.time()
    
    def add_file(self, file_path: str, metadata: dict):
        """Добавляет файл в кэш"""
        if os.path.exists(file_path):
            size_mb = os.path.getsize(file_path) / (1024 * 1024)
            self.cache_info[file_path] = {
                'size_mb': size_mb,
                'metadata': metadata,
                'added_time': time.time(),
                'access_time': time.time()
            }
            self._check_cleanup()
    
    def get_file(self, file_path: str) -> Optional[dict]:
        """Получает информацию о файле из кэша"""
        if file_path in self.cache_info:
            self.cache_info[file_path]['access_time'] = time.time()
            return self.cache_info[file_path]['metadata']
        return None
    
    def _check_cleanup(self):
        """Проверяет необходимость очистки кэша"""
        current_time = time.time()
        if current_time - self.last_cleanup < 300:  # Каждые 5 минут
            return
        
        total_size = sum(info['size_mb'] for info in self.cache_info.values())
        if total_size > self.max_size_mb * CACHE_CLEANUP_THRESHOLD:
            self._cleanup_cache()
            self.last_cleanup = current_time
    
    def _cleanup_cache(self):
        """Очищает кэш, удаляя старые и редко используемые файлы"""
        try:
            # Сортируем файлы по времени последнего доступа
            sorted_files = sorted(
                self.cache_info.items(),
                key=lambda x: x[1]['access_time']
            )
            
            # Удаляем файлы до достижения целевого размера
            target_size = self.max_size_mb * 0.5  # Цель - 50% от максимума
            current_size = sum(info['size_mb'] for info in self.cache_info.values())
            
            for file_path, info in sorted_files:
                if current_size <= target_size:
                    break
                
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        logging.info(f"Удален файл кэша: {file_path}")
                    del self.cache_info[file_path]
                    current_size -= info['size_mb']
                except Exception as e:
                    logging.error(f"Ошибка удаления файла кэша {file_path}: {e}")
            
            logging.info(f"Очистка кэша завершена. Текущий размер: {current_size:.2f}MB")
            
        except Exception as e:
            logging.error(f"Ошибка очистки кэша: {e}")

# Создаем глобальный менеджер кэша
cache_manager = CacheManager()

# === ОПТИМИЗИРОВАННЫЕ ФУНКЦИИ СКАЧИВАНИЯ ===

async def download_track_optimized(user_id: str, url: str, is_premium: bool = False) -> Optional[str]:
    """Оптимизированная функция скачивания трека"""
    try:
        # Проверяем кэш
        cached_file = await _check_cache_for_url(url)
        if cached_file:
            logging.info(f"Используем кэшированный файл: {cached_file}")
            return cached_file
        
        # Скачиваем с оптимизацией
        result = await download_manager.download_with_retry(url, user_id)
        
        if result:
            # Добавляем в кэш
            metadata = {
                'url': url,
                'user_id': user_id,
                'downloaded_time': time.time(),
                'is_premium': is_premium
            }
            cache_manager.add_file(result, metadata)
            
            logging.info(f"Трек успешно скачан: {result}")
            return result
        
        return None
        
    except Exception as e:
        logging.error(f"Ошибка оптимизированного скачивания: {e}")
        return None

async def _check_cache_for_url(url: str) -> Optional[str]:
    """Проверяет кэш на наличие файла по URL"""
    # Здесь можно реализовать более сложную логику поиска в кэше
    # Пока возвращаем None для простоты
    return None

# === ОПТИМИЗИРОВАННЫЕ ФУНКЦИИ ПОИСКА ===

@lru_cache(maxsize=500)
async def search_tracks_cached(query: str, limit: int = 10) -> List[dict]:
    """Кэшированный поиск треков"""
    cache_key = f"{query}_{limit}"
    
    if cache_key in search_cache:
        cache_entry = search_cache[cache_key]
        if time.time() - cache_entry['timestamp'] < SEARCH_CACHE_TTL:
            return cache_entry['results']
    
    # Выполняем поиск
    results = await _perform_search(query, limit)
    
    # Кэшируем результаты
    search_cache[cache_key] = {
        'results': results,
        'timestamp': time.time()
    }
    
    return results

async def _perform_search(query: str, limit: int) -> List[dict]:
    """Выполняет поиск треков"""
    # Здесь должна быть логика поиска
    # Пока возвращаем пустой список
    return []

# === ОПТИМИЗИРОВАННЫЕ ОБРАБОТЧИКИ ===

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Оптимизированный обработчик команды start"""
    try:
        await message.answer(
            "🎵 Добро пожаловать в оптимизированный Music Bot!\n"
            "Используйте /search для поиска музыки или отправьте ссылку на трек."
        )
    except Exception as e:
        logging.error(f"Ошибка в команде start: {e}")

@dp.message(Command("search"))
async def cmd_search(message: types.Message):
    """Оптимизированный поиск треков"""
    try:
        query = message.text.replace("/search", "").strip()
        if not query:
            await message.answer("Пожалуйста, укажите что искать. Например: /search название песни")
            return
        
        # Показываем индикатор загрузки
        loading_msg = await message.answer("🔍 Ищем треки...")
        
        # Выполняем поиск с кэшированием
        results = await search_tracks_cached(query, PAGE_SIZE)
        
        if results:
            # Формируем ответ
            response = "🎵 Найденные треки:\n\n"
            for i, track in enumerate(results[:PAGE_SIZE], 1):
                response += f"{i}. {track.get('title', 'Неизвестно')} - {track.get('artist', 'Неизвестно')}\n"
            
            await loading_msg.edit_text(response)
        else:
            await loading_msg.edit_text("❌ Треки не найдены. Попробуйте другой запрос.")
            
    except Exception as e:
        logging.error(f"Ошибка в поиске: {e}")
        await message.answer("Произошла ошибка при поиске. Попробуйте позже.")

@dp.message()
async def handle_url(message: types.Message):
    """Обработчик URL для скачивания"""
    try:
        # Извлекаем URL из сообщения
        urls = re.findall(r'https?://[^\s]+', message.text)
        if not urls:
            return
        
        url = urls[0]
        
        # Проверяем, что это поддерживаемый сервис
        if not _is_supported_url(url):
            await message.answer("❌ Этот сервис не поддерживается.")
            return
        
        # Показываем индикатор загрузки
        loading_msg = await message.answer("📥 Скачиваем трек...")
        
        # Скачиваем трек
        file_path = await download_track_optimized(str(message.from_user.id), url)
        
        if file_path and os.path.exists(file_path):
            # Отправляем файл
            try:
                with open(file_path, 'rb') as audio_file:
                    await message.answer_audio(
                        audio_file,
                        title=os.path.basename(file_path),
                        performer="Music Bot"
                    )
                
                # Удаляем файл после отправки
                await _cleanup_file(file_path)
                
            except Exception as e:
                logging.error(f"Ошибка отправки файла: {e}")
                await loading_msg.edit_text("❌ Ошибка отправки файла.")
        else:
            await loading_msg.edit_text("❌ Не удалось скачать трек.")
            
    except Exception as e:
        logging.error(f"Ошибка обработки URL: {e}")
        await message.answer("Произошла ошибка при скачивании.")

def _is_supported_url(url: str) -> bool:
    """Проверяет, поддерживается ли URL"""
    supported_domains = [
        'youtube.com', 'youtu.be', 'soundcloud.com', 'spotify.com',
        'vk.com', 'vk.ru', 'deezer.com', 'tidal.com'
    ]
    return any(domain in url.lower() for domain in supported_domains)

async def _cleanup_file(file_path: str):
    """Удаляет файл после использования"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logging.info(f"Файл удален: {file_path}")
    except Exception as e:
        logging.error(f"Ошибка удаления файла {file_path}: {e}")

# === ОПТИМИЗИРОВАННАЯ ГЛАВНАЯ ФУНКЦИЯ ===

async def main():
    """Главная функция с оптимизацией"""
    try:
        logging.info("🚀 Запуск оптимизированного Music Bot...")
        
        # Запускаем фоновые задачи
        asyncio.create_task(_background_cleanup())
        asyncio.create_task(_cache_monitor())
        
        # Запускаем бота
        await dp.start_polling(bot)
        
    except Exception as e:
        logging.error(f"Критическая ошибка в main: {e}")
    finally:
        # Очистка ресурсов
        yt_executor.shutdown(wait=True)
        logging.info("Бот остановлен")

async def _background_cleanup():
    """Фоновая очистка ресурсов"""
    while True:
        try:
            await asyncio.sleep(300)  # Каждые 5 минут
            
            # Очищаем старые записи в кэше
            current_time = time.time()
            expired_keys = [
                key for key, entry in search_cache.items()
                if current_time - entry['timestamp'] > SEARCH_CACHE_TTL
            ]
            
            for key in expired_keys:
                del search_cache[key]
            
            if expired_keys:
                logging.info(f"Очищено {len(expired_keys)} устаревших записей кэша")
                
        except Exception as e:
            logging.error(f"Ошибка в фоновой очистке: {e}")

async def _cache_monitor():
    """Мониторинг кэша"""
    while True:
        try:
            await asyncio.sleep(600)  # Каждые 10 минут
            
            # Проверяем размер кэша
            cache_size = sum(info['size_mb'] for info in cache_manager.cache_info.values())
            logging.info(f"Размер кэша: {cache_size:.2f}MB / {MAX_CACHE_SIZE_MB}MB")
            
        except Exception as e:
            logging.error(f"Ошибка в мониторинге кэша: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Бот остановлен пользователем")
    except Exception as e:
        logging.error(f"Критическая ошибка: {e}")
