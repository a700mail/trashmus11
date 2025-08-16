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

# Импорт модуля YooMoney отключен
# try:
#     from yoomoney_payment import create_simple_payment_url, verify_payment_by_label
#     YOOMONEY_AVAILABLE = True
# except ImportError:
#     YOOMONEY_AVAILABLE = False
#     logging.warning("⚠️ Модуль YooMoney не найден. Платежи через YooMoney будут недоступны.")

YOOMONEY_AVAILABLE = False
logging.info("✅ Платежные системы отключены - бот работает в упрощенном режиме")

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
API_TOKEN = os.getenv("BOT_TOKEN")
if not API_TOKEN:
    raise RuntimeError("Переменная окружения BOT_TOKEN не установлена")

MAX_FILE_SIZE_MB = 50
CACHE_DIR = "cache"
COOKIES_FILE = os.path.join(os.path.dirname(__file__), "cookies.txt")
TRACKS_FILE = os.path.join(os.path.dirname(__file__), "tracks.json")
SEARCH_CACHE_FILE = os.path.join(os.path.dirname(__file__), "search_cache.json")

# === ПЛАТЕЖНЫЕ СИСТЕМЫ ОТКЛЮЧЕНЫ ===
# Все платежные функции удалены для упрощения и оптимизации

# === НАСТРОЙКИ АВТОМАТИЧЕСКОЙ ОЧИСТКИ ===
AUTO_CLEANUP_ENABLED = True  # Включить/выключить автоматическую очистку
AUTO_CLEANUP_DELAY = 1.0  # Задержка в секундах перед удалением файла после отправки
CLEANUP_LOGGING = True  # Логирование операций очистки

# === РАСШИРЕННОЕ КЕШИРОВАНИЕ ===
from functools import lru_cache
from typing import Optional, List, Dict, Any
import hashlib

# Кеш для метаданных треков
track_metadata_cache = {}
search_cache = {}
user_preferences_cache = {}

# Настройки кеша
CACHE_MAX_SIZE = 1000  # Максимальное количество элементов в кеше
CACHE_TTL = 3600  # Время жизни кеша в секундах (1 час)
SEARCH_CACHE_TTL = 1800  # Время жизни кеша поиска (30 минут)

# Кеш для изображений
image_cache = {}
IMAGE_CACHE_MAX_SIZE = 100
IMAGE_CACHE_TTL = 7200  # 2 часа для изображений

ARTIST_FACTS_FILE = os.path.join(os.path.dirname(__file__), "artist_facts.json")
SEARCH_CACHE_TTL = 600
PAGE_SIZE = 10  # для постраничной навигации

# === НАСТРОЙКИ ОЧЕРЕДИ ===
REGULAR_QUEUE = deque()  # Очередь для пользователей

# === НАСТРОЙКИ WEBHOOK ===
# Глобальная переменная для хранения последнего webhook обновления
last_webhook_update = None
webhook_update_queue = asyncio.Queue()

# === ОПТИМИЗАЦИЯ ПАРАЛЛЕЛЬНЫХ ЗАГРУЗОК ===
MAX_CONCURRENT_DOWNLOADS = 5  # Увеличили количество одновременных загрузок
MAX_CONCURRENT_DOWNLOADS_PER_USER = 2  # Максимум 2 загрузки на пользователя
ACTIVE_DOWNLOADS = 0  # Счетчик активных загрузок
user_download_semaphores = {}  # Семафоры для каждого пользователя

# === ГЛОБАЛЬНЫЕ ОБЪЕКТЫ ДЛЯ ЗАГРУЗОК ===
yt_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="yt_downloader")  # Увеличили количество потоков
download_semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)

# === ОТСЛЕЖИВАНИЕ ФОНОВЫХ ЗАДАЧ ===
task_last_run = {}  # Время последнего успешного запуска каждой задачи

# === НАСТРОЙКИ SOUNDCLOUD ===
SOUNDCLOUD_SEARCH_LIMIT = 10  # Количество результатов поиска на SoundCloud
SOUNDCLOUD_CACHE_PREFIX = "sc"  # Префикс для кэша SoundCloud

# === ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ===
user_tracks = {}
user_recommendation_history = {}

# === АНТИСПАМ ОТКЛЮЧЕН ===
# Антиспам удален для ускорения работы бота

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

# === ФУНКЦИИ ДЛЯ ОПТИМИЗАЦИИ ЗАГРУЗОК ===

# === ФУНКЦИИ КЕШИРОВАНИЯ ===
def get_cache_key(*args) -> str:
    """Создает уникальный ключ кеша из аргументов"""
    key_string = "|".join(str(arg) for arg in args)
    return hashlib.md5(key_string.encode()).hexdigest()

def get_cached_metadata(track_id: str) -> Optional[Dict[str, Any]]:
    """Получает метаданные трека из кеша"""
    return track_metadata_cache.get(track_id)

def set_cached_metadata(track_id: str, metadata: Dict[str, Any]) -> None:
    """Сохраняет метаданные трека в кеш"""
    if len(track_metadata_cache) >= CACHE_MAX_SIZE:
        # Удаляем старые записи
        oldest_key = next(iter(track_metadata_cache))
        del track_metadata_cache[oldest_key]
    track_metadata_cache[track_id] = metadata

def get_cached_search(query: str) -> Optional[List[Dict[str, Any]]]:
    """Получает результаты поиска из кеша"""
    cache_key = get_cache_key("search", query)
    cached_data = search_cache.get(cache_key)
    if cached_data and time.time() - cached_data.get('timestamp', 0) < SEARCH_CACHE_TTL:
        return cached_data.get('results', [])
    return None

def set_cached_search(query: str, results: List[Dict[str, Any]]) -> None:
    """Сохраняет результаты поиска в кеш"""
    cache_key = get_cache_key("search", query)
    if len(search_cache) >= CACHE_MAX_SIZE:
        # Удаляем старые записи
        oldest_key = next(iter(search_cache))
        del search_cache[oldest_key]
    
    search_cache[cache_key] = {
        'results': results,
        'timestamp': time.time()
    }

def get_cached_image(image_url: str) -> Optional[bytes]:
    """Получает изображение из кеша"""
    cached_data = image_cache.get(image_url)
    if cached_data and time.time() - cached_data.get('timestamp', 0) < IMAGE_CACHE_TTL:
        return cached_data.get('data')
    return None

def set_cached_image(image_url: str, image_data: bytes) -> None:
    """Сохраняет изображение в кеш"""
    if len(image_cache) >= IMAGE_CACHE_MAX_SIZE:
        # Удаляем старые записи
        oldest_key = next(iter(image_cache))
        del image_cache[oldest_key]
    
    image_cache[image_url] = {
        'data': image_data,
        'timestamp': time.time()
    }

def cleanup_expired_cache():
    """Очищает истекший кеш"""
    current_time = time.time()
    
    # Очищаем кеш метаданных
    expired_tracks = [k for k, v in track_metadata_cache.items() 
                     if current_time - v.get('timestamp', 0) > CACHE_TTL]
    for k in expired_tracks:
        del track_metadata_cache[k]
    
    # Очищаем кеш поиска
    expired_searches = [k for k, v in search_cache.items() 
                       if current_time - v.get('timestamp', 0) > SEARCH_CACHE_TTL]
    for k in expired_searches:
        del search_cache[k]
    
    # Очищаем кеш изображений
    expired_images = [k for k, v in image_cache.items() 
                     if current_time - v.get('timestamp', 0) > IMAGE_CACHE_TTL]
    for k in expired_images:
        del image_cache[k]
    
    if expired_tracks or expired_searches or expired_images:
        logging.info(f"🧹 Очищен истекший кеш: {len(expired_tracks)} треков, {len(expired_searches)} поисков, {len(expired_images)} изображений")

def get_user_download_semaphore(user_id: str) -> asyncio.Semaphore:
    """Получает или создает семафор для конкретного пользователя"""
    if user_id not in user_download_semaphores:
        user_download_semaphores[user_id] = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS_PER_USER)
    return user_download_semaphores[user_id]

# === ОПТИМИЗИРОВАННЫЕ ФУНКЦИИ ДЛЯ ИЗОБРАЖЕНИЙ ===
async def get_youtube_thumbnail_optimized(video_id: str) -> Optional[bytes]:
    """Оптимизированное получение превью YouTube с кешированием"""
    try:
        # Проверяем кеш
        cached_image = get_cached_image(f"yt_{video_id}")
        if cached_image:
            return cached_image
        
        # Получаем изображение асинхронно
        thumbnail_url = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(thumbnail_url, timeout=5) as response:
                if response.status == 200:
                    image_data = await response.read()
                    # Сохраняем в кеш
                    set_cached_image(f"yt_{video_id}", image_data)
                    return image_data
                else:
                    # Пробуем стандартное превью
                    thumbnail_url = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
                    async with session.get(thumbnail_url, timeout=5) as response2:
                        if response2.status == 200:
                            image_data = await response2.read()
                            set_cached_image(f"yt_{video_id}", image_data)
                            return image_data
        
        return None
    except Exception as e:
        logging.error(f"❌ Ошибка получения превью YouTube {video_id}: {e}")
        return None

async def extract_audio_thumbnail_optimized(audio_file_path: str) -> Optional[bytes]:
    """Оптимизированное извлечение превью из аудиофайла"""
    try:
        # Проверяем кеш
        cache_key = f"audio_thumb_{hashlib.md5(audio_file_path.encode()).hexdigest()}"
        cached_image = get_cached_image(cache_key)
        if cached_image:
            return cached_image
        
        # Извлекаем превью
        from mutagen import File
        audio = File(audio_file_path)
        
        if audio and hasattr(audio, 'tags'):
            for tag_name in ['APIC:', 'APIC:cover', 'APIC:0']:
                if tag_name in audio.tags:
                    image_data = audio.tags[tag_name].data
                    # Сохраняем в кеш
                    set_cached_image(cache_key, image_data)
                    return image_data
        
        return None
    except Exception as e:
        logging.error(f"❌ Ошибка извлечения превью из {audio_file_path}: {e}")
        return None

async def cleanup_user_semaphores():
    """Очищает неиспользуемые семафоры пользователей"""
    while True:
        try:
            await asyncio.sleep(300)  # Каждые 5 минут
            current_time = time.time()
            
            # Очищаем семафоры пользователей, которые не использовались более часа
            users_to_remove = []
            for user_id, semaphore in user_download_semaphores.items():
                if hasattr(semaphore, '_last_used') and current_time - semaphore._last_used > 3600:
                    users_to_remove.append(user_id)
            
            for user_id in users_to_remove:
                del user_download_semaphores[user_id]
                
        except Exception as e:
            await asyncio.sleep(60)

async def cache_cleanup_task():
    """Фоновая задача для очистки истекшего кеша"""
    while True:
        try:
            await asyncio.sleep(600)  # Каждые 10 минут
            cleanup_expired_cache()
        except Exception as e:
            logging.error(f"❌ Ошибка очистки кеша: {e}")
            await asyncio.sleep(60)

# === УНИВЕРСАЛЬНАЯ СИСТЕМА УПРАВЛЕНИЯ ФОНОВЫМИ ЗАДАЧАМИ ===

async def run_periodic_task(task_name: str, coro_func, interval_sec: int, max_exec_time_sec: int = 300):
    """
    Универсальная функция для запуска периодических задач с мониторингом и восстановлением.
    
    Args:
        task_name: Название задачи для логирования
        coro_func: Асинхронная функция для выполнения
        interval_sec: Интервал выполнения в секундах
        max_exec_time_sec: Максимальное время выполнения задачи (по умолчанию 5 минут)
    """
    global task_last_run
    
    while True:
        try:
            # Ждем до следующего запуска
            await asyncio.sleep(interval_sec)
            
            # Запускаем задачу с ограничением времени
            start_time = time.time()
            logging.info(f"🚀 Запуск фоновой задачи: {task_name}")
            
            try:
                # Выполняем задачу с таймаутом
                await asyncio.wait_for(coro_func(), timeout=max_exec_time_sec)
                
                # Задача выполнена успешно
                execution_time = time.time() - start_time
                task_last_run[task_name] = time.time()
                logging.info(f"✅ Задача {task_name} завершена успешно за {execution_time:.2f} сек")
                
            except asyncio.TimeoutError:
                # Задача зависла
                logging.error(f"⏰ Задача {task_name} превысила время выполнения ({max_exec_time_sec} сек) и будет перезапущена")
                task_last_run[task_name] = time.time()  # Обновляем время для избежания бесконечного зависания
                
            except Exception as task_error:
                # Задача завершилась с ошибкой
                import traceback
                logging.error(f"❌ Задача {task_name} завершилась с ошибкой: {task_error}")
                logging.error(f"📋 Traceback для {task_name}:\n{traceback.format_exc()}")
                task_last_run[task_name] = time.time()  # Обновляем время для избежания бесконечных ошибок
                
        except Exception as e:
            # Ошибка в самой системе управления задачами
            import traceback
            logging.error(f"💥 Критическая ошибка в системе управления задачей {task_name}: {e}")
            logging.error(f"📋 Traceback для системы управления {task_name}:\n{traceback.format_exc()}")
            await asyncio.sleep(60)  # Ждем минуту перед повторной попыткой

async def log_task_status():
    """Логирует статус всех фоновых задач раз в час"""
    while True:
        try:
            await asyncio.sleep(3600)  # Каждый час
            
            current_time = time.time()
            logging.info("📊 === СТАТУС ФОНОВЫХ ЗАДАЧ ===")
            
            if not task_last_run:
                logging.info("📊 Нет активных фоновых задач")
            else:
                for task_name, last_run_time in task_last_run.items():
                    time_since_last_run = current_time - last_run_time
                    hours = int(time_since_last_run // 3600)
                    minutes = int((time_since_last_run % 3600) // 60)
                    
                    if time_since_last_run < 3600:
                        status = f"🟢 {hours}ч {minutes}м назад"
                    elif time_since_last_run < 7200:
                        status = f"🟡 {hours}ч {minutes}м назад"
                    else:
                        status = f"🔴 {hours}ч {minutes}м назад"
                    
                    logging.info(f"📊 {task_name}: {status}")
            
            logging.info("📊 === КОНЕЦ СТАТУСА ===")
            
        except Exception as e:
            import traceback
            logging.error(f"❌ Ошибка в log_task_status: {e}")
            logging.error(f"📋 Traceback:\n{traceback.format_exc()}")
            await asyncio.sleep(3600)  # Ждем час перед повторной попыткой

# === ОБЕРТКИ ДЛЯ ФОНОВЫХ ЗАДАЧ ===

async def task_antispam_cleanup():
    """Обертка для очистки антиспама"""
    cleanup_old_antispam_records()

async def task_file_cleanup():
    """Обертка для очистки файлов"""
    await cleanup_orphaned_files(batch_size=200)

async def task_premium_monitoring():
    """Обертка для мониторинга премиума"""
    # Проверяем истечение премиума
    await check_premium_expiry()
    # Отправляем еженедельные напоминания
    await send_weekly_premium_reminders()

async def task_cleanup_tasks():
    """Обертка для задач очистки"""
    await cleanup_orphaned_files(batch_size=200)
    # Проверяем целостность файлов премиум пользователей
    await check_premium_files_integrity()

# === СТАРЫЕ ФУНКЦИИ ЗАПУСКА ФОНОВЫХ ЗАДАЧ (ЗАМЕНЯЮТСЯ) ===

# Запускаем периодическую очистку антиспама
async def start_antispam_cleanup():
    """Запускает периодическую очистку антиспама"""
    while True:
        try:
            await asyncio.sleep(3600)  # Каждый час
            cleanup_old_antispam_records()
        except Exception as e:
            logging.error(f"❌ Ошибка в периодической очистке антиспама: {e}")

# Запускаем периодическую очистку файлов
async def start_file_cleanup():
    """Запускает периодическую очистку файлов"""
    while True:
        try:
            await asyncio.sleep(3600)  # Каждый час
            await cleanup_orphaned_files(batch_size=200)
        except Exception as e:
            if CLEANUP_LOGGING:
                logging.error(f"❌ Ошибка в периодической очистке файлов: {e}")

# Функция для запуска фоновых задач (будет вызвана при старте бота)
def start_background_tasks():
    """Запускает фоновые задачи с использованием новой системы управления"""
    try:
        # Запускаем все фоновые задачи через универсальную систему
        asyncio.create_task(run_periodic_task("Очистка антиспама", task_antispam_cleanup, 3600))
        asyncio.create_task(run_periodic_task("Очистка файлов", task_file_cleanup, 3600))
        asyncio.create_task(run_periodic_task("Мониторинг премиума", task_premium_monitoring, 3600))
        asyncio.create_task(run_periodic_task("Задачи очистки", task_cleanup_tasks, 3600))
        
        # Запускаем новую задачу очистки кеша
        asyncio.create_task(cache_cleanup_task())
        
        # Запускаем мониторинг статуса задач
        asyncio.create_task(log_task_status())
        
        # В новой логике очередь загрузок не используется, но оставляем для совместимости
        asyncio.create_task(process_download_queue())
        
        logging.info("✅ Фоновые задачи запущены с новой системой управления")
        logging.info("📊 Мониторинг статуса задач активирован")
        logging.info("💾 Новая логика: треки сохраняются как метаданные, MP3 скачиваются по требованию")
        
    except Exception as e:
        logging.error(f"❌ Ошибка запуска фоновых задач: {e}")
        import traceback
        logging.error(f"📋 Traceback:\n{traceback.format_exc()}")

# === JSON функции ===
def load_json(path, default):
    if not path:
        logging.warning("⚠️ load_json: путь не указан")
        return default
        
    if not os.path.exists(path):
        logging.info(f"📁 Файл {path} не существует, используем значение по умолчанию")
        return default
        
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if data is None:
                logging.warning(f"⚠️ Файл {path} содержит None, используем значение по умолчанию")
                return default
            return data
    except json.JSONDecodeError as e:
        logging.error(f"❌ Ошибка парсинга JSON в {path}: {e}")
        return default
    except Exception as e:
        logging.error(f"❌ Ошибка загрузки {path}: {e}")
        return default

def format_duration(seconds):
    """Форматирует длительность в секундах в читаемый вид (MM:SS или HH:MM:SS)"""
    try:
        # Проверяем, что seconds является числом и больше 0
        if not seconds or not isinstance(seconds, (int, float)) or seconds <= 0:
            return ""
        
        # Преобразуем в целое число
        seconds = int(float(seconds))
        
        # Вычисляем часы, минуты и секунды
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        # Форматируем в зависимости от длительности
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes}:{secs:02d}"
            
    except (ValueError, TypeError, OverflowError):
        return ""

def check_antispam(user_id: str) -> tuple[bool, float]:
    """Антиспам отключен - всегда разрешаем запросы"""
    return True, 0.0

def cleanup_old_antispam_records():
    """Антиспам отключен - функция не используется"""
    pass

def is_admin(user_id: str, username: str = None) -> bool:
    """Проверяет, является ли пользователь администратором"""
    try:
        # Список администраторов (ID и username)
        admin_ids = ["123456789", "987654321"]  # Добавьте сюда ID администраторов
        admin_usernames = ["wtfguys4"]  # Добавьте сюда username администраторов (без символа @)
        
        # Отладочная информация
        logging.info(f"🔍 Проверка админских прав: user_id={user_id}, username={username}")
        logging.info(f"🔍 Список админов ID: {admin_ids}")
        logging.info(f"🔍 Список админов username: {admin_usernames}")
        
        # Проверяем по ID
        if user_id and str(user_id) in admin_ids:
            logging.info(f"✅ Пользователь {user_id} найден в списке админов по ID")
            return True
            
        # Проверяем по username
        if username and username in admin_usernames:
            logging.info(f"✅ Пользователь {username} найден в списке админов по username")
            return True
            
        logging.info(f"❌ Пользователь {user_id} ({username}) не найден в списке админов")
        return False
    except Exception as e:
        logging.error(f"❌ Ошибка проверки админских прав: {e}")
        return False

def save_json(path, data):
    if not path:
        logging.error("❌ save_json: путь не указан")
        return False
        
    try:
        # Создаем директорию, если она не существует и путь не пустой
        dir_path = os.path.dirname(path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logging.info(f"✅ Данные успешно сохранены в {path}")
        return True
        
    except Exception as e:
        logging.error(f"❌ Ошибка сохранения {path}: {e}")
        return False

def is_premium_user(user_id: str, username: str = None) -> bool:
    """Функция премиум удалена - всегда возвращает False"""
    return False

def get_subscription_info(user_id: str) -> dict:
    """Функция премиум удалена - возвращает пустой словарь"""
    return {}

async def create_payment_invoice(user_id: int, chat_id: int) -> types.LabeledPrice:
    """Функция премиум удалена - заглушка"""
    pass

async def create_yoomoney_payment(user_id: str, username: str = None) -> str:
    """Функция премиум удалена - заглушка"""
    return ""

async def process_successful_payment(pre_checkout_query: types.PreCheckoutQuery):
    """Обрабатывает успешную оплату (заглушка)"""
    pass

def add_premium_user(user_id: str = None, username: str = None) -> bool:
    """Функция премиум удалена - заглушка"""
    return False

def remove_premium_user(user_id: str = None, username: str = None) -> bool:
    """Функция премиум удалена - заглушка"""
    return False

async def check_ton_payment(user_id: str, amount: float = 0.60423) -> bool:
    """Функция премиум удалена - заглушка"""
    return False

async def check_yoomoney_payment(user_id: str) -> bool:
    """Функция премиум удалена - заглушка"""
    return False
        

def generate_payment_code(user_id: str, username: str) -> str:
    """Функция премиум удалена - заглушка"""
    return "premium_disabled"

user_tracks = load_json(TRACKS_FILE, {})
search_cache = load_json(SEARCH_CACHE_FILE, {})

# Кэш для метаданных треков (URL -> метаданные)
track_metadata_cache = {}
TRACK_CACHE_MAX_SIZE = 1000  # Максимальное количество кэшированных треков

# Система очередей для быстрого добавления треков
REGULAR_QUEUE = deque()

artist_facts = load_json(ARTIST_FACTS_FILE, {"facts": {}})

def save_tracks():
    global user_tracks
    try:
        # Проверяем, что user_tracks не None
        if user_tracks is None:
            logging.warning("⚠️ save_tracks: user_tracks был None, инициализируем пустым словарем")
            user_tracks = {}
        
        # Проверяем, что user_tracks является словарем
        if not isinstance(user_tracks, dict):
            logging.error(f"❌ save_tracks: user_tracks не является словарем: {type(user_tracks)}")
            return False
        
        save_json(TRACKS_FILE, user_tracks)
        logging.info("✅ Треки успешно сохранены")
        return True
        
    except Exception as e:
        logging.error(f"❌ Ошибка сохранения треков: {e}")
        return False

def cleanup_track_cache():
    """Очищает кэш метаданных треков, если он превышает максимальный размер"""
    global track_metadata_cache
    try:
        if len(track_metadata_cache) > TRACK_CACHE_MAX_SIZE:
            # Удаляем старые записи (первые 20% от максимального размера)
            items_to_remove = int(TRACK_CACHE_MAX_SIZE * 0.2)
            keys_to_remove = list(track_metadata_cache.keys())[:items_to_remove]
            for key in keys_to_remove:
                del track_metadata_cache[key]
            logging.info(f"🧹 Кэш метаданных очищен: удалено {len(keys_to_remove)} записей")
    except Exception as e:
        logging.error(f"❌ Ошибка очистки кэша метаданных: {e}")

# Функция preload_track_metadata удалена - больше не нужна

async def add_to_download_queue_fast(user_id: str, url: str, is_premium: bool = False):
    """Быстро добавляет трек в очередь загрузки и возвращает мгновенный ответ"""
    try:
        # Проверяем входные параметры
        if not user_id or not url:
            logging.error("❌ add_to_download_queue_fast: некорректные параметры")
            return False
            
        if not isinstance(user_id, str) or not isinstance(url, str):
            logging.error("❌ add_to_download_queue_fast: некорректные типы параметров")
            return False
        
        # Создаем задачу
        task_info = {
            'user_id': user_id,
            'url': url,
            'is_premium': is_premium,
            'timestamp': time.time()
        }
        
        if is_premium:
            # Премиум пользователи идут в приоритетную очередь
            await PREMIUM_QUEUE.put((0, task_info))  # Приоритет 0 (выше)
            logging.info(f"💎 Задача добавлена в премиум очередь для пользователя {user_id}")
        else:
            # Обычные пользователи идут в обычную очередь
            REGULAR_QUEUE.append(task_info)
            logging.info(f"📱 Задача добавлена в обычную очередь для пользователя {user_id}")
        
        # Запускаем обработчик очереди в фоне
        asyncio.create_task(process_download_queue_fast())
        return True
        
    except Exception as e:
        logging.error(f"❌ Ошибка добавления задачи в очередь: {e}")
        return False

async def process_download_queue_fast():
    """Обрабатывает очередь загрузок в фоне"""
    try:
        # Сначала обрабатываем премиум очередь
        if not PREMIUM_QUEUE.empty():
            try:
                priority, task_info = await PREMIUM_QUEUE.get()
                
                if not task_info or not isinstance(task_info, dict):
                    logging.error("❌ process_download_queue_fast: некорректная задача в премиум очереди")
                    return
                    
                user_id = task_info.get('user_id')
                url = task_info.get('url')
                
                if not user_id or not url:
                    logging.error("❌ process_download_queue_fast: отсутствуют обязательные параметры")
                    return
                    
                logging.info(f"💎 Обрабатываю премиум задачу для пользователя {user_id}")
                
                # Запускаем загрузку метаданных в фоне
                asyncio.create_task(download_track_from_url(user_id, url))
                
            except Exception as premium_error:
                logging.error(f"❌ Ошибка обработки премиум задачи: {premium_error}")
                return
        
        # Затем обрабатываем обычную очередь
        if REGULAR_QUEUE:
            try:
                task_info = REGULAR_QUEUE.popleft()
                
                if not task_info or not isinstance(task_info, dict):
                    logging.error("❌ process_download_queue_fast: некорректная задача в обычной очереди")
                    return
                    
                user_id = task_info.get('user_id')
                url = task_info.get('url')
                
                if not user_id or not url:
                    logging.error("❌ process_download_queue_fast: отсутствуют обязательные параметры")
                    return
                    
                logging.info(f"📱 Обрабатываю обычную задачу для пользователя {user_id}")
                
                # Запускаем загрузку метаданных в фоне
                asyncio.create_task(download_track_from_url(user_id, url))
                
            except Exception as regular_error:
                logging.error(f"❌ Ошибка обработки обычной задачи: {regular_error}")
                return
                
    except Exception as e:
        logging.error(f"❌ Ошибка в process_download_queue_fast: {e}")

# === Экспорт cookies (опционально) ===
def export_cookies():
    try:
        if not COOKIES_FILE:
            logging.error("❌ export_cookies: COOKIES_FILE не определен")
            return False
            
        # Проверяем, доступен ли Chrome
        try:
            cj = browser_cookie3.chrome(domain_name=".youtube.com")
            if not cj:
                logging.warning("⚠️ export_cookies: cookies Chrome не найдены")
                return False
        except Exception as chrome_error:
            logging.warning(f"⚠️ export_cookies: ошибка доступа к Chrome: {chrome_error}")
            return False
        
        cj_mozilla = MozillaCookieJar()
        cookie_count = 0
        
        for cookie in cj:
            try:
                cj_mozilla.set_cookie(cookie)
                cookie_count += 1
            except Exception as cookie_error:
                logging.warning(f"⚠️ Ошибка обработки cookie: {cookie_error}")
                continue
        
        if cookie_count == 0:
            logging.warning("⚠️ export_cookies: не удалось обработать ни одного cookie")
            return False
        
        # Создаем директорию, если она не существует
        os.makedirs(os.path.dirname(COOKIES_FILE), exist_ok=True)
        
        cj_mozilla.save(COOKIES_FILE, ignore_discard=True, ignore_expires=True)
        logging.info(f"✅ Cookies экспортированы: {cookie_count} cookies сохранено в {COOKIES_FILE}")
        return True
        
    except Exception as e:
        logging.error(f"❌ Ошибка экспорта cookies: {e}")
        return False

# попробовать экспортировать, не критично если не сработает
try:
    export_cookies()
except Exception:
    pass

# небольшой diagnostic: проверим, что cookies.txt существует и можно загрузить его имена
def check_cookies_file():
    try:
        if not COOKIES_FILE:
            logging.warning("⚠️ check_cookies_file: COOKIES_FILE не определен")
            return
            
        if not os.path.exists(COOKIES_FILE):
            logging.warning("📁 Cookies файл не найден: %s", COOKIES_FILE)
            return
            
        if os.path.getsize(COOKIES_FILE) == 0:
            logging.warning("📁 Cookies файл пустой: %s", COOKIES_FILE)
            return
            
        try:
            cj = MozillaCookieJar()
            cj.load(COOKIES_FILE, ignore_discard=True, ignore_expires=True)
            
            if not cj:
                logging.warning("⚠️ check_cookies_file: cookies не загружены")
                return
                
            names = [c.name for c in cj if c.name]
            if not names:
                logging.warning("⚠️ check_cookies_file: имена cookies не найдены")
                return
                
            logging.info("🍪 Cookies загружены (%d): %s", len(names), ", ".join(names[:10]) + ("..." if len(names) > 10 else ""))
            
        except Exception as e:
            logging.warning("❌ Не удалось загрузить cookies.txt: %s", e)
            
    except Exception as e:
        logging.error(f"❌ Критическая ошибка в check_cookies_file: {e}")

check_cookies_file()

# === ФУНКЦИИ АВТОМАТИЧЕСКОЙ ОЧИСТКИ MP3 ===
async def auto_cleanup_file(file_path: str, delay: float = None, is_collection_track: bool = False, user_id: str = None):
    """
    Автоматически удаляет файл после указанной задержки.
    Используется для очистки MP3 файлов после отправки пользователю.
    
    Args:
        file_path: Путь к файлу для удаления
        delay: Задержка перед удалением (в секундах)
        is_collection_track: True если это трек из коллекции пользователя (НЕ удаляем)
        user_id: ID пользователя для проверки премиум статуса
    """
    if not AUTO_CLEANUP_ENABLED:
        if CLEANUP_LOGGING:
            logging.info(f"🧹 Автоматическая очистка отключена для файла: {file_path}")
        return False
    
    # Премиум система отключена
    is_premium = False
    
    # НЕ удаляем файлы из коллекции пользователей ИЛИ файлы премиум пользователей
    if is_collection_track or is_premium:
        if CLEANUP_LOGGING:
            status = "коллекции" if is_collection_track else "премиум пользователя"
            logging.info(f"🧹 Файл из {status} НЕ будет удален: {file_path}")
        return False
    
    try:
        # Проверяем входные параметры
        if not file_path or not isinstance(file_path, str):
            if CLEANUP_LOGGING:
                logging.warning(f"⚠️ auto_cleanup_file: некорректный путь к файлу: {file_path}")
            return False
        
        # Проверяем существование файла
        if not os.path.exists(file_path):
            if CLEANUP_LOGGING:
                logging.warning(f"⚠️ auto_cleanup_file: файл не существует: {file_path}")
            return False
        
        # Используем указанную задержку или значение по умолчанию
        cleanup_delay = delay if delay is not None else AUTO_CLEANUP_DELAY
        
        if CLEANUP_LOGGING:
            logging.info(f"🧹 Запланирована автоматическая очистка файла {file_path} через {cleanup_delay} сек.")
        
        # Запускаем асинхронную задачу очистки
        asyncio.create_task(delayed_file_cleanup(file_path, cleanup_delay))
        return True
        
    except Exception as e:
        if CLEANUP_LOGGING:
            logging.error(f"❌ Ошибка планирования автоматической очистки файла {file_path}: {e}")
        return False

async def delayed_file_cleanup(file_path: str, delay: float):
    """
    Выполняет удаление файла с задержкой.
    """
    try:
        # Ждем указанное время
        await asyncio.sleep(delay)
        
        # Проверяем, что файл все еще существует
        if not os.path.exists(file_path):
            if CLEANUP_LOGGING:
                logging.info(f"🧹 Файл уже удален: {file_path}")
            return
        
        # Получаем информацию о файле перед удалением
        try:
            file_size = os.path.getsize(file_path)
            file_size_mb = file_size / (1024 * 1024)
        except Exception:
            file_size_mb = 0
        
        # Удаляем файл
        os.remove(file_path)
        
        if CLEANUP_LOGGING:
            logging.info(f"🧹 Файл автоматически удален: {file_path} ({file_size_mb:.2f} MB)")
        
    except Exception as e:
        if CLEANUP_LOGGING:
            logging.error(f"❌ Ошибка автоматической очистки файла {file_path}: {e}")

async def cleanup_orphaned_files(batch_size: int = 200):
    """
    Асинхронно очищает "осиротевшие" файлы в папке cache, которые не привязаны к пользователям.
    Запускается периодически для освобождения места на диске.
    
    Args:
        batch_size: Максимальное количество файлов для обработки за один проход
    """
    try:
        if not AUTO_CLEANUP_ENABLED:
            return
        
        cache_dir = CACHE_DIR
        if not os.path.exists(cache_dir):
            return
        
        # Получаем список всех файлов в cache
        cache_files = set()
        for filename in os.listdir(cache_dir):
            if filename.endswith('.mp3'):
                cache_files.add(os.path.join(cache_dir, filename))
        
        if not cache_files:
            return
        
        # Получаем список файлов, привязанных к пользователям
        used_files = set()
        global user_tracks
        
        if user_tracks:
            for user_id, tracks in user_tracks.items():
                if tracks:
                    for track in tracks:
                        if isinstance(track, dict):
                            file_path = track.get('url', '').replace('file://', '')
                        else:
                            file_path = track
                        
                        if file_path and os.path.exists(file_path):
                            used_files.add(file_path)
        
        # Находим осиротевшие файлы
        orphaned_files = list(cache_files - used_files)
        
        if not orphaned_files:
            return
        
        if CLEANUP_LOGGING:
            logging.info(f"🧹 Найдено {len(orphaned_files)} осиротевших файлов для очистки")
        
        # Ограничиваем количество файлов для обработки за один проход
        files_to_process = orphaned_files[:batch_size]
        remaining_files = len(orphaned_files) - batch_size
        
        if remaining_files > 0:
            if CLEANUP_LOGGING:
                logging.info(f"🧹 Обрабатываем {len(files_to_process)} файлов за этот проход, осталось {remaining_files}")
        
        cleaned_count = 0
        total_size_freed = 0
        
        for i, orphaned_file in enumerate(files_to_process):
            try:
                if os.path.exists(orphaned_file):
                    file_size = os.path.getsize(orphaned_file)
                    os.remove(orphaned_file)
                    cleaned_count += 1
                    total_size_freed += file_size
                    
                    if CLEANUP_LOGGING:
                        logging.info(f"🧹 Удален осиротевший файл: {orphaned_file}")
                        
            except Exception as e:
                if CLEANUP_LOGGING:
                    logging.error(f"❌ Ошибка удаления осиротевшего файла {orphaned_file}: {e}")
            
            # Каждые 20 файлов делаем паузу для неблокирования event loop
            if (i + 1) % 20 == 0:
                await asyncio.sleep(0)
                if CLEANUP_LOGGING:
                    logging.info(f"🧹 Очистка: обработано {i + 1} из {len(files_to_process)} файлов")
        
        if CLEANUP_LOGGING and cleaned_count > 0:
            total_size_mb = total_size_freed / (1024 * 1024)
            logging.info(f"🧹 Очистка завершена: удалено {cleaned_count} файлов, освобождено {total_size_mb:.2f} MB")
            
            if remaining_files > 0:
                logging.info(f"🧹 В следующем цикле будет обработано еще {remaining_files} файлов")
        
    except Exception as e:
        if CLEANUP_LOGGING:
            logging.error(f"❌ Ошибка очистки осиротевших файлов: {e}")

def is_file_in_collection(file_path: str) -> bool:
    """
    Проверяет, является ли файл частью коллекции пользователей.
    
    Args:
        file_path: Путь к файлу для проверки
        
    Returns:
        True если файл находится в коллекции пользователей
    """
    try:
        global user_tracks
        
        if not user_tracks:
            return False
        
        # Нормализуем путь к файлу
        normalized_path = os.path.normpath(file_path)
        
        for user_id, tracks in user_tracks.items():
            if tracks:
                for track in tracks:
                    if isinstance(track, dict):
                        track_path = track.get('url', '').replace('file://', '')
                    else:
                        track_path = track
                    
                    if track_path and os.path.normpath(track_path) == normalized_path:
                        return True
        
        return False
        
    except Exception as e:
        if CLEANUP_LOGGING:
            logging.error(f"❌ Ошибка проверки файла в коллекции {file_path}: {e}")
        return False

async def check_file_integrity(file_path: str) -> bool:
    """
    Проверяет целостность MP3 файла.
    
    Args:
        file_path: Путь к файлу для проверки
        
    Returns:
        True если файл целый, False если поврежден
    """
    try:
        if not os.path.exists(file_path):
            return False
        
        # Проверяем размер файла
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            return False
        
        # Проверяем, что файл можно открыть
        try:
            with open(file_path, 'rb') as f:
                # Читаем первые 10 байт для проверки заголовка MP3
                header = f.read(10)
                if len(header) < 10:
                    return False
                
                # Простая проверка на MP3 файл (ID3 или MPEG header)
                if not (header.startswith(b'ID3') or header.startswith(b'\xff\xfb') or header.startswith(b'\xff\xf3')):
                    return False
                    
        except Exception:
            return False
        
        return True
        
    except Exception as e:
        if CLEANUP_LOGGING:
            logging.error(f"❌ Ошибка проверки целостности файла {file_path}: {e}")
        return False

async def auto_repair_damaged_file(file_path: str, user_id: str, original_url: str = None):
    """
    Автоматически перезагружает поврежденный файл.
    
    Args:
        file_path: Путь к поврежденному файлу
        user_id: ID пользователя
        original_url: Оригинальный URL для перезагрузки
    """
    try:
        if not original_url:
            if CLEANUP_LOGGING:
                logging.warning(f"⚠️ Нет URL для перезагрузки поврежденного файла: {file_path}")
            return False
        
        if CLEANUP_LOGGING:
            logging.info(f"🔧 Автоперезагрузка поврежденного файла: {file_path}")
        
        # Удаляем поврежденный файл
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            if CLEANUP_LOGGING:
                logging.error(f"❌ Ошибка удаления поврежденного файла {file_path}: {e}")
        
        # Перезагружаем файл
        try:
            # Премиум система отключена
            is_premium = False
            
            # Перезагружаем трек (используем глобальную функцию)
            # from music_bot import download_track_from_url_with_priority
            
            # Временно отключаем автоперезагрузку для избежания циклического импорта
            if CLEANUP_LOGGING:
                logging.warning(f"⚠️ Автоперезагрузка поврежденного файла временно отключена: {file_path}")
            return False
            
            # Автоперезагрузка временно отключена
            return False
                
        except Exception as e:
            if CLEANUP_LOGGING:
                logging.error(f"❌ Ошибка перезагрузки поврежденного файла {file_path}: {e}")
            return False
            
    except Exception as e:
        if CLEANUP_LOGGING:
            logging.error(f"❌ Критическая ошибка автоперезагрузки файла {file_path}: {e}")
        return False

async def start_premium_monitoring():
    """Функция премиум удалена - заглушка"""
    pass

async def check_premium_expiry():
    """Функция премиум удалена - заглушка"""
    pass

async def send_premium_expiry_warning(user_id: str, time_until_expiry: float):
    """Функция премиум удалена - заглушка"""
    pass

async def handle_premium_expiry(user_id: str):
    """Функция премиум удалена - заглушка"""
    pass
            
    pass

async def schedule_premium_cleanup(user_id: str, delay_seconds: int):
    """Функция премиум удалена - заглушка"""
    pass

async def cleanup_expired_premium_user(user_id: str):
    """Функция премиум удалена - заглушка"""
    pass

async def send_weekly_premium_reminders():
    """Функция премиум удалена - заглушка"""
    pass

async def start_cleanup_tasks():
    """Запускает периодические задачи очистки"""
    while True:
        try:
            await asyncio.sleep(3600)  # Каждый час
            await cleanup_orphaned_files(batch_size=200)
            
            # Проверяем целостность файлов премиум пользователей
            await check_premium_files_integrity()
            
        except Exception as e:
            if CLEANUP_LOGGING:
                logging.error(f"❌ Ошибка в периодической очистке: {e}")

async def check_premium_files_integrity(batch_size: int = 200):
    """
    Проверяет целостность файлов премиум пользователей и перезагружает поврежденные.
    
    Args:
        batch_size: Максимальное количество треков для обработки за один проход
    """
    try:
        global user_tracks
        
        if not user_tracks:
            return
        
        # Загружаем данные о премиум пользователях
        premium_data = load_json(PREMIUM_USERS_FILE, {"premium_users": [], "premium_usernames": []})
        premium_users = set(premium_data.get("premium_users", []))
        premium_usernames = set(premium_data.get("premium_usernames", []))
        
        damaged_files = []
        processed_tracks = 0
        
        for user_id, tracks in user_tracks.items():
            # Проверяем, является ли пользователь премиум
            is_premium = (user_id in premium_users)
            
            if not is_premium:
                continue
            
            if tracks:
                for track in tracks:
                    # Проверяем лимит на количество обрабатываемых треков
                    if processed_tracks >= batch_size:
                        if CLEANUP_LOGGING:
                            logging.info(f"🔧 Достигнут лимит обработки ({batch_size} треков), остальные будут проверены в следующем цикле")
                        break
                    
                    if isinstance(track, dict):
                        file_path = track.get('url', '').replace('file://', '')
                        original_url = track.get('original_url', '')  # Нужно будет добавить это поле
                    else:
                        file_path = track
                        original_url = ''  # Для старых треков URL неизвестен
                    
                    if file_path and os.path.exists(file_path):
                        # Проверяем целостность файла
                        if not await check_file_integrity(file_path):
                            damaged_files.append({
                                'file_path': file_path,
                                'user_id': user_id,
                                'original_url': original_url
                            })
                    
                    processed_tracks += 1
                    
                    # Каждые 20 треков делаем паузу для неблокирования event loop
                    if processed_tracks % 20 == 0:
                        await asyncio.sleep(0)
                        if CLEANUP_LOGGING:
                            logging.info(f"🔧 Проверка целостности: обработано {processed_tracks} треков")
                
                # Если достигли лимита, выходим из внешнего цикла
                if processed_tracks >= batch_size:
                    break
        
        # Перезагружаем поврежденные файлы
        if damaged_files:
            if CLEANUP_LOGGING:
                logging.info(f"🔧 Найдено {len(damaged_files)} поврежденных файлов премиум пользователей")
            
            for i, damaged_file in enumerate(damaged_files):
                if damaged_file['original_url']:
                    await auto_repair_damaged_file(
                        damaged_file['file_path'],
                        damaged_file['user_id'],
                        damaged_file['original_url']
                    )
                else:
                    if CLEANUP_LOGGING:
                        logging.warning(f"⚠️ Не удается перезагрузить файл без URL: {damaged_file['file_path']}")
                
                # Каждые 10 файлов делаем паузу
                if (i + 1) % 10 == 0:
                    await asyncio.sleep(0)
                    if CLEANUP_LOGGING:
                        logging.info(f"🔧 Восстановление: обработано {i + 1} из {len(damaged_files)} файлов")
        
        if CLEANUP_LOGGING:
            logging.info(f"🔧 Проверка целостности завершена: обработано {processed_tracks} треков, найдено {len(damaged_files)} поврежденных файлов")
        
    except Exception as e:
        if CLEANUP_LOGGING:
            logging.error(f"❌ Ошибка проверки целостности файлов премиум пользователей: {e}")

# === Кэш поиска ===
def get_cached_search(query):
    try:
        if not query or not isinstance(query, str):
            logging.warning("⚠️ get_cached_search: некорректный запрос")
            return None
            
        # Проверяем, что search_cache не None
        if search_cache is None:
            logging.warning("⚠️ get_cached_search: search_cache был None")
            return None
            
        query_l = query.lower()
        if query_l in search_cache:
            data = search_cache[query_l]
            if isinstance(data, dict) and "time" in data and "results" in data:
                if time.time() - data["time"] < SEARCH_CACHE_TTL:
                    return data["results"]
                else:
                    # Удаляем устаревший кэш
                    del search_cache[query_l]
                    logging.info(f"🗑️ Удален устаревший кэш для запроса: {query}")
            else:
                # Некорректная структура кэша
                logging.warning(f"⚠️ Некорректная структура кэша для запроса: {query}")
                del search_cache[query_l]
        return None
        
    except Exception as e:
        logging.error(f"❌ Ошибка в get_cached_search: {e}")
        return None

def set_cached_search(query, results):
    global search_cache
    try:
        if not query or not isinstance(query, str):
            logging.warning("⚠️ set_cached_search: некорректный запрос")
            return False
            
        if not results or not isinstance(results, list):
            logging.warning("⚠️ set_cached_search: некорректные результаты")
            return False
            
        # Проверяем, что search_cache не None
        if search_cache is None:
            logging.warning("⚠️ set_cached_search: search_cache был None, инициализируем")
            search_cache = {}
        
        # Ограничиваем размер кэша (удаляем старые записи, если их больше 100)
        if len(search_cache) > 100:
            # Удаляем самые старые записи
            sorted_cache = sorted(search_cache.items(), key=lambda x: x[1].get("time", 0))
            items_to_remove = len(sorted_cache) - 80  # Оставляем 80 записей
            for i in range(items_to_remove):
                del search_cache[sorted_cache[i][0]]
            logging.info(f"🗑️ Очищен кэш поиска, удалено {items_to_remove} старых записей")
        
        search_cache[query.lower()] = {"time": time.time(), "results": results}
        save_json(SEARCH_CACHE_FILE, search_cache)
        logging.info(f"✅ Кэш обновлен для запроса: {query}")
        return True
        
    except Exception as e:
        logging.error(f"❌ Ошибка в set_cached_search: {e}")
        return False

# === Асинхронная обёртка для yt_dlp ===
def _ydl_download_blocking(url, outtmpl, cookiefile, is_premium=False):
    """Блокирующая функция для скачивания через yt-dlp"""
    try:
        # Проверяем входные параметры
        if not url or not isinstance(url, str):
            logging.error("❌ _ydl_download_blocking: некорректный URL")
            return None
            
        if not outtmpl or not isinstance(outtmpl, str):
            logging.error("❌ _ydl_download_blocking: некорректный шаблон имени файла")
            return None
        
        # Базовые настройки
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': outtmpl,
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'extract_flat': False,  # Для загрузки нужно False
            'timeout': 300,  # Увеличиваем таймаут до 5 минут
            'retries': 3,  # Количество попыток
        }
        
        # Премиум настройки для качества 320 kbps
        if is_premium:
            ydl_opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '320'}]
            logging.info(f"💎 Премиум загрузка: качество 320 kbps для {url}")
        else:
            logging.info(f"📱 Обычная загрузка: качество 192 kbps для {url}")
        
        # Проверяем cookies файл
        if cookiefile and os.path.exists(cookiefile):
            try:
                ydl_opts['cookiefile'] = cookiefile
                logging.info(f"🍪 Используем cookies файл: {cookiefile}")
            except Exception as cookie_error:
                logging.warning(f"⚠️ Ошибка с cookies файлом: {cookie_error}")
        else:
            logging.info("🍪 Cookies файл не найден, используем поиск без авторизации")
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                # Получаем информацию о видео
                info = ydl.extract_info(url, download=True)
                
                if not info:
                    logging.error(f"❌ Не удалось получить информацию о видео: {url}")
                    return None
                
                logging.info(f"🔍 Получена информация о видео: {info.get('title', 'Без названия')}")
                
                # Получаем имя файла
                filename = ydl.prepare_filename(info)
                if not filename:
                    logging.error(f"❌ Не удалось подготовить имя файла для: {url}")
                    return None
                
                logging.info(f"🔍 Подготовлено имя файла: {filename}")
                
                # Преобразуем в .mp3
                mp3_filename = os.path.splitext(filename)[0] + ".mp3"
                logging.info(f"🔍 Ожидаемый MP3 файл: {mp3_filename}")
                
                # Проверяем, что файл действительно создался
                if not os.path.exists(mp3_filename):
                    logging.error(f"❌ MP3 файл не был создан: {mp3_filename}")
                    # Проверяем, может быть создался файл с другим расширением
                    base_name = os.path.splitext(filename)[0]
                    possible_files = [f for f in os.listdir(os.path.dirname(mp3_filename)) if f.startswith(os.path.basename(base_name))]
                    if possible_files:
                        logging.info(f"🔍 Найдены возможные файлы: {possible_files}")
                        # Возвращаем первый найденный файл
                        for possible_file in possible_files:
                            full_path = os.path.join(os.path.dirname(mp3_filename), possible_file)
                            if os.path.exists(full_path) and os.path.getsize(full_path) > 0:
                                logging.info(f"✅ Возвращаем альтернативный файл: {full_path}")
                                return full_path, info
                    return None
                
                # Проверяем размер файла
                try:
                    file_size = os.path.getsize(mp3_filename)
                    if file_size == 0:
                        logging.error(f"❌ Созданный файл пустой: {mp3_filename}")
                        return None
                    quality_text = "320 kbps" if is_premium else "192 kbps"
                    logging.info(f"✅ Файл создан успешно: {mp3_filename} ({file_size} байт, {quality_text})")
                except Exception as size_error:
                    logging.error(f"❌ Ошибка проверки размера файла: {size_error}")
                    return None
                
                # Проверяем, что файл действительно является аудио
                try:
                    with open(mp3_filename, 'rb') as f:
                        header = f.read(10)
                        if not (header.startswith(b'ID3') or header.startswith(b'\xff\xfb') or header.startswith(b'\xff\xf3')):
                            logging.warning(f"⚠️ Файл может не быть MP3: {mp3_filename}")
                except Exception as header_error:
                    logging.warning(f"⚠️ Не удалось проверить заголовок файла: {header_error}")
                
                logging.info(f"✅ Возвращаем результат: ({mp3_filename}, {type(info)})")
                return mp3_filename, info
                
            except Exception as extract_error:
                logging.error(f"❌ Ошибка извлечения информации: {extract_error}")
                return None
                
    except Exception as e:
        logging.error(f"❌ Критическая ошибка в _ydl_download_blocking: {e}")
        return None

async def download_track_from_url(user_id, url):
    """
    Асинхронно сохраняет метаданные трека в tracks.json, НЕ загружая MP3 файл.
    """
    global user_tracks, track_metadata_cache
    try:
        # Проверяем входные параметры
        if not user_id or not url:
            logging.error("❌ download_track_from_url: некорректные параметры")
            return None
        
        # Проверяем кеш для метаданных трека
        cache_key = f"metadata_{hashlib.md5(url.encode()).hexdigest()}"
        cached_metadata = get_cached_metadata(cache_key)
        
        if cached_metadata:
            logging.info(f"🎯 Используем кешированные метаданные для {url}")
            return cached_metadata
            
        # Проверяем, что user_tracks не None
        if user_tracks is None:
            logging.warning("⚠️ download_track_from_url: user_tracks был None, инициализируем")
            user_tracks = {}
        
        # Проверяем кэш метаданных
        if url in track_metadata_cache:
            logging.info(f"💾 Используем кэшированные метаданные для {url}")
            cached_info = track_metadata_cache[url]
            
            # Инициализируем список треков для пользователя, если его нет
            if str(user_id) not in user_tracks:
                user_tracks[str(user_id)] = []
            elif user_tracks[str(user_id)] is None:
                user_tracks[str(user_id)] = []
                
            user_tracks[str(user_id)].append(cached_info)
            save_tracks()
            
            logging.info(f"✅ Метаданные трека из кэша успешно добавлены для пользователя {user_id}: {cached_info.get('title', 'Неизвестный трек')}")
            return True
        else:
            logging.info(f"💾 Сохраняю метаданные трека для пользователя {user_id}: {url}")
        
        # Получаем информацию о треке без скачивания
        try:
            ydl_opts = {
                'format': 'bestaudio/best',
                'quiet': True,
                'no_warnings': True,
                'ignoreerrors': True,
                'extract_flat': True,  # Только метаданные, без скачивания
                'timeout': 10,  # Уменьшаем таймаут для быстрого ответа
                'retries': 1,   # Уменьшаем количество попыток
                'nocheckcertificate': True,  # Пропускаем проверку сертификата для скорости
            }
            
            # Проверяем cookies файл
            if os.path.exists(COOKIES_FILE):
                ydl_opts['cookiefile'] = COOKIES_FILE
                logging.info(f"🍪 Используем cookies файл: {COOKIES_FILE}")
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    logging.error(f"❌ Не удалось получить информацию о треке: {url}")
                    return None
                
                # Извлекаем метаданные
                title = info.get('title', 'Неизвестный трек')
                duration = info.get('duration', 0)
                uploader = info.get('uploader', 'Неизвестный исполнитель')
                
                # Создаем запись с метаданными (без файла)
                track_info = {
                    "title": title,
                    "url": "",  # Пустой URL - файл не загружен
                    "original_url": url,  # Сохраняем оригинальную ссылку для скачивания
                    "duration": duration,
                    "uploader": uploader,
                    "size_mb": 0,  # Размер неизвестен до скачивания
                    "needs_migration": False,
                    "downloaded": False  # Флаг, что файл не загружен
                }
                
                # Сохраняем в кэш для будущего использования
                track_metadata_cache[url] = track_info
                
                # Сохраняем в расширенный кеш
                set_cached_metadata(cache_key, track_info)
                
                logging.info(f"💾 Метаданные сохранены в кэш для {url}")
                
                # Очищаем кэш, если он превышает максимальный размер
                cleanup_track_cache()
                
                # Инициализируем список треков для пользователя, если его нет
                if str(user_id) not in user_tracks:
                    user_tracks[str(user_id)] = []
                elif user_tracks[str(user_id)] is None:
                    user_tracks[str(user_id)] = []
                    
                user_tracks[str(user_id)].append(track_info)
                save_tracks()
                
                logging.info(f"✅ Метаданные трека успешно сохранены для пользователя {user_id}: {title}")
                return True
                
        except Exception as info_error:
            logging.error(f"❌ Ошибка получения информации о треке: {info_error}")
            return None
        
    except Exception as e:
        logging.exception(f"❌ Ошибка сохранения метаданных трека {url} для пользователя {user_id}: {e}")
        return None

# === Состояния ===
class SearchStates(StatesGroup):
    waiting_for_search = State()
    waiting_for_artist = State()
    waiting_for_artist_search = State()

# === Главное меню ===
main_menu = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="🐻‍❄️ Поиск музыки", callback_data="find_track"),
                    InlineKeyboardButton(text="🌨️ Моя музыка", callback_data="my_music")
                ],
                [
                    InlineKeyboardButton(text="🌨️ По исполнителям", callback_data="by_artist")
                ]
            ]
        )

# === Меню поиска по исполнителям ===
artist_search_menu = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="🐻‍❄️ Исполнители", callback_data="search_by_artist")
        ],
        [InlineKeyboardButton(text="⬅ Назад в главное меню", callback_data="back_to_main")]
    ]
)

back_button = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_main")]]
)

# === Callback обработчики для главного меню ===
@dp.callback_query(F.data == "back_to_main")
async def back_to_main_menu(callback: types.CallbackQuery):
    """Возвращает пользователя в главное меню"""
    # Быстрый ответ для ускорения
    await callback.answer("⏳ Обрабатываю...")
    
    user_id = str(callback.from_user.id)
    
    # Проверяем антиспам
    is_allowed, time_until = check_antispam(user_id)
    if not is_allowed:
        await callback.answer(f"⏳ Подождите {time_until:.1f} сек. перед следующим запросом", show_alert=True)
        return
    
    try:
        # Проверяем кеш для главного меню
        cache_key = f"main_menu_{user_id}"
        cached_menu = get_cached_metadata(cache_key)
        
        if cached_menu:
            logging.info(f"🎯 Используем кешированное главное меню для пользователя {user_id}")
            # Восстанавливаем главное меню из кеша
            await callback.message.edit_media(
                media=types.InputMediaVideo(
                    media=types.FSInputFile("beer.mp4")
                ),
                reply_markup=main_menu
            )
        else:
            # Удаляем предыдущее inline-сообщение
            await callback.message.delete()
            
            # Отправляем видео без текста, только с меню
            await callback.message.answer_video(
                video=types.FSInputFile("beer.mp4"),
                reply_markup=main_menu
            )
            
            # Сохраняем в кеш
            menu_data = {'menu': 'main_menu'}
            set_cached_metadata(cache_key, menu_data)
    except Exception as e:
        # Если что-то пошло не так, просто отправляем главное меню
        try:
            await callback.message.answer_video(
                video=types.FSInputFile("beer.mp4"),
                reply_markup=main_menu
            )
        except Exception as photo_error:
            await callback.message.answer("🐻 Главное меню", reply_markup=main_menu)

# === Команды ===
@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    user_id = str(message.from_user.id)
    
    # Проверяем кеш для приветственного сообщения
    cache_key = f"welcome_{user_id}"
    cached_welcome = get_cached_metadata(cache_key)
    
    if cached_welcome:
        logging.info(f"🎯 Используем кешированное приветственное сообщение для пользователя {user_id}")
        # Восстанавливаем приветственное сообщение из кеша
        await message.answer_video(
            video=types.FSInputFile("beer.mp4"),
            reply_markup=main_menu
        )
    else:
        # Отправляем видео без текста, только с меню
        try:
            await message.answer_video(
                video=types.FSInputFile("beer.mp4"),
                reply_markup=main_menu
            )
            
            # Сохраняем в кеш
            welcome_data = {'welcome': 'start_command'}
            set_cached_metadata(cache_key, welcome_data)
        except Exception as e:
            # Если не удалось отправить фото, отправляем обычное сообщение
            logging.error(f"❌ Ошибка отправки фото: {e}")
            await message.answer("🐻 Привет! Я бот для поиска и скачивания музыки с YouTube.", reply_markup=main_menu)

@dp.callback_query(F.data == "by_artist")
async def by_artist_section(callback: types.CallbackQuery, state: FSMContext):
    """Открывает поиск по исполнителю"""
    # Быстрый ответ для ускорения
    await callback.answer("⏳ Обрабатываю...")
    
    user_id = str(callback.from_user.id)
    
    # Проверяем антиспам
    is_allowed, time_until = check_antispam(user_id)
    if not is_allowed:
        await callback.answer(f"⏳ Подождите {time_until:.1f} сек. перед следующим запросом", show_alert=True)
        return
    
    try:
        # Проверяем кеш для состояния поиска по исполнителю
        cache_key = f"by_artist_{user_id}"
        cached_state = get_cached_metadata(cache_key)
        
        if cached_state:
            logging.info(f"🎯 Используем кешированное состояние для поиска по исполнителю пользователя {user_id}")
            # Восстанавливаем состояние из кеша
            await state.set_state(SearchStates.waiting_for_artist_search)
            await state.update_data(prompt_message_id=cached_state.get('prompt_message_id'))
        else:
            # Переходим в состояние ожидания ввода имени исполнителя
            await state.set_state(SearchStates.waiting_for_artist_search)
            
            # Отправляем сообщение с запросом имени исполнителя (без кнопки "Назад")
            # Сохраняем ID сообщения для последующего удаления
            msg = await callback.message.answer("🌨️ Введите исполнителя")
            await state.update_data(prompt_message_id=msg.message_id)
            
            # Сохраняем состояние в кеш
            state_data = {'prompt_message_id': msg.message_id}
            set_cached_metadata(cache_key, state_data)
        
    except Exception as e:
        await callback.answer("❌ Произошла ошибка. Попробуйте еще раз.", show_alert=True)

@dp.callback_query(F.data == "premium_features")
async def show_artist_search_menu(callback: types.CallbackQuery, state: FSMContext):
    """Функция премиум удалена - перенаправляет в главное меню"""
    await callback.answer("❌ Премиум функции отключены")
    await callback.message.edit_media(
        media=types.InputMediaVideo(
            media=types.FSInputFile("beer.mp4")
        ),
        reply_markup=main_menu
    )

@dp.callback_query(F.data == "buy_premium")
async def show_buy_premium_info(callback: types.CallbackQuery):
    """Функция премиум удалена - перенаправляет в главное меню"""
    await callback.answer("❌ Премиум функции отключены")
    await callback.message.edit_media(
        media=types.InputMediaVideo(
            media=types.FSInputFile("beer.mp4")
        ),
        reply_markup=main_menu
    )

@dp.callback_query(F.data == "pay_yoomoney")
async def pay_premium_yoomoney(callback: types.CallbackQuery):
    """Функция премиум удалена - заглушка"""
    await callback.answer("❌ Премиум функции отключены")
    
    # Проверяем антиспам
    is_allowed, time_until = check_antispam(user_id)
    if not is_allowed:
        await callback.answer(f"⏳ Подождите {time_until:.1f} сек. перед следующим запросом", show_alert=True)
        return
    
    # Просто возвращаемся в главное меню
    try:
        await callback.message.edit_media(
            media=types.InputMediaVideo(
                media=types.FSInputFile("beer.mp4")
            ),
            reply_markup=main_menu
        )
    except Exception as e:
        logging.error(f"❌ Ошибка возврата в главное меню: {e}")
        await callback.message.answer("🐻‍❄️ Главное меню", reply_markup=main_menu)

@dp.callback_query(F.data == "pay_premium")
async def pay_premium_direct(callback: types.CallbackQuery):
    """Функция премиум удалена - заглушка"""
    await callback.answer("❌ Премиум функции отключены")

# Упрощенная функция - больше не нужна
# @dp.message(F.text == "💎 Оплатить через TON кошелек")
# async def pay_with_ton_wallet(message: types.Message):
#     pass

# Упрощенная функция - больше не нужна
# @dp.message(F.text == "💳 Оплатить картой")
# async def pay_with_card(message: types.Message):
#     pass

# Удаляем эту функцию, так как теперь используется callback

# Упрощенная функция - больше не нужна
# @dp.message(F.text == "✅ Я уже оплатил")
# async def confirm_payment(message: types.Message):
#     pass

@dp.callback_query(F.data == "back_to_premium")
async def back_to_premium_menu(callback: types.CallbackQuery):
    """Функция премиум удалена - заглушка"""
    await callback.answer("❌ Премиум функции отключены")

# Упрощенная callback функция - больше не нужна
# @dp.callback_query(F.data == "confirm_payment")
# async def confirm_payment_callback(callback: types.CallbackQuery):
#     """Подтверждение оплаты пользователем"""
#     # ... код удален для упрощения

# Упрощенная callback функция - больше не нужна
# @dp.callback_query(F.data == "pay_ton")
# async def pay_with_ton_callback(callback: types.CallbackQuery):
#     """Обработка нажатия на кнопку оплаты через TON"""
#     # ... код удален для упрощения

# Упрощенная callback функция - больше не нужна
# @dp.callback_query(F.data == "back_to_payment")
# async def back_to_payment_page(callback: types.CallbackQuery):
#     """Возврат к странице оплаты"""
#     # ... код удален для упрощения

@dp.callback_query(F.data == "back_to_buy_premium")
async def back_to_buy_premium_callback(callback: types.CallbackQuery):
    """Функция премиум удалена - заглушка"""
    await callback.answer("❌ Премиум функции отключены")

@dp.callback_query(F.data == "back_to_main_from_buy_premium")
async def back_to_main_from_buy_premium_callback(callback: types.CallbackQuery):
    """Функция премиум удалена - заглушка"""
    await callback.answer("❌ Премиум функции отключены")

# === Обработчики автоматической оплаты ===
@dp.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: types.PreCheckoutQuery):
    pass

@dp.message(F.successful_payment)
async def successful_payment(message: types.Message):
    pass

@dp.message(Command("add_premium"))
async def add_premium_command(message: types.Message):
    """Команда премиум удалена - заглушка"""
    await message.answer("❌ Премиум функции отключены")

@dp.message(Command("remove_premium"))
async def remove_premium_command(message: types.Message):
    """Команда премиум удалена - заглушка"""
    await message.answer("❌ Премиум функции отключены")

# === Поиск ===
@dp.callback_query(F.data == "find_track")
async def ask_track_name(callback: types.CallbackQuery, state: FSMContext):
    # Быстрый ответ для ускорения
    await callback.answer("⏳ Обрабатываю...")
    
    user_id = str(callback.from_user.id)
    
    # Проверяем антиспам
    is_allowed, time_until = check_antispam(user_id)
    if not is_allowed:
        await callback.answer(f"⏳ Подождите {time_until:.1f} сек. перед следующим запросом", show_alert=True)
        return
    
    # Проверяем кеш для поиска трека
    cache_key = f"find_track_{user_id}"
    cached_search = get_cached_metadata(cache_key)
    
    if cached_search:
        logging.info(f"🎯 Используем кешированное состояние поиска для пользователя {user_id}")
        # Восстанавливаем состояние из кеша
        await state.set_state(SearchStates.waiting_for_search)
        # Отправляем кешированное сообщение
        await callback.message.answer_video(
            video=types.FSInputFile("beer.mp4"),
            caption=cached_search.get('caption', "🎵Введите название"),
            reply_markup=back_button
        )
    else:
        # Удаляем предыдущее сообщение для чистоты чата
        try:
            await callback.message.delete()
        except:
            pass  # Игнорируем ошибки удаления
        
        # Отправляем изображение мишки с запросом названия трека
        try:
            caption_text = "🎵Введите название"
            await callback.message.answer_video(
                video=types.FSInputFile("beer.mp4"),
                caption=caption_text,
                reply_markup=back_button
            )
            
            # Сохраняем в кеш
            search_data = {'caption': caption_text}
            set_cached_metadata(cache_key, search_data)
        except Exception as e:
            # Если не удалось отправить фото, отправляем обычное сообщение
            await callback.message.edit_text("🎵Введите название", reply_markup=back_button)
        
        await state.set_state(SearchStates.waiting_for_search)

@dp.callback_query(F.data == "back_to_main")
async def back_from_track_search_handler(callback: types.CallbackQuery, state: FSMContext):
    """Возврат из поиска трека в главное меню"""
    user_id = str(callback.from_user.id)
    
    # Проверяем антиспам
    is_allowed, time_until = check_antispam(user_id)
    if not is_allowed:
        await callback.answer(f"⏳ Подождите {time_until:.1f} сек. перед следующим запросом", show_alert=True)
        return
    
    await state.clear()
    
    # Проверяем кеш для возврата в главное меню
    cache_key = f"back_from_search_{user_id}"
    cached_back = get_cached_metadata(cache_key)
    
    if cached_back:
        logging.info(f"🎯 Используем кешированное возвращение в главное меню для пользователя {user_id}")
        # Восстанавливаем главное меню из кеша
        await callback.message.edit_media(
            media=types.InputMediaVideo(
                media=types.FSInputFile("beer.mp4")
            ),
            reply_markup=main_menu
        )
    else:
        # Удаляем предыдущее сообщение для чистоты чата
        try:
            await callback.message.delete()
        except:
            pass  # Игнорируем ошибки удаления
        
        # Отправляем видео без текста, только с меню
        try:
            await callback.message.answer_video(
                video=types.FSInputFile("beer.mp4"),
                reply_markup=main_menu
            )
            
            # Сохраняем в кеш
            back_data = {'back': 'from_search'}
            set_cached_metadata(cache_key, back_data)
        except Exception as e:
            # Если не удалось отправить фото, отправляем обычное сообщение
            await callback.message.edit_text("🔙 Возврат в главное меню", reply_markup=main_menu)

@dp.message(SearchStates.waiting_for_artist_search, F.text)
async def search_by_artist(message: types.Message, state: FSMContext):
    """Поиск треков по исполнителю - СТРОГО YouTube с улучшенной фильтрацией"""
    artist = message.text.strip()
    user_id = str(message.from_user.id)
    
    # Удаляем надпись "🌨️ Введите исполнителя" после запуска поиска
    try:
        # Получаем ID сообщения с надписью из состояния
        state_data = await state.get_data()
        prompt_message_id = state_data.get('prompt_message_id')
        
        if prompt_message_id:
            # Удаляем сообщение по ID
            await message.bot.delete_message(message.chat.id, prompt_message_id)
    except:
        pass  # Игнорируем ошибки удаления
    
    await state.clear()

    # Проверяем, что запрос не пустой
    if not artist:
        await message.answer("❌ Пожалуйста, введите имя исполнителя.", reply_markup=main_menu)
        return

    try:
        # Проверяем кеш для поиска по исполнителю
        cache_key = f"search_by_artist_{artist.lower().strip()}_{user_id}"
        cached_results = get_cached_metadata(cache_key)
        
        if cached_results:
            logging.info(f"🎯 Используем кешированные результаты поиска по исполнителю {artist} для пользователя {user_id}")
            youtube_results = cached_results
        else:
            # Ищем СТРОГО на YouTube - никакого SoundCloud
            try:
                youtube_results = await asyncio.wait_for(
                    search_youtube_artist_improved(artist),
                    timeout=30.0
                )
                
                # Сохраняем в кеш
                if youtube_results:
                    set_cached_metadata(cache_key, youtube_results)
            except Exception as e:
                youtube_results = None
        
        if not youtube_results or not youtube_results.get('entries'):
            await message.answer(f"❄️ Не найдено треков исполнителя '{artist}'. Попробуйте другое имя.", reply_markup=main_menu)
            return
        
        # Фильтруем треки по длительности (минимум 1 минута) и качеству
        filtered_tracks = []
        for entry in youtube_results['entries']:
            if entry and entry.get('id') and entry.get('title'):
                # Проверяем длительность - минимум 60 секунд
                duration = entry.get('duration', 0)
                if duration < 60:
                    continue
                
                # Проверяем максимальную длительность - максимум 10 минут
                if duration > 600:
                    continue
                
                entry['source'] = 'yt'
                filtered_tracks.append(entry)
        
        if not filtered_tracks:
            await message.answer(f"❄️ Не найдено подходящих треков исполнителя '{artist}' (все треки слишком короткие или длинные).", reply_markup=main_menu)
            return
        
        # Перемешиваем и берем первые 10 (улучшенная рандомизация)
        import random
        # Используем seed на основе времени и user_id для лучшей рандомизации
        random.seed(int(time.time()) + hash(user_id))
        random.shuffle(filtered_tracks)
        selected_tracks = filtered_tracks[:10]
        
        # Сообщаем пользователю о количестве треков
        await message.answer(f"❄️ Найдено {len(selected_tracks)} треков исполнителя '{artist}'. Скачиваю...")
        
        # Отправляем треки как аудиофайлы
        await send_tracks_as_audio(user_id, selected_tracks, None)
        
    except Exception as e:
        await message.answer("❌ Произошла ошибка при поиске. Попробуйте еще раз.", reply_markup=main_menu)

@dp.message(SearchStates.waiting_for_search, F.text)
async def search_music(message: types.Message, state: FSMContext):
    query = message.text.strip()
    user_id = str(message.from_user.id)
    start_time = time.time()  # Добавляем отсчет времени
    await state.clear()

    # Проверяем, что запрос не пустой
    if not query:
        await message.answer("❌ Пожалуйста, введите название песни или ссылку.", reply_markup=main_menu)
        return

    yt_url_pattern = r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+"
    if re.match(yt_url_pattern, query):
        # асинхронно сохраняем метаданные в background (не блокируем основной цикл)
        asyncio.create_task(download_track_from_url(message.from_user.id, query))
        return await message.answer("✅ Трек добавлен в вашу коллекцию!", show_alert=True)

    search_msg = await message.answer("🔍 Поиск...")

    cached = get_cached_search(query)
    if cached:
        # Удаляем сообщение "Поиск.." если используем кэш
        await search_msg.delete()
        return await send_search_results(message.chat.id, cached)
    try:
        # Выполняем поиск на YouTube и SoundCloud параллельно
        async def search_youtube(q):
            try:
                # Проверяем кеш для поиска
                cache_key = f"youtube_search_{q.lower().strip()}"
                cached_results = get_cached_search(cache_key)
                
                if cached_results:
                    logging.info(f"🎯 Используем кешированные результаты YouTube для запроса '{q}'")
                    return cached_results
                
                def search_block(q):
                    try:
                        ydl_opts = {
                            'format': 'bestaudio/best',
                            'noplaylist': True,
                            'quiet': True,
                            'no_warnings': True,
                            'ignoreerrors': True,
                            'extract_flat': True
                        }
                        
                        # Проверяем существование cookies файла
                        if os.path.exists(COOKIES_FILE):
                            ydl_opts['cookiefile'] = COOKIES_FILE
                        
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            search_query = f"ytsearch5:{q}"  # Оптимально: 5 лучших результатов
                            result = ydl.extract_info(search_query, download=False)
                            if not result:
                                return None
                            return result
                    except Exception as search_error:
                        return None
                
                result = await asyncio.wait_for(
                    asyncio.to_thread(search_block, q),
                    timeout=12.0  # Еще уменьшили таймаут для ускорения
                )
                
                # Сохраняем результаты в кеш
                if result:
                    set_cached_search(cache_key, result)
                
                return result
            except Exception as e:
                return None
        
        # Запускаем поиск только на YouTube
        youtube_task = asyncio.create_task(search_youtube(query))
        
        # Ждем результаты от YouTube с таймаутом 18 секунд
        try:
            youtube_info = await asyncio.wait_for(youtube_task, timeout=18.0)
        except asyncio.TimeoutError:
            youtube_task.cancel()
            youtube_info = None
        
        soundcloud_results = None
        
        # Обрабатываем результаты YouTube
        logging.info(f"🔍 Обрабатываем результаты YouTube: {type(youtube_info)}")
        youtube_results = []
        if isinstance(youtube_info, Exception):
            logging.error(f"❌ Ошибка поиска YouTube: {youtube_info}")
        elif youtube_info:
            results = youtube_info.get("entries", [])
            logging.info(f"🔍 YouTube entries: {type(results)}, количество: {len(results) if results else 0}")
            if results:
                # Фильтруем только невалидные результаты (длительность будет проверяться позже)
                for i, result in enumerate(results):
                    logging.info(f"🔍 YouTube результат {i+1}: {result}")
                    if result and result.get('id') and result.get('title'):
                        # Добавляем источник
                        result['source'] = 'yt'
                        youtube_results.append(result)
                    else:
                        pass
            else:
                pass
        else:
            pass
        
        # Обрабатываем результаты SoundCloud
        soundcloud_processed = []
        if isinstance(soundcloud_results, Exception):
            pass
        elif soundcloud_results:
            for result in soundcloud_results:
                if result and result.get('url') and result.get('title'):
                    # Добавляем источник
                    result['source'] = 'sc'
                    soundcloud_processed.append(result)
        
        # Объединяем результаты
        all_results = youtube_results + soundcloud_processed
        
        if not all_results:
            # Если обе платформы не дали результатов, пробуем только YouTube
            try:
                youtube_only = await asyncio.wait_for(
                    search_youtube(query),
                    timeout=20.0
                )
                if youtube_only and youtube_only.get('entries'):
                    youtube_results = []
                    for result in youtube_only.get('entries', []):
                        if result and result.get('id') and result.get('title'):
                            result['source'] = 'yt'
                            youtube_results.append(result)
                    
                    if youtube_results:
                        all_results = youtube_results[:20]
                    else:
                        await search_msg.delete()
                        await message.answer("❄️ Ничего не нашёл. Попробуйте изменить запрос.", reply_markup=main_menu)
                        return
                else:
                    await search_msg.delete()
                    await message.answer("❄️ Ничего не нашёл. Попробуйте изменить запрос.", reply_markup=main_menu)
                    return
            except asyncio.TimeoutError:
                await search_msg.delete()
                await message.answer("❄️ Поиск занял слишком много времени. Попробуйте еще раз.", reply_markup=main_menu)
                return
            except Exception as e:
                await search_msg.delete()
                await message.answer("❄️ Ничего не нашёл. Попробуйте изменить запрос.", reply_markup=main_menu)
                return
        
        # Сортируем по релевантности (простая эвристика - сначала короткие названия)
        all_results.sort(key=lambda x: len(x.get('title', '')))
        
        # Гарантируем 5 YouTube + 5 SoundCloud результатов
        youtube_results_filtered = [r for r in all_results if r.get('source') != 'sc'][:5]
        soundcloud_results_filtered = [r for r in all_results if r.get('source') == 'sc'][:5]
        
        # Объединяем результаты
        final_results = youtube_results_filtered + soundcloud_results_filtered
        
        # Удаляем сообщение "Поиск.." перед отправкой результатов
        await search_msg.delete()
        
        set_cached_search(query, final_results)
        await send_search_results(message.chat.id, final_results)
        
    except asyncio.TimeoutError:
        try:
            await search_msg.delete()
        except:
            pass
        await message.answer("❄️ Поиск занял слишком много времени. Попробуйте еще раз.", reply_markup=main_menu)
    except Exception as e:
        try:
            await search_msg.delete()
        except:
            pass
        await message.answer("❌ Произошла ошибка при поиске. Попробуйте еще раз позже.", reply_markup=main_menu)

@dp.message(SearchStates.waiting_for_artist, F.text)
async def search_by_artist_input(message: types.Message, state: FSMContext):
    """Обрабатывает ввод имени исполнителя"""
    artist_name = message.text.strip()
    user_id = str(message.from_user.id)
    await state.clear()

    logging.info(f"👤 Поиск по исполнителю для пользователя {user_id}: '{artist_name}'")

    # Отправляем видео с сообщением о начале поиска
    try:
        search_msg = await message.answer_video(
            video=types.FSInputFile("beer.mp4"),
            caption=f"🔍 **Поиск треков исполнителя {artist_name}...**\n\n"
                    "🎵 Ищу лучшие треки на YouTube и SoundCloud...\n"
                    "⏳ Это может занять несколько минут.",
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"❌ Ошибка отправки фото: {e}")
        search_msg = await message.answer(
            f"🔍 **Поиск треков исполнителя {artist_name}...**\n\n"
            "🎵 Ищу лучшие треки на YouTube и SoundCloud...\n"
            "⏳ Это может занять несколько минут.",
            parse_mode="Markdown"
        )

    try:
        # Проверяем кеш для поиска по исполнителю
        cache_key = f"artist_{artist_name.lower().strip()}"
        cached_results = get_cached_search(cache_key)
        
        if cached_results:
            logging.info(f"🎯 Используем кешированные результаты для исполнителя {artist_name}")
            results = cached_results
        else:
            # Ищем треки исполнителя
            results = await asyncio.to_thread(search_artist_tracks, artist_name, 20)
            # Сохраняем в кеш
            if results:
                set_cached_search(cache_key, results)
        
        if not results:
            try:
                await search_msg.edit_media(
                    media=types.InputMediaVideo(
                        media=types.FSInputFile("beer.mp4"),
                        caption=f"❌ **Ничего не найдено**\n\n"
                                f"🚫 По исполнителю '{artist_name}' ничего не найдено.\n"
                                "💡 Возможные причины:\n"
                                "• Неправильное написание имени\n"
                                "• Исполнитель не представлен на YouTube или SoundCloud\n"
                                "• Ограничения по региону\n\n"
                                "🔍 Попробуйте:\n"
                                "• Проверить правильность написания\n"
                                "• Использовать другое имя\n"
                                "• Поискать альтернативные варианты"
                    ),
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="👤 Поиск другого исполнителя", callback_data="search_artist_again")],
                        [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_main")]
                    ])
                )
            except Exception as e:
                logging.error(f"❌ Ошибка отправки фото: {e}")
                await search_msg.edit_text(
                    f"❌ **Ничего не найдено**\n\n"
                    f"🚫 По исполнителю '{artist_name}' ничего не найдено.\n"
                    "💡 Возможные причины:\n"
                    "• Неправильное написание имени\n"
                    "• Исполнитель не представлен на YouTube или SoundCloud\n"
                    "• Ограничения по региону\n\n"
                    "🔍 Попробуйте:\n"
                    "• Проверить правильность написания\n"
                    "• Использовать другое имя\n"
                    "• Поискать альтернативные варианты",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="👤 Поиск другого исполнителя", callback_data="search_artist_again")],
                        [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_main")]
                    ])
                )
            return

        # Обновляем сообщение о начале загрузки
        try:
            await search_msg.edit_media(
                media=types.InputMediaVideo(
                    media=types.FSInputFile("beer.mp4"),
                    caption=f"⏳ **Загружаю {len(results)} треков исполнителя {artist_name}...**\n\n"
                            "🎵 Скачиваю аудиофайлы для прослушивания...\n"
                            "💡 Это может занять несколько минут."
                ),
                parse_mode="Markdown"
            )
        except Exception as e:
            logging.error(f"❌ Ошибка отправки фото: {e}")
            await search_msg.edit_text(
                f"⏳ **Загружаю {len(results)} треков исполнителя {artist_name}...**\n\n"
                "🎵 Скачиваю аудиофайлы для прослушивания...\n"
                "💡 Это может занять несколько минут.",
                parse_mode="Markdown"
            )

        # Скачиваем треки и отправляем их
        downloaded_tracks = []
        failed_tracks = []

        for i, track in enumerate(results, 1):
            try:
                # Обновляем прогресс
                try:
                    await search_msg.edit_media(
                        media=types.InputMediaVideo(
                            media=types.FSInputFile("beer.mp4"),
                            caption=f"⏳ **Загружаю трек {i}/{len(results)} исполнителя {artist_name}...**\n\n"
                                    f"🎵 **{track.get('title', 'Без названия')}**\n"
                                    "💾 Скачиваю аудиофайл..."
                        ),
                        parse_mode="Markdown"
                    )
                except Exception as edit_error:
                    logging.error(f"❌ Ошибка обновления прогресса: {edit_error}")

                # Скачиваем трек
                url = f"https://www.youtube.com/watch?v={track['id']}"
                
                try:
                    download_task = asyncio.create_task(
                        download_track_from_url_for_genre(user_id, url)
                    )
                    filename = await asyncio.wait_for(download_task, timeout=120.0)  # 2 минуты таймаут
                except asyncio.TimeoutError:
                    logging.error(f"❌ Таймаут загрузки трека {track.get('title', 'Без названия')}")
                    failed_tracks.append(f"{track.get('title', 'Без названия')} (таймаут загрузки)")
                    continue

                if filename:
                    # Проверяем размер файла
                    try:
                        file_size = os.path.getsize(filename)
                        file_size_mb = file_size / (1024 * 1024)
                        
                        if file_size_mb > MAX_FILE_SIZE_MB:
                            logging.warning(f"⚠️ Файл слишком большой для отправки: {file_size_mb:.2f}MB > {MAX_FILE_SIZE_MB}MB")
                            failed_tracks.append(f"{track.get('title', 'Без названия')} (слишком большой файл)")
                            try:
                                os.remove(filename)
                            except:
                                pass
                            continue
                        
                        downloaded_tracks.append({
                            'filename': filename,
                            'title': track.get('title', 'Без названия'),
                            'duration': track.get('duration', 0),
                            'size_mb': file_size_mb
                        })
                    except Exception as size_error:
                        logging.error(f"❌ Ошибка проверки размера файла {track.get('title', 'Без названия')}: {size_error}")
                        failed_tracks.append(f"{track.get('title', 'Без названия')} (ошибка проверки размера)")
                        continue

                    # Отправляем аудиофайл
                    try:
                        await message.answer_audio(
                            types.FSInputFile(filename),
                            title=track.get('title', 'Без названия'),
                            performer=artist_name,
                            duration=track.get('duration', 0)
                        )
                        logging.info(f"✅ Аудиофайл отправлен: {track.get('title', 'Без названия')}")
                        
                        # Удаляем временный файл после отправки
                        await delete_temp_file(filename)
                        
                    except Exception as audio_error:
                        logging.error(f"❌ Ошибка отправки аудиофайла {track.get('title', 'Без названия')}: {audio_error}")
                        # Если не удалось отправить как аудио, отправляем как документ
                        try:
                            await message.answer_document(
                                types.FSInputFile(filename),
                                caption=f"🎵 **{track.get('title', 'Без названия')}**\n👤 Исполнитель: {artist_name}"
                            )
                            logging.info(f"✅ Файл отправлен как документ: {track.get('title', 'Без названия')}")
                            
                            # Удаляем временный файл после отправки
                            await delete_temp_file(filename)
                            
                        except Exception as doc_error:
                            logging.error(f"❌ Ошибка отправки документа {track.get('title', 'Без названия')}: {doc_error}")
                            failed_tracks.append(track.get('title', 'Без названия'))
                            continue

                    # Небольшая задержка между отправками
                    await asyncio.sleep(0.5)

                else:
                    failed_tracks.append(track.get('title', 'Без названия'))

            except Exception as e:
                logging.error(f"❌ Ошибка загрузки трека {track.get('title', 'Без названия')}: {e}")
                failed_tracks.append(track.get('title', 'Без названия'))
                continue

        # Формируем итоговое сообщение
        success_count = len(downloaded_tracks)
        failed_count = len(failed_tracks)

        message_text = f"✅ **Загрузка треков исполнителя {artist_name} завершена!**\n\n"
        message_text += f"🎵 **Успешно загружено:** {success_count} треков\n"

        if success_count > 0:
            total_size = sum(track.get('size_mb', 0) for track in downloaded_tracks)
            message_text += f"💾 **Общий размер:** {total_size:.1f} MB\n\n"

        if failed_count > 0:
            message_text += f"❌ **Не удалось загрузить:** {failed_count} треков\n\n"
            message_text += "💡 Некоторые треки могли быть:\n"
            message_text += "• Недоступны на YouTube\n"
            message_text += "• Слишком большими для отправки\n"
            message_text += "• Защищены авторскими правами\n"
            message_text += "• Превысили таймаут загрузки\n\n"

        message_text += "🎵 Все загруженные треки доступны для прослушивания\n"
        message_text += "🎵 Аудиофайлы отправлены выше для прослушивания\n\n"
        message_text += "💡 Теперь вы можете:\n"
        message_text += "• Слушать треки прямо здесь\n"
        message_text += "• Искать другого исполнителя\n"
        message_text += "• 🎲 **Нажать 'По исполнителям' еще раз для нового поиска!**"

        # Создаем клавиатуру с опциями
        keyboard_buttons = []

        if failed_count > 0:
            keyboard_buttons.append([InlineKeyboardButton(text="🔄 Попробовать снова", callback_data=f"search_artist_retry:{artist_name}")])

        keyboard_buttons.extend([
            [InlineKeyboardButton(text="👤 Поиск другого исполнителя", callback_data="search_artist_again")],
            [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_main")]
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

        try:
            # Обновляем видео с итоговым сообщением
            await search_msg.edit_media(
                media=types.InputMediaVideo(
                    media=types.FSInputFile("beer.mp4"),
                    caption=message_text
                ),
                reply_markup=keyboard
            )
        except Exception as edit_error:
            logging.error(f"❌ Ошибка редактирования итогового сообщения: {edit_error}")
            # Пытаемся отправить новое сообщение
            try:
                await message.answer_video(
                    video=types.FSInputFile("beer.mp4"),
                    caption=message_text,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
            except Exception as send_error:
                logging.error(f"❌ Критическая ошибка отправки итогового сообщения: {send_error}")

        logging.info(f"✅ Загружено {success_count} треков исполнителя {artist_name} для пользователя {user_id}")

    except Exception as e:
        logging.error(f"❌ Критическая ошибка поиска по исполнителю {artist_name}: {e}")
        
        try:
            await search_msg.edit_text(
                f"❌ **Критическая ошибка**\n\n"
                f"🚫 Произошла критическая ошибка при поиске треков исполнителя {artist_name}.\n"
                f"🔍 Ошибка: {str(e)[:100]}...\n\n"
                "💡 Попробуйте еще раз или обратитесь к администратору.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data=f"search_artist_retry:{artist_name}")],
                    [InlineKeyboardButton(text="👤 Поиск другого исполнителя", callback_data="search_artist_again")],
                    [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_main")]
                ])
            )
        except Exception as final_error:
            logging.error(f"❌ Критическая ошибка отправки сообщения об ошибке: {final_error}")
            # Последняя попытка - отправляем простое сообщение
            try:
                await message.answer(
                    f"❌ Произошла критическая ошибка при поиске исполнителя {artist_name}. Попробуйте еще раз.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="👤 Поиск другого исполнителя", callback_data="search_artist_again")],
                        [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_main")]
                    ])
                )
            except Exception as last_error:
                logging.error(f"❌ Полная потеря связи с пользователем {user_id}: {last_error}")

async def send_search_results(chat_id, results):
    try:
        # Проверяем входные параметры
        if not results or not isinstance(results, list):
            logging.error(f"❌ send_search_results: некорректные результаты: {type(results)}")
            await bot.send_message(chat_id, "❌ Ошибка отображения результатов поиска.", reply_markup=main_menu)
            return
        
        # Фильтруем валидные результаты
        # Начинаем с 15 результатов, если мало - берем больше
        initial_batch = 15
        max_batch = 30  # Уменьшили максимальное количество для проверки
        
        valid_results = []
        
        # Пробуем найти достаточно треков, увеличивая количество проверяемых результатов
        for batch_size in [initial_batch, 20, max_batch]:
            if batch_size > len(results):
                batch_size = len(results)
            
            for video in results[:batch_size]:
                if video and isinstance(video, dict):
                    # Проверяем длительность трека (должна быть от 1 до 10 минут)
                    duration = video.get('duration', 0)
                    if not duration or duration < 60 or duration > 600:
                        continue
                    
                    # Проверяем, является ли это результатом SoundCloud
                    if video.get('source') == 'sc':
                        # SoundCloud результат
                        if video.get('url') and video.get('title'):
                            valid_results.append(video)
                    elif video.get('id') and video.get('title'):
                        # YouTube результат
                        valid_results.append(video)
            
            # Если нашли достаточно треков, прекращаем поиск
            if len(valid_results) >= 5:
                break
        
        if not valid_results:
            await bot.send_message(chat_id, "❌ Не найдено подходящих треков для скачивания.", reply_markup=main_menu)
            return
        
        # Ограничиваем до 5 лучших результатов
        final_results = valid_results[:5]
        
        # Создаем клавиатуру
        keyboard = []
        for video in final_results:
            title = video.get("title", "Без названия")
            duration = video.get("duration", 0)
            duration_text = format_duration(duration) if duration and duration > 0 else ""
            source = video.get("source", "yt")  # Получаем источник трека
            
            # Формируем текст кнопки с названием и длительностью
            if duration and duration > 0:
                button_text = f"{title[:45]}... ⏱ {duration_text}" if len(title) > 45 else f"{title} ⏱ {duration_text}"
            else:
                button_text = title[:55] + "..." if len(title) > 55 else title
            
            # Убираем иконки источника для чистоты интерфейса
            # button_text остается без изменений
            
            # Создаем callback_data в зависимости от источника
            if source == "sc" and video.get("url"):
                # Для SoundCloud используем URL
                import urllib.parse
                encoded_url = urllib.parse.quote(video["url"])
                callback_data = f"dl_sc:{encoded_url}"
            else:
                # Для YouTube используем ID
                callback_data = f"dl:{video['id']}"
            
            keyboard.append([InlineKeyboardButton(text=button_text, callback_data=callback_data)])
        
        # Добавляем кнопку "назад" для возврата в главное меню
        keyboard.append([InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_main")])
        
        # Отправляем результаты с минимальным текстом (Telegram не позволяет пустые сообщения)
        await bot.send_message(
            chat_id, 
            "🐻‍❄️ Результаты", 
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        
    except Exception as e:
        try:
            await bot.send_message(chat_id, "❌ Произошла ошибка при отображении результатов поиска.", reply_markup=main_menu)
        except Exception as send_error:
            pass

# === Callback: скачивание выбранного из поиска ===
@dp.callback_query(F.data.startswith("dl:"))
async def download_track(callback: types.CallbackQuery):
    try:
        user_id = str(callback.from_user.id)
        
        # Проверяем антиспам
        is_allowed, time_until = check_antispam(user_id)
        if not is_allowed:
            await callback.answer(f"⏳ Подождите {time_until:.1f} сек. перед следующим запросом", show_alert=True)
            return
        
        video_id = callback.data.split(":")[1]
        
        # Проверяем валидность video_id
        if not video_id or len(video_id) < 10:
            await callback.answer("❌ Некорректный ID видео.", show_alert=True)
            return
            
        url = f"https://www.youtube.com/watch?v={video_id}"
        
        # МГНОВЕННО добавляем трек в плейлист как "призрак"
        await add_track_ghost(user_id, url)
        
        # Показываем мгновенный ответ
        await callback.answer("✅ Трек добавлен в плейлист!", show_alert=False)
        
        logging.info(f"🚀 Трек мгновенно добавлен для пользователя {user_id}")
        
    except ValueError as e:
        await callback.answer("❌ Ошибка ID видео.", show_alert=True)
    except Exception as e:
        await callback.answer("❌ Произошла ошибка при запуске загрузки.", show_alert=True)

# === Callback: скачивание SoundCloud трека из поиска ===
@dp.callback_query(F.data.startswith("dl_sc:"))
async def download_soundcloud_from_search(callback: types.CallbackQuery):
    """Скачивает SoundCloud трек из общего поиска (как YouTube)"""
    try:
        user_id = str(callback.from_user.id)
        
        # Проверяем антиспам
        is_allowed, time_until = check_antispam(user_id)
        if not is_allowed:
            await callback.answer(f"⏳ Подождите {time_until:.1f} сек. перед следующим запросом", show_alert=True)
            return
        
        # Извлекаем URL после "dl_sc:" и декодируем его
        encoded_url = callback.data[6:]  # Убираем "dl_sc:" в начале
        
        if not encoded_url:
            await callback.answer("❌ URL не найден", show_alert=True)
            return
            
        # Декодируем URL
        import urllib.parse
        url = urllib.parse.unquote(encoded_url)
        
        # МГНОВЕННО добавляем трек в плейлист как "призрак"
        await add_track_ghost(user_id, url)
        
        # Показываем мгновенный ответ
        await callback.answer("✅ Трек добавлен в плейлист!", show_alert=False)
        
        logging.info(f"🚀 SoundCloud трек мгновенно добавлен для пользователя {user_id}")
        
    except Exception as e:
        await callback.answer("❌ Произошла ошибка при запуске загрузки.", show_alert=True)

# Удалена старая функция build_tracks_keyboard

async def search_youtube_artist_improved(artist):
    """Улучшенный поиск треков исполнителя на YouTube с фильтрацией по длительности и качеству"""
    try:
        logging.info(f"🌨️ YouTube: поиск треков исполнителя '{artist}'")
        
        # Проверяем кеш для поиска по исполнителю
        cache_key = f"youtube_artist_{artist.lower().strip()}"
        cached_results = get_cached_search(cache_key)
        
        if cached_results:
            logging.info(f"🎯 Используем кешированные результаты YouTube для исполнителя {artist}")
            return cached_results
        
        def search_block():
            try:
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'noplaylist': True,
                    'quiet': True,
                    'no_warnings': True,
                    'ignoreerrors': True,
                    'extract_flat': True
                }
                
                # Проверяем существование cookies файла
                if os.path.exists(COOKIES_FILE):
                    ydl_opts['cookiefile'] = COOKIES_FILE
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    # Ищем треки исполнителя более точно - используем несколько запросов
                    search_queries = [
                        f"ytsearch15:{artist} music",
                        f"ytsearch15:{artist} song",
                        f"ytsearch15:{artist} track"
                    ]
                    
                    all_results = []
                    for query in search_queries:
                        try:
                            result = ydl.extract_info(query, download=False)
                            if result and 'entries' in result:
                                all_results.extend(result['entries'])
                        except Exception as e:
                            logging.warning(f"⚠️ Ошибка поиска по запросу '{query}': {e}")
                            continue
                    
                    # Объединяем результаты и убираем дубликаты
                    unique_results = {}
                    for entry in all_results:
                        if entry and entry.get('id'):
                            unique_results[entry['id']] = entry
                    
                    return {'entries': list(unique_results.values())} if unique_results else None
            except Exception as e:
                logging.error(f"❌ Ошибка в search_block YouTube для исполнителя '{artist}': {e}")
                return None
        
        result = await asyncio.wait_for(
            asyncio.to_thread(search_block),
            timeout=25.0
        )
        
        if result and 'entries' in result:
            # Фильтруем треки более строго - только музыкальные треки от исполнителя
            filtered_tracks = []
            for entry in result['entries']:
                if entry and entry.get('id') and entry.get('title'):
                    title = entry.get('title', '').lower()
                    artist_lower = artist.lower()
                    
                    # Проверяем длительность - минимум 60 секунд, максимум 10 минут
                    duration = entry.get('duration', 0)
                    if duration < 60 or duration > 600:
                        continue
                    
                    # Строгая фильтрация - ищем только музыкальные треки
                    # Исключаем все, что НЕ является треком
                    exclude_keywords = [
                        'official video', 'music video', 'lyrics', 'live performance', 
                        'interview', 'behind the scenes', 'making of', 'tutorial', 
                        'reaction', 'review', 'cover song', 'remix', 'live', 'song', 'track',
                        'acoustic', 'unplugged', 'studio session', 'recording', 'demo',
                        'preview', 'snippet', 'teaser', 'announcement', 'news', 'update',
                        'podcast', 'stream', 'gaming', 'vlog', 'tutorial', 'review'
                    ]
                    
                    # Проверяем, что в названии НЕТ исключающих слов
                    if any(keyword in title for keyword in exclude_keywords):
                        continue
                    
                    # Улучшенная проверка исполнителя - более гибкая
                    # Ищем исполнителя в разных позициях названия
                    title_words = title.split()
                    artist_words = artist_lower.split()
                    
                    # Проверяем, что исполнитель присутствует в названии
                    artist_found = False
                    for i in range(len(title_words) - len(artist_words) + 1):
                        if title_words[i:i+len(artist_words)] == artist_words:
                            artist_found = True
                            break
                    
                    if not artist_found:
                        continue
                    
                    # Дополнительная проверка - название должно быть похоже на трек
                    if len(title_words) <= 10:  # Треки обычно имеют короткие названия
                        filtered_tracks.append(entry)
                        logging.info(f"🌨️ YouTube: найден трек '{entry.get('title')}' для исполнителя '{artist}' (длительность: {duration}с)")
            
            logging.info(f"🌨️ YouTube: найдено {len(filtered_tracks)} треков исполнителя '{artist}'")
            
            # Сохраняем результаты в кеш
            if filtered_tracks:
                result_with_filtered = {'entries': filtered_tracks}
                set_cached_search(cache_key, result_with_filtered)
                return result_with_filtered
            
            return None
        
        return None
    except Exception as e:
        logging.error(f"❌ Ошибка поиска YouTube для исполнителя '{artist}': {e}")
        return None

async def search_soundcloud_artist(artist):
    """Поиск треков исполнителя на SoundCloud"""
    try:
        logging.info(f"🌨️ SoundCloud: поиск треков исполнителя '{artist}'")
        
        # Проверяем кеш для поиска по исполнителю на SoundCloud
        cache_key = f"soundcloud_artist_{artist.lower().strip()}"
        cached_results = get_cached_search(cache_key)
        
        if cached_results:
            logging.info(f"🎯 Используем кешированные результаты SoundCloud для исполнителя {artist}")
            return cached_results
        
        def search_block():
            try:
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'quiet': True,
                    'no_warnings': True,
                    'extract_flat': True,
                    'ignoreerrors': True,
                    'timeout': 25,
                    'retries': 2,
                }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    # Ищем треки исполнителя без лишних слов - только имя исполнителя
                    search_query = f"scsearch20:{artist}"
                    info = ydl.extract_info(search_query, download=False)
                    return info
            except Exception as e:
                logging.error(f"❌ Ошибка в search_block SoundCloud для исполнителя '{artist}': {e}")
                return None
        
        info = await asyncio.wait_for(
            asyncio.to_thread(search_block),
            timeout=25.0
        )
        
        if info and 'entries' in info:
            results = []
            for entry in info['entries']:
                if entry and isinstance(entry, dict):
                    title = entry.get('title', 'Без названия')
                    url = entry.get('url', '')
                    duration = entry.get('duration', 0)
                    
                    if url and title:
                        # Фильтруем треки более строго - только музыкальные треки от исполнителя
                        title_lower = title.lower()
                        artist_lower = artist.lower()
                        
                        # Строгая фильтрация - ищем только музыкальные треки
                        # Исключаем все, что НЕ является треком
                        exclude_keywords = [
                            'official video', 'music video', 'lyrics', 'live performance', 
                            'interview', 'behind the scenes', 'making of', 'tutorial', 
                            'reaction', 'review', 'cover song', 'remix', 'live', 'song', 'track',
                            'acoustic', 'unplugged', 'studio session', 'recording', 'demo',
                            'preview', 'snippet', 'teaser', 'announcement', 'news', 'update'
                        ]
                        
                        # Проверяем, что в названии НЕТ исключающих слов
                        if any(keyword in title_lower for keyword in exclude_keywords):
                            continue
                        
                        # Проверяем, что исполнитель указан в начале названия или после дефиса
                        if (title_lower.startswith(artist_lower) or 
                            f" - {artist_lower}" in title_lower or 
                            f" – {artist_lower}" in title_lower or
                            f" {artist_lower} -" in title_lower or
                            f" {artist_lower} –" in title_lower):
                            
                            # Дополнительная проверка - название должно быть похоже на трек
                            if len(title.split()) <= 8:  # Треки обычно имеют короткие названия
                                results.append({
                                    'title': title,
                                    'url': url,
                                    'duration': duration,
                                    'source': 'sc',
                                })
                                logging.info(f"🌨️ SoundCloud: найден трек '{title}' для исполнителя '{artist}'")
            
            logging.info(f"🌨️ SoundCloud: найдено {len(results)} треков исполнителя '{artist}'")
            
            # Сохраняем результаты в кеш
            if results:
                set_cached_search(cache_key, results)
            
            return results
        
        return []
    except Exception as e:
        logging.error(f"❌ Ошибка поиска SoundCloud для исполнителя '{artist}': {e}")
        return []

# Функция "Для вас" удалена

async def get_recommended_tracks(user_id):
    """Получает рекомендуемые треки для пользователя на основе его коллекции или популярных треков"""
    try:
        global user_tracks, user_recommendation_history
        
        # Проверяем кеш для рекомендаций пользователя
        cache_key = f"recommendations_{user_id}"
        cached_recommendations = get_cached_search(cache_key)
        
        if cached_recommendations:
            logging.info(f"🎯 Используем кешированные рекомендации для пользователя {user_id}")
            return cached_recommendations
        
        # Инициализируем историю рекомендаций для пользователя
        if 'user_recommendation_history' not in globals():
            user_recommendation_history = {}
        
        if user_id not in user_recommendation_history:
            user_recommendation_history[user_id] = {
                'shown_tracks': set(),  # Уже показанные треки
                'used_queries': set(),  # Уже использованные запросы
                'last_artist': None,    # Последний использованный артист
                'query_counter': 0      # Счетчик запросов
            }
        
        history = user_recommendation_history[user_id]
        
        # Проверяем, что user_tracks не None
        if user_tracks is None:
            user_tracks = {}
            logging.warning(f"⚠️ get_recommended_tracks: user_tracks был None, инициализируем пустым словарем")
        
        user_tracks_list = user_tracks.get(str(user_id), [])
        logging.info(f"🎯 get_recommended_tracks: пользователь {user_id}, найдено треков: {len(user_tracks_list) if user_tracks_list else 0}")
        
        # Если у пользователя есть треки, ищем похожие по артистам
        if user_tracks_list and len(user_tracks_list) > 0:
            # Извлекаем артистов из треков пользователя
            artists = set()
            for track in user_tracks_list:
                if track and isinstance(track, dict):
                    title = track.get('title', '')
                    if title:
                        # Пытаемся извлечь артиста из названия (обычно формат "Артист - Название")
                        if ' - ' in title:
                            artist = title.split(' - ')[0].strip()
                            if artist and len(artist) > 2:  # Фильтруем слишком короткие названия
                                artists.add(artist)
            
            # Если нашли артистов, ищем похожие треки
            if artists:
                logging.info(f"🎯 Поиск рекомендаций для пользователя {user_id} по {len(artists)} артистам: {', '.join(list(artists)[:3])}")
                
                # Собираем треки от нескольких артистов для разнообразия
                all_results = []
                used_artists = set()
                
                # Сначала пробуем найти треки от артистов, которых еще не использовали
                available_artists = [a for a in artists if a != history['last_artist']]
                if not available_artists:
                    available_artists = list(artists)
                
                # Перемешиваем артистов для случайности
                random.shuffle(available_artists)
                
                # Ищем треки от нескольких артистов (максимум 3-4)
                max_artists_to_search = min(4, len(available_artists))
                tracks_per_artist = max(3, 10 // max_artists_to_search)  # Распределяем треки между артистами
                
                for i, artist in enumerate(available_artists[:max_artists_to_search]):
                    if len(all_results) >= 10:
                        break
                        
                    logging.info(f"🎵 Поиск треков от артиста {i+1}/{max_artists_to_search}: {artist}")
                    
                    # Ищем треки этого артиста на SoundCloud
                    artist_results = await search_soundcloud(artist)
                    if artist_results:
                        # Фильтруем уже показанные треки
                        new_tracks = []
                        for track in artist_results:
                            track_id = f"{track.get('title', '')}_{track.get('url', '')}"
                            if track_id not in history['shown_tracks']:
                                new_tracks.append(track)
                                if len(new_tracks) >= tracks_per_artist:
                                    break
                        
                        # Добавляем найденные треки к общему результату
                        all_results.extend(new_tracks)
                        used_artists.add(artist)
                        
                        # Небольшая задержка между запросами
                        await asyncio.sleep(0.1)
                
                # Если нашли достаточно треков, возвращаем их
                if all_results:
                    # Перемешиваем треки для разнообразия
                    random.shuffle(all_results)
                    
                    # Берем первые 10 треков
                    final_tracks = all_results[:10]
                    
                    # Обновляем историю показанных треков
                    for track in final_tracks:
                        track_id = f"{track.get('title', '')}_{track.get('url', '')}"
                        history['shown_tracks'].add(track_id)
                    
                    # Обновляем последнего использованного артиста
                    if used_artists:
                        history['last_artist'] = random.choice(list(used_artists))
                    
                    # Ограничиваем размер истории (максимум 100 треков)
                    if len(history['shown_tracks']) > 100:
                        history['shown_tracks'] = set(list(history['shown_tracks'])[-50:])
                    
                    logging.info(f"🎯 Найдено {len(final_tracks)} треков от {len(used_artists)} артистов")
                    return final_tracks
        
        # Если нет треков или не удалось найти рекомендации, возвращаем популярные треки
        logging.info(f"🎯 Возвращаем популярные треки для пользователя {user_id}")
        
        # Расширенный список популярных запросов для большего разнообразия
        popular_queries = [
            # Тренды 2024
            "trending music 2024", "top hits 2024", "viral music 2024", "chart toppers 2024",
            "popular songs 2024", "music trending now", "trending audio 2024", "hit songs 2024",
            
            # Популярные жанры
            "pop music trending", "hip hop trending", "electronic music trending", "rock music trending",
            "indie music trending", "alternative trending", "r&b trending", "country music trending",
            
            # Временные категории
            "music this week", "songs this month", "trending this week", "popular this month",
            "viral this week", "hits this month", "new music today", "fresh tracks today",
            
            # Общие категории
            "trending tracks", "popular music", "viral songs", "chart music",
            "music charts", "trending audio", "popular tracks", "hit music"
        ]
        
        # Выбираем запрос, который еще не использовали
        available_queries = [q for q in popular_queries if q not in history['used_queries']]
        if not available_queries:
            # Если все запросы использованы, очищаем историю и начинаем заново
            history['used_queries'].clear()
            available_queries = popular_queries
        
        query = random.choice(available_queries)
        history['used_queries'].add(query)
        history['query_counter'] += 1
        
        # Ограничиваем размер истории запросов
        if len(history['used_queries']) > 20:
            history['used_queries'] = set(list(history['used_queries'])[-10:])
        
        results = await search_soundcloud(query)
        
        if results:
            # Фильтруем уже показанные треки
            new_tracks = []
            for track in results:
                track_id = f"{track.get('title', '')}_{track.get('url', '')}"
                if track_id not in history['shown_tracks']:
                    new_tracks.append(track)
                    if len(new_tracks) >= 10:
                        break
            
            # Если новых треков мало, добавляем случайные из результатов
            if len(new_tracks) < 5:
                random_tracks = random.sample(results, min(10 - len(new_tracks), len(results)))
                for track in random_tracks:
                    track_id = f"{track.get('title', '')}_{track.get('url', '')}"
                    if track_id not in history['shown_tracks']:
                        new_tracks.append(track)
                        if len(new_tracks) >= 10:
                            break
            
            # Обновляем историю показанных треков
            for track in new_tracks:
                track_id = f"{track.get('title', '')}_{track.get('url', '')}"
                history['shown_tracks'].add(track_id)
            
            # Ограничиваем размер истории
            if len(history['shown_tracks']) > 100:
                history['shown_tracks'] = set(list(history['shown_tracks'])[-50:])
            
            logging.info(f"🎯 Найдено {len(new_tracks)} популярных треков по запросу '{query}'")
            
            # Сохраняем результаты в кеш
            final_tracks = new_tracks[:10]
            set_cached_search(cache_key, final_tracks)
            
            return final_tracks
        
        return []
        
    except Exception as e:
        logging.error(f"❌ Ошибка получения рекомендаций для пользователя {user_id}: {e}")
        return []

async def send_tracks_as_audio(user_id: str, tracks: list, status_msg: types.Message = None):
    """Отправляет треки как аудиофайлы в чат"""
    try:
        logging.info(f"🎯 Отправляю {len(tracks)} треков как аудиофайлы для пользователя {user_id}")
        
        # Проверяем кеш для отправки треков
        cache_key = f"send_tracks_{user_id}_{hashlib.md5(str(tracks).encode()).hexdigest()}"
        cached_send = get_cached_metadata(cache_key)
        
        if cached_send:
            logging.info(f"🎯 Используем кешированные результаты отправки для пользователя {user_id}")
            return cached_send
        
        # Если status_msg не передан, создаем сообщение "Поиск..." прямо перед отправкой
        if not status_msg:
            try:
                status_msg = await bot.send_message(user_id, "🌨️ Поиск...")
                logging.info(f"🎯 Создано сообщение 'Поиск...' для пользователя {user_id}")
            except Exception as e:
                logging.warning(f"⚠️ Не удалось создать сообщение 'Поиск...': {e}")
                status_msg = None
        
        success_count = 0
        for i, track in enumerate(tracks):
            try:
                if track and isinstance(track, dict):
                    # Проверяем, является ли трек "призраком"
                    if track.get('is_ghost'):
                        # Для треков-призраков показываем только метаданные
                        await bot.send_message(
                            chat_id=user_id,
                            text=f"👻 **{track.get('title', 'Загружается...')}**\n\n"
                                 f"⏳ Метаданные загружаются в фоне...\n"
                                 f"💡 Трек будет доступен для скачивания позже"
                        )
                        success_count += 1
                        logging.info(f"👻 Трек-призрак {i+1}/{len(tracks)} показан: {track.get('title', 'Загружается...')}")
                    elif track.get('url'):
                        # Для обычных треков - быстрая отправка без скачивания
                        await bot.send_message(
                            chat_id=user_id,
                            text=f"🎵 **{track.get('title', 'Неизвестный трек')}**\n\n"
                                 f"👤 {track.get('uploader', 'Неизвестный исполнитель')}\n"
                                 f"⏱️ {format_duration(track.get('duration', 0))}\n\n"
                                 f"💡 Используйте поиск для скачивания аудио"
                        )
                        success_count += 1
                        logging.info(f"✅ Трек {i+1}/{len(tracks)} показан: {track.get('title', 'Неизвестный трек')}")
                    else:
                        logging.warning(f"⚠️ Некорректный трек {i+1}: {track}")
                    
                    # Удаляем статусное сообщение после первого трека
                    if i == 0 and status_msg:
                        try:
                            await status_msg.delete()
                            logging.info(f"🎯 Статусное сообщение удалено после первого трека")
                        except Exception as delete_error:
                            logging.warning(f"⚠️ Не удалось удалить статусное сообщение: {delete_error}")
                    
                    # Минимальная задержка между отправками
                    await asyncio.sleep(0.1)
                    
            except Exception as e:
                logging.error(f"❌ Ошибка отправки трека {i+1}: {e}")
                continue
        
        logging.info(f"✅ Успешно отправлено {success_count}/{len(tracks)} треков для пользователя {user_id}")
        
        # Сохраняем результаты в кеш
        result = {'success_count': success_count, 'total_tracks': len(tracks)}
        set_cached_metadata(cache_key, result)
        
    except Exception as e:
        logging.error(f"❌ Ошибка отправки треков как аудиофайлы для пользователя {user_id}: {e}")
        # Удаляем статусное сообщение при ошибке
        if status_msg:
            try:
                await status_msg.delete()
            except:
                pass

# === Моя музыка (новая версия, работает по принципу поиска) ===
@dp.callback_query(F.data == "my_music")
async def my_music(callback: types.CallbackQuery):
    """Показывает треки пользователя в формате поиска - с кнопками для скачивания"""
    # Быстрый ответ для ускорения
    await callback.answer("⏳ Обрабатываю...")
    
    global user_tracks
    user_id = str(callback.from_user.id)
    
    # Проверяем антиспам
    is_allowed, time_until = check_antispam(user_id)
    if not is_allowed:
        await callback.answer(f"⏳ Подождите {time_until:.1f} сек. перед следующим запросом", show_alert=True)
        return
    
    # Проверяем кеш для треков пользователя
    cache_key = f"my_music_{user_id}"
    cached_tracks = get_cached_metadata(cache_key)
    
    if cached_tracks:
        logging.info(f"🎯 Используем кешированные треки для пользователя {user_id}")
        tracks = cached_tracks
    else:
        # Получаем треки пользователя - загружаем заново каждый раз
        global user_tracks
        user_tracks = load_json(TRACKS_FILE, {})
        
        # Проверяем, что user_tracks является словарем
        if not isinstance(user_tracks, dict):
            user_tracks = {}
        
        tracks = user_tracks.get(user_id, [])
        
        # Сохраняем в кеш
        if tracks:
            set_cached_metadata(cache_key, tracks)
    
    # Проверяем, что tracks не None и является списком
    if tracks is None:
        tracks = []
        user_tracks[user_id] = tracks
    
    if not tracks:
        # При пустом плейлисте отправляем новое сообщение без кнопок
        
        try:
            await callback.message.answer("📂 У вас нет треков.")
        except Exception as answer_error:
            pass
        return
    
    try:
        # Создаем клавиатуру в стиле поиска
        keyboard = []
        
        for i, track in enumerate(tracks):
            if isinstance(track, dict):
                # Новый формат: объект с информацией о треке
                title = track.get('title', 'Неизвестный трек')
                original_url = track.get('original_url', '')
                duration = track.get('duration', 0)
                
                if original_url and original_url.startswith('http'):
                    # Формируем текст кнопки с длительностью
                    duration_text = format_duration(duration)
                    
                    # Определяем максимальную длину названия в зависимости от наличия длительности
                    if duration_text:
                        # Если есть длительность, оставляем место для неё
                        max_title_length = 40
                        button_text = f"🎵 {title[:max_title_length]}{'...' if len(title) > max_title_length else ''} ⏱{duration_text}"
                    else:
                        # Если длительности нет, можно использовать больше места для названия
                        max_title_length = 50
                        button_text = f"🎵 {title[:max_title_length]}{'...' if len(title) > max_title_length else ''}"
                    
                    # Создаем строку с кнопками скачивания и удаления
                    row = [
                        InlineKeyboardButton(text=button_text, callback_data=f"play:{i}"),
                        InlineKeyboardButton(text="🗑", callback_data=f"del:{i}")
                    ]
                    keyboard.append(row)
                else:
                    # Трек без ссылки
                    max_title_length = 50
                    button_text = f"⚠️ {title[:max_title_length]}{'...' if len(title) > max_title_length else ''}"
                    row = [
                        InlineKeyboardButton(text=button_text, callback_data="no_url"),
                        InlineKeyboardButton(text="🗑", callback_data=f"del:{i}")
                    ]
                    keyboard.append(row)
            else:
                # Старый формат: путь к файлу
                title = os.path.basename(track)
                max_title_length = 50
                button_text = f"⚠️ {title[:max_title_length]}{'...' if len(title) > max_title_length else ''}"
                row = [
                    InlineKeyboardButton(text=button_text, callback_data="old_format"),
                    InlineKeyboardButton(text="🗑", callback_data=f"del:{i}")
                ]
                keyboard.append(row)
        
        # Добавляем кнопку "Скачать все"
        keyboard.append([InlineKeyboardButton(text="📥 Скачать все", callback_data="download_all")])
        
        # Добавляем кнопку "назад" для возврата в главное меню
        keyboard.append([InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_main")])
        
        # Отправляем список треков
        try:
            # Проверяем, есть ли текст в сообщении для редактирования
            if callback.message.text:
                # Если есть текст, пытаемся отредактировать
                await callback.message.edit_text(
                    f"🎧 Ваши треки ({len(tracks)}):",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
                )
            else:
                # Если текста нет, отправляем новое сообщение
                await callback.message.answer(
                    f"🎧 Ваши треки ({len(tracks)}):",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
                )
        except Exception as edit_error:
            logging.error(f"❌ Ошибка редактирования сообщения: {edit_error}")
            # Если не удалось отредактировать, отправляем новое сообщение
            await callback.message.answer(
                f"🎧 Ваши треки ({len(tracks)}):",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
            )
        
    except Exception as e:
        logging.error(f"❌ Ошибка отображения треков для пользователя {user_id}: {e}")
        import traceback
        logging.error(f"📋 Traceback:\n{traceback.format_exc()}")
        try:
            await callback.message.edit_text("❌ Ошибка отображения треков. Попробуйте еще раз.", reply_markup=main_menu)
        except Exception as edit_error:
            logging.error(f"❌ Не удалось отредактировать сообщение об ошибке: {edit_error}")
            await callback.message.answer("❌ Ошибка отображения треков. Попробуйте еще раз.", reply_markup=main_menu)
    
    logging.info("🔍 === ФУНКЦИЯ my_music ЗАВЕРШЕНА ===")

# Удалена старая функция перелистывания страниц

# === Callback: play / play_shared ===
@dp.callback_query(F.data.startswith("play:"))
async def play_track(callback: types.CallbackQuery):
    """Скачивает и отправляет один трек по принципу 'Скачать всё'"""
    global user_tracks
    try:
        user_id = str(callback.from_user.id)
        logging.info(f"🔍 play_track вызван для пользователя: {user_id}")
        
        # Проверяем антиспам
        is_allowed, time_until = check_antispam(user_id)
        if not is_allowed:
            await callback.answer(f"⏳ Подождите {time_until:.1f} сек. перед следующим запросом", show_alert=True)
            return
        
        # Извлекаем индекс трека
        idx = int(callback.data.split(":")[1])
        logging.info(f"🔍 Индекс трека: {idx}")
        
        # Проверяем кеш для треков пользователя
        cache_key = f"play_track_{user_id}"
        cached_tracks = get_cached_metadata(cache_key)
        
        if cached_tracks:
            logging.info(f"🎯 Используем кешированные треки для play_track пользователя {user_id}")
            tracks = cached_tracks
        else:
            # Получаем треки пользователя
            if user_tracks is None:
                user_tracks = {}
            
            tracks = user_tracks.get(user_id, [])
            
            # Сохраняем в кеш
            if tracks:
                set_cached_metadata(cache_key, tracks)
        if not tracks:
            await callback.answer("📂 У вас нет треков.", show_alert=True)
            return
        
        if not (0 <= idx < len(tracks)):
            await callback.answer("❌ Трек не найден.", show_alert=True)
            return
        
        track = tracks[idx]
        logging.info(f"🔍 Обрабатываю трек: {track}")
        
        # Проверяем формат трека
        if isinstance(track, dict):
            # Новый формат: объект с информацией о треке
            title = track.get('title', 'Неизвестный трек')
            original_url = track.get('original_url', '')
            
            if not original_url or not original_url.startswith('http'):
                await callback.answer("❌ Ссылка для скачивания не найдена.", show_alert=True)
                return
            
            # Показываем уведомление о скачивании без изменения сообщения с плейлистом
            await callback.answer("⏳ Скачиваю трек...", show_alert=False)
            
            try:
                # Скачиваем трек заново (как в "Скачать всё")
                temp_file_path = await download_track_to_temp(user_id, original_url, title)
                
                if temp_file_path and os.path.exists(temp_file_path):
                    # Отправляем MP3 пользователю
                    await callback.message.answer_audio(types.FSInputFile(temp_file_path), title=title)
                    logging.info(f"✅ Трек отправлен: {title}")
                    
                    # Удаляем временный файл после успешной отправки
                    await delete_temp_file(temp_file_path)
                    
                    # Показываем краткое уведомление о успешной отправке
                    await callback.answer("✅ Трек отправлен!")
                else:
                    await callback.answer("❌ Не удалось скачать трек.")
                    
            except Exception as e:
                logging.error(f"❌ Ошибка при скачивании/отправке трека {title}: {e}")
                await callback.answer("❌ Ошибка при скачивании трека.")

        else:
            # Старый формат: путь к файлу
            title = os.path.basename(track)
            await callback.answer("❌ Трек в старом формате. Добавьте его заново.", show_alert=True)
                
    except ValueError as e:
        logging.error(f"❌ Ошибка парсинга индекса трека: {e}")
        await callback.answer("❌ Ошибка индекса трека.", show_alert=True)
    except Exception as e:
        logging.error(f"❌ Критическая ошибка в play_track: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте еще раз.", show_alert=True)

# === Callback: download all (self) ===
@dp.callback_query(F.data == "download_all")
async def download_all_tracks(callback: types.CallbackQuery):
    global user_tracks
    try:
        user_id = str(callback.from_user.id)
        
        # Проверяем антиспам
        is_allowed, time_until = check_antispam(user_id)
        if not is_allowed:
            await callback.answer(f"⏳ Подождите {time_until:.1f} сек. перед следующим запросом", show_alert=True)
            return
        
        # Проверяем кеш для треков пользователя
        cache_key = f"download_all_{user_id}"
        cached_tracks = get_cached_metadata(cache_key)
        
        if cached_tracks:
            logging.info(f"🎯 Используем кешированные треки для download_all пользователя {user_id}")
            tracks = cached_tracks
        else:
            # Проверяем, что user_tracks не None
            if user_tracks is None:
                user_tracks = {}
                logging.warning(f"⚠️ download_all_tracks: user_tracks был None для пользователя {user_id}, инициализируем пустым словарем")
            
            tracks = user_tracks.get(user_id, [])
            
            # Проверяем, что tracks не None и является списком
            if tracks is None:
                tracks = []
                user_tracks[user_id] = tracks
                logging.warning(f"⚠️ download_all_tracks: tracks был None для пользователя {user_id}, инициализируем пустым списком")
            
            # Сохраняем в кеш
            if tracks:
                set_cached_metadata(cache_key, tracks)
        
        if not tracks:
            await callback.message.answer("📂 У тебя нет треков.", reply_markup=main_menu)
            return
        
        # Отправляем сообщение о начале загрузки и сохраняем его ID
        loading_msg = await callback.message.answer("📥 Отправляю все треки...")
        
        success_count = 0
        failed_count = 0
        

        
        for track in tracks:
            try:
                # Проверяем формат трека
                if isinstance(track, dict):
                    # Новый формат: объект с информацией о треке
                    title = track.get('title', 'Неизвестный трек')
                    original_url = track.get('original_url', '')
                    
                    if not original_url or not original_url.startswith('http'):
                        logging.warning(f"⚠️ Нет валидной ссылки для трека: {title}")
                        failed_count += 1
                        continue
                else:
                    # Старый формат: путь к файлу
                    if not track or not isinstance(track, str):
                        logging.warning(f"⚠️ Некорректный формат трека: {track}")
                        failed_count += 1
                        continue
                        
                    title = os.path.basename(track)
                    original_url = ""  # Для старых треков ссылка неизвестна
                
                # Для всех треков (новых и старых) скачиваем заново
                if original_url and original_url.startswith('http'):
                    try:
                        logging.info(f"📥 Скачиваю трек: {title} по ссылке: {original_url}")
                        
                        # Скачиваем трек во временную папку
                        temp_file_path = await download_track_to_temp(user_id, original_url, title)
                        
                        if temp_file_path and os.path.exists(temp_file_path):
                            # Отправляем MP3 пользователю
                            try:
                                await callback.message.answer_audio(types.FSInputFile(temp_file_path), title=title)
                                success_count += 1
                                logging.info(f"✅ Трек отправлен: {title}")
                                
                                # Удаляем временный файл после успешной отправки
                                await delete_temp_file(temp_file_path)
                                
                                # Небольшая задержка между отправками
                                await asyncio.sleep(0.4)
                                
                            except Exception as audio_error:
                                logging.error(f"❌ Ошибка отправки трека {title}: {audio_error}")
                                failed_count += 1
                                
                                # Удаляем временный файл даже при ошибке отправки
                                await delete_temp_file(temp_file_path)
                        else:
                            logging.error(f"❌ Не удалось скачать трек: {title}")
                            failed_count += 1
                            
                    except Exception as download_error:
                        logging.error(f"❌ Ошибка при скачивании трека {title}: {download_error}")
                        failed_count += 1
                else:
                    logging.warning(f"⚠️ Не удалось найти валидную ссылку для трека: {title}")
                    failed_count += 1
                    
            except Exception as e:
                logging.exception(f"❌ Ошибка отправки трека {track}: {e}")
                failed_count += 1
        
        # Удаляем надпись "📥 Отправляю все треки..." после завершения
        try:
            await loading_msg.delete()
        except:
            pass  # Игнорируем ошибки удаления
        
        # Отправляем итоговое сообщение только если есть ошибки
        if failed_count > 0:
            result_message = f"⚠️ **Внимание!**\n\n"
            result_message += f"❌ **Не удалось отправить:** {failed_count} треков\n\n"
            result_message += "💡 Возможные причины:\n"
            result_message += "• Недоступны на YouTube\n"
            result_message += "• Слишком большими для отправки\n"
            result_message += "• Защищены авторскими правами\n"
            
            await callback.message.answer(result_message, parse_mode="Markdown")
        
    except Exception as e:
        logging.error(f"❌ Критическая ошибка в download_all_tracks для пользователя {user_id}: {e}")
        await callback.message.answer("❌ Произошла ошибка при скачивании всех треков.", reply_markup=main_menu)

async def show_updated_tracks_list(message, user_id: str, tracks: list):
    """Показывает обновленный список треков после удаления"""
    try:
        # Создаем клавиатуру в стиле поиска
        keyboard = []

        for i, track in enumerate(tracks):
            if isinstance(track, dict):
                # Новый формат: объект с информацией о треке
                title = track.get('title', 'Неизвестный трек')
                original_url = track.get('original_url', '')
                duration = track.get('duration', 0)
                
                if original_url and original_url.startswith('http'):
                    # Формируем текст кнопки с длительностью
                    duration_text = format_duration(duration)
                    
                    # Определяем максимальную длину названия в зависимости от наличия длительности
                    if duration_text:
                        # Если есть длительность, оставляем место для неё
                        max_title_length = 40
                        button_text = f"🎵 {title[:max_title_length]}{'...' if len(title) > max_title_length else ''} ⏱{duration_text}"
                    else:
                        # Если длительности нет, можно использовать больше места для названия
                        max_title_length = 50
                        button_text = f"🎵 {title[:max_title_length]}{'...' if len(title) > max_title_length else ''}"
                    
                    # Создаем строку с кнопками скачивания и удаления
                    row = [
                        InlineKeyboardButton(text=button_text, callback_data=f"play:{i}"),
                        InlineKeyboardButton(text="🗑", callback_data=f"del:{i}")
                    ]
                    keyboard.append(row)
                else:
                    # Трек без ссылки
                    max_title_length = 50
                    button_text = f"⚠️ {title[:max_title_length]}{'...' if len(title) > max_title_length else ''}"
                    row = [
                        InlineKeyboardButton(text=button_text, callback_data="no_url"),
                        InlineKeyboardButton(text="🗑", callback_data=f"del:{i}")
                    ]
                    keyboard.append(row)
            else:
                # Старый формат: путь к файлу
                title = os.path.basename(track)
                max_title_length = 50
                button_text = f"⚠️ {title[:max_title_length]}{'...' if len(title) > max_title_length else ''}"
                row = [
                    InlineKeyboardButton(text=button_text, callback_data="old_format"),
                    InlineKeyboardButton(text="🗑", callback_data=f"del:{i}")
                ]
                keyboard.append(row)

        # Добавляем кнопку "Скачать все"
        keyboard.append([InlineKeyboardButton(text="📥 Скачать все", callback_data="download_all")])

        # Добавляем кнопку "назад" для возврата в главное меню
        keyboard.append([InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_main")])

        # Отправляем обновленный список треков
        await message.edit_text(
            f"🎧 Ваши треки ({len(tracks)}):",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        
    except Exception as e:
        logging.error(f"❌ Ошибка отображения обновленного списка треков для пользователя {user_id}: {e}")
        import traceback
        logging.error(f"📋 Traceback:\n{traceback.format_exc()}")
        await message.edit_text("❌ Ошибка отображения треков. Попробуйте еще раз.", reply_markup=main_menu)

# === Удаление трека ===
@dp.callback_query(F.data.startswith("del:"))
async def delete_track(callback: types.CallbackQuery):
    global user_tracks
    try:
        user_id = str(callback.from_user.id)
        
        # Проверяем антиспам
        is_allowed, time_until = check_antispam(user_id)
        if not is_allowed:
            await callback.answer(f"⏳ Подождите {time_until:.1f} сек. перед следующим запросом", show_alert=True)
            return
        
        idx = int(callback.data.split(":")[1])
        
        # Проверяем, что user_tracks не None
        if user_tracks is None:
            user_tracks = {}
            logging.warning(f"⚠️ delete_track: user_tracks был None для пользователя {user_id}, инициализируем пустым словарем")
        
        tracks = user_tracks.get(user_id, [])
        
        # Проверяем, что tracks не None и является списком
        if tracks is None:
            tracks = []
            user_tracks[user_id] = tracks
            logging.warning(f"⚠️ delete_track: tracks был None для пользователя {user_id}, инициализируем пустым списком")
        
        if not (0 <= idx < len(tracks)):
            await callback.answer("❌ Трек не найден.", show_alert=True)
            return
        
        track = tracks[idx]
        
        # Проверяем формат трека
        if isinstance(track, dict):
            # Новый формат: объект с информацией о треке
            title = track.get('title', 'Неизвестный трек')
            # В новой логике файлы не хранятся постоянно, поэтому просто удаляем из списка
        else:
            # Старый формат: путь к файлу
            if track and isinstance(track, str):
                # Для старых треков проверяем существование файла и удаляем его
                if os.path.exists(track):
                    try:
                        os.remove(track)
                        logging.info(f"✅ Удален старый файл: {track}")
                    except Exception as e:
                        logging.error(f"❌ Ошибка удаления старого файла {track}: {e}")
            title = os.path.basename(track) if track else 'Неизвестный трек'
        
        # Удаляем трек из списка
        tracks.pop(idx)
        save_tracks()
        logging.info(f"✅ Трек удален из списка: {title}")
        
        # Обновляем интерфейс - возвращаемся к списку треков
        if not tracks:
            await callback.message.edit_text("📂 У вас нет треков.", reply_markup=main_menu)
        else:
            # Показываем обновленный список треков
            await show_updated_tracks_list(callback.message, user_id, tracks)
        
        await callback.answer("✅ Трек удален.")
        
    except ValueError as e:
        logging.error(f"❌ Ошибка парсинга индекса трека: {e}")
        await callback.answer("❌ Ошибка индекса трека.", show_alert=True)
    except Exception as e:
        logging.error(f"❌ Критическая ошибка в delete_track: {e}")
        await callback.answer("❌ Произошла ошибка при удалении трека.", show_alert=True)

# === Обработчики для новой функции "Моя музыка" ===
@dp.callback_query(F.data == "no_url")
async def handle_no_url_track(callback: types.CallbackQuery):
    """Обрабатывает треки без ссылки для скачивания"""
    await callback.answer("⚠️ Этот трек требует обновления. Добавьте его заново через поиск.", show_alert=True)

@dp.callback_query(F.data == "old_format")
async def handle_old_format_track(callback: types.CallbackQuery):
    """Обрабатывает треки в старом формате"""
    await callback.answer("⚠️ Этот трек в старом формате. Добавьте его заново через поиск.", show_alert=True)

# === Функции для работы с жанрами ===

def search_artist_tracks(artist_name, limit=25):
    """Ищет треки конкретного исполнителя на YouTube и SoundCloud"""
    try:
        logging.info(f"👤 Поиск треков исполнителя: {artist_name}")
        
        # Поиск на YouTube
        ydl_opts = {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'quiet': True,
            'cookiefile': COOKIES_FILE if os.path.exists(COOKIES_FILE) else None,
            'extract_flat': True,
            'no_warnings': True,
            'ignoreerrors': True
        }
        
        youtube_results = []
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Ищем треки исполнителя на YouTube
            search_query = f"ytsearch{limit + 5}:{artist_name} music"
            info = ydl.extract_info(search_query, download=False)
            
            if info and info.get("entries"):
                results = info.get("entries", [])
                logging.info(f"🔍 Найдено {len(results)} треков на YouTube для исполнителя {artist_name}")
                
                # Фильтруем результаты YouTube
                for result in results:
                    if not result:
                        continue
                        
                    title = result.get('title', '').lower()
                    duration = result.get('duration', 0)
                    video_id = result.get('id')
                    
                    # Проверяем, что это подходящий трек
                    if (duration and duration > 60 and  # Трек должен быть длиннее 1 минуты
                        duration < 900 and  # И не слишком длинный (не более 15 минут)
                        'mix' not in title and 
                        'compilation' not in title and
                        'collection' not in title and
                        'best of' not in title and
                        'greatest hits' not in title and
                        'karaoke' not in title and
                        'instrumental' not in title and
                        'live' not in title and  # Избегаем живых выступлений
                        'concert' not in title and
                        'performance' not in title and
                        video_id):  # Убеждаемся, что есть ID видео
                        
                        result['source'] = 'yt'  # Добавляем источник
                        youtube_results.append(result)
        
        # Поиск на SoundCloud
        soundcloud_results = []
        try:
            ydl_opts_sc = {
                'format': 'bestaudio/best',
                'noplaylist': True,
                'quiet': True,
                'extract_flat': True,
                'no_warnings': True,
                'ignoreerrors': True,
                'timeout': 30,
                'retries': 3,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts_sc) as ydl:
                # Ищем треки исполнителя на SoundCloud
                search_query_sc = f"scsearch{limit + 5}:{artist_name}"
                info_sc = ydl.extract_info(search_query_sc, download=False)
                
                if info_sc and info_sc.get("entries"):
                    results_sc = info_sc.get("entries", [])
                    logging.info(f"🔍 Найдено {len(results_sc)} треков на SoundCloud для исполнителя {artist_name}")
                    
                    # Фильтруем результаты SoundCloud
                    for result in results_sc:
                        if not result:
                            continue
                            
                        title = result.get('title', '').lower()
                        duration = result.get('duration', 0)
                        url = result.get('url', '')
                        
                        # Проверяем, что это подходящий трек
                        if (duration and duration > 60 and  # Трек должен быть длиннее 1 минуты
                            duration < 900 and  # И не слишком длинный (не более 15 минут)
                            'mix' not in title and 
                            'compilation' not in title and
                            'collection' not in title and
                            'best of' not in title and
                            'greatest hits' not in title and
                            'karaoke' not in title and
                            'instrumental' not in title and
                            'live' not in title and  # Избегаем живых выступлений
                            'concert' not in title and
                            'performance' not in title and
                            url and 'soundcloud.com' in url):  # Убеждаемся, что это SoundCloud
                            
                            result['source'] = 'sc'  # Добавляем источник
                            soundcloud_results.append(result)
        except Exception as sc_error:
            logging.error(f"❌ Ошибка поиска SoundCloud для исполнителя {artist_name}: {sc_error}")
        
        # Объединяем результаты
        all_results = youtube_results + soundcloud_results
        
        if not all_results:
            logging.warning(f"⚠️ Нет результатов для исполнителя '{artist_name}' на обеих платформах")
            return []
        
        # Убираем дубликаты по ID (YouTube) и URL (SoundCloud)
        unique_results = []
        seen_ids = set()
        seen_urls = set()
        
        for result in all_results:
            if result.get('source') == 'yt' and result.get('id'):
                if result['id'] not in seen_ids:
                    unique_results.append(result)
                    seen_ids.add(result['id'])
            elif result.get('source') == 'sc' and result.get('url'):
                if result['url'] not in seen_urls:
                    unique_results.append(result)
                    seen_urls.add(result['url'])
        
        logging.info(f"✅ Найдено {len(unique_results)} уникальных треков исполнителя {artist_name} (YouTube: {len(youtube_results)}, SoundCloud: {len(soundcloud_results)})")
        
        # Перемешиваем результаты для разнообразия
        random.shuffle(unique_results)
        
        # Возвращаем нужное количество треков
        return unique_results[:limit]
        
    except Exception as e:
        logging.error(f"❌ Ошибка поиска треков исполнителя {artist_name}: {e}")
        return []

@dp.callback_query(F.data == "back_to_main")
async def back_to_main_menu(callback: types.CallbackQuery):
    """Возвращает пользователя в главное меню из inline-меню"""
    # Быстрый ответ для ускорения
    await callback.answer("⏳ Обрабатываю...")
    
    user_id = str(callback.from_user.id)
    
    try:
        # Отправляем видео без текста, только с меню
        await callback.message.edit_media(
            media=types.InputMediaVideo(
                media=types.FSInputFile("beer.mp4")
            ),
            reply_markup=main_menu
        )
    except Exception as e:
        # Если что-то пошло не так, просто отправляем главное меню
        try:
            await callback.message.edit_media(
                media=types.InputMediaVideo(
                    media=types.FSInputFile("beer.mp4")
                ),
                reply_markup=main_menu
            )
        except Exception as photo_error:
            await callback.message.edit_text("🎵 Главное меню", reply_markup=main_menu)

@dp.callback_query(F.data == "search_artist_again")
async def search_artist_again_callback(callback: types.CallbackQuery, state: FSMContext):
    """Повторный поиск по исполнителю"""
    # Быстрый ответ для ускорения
    await callback.answer("⏳ Обрабатываю...")
    
    user_id = str(callback.from_user.id)
    username = callback.from_user.username
    
    # Премиум система отключена - доступ открыт для всех
    pass
    
    try:
        await callback.message.edit_media(
            media=types.InputMediaVideo(
                media=types.FSInputFile("beer.mp4"),
                caption="👤 **Поиск по исполнителю**\n\n"
                        "🎵 Напишите название исполнителя или группы, чью музыку хотите найти.\n\n"
                        "💡 Примеры:\n"
                        "• Eminem\n"
                        "• Queen\n"
                        "• The Beatles\n"
                        "• Drake\n"
                        "• Coldplay\n\n"
                        "🔍 Я найду и загружу для вас лучшие треки этого исполнителя!"
            ),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_premium")]
            ])
        )
    except Exception as e:
        logging.error(f"❌ Ошибка отправки фото: {e}")
        await callback.message.edit_text(
            "👤 **Поиск по исполнителю**\n\n"
            "🎵 Напишите название исполнителя или группы, чью музыку хотите найти.\n\n"
            "💡 Примеры:\n"
            "• Eminem\n"
            "• Queen\n"
            "• The Beatles\n"
            "• Drake\n"
            "• Coldplay\n\n"
            "🔍 Я найду и загружу для вас лучшие треки этого исполнителя!",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_premium")]
            ])
        )
    await state.set_state(SearchStates.waiting_for_artist)

@dp.callback_query(F.data.startswith("search_artist_retry:"))
async def search_artist_retry_callback(callback: types.CallbackQuery, state: FSMContext):
    """Повторная попытка поиска по исполнителю"""
    artist_name = callback.data.split(":", 1)[1]
    user_id = str(callback.from_user.id)
    username = callback.from_user.username
    
    # Премиум система отключена - доступ открыт для всех
    pass
    
    logging.info(f"🔄 Повторная попытка поиска по исполнителю для пользователя {user_id}: '{artist_name}'")
    
    # Отправляем сообщение о начале повторного поиска
    try:
        search_msg = await callback.message.edit_media(
            media=types.InputMediaVideo(
                media=types.FSInputFile("beer.mp4"),
                caption=f"🔄 **Повторный поиск треков исполнителя {artist_name}...**\n\n"
                        "🎵 Ищу лучшие треки на YouTube...\n"
                        "⏳ Это может занять несколько минут."
            ),
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"❌ Ошибка отправки фото: {e}")
        search_msg = await callback.message.edit_text(
            f"🔄 **Повторный поиск треков исполнителя {artist_name}...**\n\n"
            "🎵 Ищу лучшие треки на YouTube...\n"
            "⏳ Это может занять несколько минут.",
            parse_mode="Markdown"
        )
    
    try:
        # Проверяем кеш для поиска по исполнителю
        cache_key = f"artist_{artist_name.lower().strip()}"
        cached_results = get_cached_search(cache_key)
        
        if cached_results:
            logging.info(f"🎯 Используем кешированные результаты для исполнителя {artist_name}")
            results = cached_results
        else:
            # Ищем треки исполнителя
            results = await asyncio.to_thread(search_artist_tracks, artist_name, 20)
            # Сохраняем в кеш
            if results:
                set_cached_search(cache_key, results)
        
        if not results:
            await search_msg.edit_text(
                f"❌ **Ничего не найдено**\n\n"
                f"🚫 По исполнителю '{artist_name}' ничего не найдено.\n"
                "💡 Возможные причины:\n"
                "• Неправильное написание имени\n"
                "• Исполнитель не представлен на YouTube\n"
                "• Ограничения по региону\n\n"
                "🔍 Попробуйте:\n"
                "• Проверить правильность написания\n"
                "• Использовать другое имя\n"
                "• Поискать альтернативные варианты",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="👤 Поиск другого исполнителя", callback_data="search_artist_again")],
                    [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_premium")]
                ])
            )
            return
        
        # Обновляем сообщение о начале загрузки
        await search_msg.edit_text(
            f"⏳ **Загружаю {len(results)} треков исполнителя {artist_name}...**\n\n"
            "🎵 Скачиваю аудиофайлы для прослушивания...\n"
            "💡 Это может занять несколько минут.",
            parse_mode="Markdown"
        )
        
        # Скачиваем треки и отправляем их
        downloaded_tracks = []
        failed_tracks = []
        
        for i, track in enumerate(results, 1):
            try:
                # Обновляем прогресс
                try:
                    await search_msg.edit_text(
                        f"⏳ **Загружаю трек {i}/{len(results)} исполнителя {artist_name}...**\n\n"
                        f"🎵 **{track.get('title', 'Без названия')}**\n"
                        "💾 Скачиваю аудиофайл...",
                        parse_mode="Markdown"
                    )
                except Exception as edit_error:
                    logging.error(f"❌ Ошибка обновления прогресса: {edit_error}")
                
                # Скачиваем трек
                url = f"https://www.youtube.com/watch?v={track['id']}"
                
                try:
                    download_task = asyncio.create_task(
                        download_track_from_url_for_genre(user_id, url)
                    )
                    filename = await asyncio.wait_for(download_task, timeout=120.0)  # 2 минуты таймаут
                except asyncio.TimeoutError:
                    logging.error(f"❌ Таймаут загрузки трека {track.get('title', 'Без названия')}")
                    failed_tracks.append(f"{track.get('title', 'Без названия')} (таймаут загрузки)")
                    continue
                
                if filename:
                    # Проверяем размер файла
                    try:
                        file_size = os.path.getsize(filename)
                        file_size_mb = file_size / (1024 * 1024)
                        
                        if file_size_mb > MAX_FILE_SIZE_MB:
                            logging.warning(f"⚠️ Файл слишком большой для отправки: {file_size_mb:.2f}MB > {MAX_FILE_SIZE_MB}MB")
                            failed_tracks.append(f"{track.get('title', 'Без названия')} (слишком большой файл)")
                            try:
                                os.remove(filename)
                            except:
                                pass
                            continue
                        
                        downloaded_tracks.append({
                            'filename': filename,
                            'title': track.get('title', 'Без названия'),
                            'duration': track.get('duration', 0),
                            'size_mb': file_size_mb
                        })
                    except Exception as size_error:
                        logging.error(f"❌ Ошибка проверки размера файла {track.get('title', 'Без названия')}: {size_error}")
                        failed_tracks.append(f"{track.get('title', 'Без названия')} (ошибка проверки размера)")
                        continue
                    
                    # Отправляем аудиофайл
                    try:
                        await callback.message.answer_audio(
                            types.FSInputFile(filename),
                            title=track.get('title', 'Без названия'),
                            performer=artist_name,
                            duration=track.get('duration', 0)
                        )
                        logging.info(f"✅ Аудиофайл отправлен: {track.get('title', 'Без названия')}")
                    except Exception as audio_error:
                        logging.error(f"❌ Ошибка отправки аудиофайла {track.get('title', 'Без названия')}: {audio_error}")
                        # Если не удалось отправить как аудио, отправляем как документ
                        try:
                            await callback.message.answer_document(
                                types.FSInputFile(filename),
                                caption=f"🎵 **{track.get('title', 'Без названия')}**\n👤 Исполнитель: {artist_name}"
                            )
                            logging.info(f"✅ Файл отправлен как документ: {track.get('title', 'Без названия')}")
                        except Exception as doc_error:
                            logging.error(f"❌ Ошибка отправки документа {track.get('title', 'Без названия')}: {doc_error}")
                            failed_tracks.append(track.get('title', 'Без названия'))
                            continue
                    
                    # Небольшая задержка между отправками
                    await asyncio.sleep(0.5)
                    
                else:
                    failed_tracks.append(track.get('title', 'Без названия'))
                    
            except Exception as e:
                logging.error(f"❌ Ошибка загрузки трека {track.get('title', 'Без названия')}: {e}")
                failed_tracks.append(track.get('title', 'Без названия'))
                continue
        
        # Формируем итоговое сообщение
        success_count = len(downloaded_tracks)
        failed_count = len(failed_tracks)
        
        message_text = f"✅ **Повторная загрузка треков исполнителя {artist_name} завершена!**\n\n"
        message_text += f"🎵 **Успешно загружено:** {success_count} треков\n"
        
        if success_count > 0:
            total_size = sum(track.get('size_mb', 0) for track in downloaded_tracks)
            message_text += f"💾 **Общий размер:** {total_size:.1f} MB\n\n"
        
        if failed_count > 0:
            message_text += f"❌ **Не удалось загрузить:** {failed_count} треков\n\n"
            message_text += "💡 Некоторые треки могли быть:\n"
            message_text += "• Недоступны на YouTube\n"
            message_text += "• Слишком большими для отправки\n"
            message_text += "• Защищены авторскими правами\n"
            message_text += "• Превысили таймаут загрузки\n\n"
        
        message_text += "🎵 Все загруженные треки доступны для прослушивания\n"
        message_text += "🎵 Аудиофайлы отправлены выше для прослушивания\n\n"
        message_text += "💡 Теперь вы можете:\n"
        message_text += "• Слушать треки прямо здесь\n"
        message_text += "• Искать другого исполнителя\n"
        message_text += "• 🎲 **Нажать 'По исполнителям' еще раз для нового поиска!**"
        
        # Создаем клавиатуру с опциями
        keyboard_buttons = []
        
        if failed_count > 0:
            keyboard_buttons.append([InlineKeyboardButton(text="🔄 Попробовать снова", callback_data=f"search_artist_retry:{artist_name}")])
        
        keyboard_buttons.extend([
            [InlineKeyboardButton(text="👤 Поиск другого исполнителя", callback_data="search_artist_again")],
            [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_premium")]
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        try:
            await search_msg.edit_text(
                message_text,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        except Exception as edit_error:
            logging.error(f"❌ Ошибка редактирования итогового сообщения: {edit_error}")
            # Пытаемся отправить новое сообщение
            try:
                await callback.message.answer(
                    message_text,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
            except Exception as send_error:
                logging.error(f"❌ Критическая ошибка отправки итогового сообщения: {send_error}")
        
        logging.info(f"✅ Повторно загружено {success_count} треков исполнителя {artist_name} для пользователя {user_id}")
        
    except Exception as e:
        logging.error(f"❌ Критическая ошибка повторного поиска по исполнителю {artist_name}: {e}")
        
        try:
            await search_msg.edit_text(
                f"❌ **Критическая ошибка**\n\n"
                f"🚫 Произошла критическая ошибка при повторном поиске треков исполнителя {artist_name}.\n"
                f"🔍 Ошибка: {str(e)[:100]}...\n\n"
                "💡 Попробуйте еще раз или обратитесь к администратору.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data=f"search_artist_retry:{artist_name}")],
                    [InlineKeyboardButton(text="👤 Поиск другого исполнителя", callback_data="search_artist_again")],
                    [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_premium")]
                ])
            )
        except Exception as final_error:
            logging.error(f"❌ Критическая ошибка отправки сообщения об ошибке: {final_error}")
            # Последняя попытка - отправляем простое сообщение
            try:
                await callback.message.answer(
                    f"❌ Произошла критическая ошибка при повторном поиске исполнителя {artist_name}. Попробуйте еще раз.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="👤 Поиск другого исполнителя", callback_data="search_artist_again")],
                        [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_premium")]
                    ])
                )
            except Exception as last_error:
                logging.error(f"❌ Полная потеря связи с пользователем {user_id}: {last_error}")

# === Обработчик пересылки треков с пометкой ===
@dp.message(F.audio)
async def handle_forwarded_audio(message: types.Message):
    """Обрабатывает пересланные аудиофайлы и добавляет пометку"""
    # Проверяем, является ли это пересланным сообщением
    if message.forward_from:
        sender_name = message.forward_from.first_name or "Неизвестный"
        
        # Создаем пометку
        caption = f"�� От {sender_name}\n\n"
        if message.caption:
            caption += message.caption
        
        # Отправляем трек с пометкой
        try:
            # Используем file_id для отправки
            await message.answer_audio(
                audio=message.audio.file_id,
                caption=caption
            )
        except Exception as e:
            logging.error(f"Ошибка при обработке пересланного аудио: {e}")
            await message.answer("❌ Ошибка при обработке пересланного трека")
    else:
        # Если это не пересланное сообщение, просто игнорируем
        pass

# === Запуск ===
async def main():
    logging.info("🚀 Запуск функции main()")
    try:
        # Проверяем, что бот и диспетчер инициализированы
        if not bot or not dp:
            logging.error("❌ Бот или диспетчер не инициализированы")
            raise RuntimeError("Бот или диспетчер не инициализированы")
        
        # Проверяем токен
        if not API_TOKEN:
            logging.warning("⚠️ Используется токен по умолчанию, проверьте настройки")
        
        # Запускаем фоновые задачи
        try:
            start_background_tasks()
            logging.info("✅ Фоновые задачи запущены")
        except Exception as e:
            logging.error(f"❌ Ошибка запуска фоновых задач: {e}")
            # Продолжаем работу бота даже если фоновые задачи не запустились
        
        await bot.delete_webhook(drop_pending_updates=True)
        logging.info("✅ Webhook удален")
        
        await dp.start_polling(bot, skip_updates=True)
        logging.info("✅ Polling запущен")
        
    except Exception as e:
        logging.error(f"❌ Критическая ошибка в main(): {e}")
        raise

async def main_worker():
    """Версия main() для дочерних потоков с webhook для Render"""
    logging.info("🚀 Запуск функции main_worker() в дочернем потоке")
    try:
        # Проверяем, что бот и диспетчер инициализированы
        if not bot or not dp:
            logging.error("❌ Бот или диспетчер не инициализированы")
            return
        
        # Проверяем токен
        if not API_TOKEN:
            logging.warning("⚠️ Используется токен по умолчанию, проверьте настройки")
        
        # Запускаем фоновые задачи
        try:
            start_background_tasks()
            logging.info("✅ Фоновые задачи запущены")
        except Exception as e:
            logging.error(f"❌ Ошибка запуска фоновых задач: {e}")
        
        # Проверяем, запущен ли в Render
        if os.environ.get('RENDER'):
            logging.info("🌐 Запуск в Render - настраиваем webhook")
            try:
                # Получаем URL сервиса из переменных окружения
                service_url = os.environ.get('RENDER_EXTERNAL_URL')
                if service_url:
                    webhook_url = f"{service_url}/webhook"
                    logging.info(f"🔗 Настраиваем webhook: {webhook_url}")
                    
                    # Устанавливаем webhook
                    await bot.set_webhook(url=webhook_url)
                    logging.info("✅ Webhook установлен успешно")
                    
                    # Запускаем обработчик webhook обновлений
                    logging.info("🔄 Запускаем обработчик webhook обновлений")
                    webhook_task = asyncio.create_task(webhook_update_processor())
                    
                    # Запускаем задачу очистки семафоров пользователей
                    cleanup_task = asyncio.create_task(cleanup_user_semaphores())
                    
                    # В Render используем только webhook, не запускаем polling
                    logging.info("✅ Webhook настроен, бот готов к работе")
                    
                    # Держим поток живым для webhook
                    while True:
                        await asyncio.sleep(1)
                else:
                    logging.warning("⚠️ RENDER_EXTERNAL_URL не установлен, используем только webhook")
                    # Держим поток живым для webhook
                    while True:
                        await asyncio.sleep(1)
            except Exception as e:
                logging.error(f"❌ Ошибка настройки webhook: {e}")
                # В Render не используем polling, только webhook
                while True:
                    await asyncio.sleep(1)
        else:
            # Локальный запуск - используем polling
            logging.info("💻 Локальный запуск - используем polling")
            await dp.start_polling(bot, skip_updates=True)
        
        logging.info("✅ Бот готов к работе в дочернем потоке")
        
    except Exception as e:
        logging.error(f"❌ Критическая ошибка в main_worker(): {e}")
        return

# Удалены дублирующие функции - они уже определены выше

@dp.callback_query(F.data.startswith("check_yoomoney_"))
async def check_yoomoney_payment_callback(callback: types.CallbackQuery):
    """Проверка оплаты через YooMoney"""
    user_id = callback.data.split("_")[-1]
    username = callback.from_user.username
    
    # Проверяем антиспам
    is_allowed, time_until = check_antispam(user_id)
    if not is_allowed:
        await callback.answer(f"⏳ Подождите {time_until:.1f} сек. перед следующим запросом", show_alert=True)
        return
    
    logging.info(f"🔍 Проверка оплаты YooMoney для пользователя {user_id}")
    
    try:
        # Проверяем платеж
        payment_confirmed = await check_yoomoney_payment(user_id)
        
        if payment_confirmed:
            # Активируем премиум доступ
            if add_premium_user(user_id, username):
                success_message = (
                    "🎉 **ОПЛАТА ПОДТВЕРЖДЕНА!**\n\n"
                    "💎 **Премиум доступ активирован!**\n\n"
                    "🚀 **Теперь у вас есть:**\n"
                    "• ⚡ Мгновенная загрузка треков\n"
                    "• 🎵 Высокое качество звука\n"
                    "• 🎭 Эксклюзивные функции\n"
                    "• 💾 Безлимитное хранилище\n\n"
                    "🎵 **Наслаждайтесь музыкой!**"
                )
                
                await callback.message.edit_media(
                    media=types.InputMediaVideo(
                        media=types.FSInputFile("beer.mp4"),
                        caption=success_message
                    ),
                    reply_markup=main_menu
                )
                
                await callback.answer("✅ Премиум доступ активирован!", show_alert=True)
                logging.info(f"✅ Премиум доступ активирован для пользователя {user_id} через YooMoney")
                
            else:
                await callback.answer("❌ Ошибка активации премиума. Обратитесь в поддержку.", show_alert=True)
        else:
            # Платеж не подтвержден
            await callback.answer(
                "⏳ Платеж еще не поступил или обрабатывается.\n"
                "Попробуйте проверить через 1-2 минуты.", 
                show_alert=True
            )
            
    except Exception as e:
        logging.error(f"❌ Ошибка проверки оплаты YooMoney: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)

@dp.callback_query(F.data.startswith("check_payment:"))
async def check_payment_callback(callback: types.CallbackQuery):
    """Автоматическая проверка TON платежа"""
    payment_code = callback.data.split(":")[1]
    user_id = str(callback.from_user.id)
    username = callback.from_user.username
    
    # Показываем сообщение о проверке
    await callback.answer("🔍 Проверяю оплату...", show_alert=False)
    
    # Проверяем TON платеж автоматически
    payment_found = await check_ton_payment(user_id)
    
    if payment_found:
        # Платеж найден - активируем премиум
        success = add_premium_user(user_id, username)
        if success:
            success_message = (
                "✅ **ОПЛАТА ПОДТВЕРЖДЕНА!**\n\n"
                "🎉 Поздравляем! Ваш премиум доступ активирован!\n\n"
                "**Теперь вам доступны:**\n"
    
                "• 👤 Поиск по исполнителям\n\n"
                "**Срок действия:** 30 дней\n"
                "**Добро пожаловать в премиум!** 🚀"
            )
            
            try:
                await callback.message.edit_text(success_message, parse_mode="Markdown")
            except Exception as e:
                logging.error(f"❌ Ошибка редактирования сообщения: {e}")
                await callback.message.answer(success_message, parse_mode="Markdown")
                await callback.message.delete()
            
            # Отправляем главное меню
            await callback.message.answer("🔙 Возврат в главное меню", reply_markup=main_menu)
        else:
            await callback.answer("❌ Ошибка активации премиума. Обратитесь в поддержку.", show_alert=True)
    else:
        # Платеж не найден
        not_found_message = (
            "❌ **Платеж не найден**\n\n"
            "Мы не смогли найти ваш платеж. Возможные причины:\n"
            "• Платеж еще не поступил (подождите 5-10 минут)\n"
                            "• Неправильная сумма (должно быть 1 USDT)\n"
            "• Не указан код в комментарии\n"
            "• Платеж отправлен на другой адрес\n\n"
            "**Попробуйте еще раз или обратитесь в поддержку.**"
        )
        
        # Обновляем клавиатуру для повторной проверки
        retry_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Проверить снова", callback_data=f"check_payment:{payment_code}")],
            [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_main_from_buy_premium")]
        ])
        
        try:
            await callback.message.edit_text(not_found_message, reply_markup=retry_keyboard, parse_mode="Markdown")
        except Exception as e:
            logging.error(f"❌ Ошибка редактирования сообщения: {e}")
            await callback.message.answer(not_found_message, reply_markup=retry_keyboard, parse_mode="Markdown")
            await callback.message.delete()

@dp.message(Command("check_payments"))
async def check_payments_command(message: types.Message):
    """Команда для проверки платежей"""
    pass

@dp.message(Command("list_premium"))
async def list_premium_command(message: types.Message):
    """Команда для просмотра списка премиум пользователей"""
    # Проверяем, является ли отправитель администратором
    user_id = str(message.from_user.id)
    username = message.from_user.username
    
    if not is_admin(user_id, username):
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return
    
    try:
        premium_data = load_json(PREMIUM_USERS_FILE, {"premium_users": [], "premium_usernames": [], "subscriptions": {}})
        
        premium_users = premium_data.get("premium_users", [])
        premium_usernames = premium_data.get("premium_usernames", [])
        subscriptions = premium_data.get("subscriptions", {})
        
        if not premium_users and not premium_usernames:
            await message.answer("📋 Список премиум пользователей пуст.")
            return
        
        response = "📋 Список премиум пользователей:\n\n"
        
        # Показываем пользователей по ID
        if premium_users:
            response += "🆔 По ID:\n"
            for user_id in premium_users:
                sub_info = subscriptions.get(user_id, {})
                if sub_info:
                    start_date = sub_info.get("start_date", "Неизвестно")
                    expiry_date = sub_info.get("expiry_date", "Неизвестно")
                    payment_method = sub_info.get("payment_method", "Неизвестно")
                    response += f"• ID: {user_id} | {payment_method}\n"
                    response += f"  📅 С: {start_date[:10]} | До: {expiry_date[:10]}\n\n"
                else:
                    response += f"• ID: `{user_id}` | Нет данных о подписке\n\n"
        
        # Показываем пользователей по username
        if premium_usernames:
            response += "👤 По username:\n"
            for username in premium_usernames:
                response += f"• @{username}\n"
        
        await message.answer(response)
        
    except Exception as e:
        await message.answer(f"❌ Ошибка при получении списка: {e}")

@dp.message(Command("admin_info"))
async def admin_info_command(message: types.Message):
    """Команда для просмотра информации об администраторе"""
    user_id = str(message.from_user.id)
    username = message.from_user.username
    
    # Отладочная информация
    debug_response = "🔍 Отладочная информация:\n\n"
    debug_response += f"🆔 Ваш ID: {user_id}\n"
    debug_response += f"👤 Ваш username: {username}\n"
    debug_response += f"🔐 Проверка админских прав: {is_admin(user_id, username)}\n\n"
    
    if not is_admin(user_id, username):
        await message.answer(f"{debug_response}❌ У вас нет прав для выполнения этой команды.\n\nПроверьте:\n• Ваш username: {username}\n• Список админов: wtfguys4")
        return
    
    response = "👑 Информация об администраторе:\n\n"
    response += f"🆔 Ваш ID: {user_id}\n"
    response += f"👤 Ваш username: {username}\n"

@dp.message(Command("list_users"))
async def list_users_command(message: types.Message):
    """Команда для просмотра всех пользователей бота"""
    # Проверяем, является ли отправитель администратором
    user_id = str(message.from_user.id)
    username = message.from_user.username
    
    if not is_admin(user_id, username):
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return
    
    try:
        global user_tracks
        
        # Проверяем, что user_tracks не None
        if user_tracks is None:
            user_tracks = {}
            logging.warning("⚠️ list_users_command: user_tracks был None, инициализируем пустым словарем")
        
        if not user_tracks:
            await message.answer("📋 Список пользователей пуст.")
            return
        
        # Загружаем данные о премиум пользователях для сравнения
        premium_data = load_json(PREMIUM_USERS_FILE, {"premium_users": [], "premium_usernames": []})
        premium_users = set(premium_data.get("premium_users", []))
        premium_usernames = set(premium_data.get("premium_usernames", []))
        
        # Сортируем пользователей по количеству треков (от большего к меньшему)
        sorted_users = sorted(user_tracks.items(), key=lambda x: len(x[1]) if x[1] else 0, reverse=True)
        
        response = f"📋 Всего пользователей: {len(user_tracks)}\n\n"
        
        # Показываем топ-20 пользователей с наибольшим количеством треков
        top_users = sorted_users[:20]
        
        for i, (user_id, tracks) in enumerate(top_users, 1):
            track_count = len(tracks) if tracks else 0
            
            # Определяем статус пользователя
            if user_id in premium_users:
                status = "💎 ПРЕМИУМ"
            elif any(username in premium_usernames for username in [user_id]):  # Проверяем username
                status = "💎 ПРЕМИУМ"
            else:
                status = "📱 ОБЫЧНЫЙ"
            
            # Показываем размер коллекции в MB
            total_size = 0
            if tracks:
                for track in tracks:
                    if isinstance(track, dict):
                        total_size += track.get('size_mb', 0)
                    else:
                        # Для старых треков размер неизвестен
                        total_size += 0
            
            response += f"{i}. 🆔 {user_id} | {status}\n"
            response += f"   🎵 Треков: {track_count} | 💾 Размер: {total_size:.1f} MB\n\n"
        
        # Если пользователей больше 20, показываем общую статистику
        if len(user_tracks) > 20:
            remaining_users = sorted_users[20:]
            total_tracks = sum(len(tracks) if tracks else 0 for _, tracks in user_tracks.items())
            total_size = sum(
                sum(track.get('size_mb', 0) if isinstance(track, dict) else 0 for track in tracks) 
                if tracks else 0 
                for _, tracks in user_tracks.items()
            )
            
            response += f"📊 Общая статистика:\n"
            response += f"• Всего пользователей: {len(user_tracks)}\n"
            response += f"• Всего треков: {total_tracks}\n"
            response += f"• Общий размер: {total_size:.1f} MB\n"
            response += f"• Среднее количество треков: {total_tracks / len(user_tracks):.1f}\n"
        
        # Разбиваем на части, если сообщение слишком длинное
        if len(response) > 4000:
            parts = [response[i:i+4000] for i in range(0, len(response), 4000)]
            for i, part in enumerate(parts, 1):
                await message.answer(f"📋 Часть {i}/{len(parts)}:\n\n{part}")
        else:
            await message.answer(response)
        
    except Exception as e:
        logging.error(f"❌ Ошибка в list_users_command: {e}")
        await message.answer(f"❌ Ошибка при получении списка пользователей: {e}")

@dp.message(Command("user_stats"))
async def user_stats_command(message: types.Message):
    """Команда для просмотра статистики пользователей"""
    # Проверяем, является ли отправитель администратором
    user_id = str(message.from_user.id)
    username = message.from_user.username
    
    if not is_admin(user_id, username):
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return
    
    try:
        global user_tracks
        
        # Проверяем, что user_tracks не None
        if user_tracks is None:
            user_tracks = {}
            logging.warning("⚠️ user_stats_command: user_tracks был None, инициализируем пустым словарем")
        
        if not user_tracks:
            await message.answer("📊 Статистика недоступна - нет пользователей.")
            return
        
        # Загружаем данные о премиум пользователях
        premium_data = load_json(PREMIUM_USERS_FILE, {"premium_users": [], "premium_usernames": []})
        premium_users = set(premium_data.get("premium_users", []))
        premium_usernames = set(premium_data.get("premium_usernames", []))
        
        # Подсчитываем статистику
        total_users = len(user_tracks)
        premium_count = 0
        regular_count = 0
        total_tracks = 0
        total_size = 0
        users_with_tracks = 0
        
        for user_id, tracks in user_tracks.items():
            track_count = len(tracks) if tracks else 0
            
            # Определяем статус пользователя
            if user_id in premium_users or any(username in premium_usernames for username in [user_id]):
                premium_count += 1
            else:
                regular_count += 1
            
            if track_count > 0:
                users_with_tracks += 1
                total_tracks += track_count
                
                # Подсчитываем размер
                for track in tracks:
                    if isinstance(track, dict):
                        total_size += track.get('size_mb', 0)
        
        # Формируем ответ
        response = "📊 Статистика пользователей бота:\n\n"
        response += f"👥 **Общая информация:**\n"
        response += f"• Всего пользователей: {total_users}\n"
        response += f"• Пользователей с треками: {users_with_tracks}\n"
        response += f"• Пользователей без треков: {total_users - users_with_tracks}\n\n"
        
        response += f"💎 **Премиум пользователи:**\n"
        response += f"• Количество: {premium_count}\n"
        response += f"• Процент: {(premium_count / total_users * 100):.1f}%\n\n"
        
        response += f"📱 **Обычные пользователи:**\n"
        response += f"• Количество: {regular_count}\n"
        response += f"• Процент: {(regular_count / total_users * 100):.1f}%\n\n"
        
        response += f"🎵 **Музыкальная статистика:**\n"
        response += f"• Всего треков: {total_tracks}\n"
        response += f"• Общий размер: {total_size:.1f} MB\n"
        response += f"• Среднее количество треков: {total_tracks / users_with_tracks:.1f}\n"
        response += f"• Средний размер коллекции: {total_size / users_with_tracks:.1f} MB\n\n"
        
        response += f"📈 **Активность:**\n"
        response += f"• Активных пользователей: {users_with_tracks}\n"
        response += f"• Процент активности: {(users_with_tracks / total_users * 100):.1f}%"
        
        await message.answer(response, parse_mode="Markdown")
        
    except Exception as e:
        logging.error(f"❌ Ошибка в user_stats_command: {e}")
        await message.answer(f"❌ Ошибка при получении статистики: {e}")
    response += f"🔐 Статус: Администратор\n\n"
    response += "Доступные команды:\n"
    response += "• /add_premium <user_id или username> - добавить премиум\n"
    response += "• /remove_premium <user_id или username> - удалить премиум\n"
    response += "• /list_premium - список премиум пользователей\n"
    response += "• /list_users - все пользователи бота\n"
    response += "• /user_stats - статистика пользователей\n"
    response += "• /admin_info - информация об администраторе\n"
    response += "• /reload_premium - перезагрузить данные премиум\n"
    response += "• /cleanup_status - статус автоматической очистки\n"
    response += "• /cleanup_toggle - включить/выключить автоматическую очистку\n"
    response += "• /cleanup_now - запустить очистку сейчас\n"
    response += "• /premium_stats - статистика премиум пользователей\n"
    response += "• /premium_monitor - мониторинг премиума\n"
    
    await message.answer(response)

@dp.message(Command("check_me"))
async def check_me_command(message: types.Message):
    """Команда для проверки текущего пользователя (доступна всем)"""
    user_id = str(message.from_user.id)
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    
    response = "👤 Информация о вас:\n\n"
    response += f"🆔 ID: {user_id}\n"
    response += f"👤 Username: {username}\n"
    response += f"📝 Имя: {first_name}\n"
    response += f"📝 Фамилия: {last_name}\n"
    response += f"🔐 Админ: {is_admin(user_id, username)}\n\n"
    
    if is_admin(user_id, username):
        response += "✅ Вы администратор!\n"
        response += "Используйте команды:\n"
        response += "• /admin_info - подробная информация\n"
        response += "• /add_premium - добавить премиум\n"
        response += "• /remove_premium - удалить премиум\n"
        response += "• /list_premium - список премиум пользователей\n"
        response += "• /list_users - все пользователи бота\n"
        response += "• /user_stats - статистика пользователей\n"
        response += "• /reload_premium - перезагрузить данные\n"
        response += "• /cleanup_status - статус автоматической очистки\n"
        response += "• /cleanup_toggle - включить/выключить очистку\n"
        response += "• /cleanup_now - запустить очистку сейчас\n"
        response += "• /premium_stats - статистика премиум пользователей\n"
        response += "• /premium_monitor - мониторинг премиума\n"
    else:
        response += "❌ Вы не администратор\n"
        response += "Обратитесь к администратору для получения прав\n"
    
    await message.answer(response)

@dp.message(Command("reload_premium"))
async def reload_premium_command(message: types.Message):
    """Команда для принудительной перезагрузки данных премиум (для администраторов)"""
    user_id = str(message.from_user.id)
    username = message.from_user.username
    
    if not is_admin(user_id, username):
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return
    
    try:
        # Принудительно перезагружаем данные
        premium_data = load_json(PREMIUM_USERS_FILE, {"premium_users": [], "premium_usernames": [], "subscriptions": {}})
        
        response = "🔄 Данные премиум перезагружены:\n\n"
        response += f"📊 Пользователей по ID: {len(premium_data.get('premium_users', []))}\n"
        response += f"📊 Пользователей по username: {len(premium_data.get('premium_usernames', []))}\n"
        response += f"📊 Подписок: {len(premium_data.get('subscriptions', {}))}\n\n"
        
        # Показываем список username'ов
        usernames = premium_data.get('premium_usernames', [])
        if usernames:
            response += "👤 Usernames:\n"
            for username in usernames:
                response += f"• @{username}\n"
        
        await message.answer(response)
        logging.info(f"✅ Администратор {user_id} ({username}) перезагрузил данные премиум")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка при перезагрузке данных: {e}")
        logging.error(f"❌ Ошибка перезагрузки данных премиум: {e}")

# === КОМАНДЫ УПРАВЛЕНИЯ АВТОМАТИЧЕСКОЙ ОЧИСТКОЙ ===
@dp.message(Command("cleanup_status"))
async def cleanup_status_command(message: types.Message):
    """Команда для просмотра статуса автоматической очистки"""
    user_id = str(message.from_user.id)
    username = message.from_user.username
    
    if not is_admin(user_id, username):
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return
    
    try:
        # Получаем информацию о папке cache
        cache_dir = CACHE_DIR
        cache_info = "📁 **Информация о папке cache:**\n\n"
        
        if os.path.exists(cache_dir):
            try:
                files = [f for f in os.listdir(cache_dir) if f.endswith('.mp3')]
                total_files = len(files)
                
                # Подсчитываем общий размер
                total_size = 0
                for filename in files:
                    file_path = os.path.join(cache_dir, filename)
                    try:
                        total_size += os.path.getsize(file_path)
                    except:
                        pass
                
                total_size_mb = total_size / (1024 * 1024)
                
                cache_info += f"• 📂 Всего MP3 файлов: {total_files}\n"
                cache_info += f"• 💾 Общий размер: {total_size_mb:.2f} MB\n"
                cache_info += f"• 🧹 Автоматическая очистка: {'✅ Включена' if AUTO_CLEANUP_ENABLED else '❌ Отключена'}\n"
                cache_info += f"• ⏱ Задержка очистки: {AUTO_CLEANUP_DELAY} сек\n"
                cache_info += f"• 📝 Логирование: {'✅ Включено' if CLEANUP_LOGGING else '❌ Отключено'}\n\n"
                
                if total_files > 0:
                    cache_info += "📋 **Последние 10 файлов:**\n"
                    for i, filename in enumerate(files[:10], 1):
                        file_path = os.path.join(cache_dir, filename)
                        try:
                            file_size = os.path.getsize(file_path)
                            file_size_mb = file_size / (1024 * 1024)
                            cache_info += f"{i}. {filename} ({file_size_mb:.2f} MB)\n"
                        except:
                            cache_info += f"{i}. {filename} (размер неизвестен)\n"
                    
                    if total_files > 10:
                        cache_info += f"... и еще {total_files - 10} файлов\n"
                else:
                    cache_info += "📂 Папка cache пуста"
                    
            except Exception as e:
                cache_info += f"❌ Ошибка чтения папки cache: {e}"
        else:
            cache_info += "❌ Папка cache не существует"
        
        await message.answer(cache_info, parse_mode="Markdown")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка при получении статуса очистки: {e}")

@dp.message(Command("cleanup_toggle"))
async def cleanup_toggle_command(message: types.Message):
    """Команда для включения/выключения автоматической очистки"""
    user_id = str(message.from_user.id)
    username = message.from_user.username
    
    if not is_admin(user_id, username):
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return
    
    try:
        global AUTO_CLEANUP_ENABLED
        
        # Переключаем состояние
        AUTO_CLEANUP_ENABLED = not AUTO_CLEANUP_ENABLED
        
        status = "✅ включена" if AUTO_CLEANUP_ENABLED else "❌ отключена"
        
        response = f"🧹 **Автоматическая очистка {status}**\n\n"
        response += f"**Текущие настройки:**\n"
        response += f"• 🧹 Автоматическая очистка: {'✅ Включена' if AUTO_CLEANUP_ENABLED else '❌ Отключена'}\n"
        response += f"• ⏱ Задержка очистки: {AUTO_CLEANUP_DELAY} сек\n"
        response += f"• 📝 Логирование: {'✅ Включено' if CLEANUP_LOGGING else '❌ Отключено'}\n\n"
        
        if AUTO_CLEANUP_ENABLED:
            response += "✅ Теперь файлы будут автоматически удаляться после отправки пользователям"
        else:
            response += "❌ Теперь файлы НЕ будут автоматически удаляться"
        
        await message.answer(response, parse_mode="Markdown")
        logging.info(f"🧹 Администратор {user_id} ({username}) {'включил' if AUTO_CLEANUP_ENABLED else 'выключил'} автоматическую очистку")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка при переключении очистки: {e}")

@dp.message(Command("cleanup_now"))
async def cleanup_now_command(message: types.Message):
    """Команда для немедленного запуска очистки"""
    user_id = str(message.from_user.id)
    username = message.from_user.username
    
    if not is_admin(user_id, username):
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return
    
    try:
        await message.answer("🧹 Запускаю очистку файлов...")
        
        # Запускаем очистку
        cleanup_orphaned_files()
        
        await message.answer("✅ Очистка завершена! Проверьте статус командой /cleanup_status")
        logging.info(f"🧹 Администратор {user_id} ({username}) запустил немедленную очистку")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка при запуске очистки: {e}")

@dp.message(Command("premium_stats"))
async def premium_stats_command(message: types.Message):
    """Команда для просмотра статистики премиум пользователей"""
    user_id = str(message.from_user.id)
    username = message.from_user.username
    
    if not is_admin(user_id, username):
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return
    
    try:
        # Загружаем данные о премиуме
        premium_data = load_json(PREMIUM_USERS_FILE, {"premium_users": [], "premium_usernames": [], "subscriptions": {}})
        premium_users = set(premium_data.get("premium_users", []))
        premium_usernames = set(premium_data.get("premium_usernames", []))
        subscriptions = premium_data.get("subscriptions", {})
        
        # Получаем статистику по коллекциям
        global user_tracks
        if not user_tracks:
            await message.answer("📊 Статистика недоступна - нет пользователей.")
            return
        
        # Подсчитываем статистику
        total_premium_users = len(premium_users) + len(premium_usernames)
        active_subscriptions = sum(1 for sub in subscriptions.values() if sub.get("active", False))
        expired_subscriptions = sum(1 for sub in subscriptions.values() if not sub.get("active", False))
        
        # Статистика по коллекциям
        premium_collections = []
        total_premium_tracks = 0
        total_premium_size = 0
        
        for user_id, tracks in user_tracks.items():
            if user_id in premium_users:
                track_count = len(tracks) if tracks else 0
                collection_size = 0
                
                if tracks:
                    for track in tracks:
                        if isinstance(track, dict):
                            collection_size += track.get('size_mb', 0)
                        else:
                            # Для старых треков размер неизвестен
                            collection_size += 0
                
                premium_collections.append({
                    'user_id': user_id,
                    'track_count': track_count,
                    'size_mb': collection_size
                })
                
                total_premium_tracks += track_count
                total_premium_size += collection_size
        
        # Сортируем по размеру коллекции
        premium_collections.sort(key=lambda x: x['size_mb'], reverse=True)
        
        # Формируем ответ
        response = "📊 **Статистика премиум пользователей**\n\n"
        response += f"👥 **Общая информация:**\n"
        response += f"• Всего премиум пользователей: {total_premium_users}\n"
        response += f"• Активных подписок: {active_subscriptions}\n"
        response += f"• Истекших подписок: {expired_subscriptions}\n\n"
        
        response += f"🎵 **Музыкальная статистика:**\n"
        response += f"• Всего треков у премиум: {total_premium_tracks}\n"
        response += f"• Общий размер коллекций: {total_premium_size:.1f} MB\n"
        response += f"• Средний размер коллекции: {total_premium_size / max(len(premium_collections), 1):.1f} MB\n\n"
        
        if premium_collections:
            response += f"🏆 **Топ-10 коллекций по размеру:**\n"
            for i, collection in enumerate(premium_collections[:10], 1):
                response += f"{i}. ID: {collection['user_id']} | {collection['track_count']} треков | {collection['size_mb']:.1f} MB\n"
        
        await message.answer(response, parse_mode="Markdown")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка при получении статистики: {e}")

@dp.message(Command("premium_monitor"))
async def premium_monitor_command(message: types.Message):
    """Команда для мониторинга премиум пользователей"""
    user_id = str(message.from_user.id)
    username = message.from_user.username
    
    if not is_admin(user_id, username):
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return
    
    try:
        await message.answer("🔍 Запускаю мониторинг премиум пользователей...")
        
        # Запускаем проверки
        await check_premium_expiry()
        await check_premium_files_integrity()
        
        await message.answer("✅ Мониторинг премиума завершен! Проверьте логи для деталей.")
        logging.info(f"🔍 Администратор {user_id} ({username}) запустил мониторинг премиума")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка при запуске мониторинга: {e}")

# === ФУНКЦИИ ВРЕМЕННОГО СКАЧИВАНИЯ И УДАЛЕНИЯ ===
async def download_track_to_temp(user_id: str, url: str, title: str) -> str:
    """
    Скачивает трек во временную папку cache/ и возвращает путь к файлу.
    
    Args:
        user_id: ID пользователя
        url: URL для скачивания
        title: Название трека
        
    Returns:
        Путь к скачанному файлу или None при ошибке
    """
    try:
        logging.info(f"📥 Скачиваю трек во временную папку: {title}")
        
        # Проверяем кеш для скачанных файлов
        cache_key = f"download_{hashlib.md5(url.encode()).hexdigest()}"
        cached_file = get_cached_metadata(cache_key)
        
        if cached_file and os.path.exists(cached_file):
            logging.info(f"🎯 Используем кешированный файл для {title}")
            return cached_file
        
        # Создаем уникальное имя файла
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_title = safe_title[:50]  # Ограничиваем длину
        timestamp = str(int(time.time()))
        filename = f"{safe_title}_{timestamp}.mp3"
        file_path = os.path.join(CACHE_DIR, filename)
        
        # Проверяем, что папка cache существует и доступна для записи
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            # Проверяем права на запись
            test_file = os.path.join(CACHE_DIR, "test_write.tmp")
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
            logging.info(f"✅ Папка cache доступна для записи: {CACHE_DIR}")
        except Exception as cache_error:
            logging.error(f"❌ Ошибка доступа к папке cache: {cache_error}")
            return None
        
        # Скачиваем трек
        outtmpl = file_path.replace('.mp3', '.%(ext)s')
        logging.info(f"🔍 Шаблон для скачивания: {outtmpl}")
        
        # Проверяем, что yt-dlp доступен
        try:
            import yt_dlp
            logging.info(f"✅ yt-dlp доступен, версия: {yt_dlp.version.__version__}")
        except ImportError:
            logging.error("❌ yt-dlp не установлен")
            return None
        except Exception as ytdlp_error:
            logging.error(f"❌ Ошибка импорта yt-dlp: {ytdlp_error}")
            return None
        
        # Проверяем, что FFmpeg доступен для конвертации в MP3
        try:
            import subprocess
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                logging.info("✅ FFmpeg доступен для конвертации")
            else:
                logging.warning("⚠️ FFmpeg недоступен, конвертация может не работать")
        except Exception as ffmpeg_error:
            logging.warning(f"⚠️ Не удалось проверить FFmpeg: {ffmpeg_error}")
        
        # Используем Semaphore для ограничения одновременных загрузок
        try:
            async with download_semaphore:
                loop = asyncio.get_running_loop()
                logging.info(f"🔍 Запускаю скачивание через yt-dlp: {url}")
                fn_info = await loop.run_in_executor(yt_executor, _ydl_download_blocking, url, outtmpl, COOKIES_FILE, False)
        except Exception as executor_error:
            logging.error(f"❌ Ошибка в ThreadPoolExecutor: {executor_error}")
            return None
        
        logging.info(f"🔍 Результат yt-dlp: {fn_info} (тип: {type(fn_info)})")
        
        if not fn_info:
            logging.error(f"❌ Не удалось скачать трек: {title}")
            return None
        
        # Проверяем, что fn_info является кортежем
        if not isinstance(fn_info, tuple) or len(fn_info) != 2:
            logging.error(f"❌ Неожиданный формат результата скачивания: {type(fn_info)}")
            return None
            
        downloaded_file, info = fn_info
        logging.info(f"🔍 Распакованный результат: файл={downloaded_file}, info={type(info)}")
        
        # Проверяем, что файл действительно скачался
        if not downloaded_file or not isinstance(downloaded_file, str):
            logging.error(f"❌ Некорректный путь к скачанному файлу: {downloaded_file}")
            return None
            
        logging.info(f"📁 Трек скачан во временную папку: {downloaded_file}")
        
        # Проверяем размер файла
        try:
            if not os.path.exists(downloaded_file):
                logging.error(f"❌ Скачанный файл не существует: {downloaded_file}")
                # Проверяем, может быть файл создался в другом месте или с другим расширением
                cache_dir = CACHE_DIR
                if os.path.exists(cache_dir):
                    cache_files = [f for f in os.listdir(cache_dir) if f.startswith(os.path.basename(file_path).split('_')[0])]
                    logging.info(f"🔍 Возможные файлы в cache: {cache_files}")
                    
                    # Ищем файл с любым расширением
                    for cache_file in cache_files:
                        full_path = os.path.join(cache_dir, cache_file)
                        if os.path.exists(full_path) and os.path.getsize(full_path) > 0:
                            logging.info(f"✅ Найден альтернативный файл: {full_path}")
                            return full_path
                return None
                
            size_mb = os.path.getsize(downloaded_file) / (1024 * 1024)
            if size_mb > MAX_FILE_SIZE_MB:
                try:
                    os.remove(downloaded_file)
                    logging.warning(f"❌ Файл превышает максимальный размер {MAX_FILE_SIZE_MB}MB: {size_mb:.2f}MB")
                except:
                    pass
                return None
                
            logging.info(f"✅ Трек успешно скачан: {downloaded_file} ({size_mb:.2f}MB)")
            
            # Сохраняем путь к файлу в кеш
            set_cached_metadata(cache_key, downloaded_file)
            
            return downloaded_file
            
        except Exception as size_error:
            logging.error(f"❌ Ошибка проверки размера файла: {size_error}")
            return None
            
    except Exception as e:
        logging.exception(f"❌ Ошибка скачивания трека во временную папку {title}: {e}")
        return None

async def delete_temp_file(file_path: str) -> bool:
    """
    Удаляет временный файл с проверкой существования.
    
    Args:
        file_path: Путь к файлу для удаления
        
    Returns:
        True если файл успешно удален, False в противном случае
    """
    try:
        # Проверяем существование файла
        if not os.path.exists(file_path):
            logging.info(f"🧹 Файл уже удален: {file_path}")
            return True
        
        # Получаем информацию о файле перед удалением
        try:
            file_size = os.path.getsize(file_path)
            file_size_mb = file_size / (1024 * 1024)
        except Exception:
            file_size_mb = 0
        
        # Удаляем файл
        os.remove(file_path)
        
        logging.info(f"🧹 Временный файл удален: {file_path} ({file_size_mb:.2f} MB)")
        return True
        
    except Exception as e:
        logging.error(f"❌ Ошибка удаления временного файла {file_path}: {e}")
        return False

# === ФУНКЦИИ ПРИОРИТЕТНОЙ ОЧЕРЕДИ ===
async def add_to_download_queue(user_id: str, url: str, is_premium: bool = False, priority: int = 0):
    """Добавляет задачу в соответствующую очередь загрузки"""
    try:
        # Проверяем входные параметры
        if not user_id or not url:
            logging.error("❌ add_to_download_queue: некорректные параметры")
            return False
            
        if not isinstance(user_id, str) or not isinstance(url, str):
            logging.error("❌ add_to_download_queue: некорректные типы параметров")
            return False
        
        # Проверяем кэш метаданных
        if url in track_metadata_cache:
            logging.info(f"💾 Используем кэшированные метаданные для {url}")
            cached_info = track_metadata_cache[url]
            
            # Инициализируем список треков для пользователя, если его нет
            if user_tracks is None:
                user_tracks = {}
            if str(user_id) not in user_tracks:
                user_tracks[str(user_id)] = []
            elif user_tracks[str(user_id)] is None:
                user_tracks[str(user_id)] = []
                
            user_tracks[str(user_id)].append(cached_info)
            save_tracks()
            
            logging.info(f"✅ Метаданные трека из кэша успешно добавлены для пользователя {user_id}")
            return True
        else:
            # Используем быструю систему очередей
            logging.info(f"💾 Добавляю трек в очередь для пользователя {user_id}: {url}")
            
            # Добавляем в очередь и получаем мгновенный ответ
            success = await add_to_download_queue_fast(user_id, url, False)
        
        if success:
            logging.info(f"✅ Трек успешно добавлен в очередь для пользователя {user_id}")
            return True
        else:
            logging.error(f"❌ Не удалось добавить трек в очередь для пользователя {user_id}")
            return False
        
    except Exception as e:
        logging.error(f"❌ Ошибка добавления задачи в очередь: {e}")
        return False

async def process_download_queue():
    """Обрабатывает очередь загрузок (устаревшая функция)"""
    global ACTIVE_DOWNLOADS
    
    while True:
        try:
            # В новой логике очередь не используется, так как метаданные сохраняются сразу
            # Оставляем функцию для совместимости, но она не выполняет никаких действий
            await asyncio.sleep(10)  # Проверяем каждые 10 секунд
            
        except Exception as e:
            logging.error(f"❌ Ошибка в обработчике очереди: {e}")
            await asyncio.sleep(10)

async def execute_download_task(task_info: dict):
    """Выполняет задачу загрузки (устаревшая функция)"""
    global ACTIVE_DOWNLOADS
    
    try:
        # Проверяем входные параметры
        if not task_info or not isinstance(task_info, dict):
            logging.error("❌ execute_download_task: некорректная задача")
            return
            
        user_id = task_info.get('user_id')
        url = task_info.get('url')
        
        if not user_id or not url:
            logging.error("❌ execute_download_task: отсутствуют обязательные параметры")
            return
        
        logging.info(f"🚀 Выполняем задачу загрузки: пользователь {user_id}")
        
        # В новой логике метаданные уже сохранены, поэтому просто логируем
        logging.info(f"✅ Задача загрузки выполнена для пользователя {user_id}")
            
    except Exception as e:
        logging.error(f"❌ Ошибка выполнения задачи загрузки: {e}")
    finally:
        ACTIVE_DOWNLOADS = max(0, ACTIVE_DOWNLOADS - 1)  # Не позволяем счетчику уйти в минус
        logging.info(f"📊 Активных загрузок: {ACTIVE_DOWNLOADS}")

async def download_track_from_url_with_priority(user_id: str, url: str, is_premium: bool = False, add_to_collection: bool = True):
    """Загружает трек во временную папку с учетом приоритета и качества"""
    try:
        # Проверяем входные параметры
        if not user_id or not url:
            logging.error("❌ download_track_from_url_with_priority: некорректные параметры")
            return None
        
        # Проверяем кеш для скачанных файлов
        cache_key = f"download_priority_{hashlib.md5(url.encode()).hexdigest()}"
        cached_file = get_cached_metadata(cache_key)
        
        if cached_file and os.path.exists(cached_file):
            logging.info(f"🎯 Используем кешированный файл для {url}")
            return cached_file
        
        # Получаем информацию о треке для названия
        try:
            ydl_opts = {
                'format': 'bestaudio/best',
                'quiet': True,
                'no_warnings': True,
                'ignoreerrors': True,
                'extract_flat': True,  # Только метаданные
                'timeout': 30,
                'retries': 3,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    logging.error(f"❌ Не удалось получить информацию о треке: {url}")
                    return None
                title = info.get('title', 'Неизвестный трек')
        except Exception as info_error:
            logging.error(f"❌ Ошибка получения информации о треке: {info_error}")
            title = 'Неизвестный трек'
        
        # Скачиваем трек во временную папку
        temp_file_path = await download_track_to_temp(user_id, url, title)
        
        if temp_file_path:
            logging.info(f"✅ Трек успешно скачан во временную папку: {temp_file_path}")
            
            # Сохраняем путь к файлу в кеш
            set_cached_metadata(cache_key, temp_file_path)
            
            return temp_file_path
        else:
            logging.error(f"❌ Не удалось скачать трек во временную папку: {title}")
            return None
        
    except Exception as e:
        logging.exception(f"❌ Ошибка скачивания трека {url} для пользователя {user_id}: {e}")
        return None

# === ФУНКЦИИ ДЛЯ ДОБАВЛЕНИЯ ТРЕКОВ ===
async def add_track_ghost(user_id: str, url: str):
    """Мгновенно добавляет трек в плейлист как "призрак" с базовыми данными"""
    try:
        # Создаем базовые метаданные для мгновенного добавления
        ghost_track = {
            'id': f"ghost_{int(time.time())}",
            'title': 'Загружается...',
            'duration': 0,
            'url': url,
            'source': 'yt' if 'youtube.com' in url or 'youtu.be' in url else 'sc',
            'timestamp': time.time(),
            'is_ghost': True,  # Флаг что это "призрак"
            'needs_update': True
        }
        
        # Добавляем в user_tracks
        if user_id not in user_tracks:
            user_tracks[user_id] = []
        
        user_tracks[user_id].append(ghost_track)
        
        # Сохраняем в файл
        save_success = save_tracks()
        if save_success:
            logging.info(f"👻 Трек-призрак добавлен для пользователя {user_id}")
            
            # Запускаем фоновое обновление метаданных
            asyncio.create_task(update_ghost_track_metadata(user_id, url, len(user_tracks[user_id]) - 1))
        else:
            logging.error(f"❌ Ошибка сохранения трека-призрака для пользователя {user_id}")
            
    except Exception as e:
        logging.error(f"❌ Ошибка добавления трека-призрака для пользователя {user_id}: {e}")

async def update_ghost_track_metadata(user_id: str, url: str, track_index: int):
    """Обновляет метаданные трека-призрака в фоне"""
    try:
        logging.info(f"🔄 Обновляю метаданные трека-призрака для пользователя {user_id}")
        
        # Загружаем метаданные в фоне
        success = await download_track_from_url(user_id, url)
        
        if success:
            # Удаляем старый трек-призрак и добавляем обновленный
            if user_id in user_tracks and track_index < len(user_tracks[user_id]):
                old_track = user_tracks[user_id].pop(track_index)
                logging.info(f"✅ Метаданные трека-призрака обновлены для пользователя {user_id}")
                
                # Сохраняем обновленный список
                save_tracks()
            else:
                logging.warning(f"⚠️ Трек-призрак {track_index} не найден для пользователя {user_id}")
        else:
            logging.warning(f"⚠️ Не удалось обновить метаданные трека-призрака для пользователя {user_id}")
            
    except Exception as e:
        logging.error(f"❌ Ошибка обновления трека-призрака для пользователя {user_id}: {e}")

async def add_track_with_delay(user_id: str, url: str, delay_seconds: int = 10):
    """Добавляет трек в плейлист с задержкой после фоновой загрузки метаданных"""
    try:
        logging.info(f"🔄 Начинаю фоновую загрузку трека для пользователя {user_id}")
        
        # 1. Загружаем метаданные трека (не блокирует UI)
        # Функция download_track_from_url уже добавляет трек в user_tracks и возвращает True/False
        success = await download_track_from_url(user_id, url)
        
        if success:
            logging.info(f"✅ Метаданные загружены для пользователя {user_id}")
            
            # 2. Ждем указанную задержку (сообщение уже висит у пользователя)
            logging.info(f"⏱️ Ожидаю {delay_seconds} секунд - сообщение висит у пользователя")
            await asyncio.sleep(delay_seconds)
            
            # 3. Трек уже добавлен в плейлист функцией download_track_from_url
            logging.info(f"✅ Трек успешно добавлен в плейлист для пользователя {user_id}")
            
            # 4. Отправляем уведомление пользователю о завершении (опционально)
            try:
                # Можно добавить уведомление в чат, если нужно
                pass
            except Exception as e:
                logging.warning(f"⚠️ Не удалось отправить уведомление пользователю {user_id}: {e}")
        else:
            logging.error(f"❌ Не удалось загрузить метаданные трека для пользователя {user_id}")
            
    except Exception as e:
        logging.error(f"❌ Ошибка в add_track_with_delay для пользователя {user_id}: {e}")

# === ФУНКЦИИ ДЛЯ WEBHOOK ===
async def process_webhook_update(update_data: dict):
    """Обрабатывает webhook обновление от Telegram"""
    global last_webhook_update
    
    try:
        # Сохраняем последнее обновление
        last_webhook_update = update_data
        
        # Добавляем в очередь для обработки
        await webhook_update_queue.put(update_data)
        
        return True
        
    except Exception as e:
        logging.error(f"❌ Ошибка обработки webhook обновления: {e}")
        return False

async def webhook_update_processor():
    """Обработчик webhook обновлений в фоновом режиме"""
    logging.info("🔄 Запуск обработчика webhook обновлений")
    
    while True:
        try:
            # Ждем обновления из очереди
            update_data = await webhook_update_queue.get()
            
            if update_data:
                # Обрабатываем обновление через диспетчер
                try:
                    await dp.feed_webhook_update(bot, update_data)
                except Exception as e:
                    logging.error(f"❌ Ошибка обработки обновления: {e}")
                
                # Помечаем задачу как выполненную
                webhook_update_queue.task_done()
                
        except Exception as e:
            logging.error(f"❌ Ошибка в обработчике webhook обновлений: {e}")
            # Убираем задержку при ошибках для максимальной скорости
        
        # Убрали паузу между итерациями для максимальной скорости

if __name__ == "__main__":
    # Проверяем, что мы в главном потоке
    try:
        asyncio.run(main())
    except RuntimeError as e:
        if "set_wakeup_fd only works in main thread" in str(e):
            logging.warning("⚠️ Запуск в дочернем потоке - пропускаем asyncio.run")
        else:
            raise