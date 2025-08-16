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

# Импорт для работы с аудио
try:
    from pydub import AudioSegment
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False
    logging.warning("🐻‍❄️ Модуль pydub не найден. Конвертация аудио будет недоступна.")

# Импорт модуля YooMoney
try:
    from yoomoney_payment import create_simple_payment_url, verify_payment_by_label
    YOOMONEY_AVAILABLE = True
except ImportError:
    YOOMONEY_AVAILABLE = False
    logging.warning("🐻‍❄️ Модуль YooMoney не найден. Платежи через YooMoney будут недоступны.")

import re
import urllib.parse
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
    logging.info("🐻‍❄️ Переменные окружения загружены из .env файла")
except ImportError:
    logging.warning("🐻‍❄️ python-dotenv не установлен. Переменные окружения загружаются из системы.")
except Exception as e:
    logging.error(f"🌨️ Ошибка загрузки .env файла: {e}")

# === НАСТРОЙКИ ===
API_TOKEN = os.getenv("BOT_TOKEN")
if not API_TOKEN:
    raise RuntimeError("Переменная окружения BOT_TOKEN не установлена")

MAX_FILE_SIZE_MB = 50
CACHE_DIR = "cache"
COOKIES_FILE = os.path.join(os.path.dirname(__file__), "cookies.txt")
TRACKS_FILE = os.path.join(os.path.dirname(__file__), "tracks.json")
SEARCH_CACHE_FILE = os.path.join(os.path.dirname(__file__), "search_cache.json")

# === НАСТРОЙКИ SOUNDCLOUD ===
SOUNDCLOUD_SEARCH_LIMIT = 10  # Количество результатов поиска на SoundCloud
SOUNDCLOUD_CACHE_PREFIX = "sc"  # Префикс для кэша SoundCloud

# === НАСТРОЙКИ ПЛАТЕЖЕЙ ===
PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN")
if not PAYMENT_PROVIDER_TOKEN:
    raise RuntimeError("Переменная окружения PAYMENT_PROVIDER_TOKEN не установлена")

PAYMENT_AMOUNT = 100  # 1 USD в центах (100 центов = 1 USD)
PAYMENT_CURRENCY = "USD"
PAYMENT_TITLE = "Премиум доступ к Music Bot"
PAYMENT_DESCRIPTION = "Месячная подписка на премиум функции - автоматическая активация (карты Ammer)"

# === НАСТРОЙКИ YOOMONEY ===
YOOMONEY_CLIENT_ID = os.getenv("YOOMONEY_CLIENT_ID")
if not YOOMONEY_CLIENT_ID:
    raise RuntimeError("Переменная окружения YOOMONEY_CLIENT_ID не установлена")

YOOMONEY_CLIENT_SECRET = os.getenv("YOOMONEY_CLIENT_SECRET")
if not YOOMONEY_CLIENT_SECRET:
    raise RuntimeError("Переменная окружения YOOMONEY_CLIENT_SECRET не установлена")

YOOMONEY_REDIRECT_URI = os.getenv("YOOMONEY_REDIRECT_URI")
if not YOOMONEY_REDIRECT_URI:
    raise RuntimeError("Переменная окружения YOOMONEY_REDIRECT_URI не установлена")

YOOMONEY_ACCOUNT = os.getenv("YOOMONEY_ACCOUNT")
if not YOOMONEY_ACCOUNT:
    raise RuntimeError("Переменная окружения YOOMONEY_ACCOUNT не установлена")

YOOMONEY_PAYMENT_AMOUNT = 100.0  # Сумма в рублях
YOOMONEY_ENABLED = True  # Включить/выключить YooMoney

# === НАСТРОЙКИ АВТОМАТИЧЕСКОЙ ОПЛАТЫ ===
CARD_NUMBER = os.getenv("CARD_NUMBER")  # пример: XXXX XXXX XXXX XXXX
if not CARD_NUMBER:
    raise RuntimeError("Переменная окружения CARD_NUMBER не установлена")

TON_WALLET = os.getenv("TON_WALLET")
if not TON_WALLET:
    raise RuntimeError("Переменная окружения TON_WALLET не установлена")

PAYMENT_AMOUNT_USD = os.getenv("PAYMENT_AMOUNT_USD")
if not PAYMENT_AMOUNT_USD:
    raise RuntimeError("Переменная окружения PAYMENT_AMOUNT_USD не установлена")

PAYMENT_AMOUNT_USDT = os.getenv("PAYMENT_AMOUNT_USDT")
if not PAYMENT_AMOUNT_USDT:
    raise RuntimeError("Переменная окружения PAYMENT_AMOUNT_USDT не установлена")

TON_API_KEY = os.getenv("TON_API_KEY")
if not TON_API_KEY:
    raise RuntimeError("Переменная окружения TON_API_KEY не установлена")

# === НАСТРОЙКИ АВТОМАТИЧЕСКОЙ ОЧИСТКИ ===
AUTO_CLEANUP_ENABLED = True  # Включить/выключить автоматическую очистку
AUTO_CLEANUP_DELAY = 1.0  # Задержка в секундах перед удалением файла после отправки
CLEANUP_LOGGING = True  # Логирование операций очистки

# === НАСТРОЙКИ ПРЕМИУМ МОНИТОРИНГА ===
PREMIUM_NOTIFICATION_INTERVAL = 604800  # 7 дней в секундах (напоминания о премиуме)
PREMIUM_GRACE_PERIOD = 259200  # 3 дня в секундах (грация после отмены премиума)
PREMIUM_EXPIRY_WARNING = 86400  # 1 день в секундах (предупреждение об истечении)

ARTIST_FACTS_FILE = os.path.join(os.path.dirname(__file__), "artist_facts.json")
PREMIUM_USERS_FILE = os.path.join(os.path.dirname(__file__), "premium_users.json")
SEARCH_CACHE_TTL = 600
PAGE_SIZE = 10  # для постраничной навигации

# === НАСТРОЙКИ ПРИОРИТЕТНОЙ ОЧЕРЕДИ ===
PREMIUM_QUEUE = PriorityQueue()  # Приоритетная очередь для премиум пользователей
REGULAR_QUEUE = deque()  # Обычная очередь для обычных пользователей
MAX_CONCURRENT_DOWNLOADS = 3  # Максимальное количество одновременных загрузок
ACTIVE_DOWNLOADS = 0  # Счетчик активных загрузок

# === ГЛОБАЛЬНЫЕ ОБЪЕКТЫ ДЛЯ ЗАГРУЗОК ===
yt_executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="yt_downloader")
download_semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)

# === ОТСЛЕЖИВАНИЕ ФОНОВЫХ ЗАДАЧ ===
task_last_run = {}  # Время последнего успешного запуска каждой задачи

# === НАСТРОЙКИ АНТИСПАМА ===
ANTISPAM_DELAY = 1.0  # Задержка между запросами в секундах (1 сек)
user_last_request = {}  # Словарь для отслеживания времени последних запросов пользователей

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
os.makedirs(CACHE_DIR, exist_ok=True)

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
        
        # Запускаем мониторинг статуса задач
        asyncio.create_task(log_task_status())
        
        logging.info("✅ Фоновые задачи запущены с новой системой управления")
        logging.info("📊 Мониторинг статуса задач активирован")
        
    except Exception as e:
        logging.error(f"❌ Ошибка запуска фоновых задач: {e}")
        import traceback
        logging.error(f"📋 Traceback:\n{traceback.format_exc()}")

# === JSON функции ===
def load_json(path, default):
    if not path:
        logging.warning("🐻‍❄️ load_json: путь не указан")
        return default
        
    if not os.path.exists(path):
        logging.info(f"📁 Файл {path} не существует, используем значение по умолчанию")
        return default
        
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if data is None:
                logging.warning(f"🐻‍❄️ Файл {path} содержит None, используем значение по умолчанию")
                return default
            return data
    except json.JSONDecodeError as e:
        logging.error(f"🌨️ Ошибка парсинга JSON в {path}: {e}")
        return default
    except Exception as e:
        logging.error(f"🌨️ Ошибка загрузки {path}: {e}")
        return default

def format_duration(seconds):
    """Форматирует длительность в секундах в читаемый вид (MM:SS или HH:MM:SS)"""
    if not seconds or seconds <= 0:
        return "??:??"
    
    try:
        seconds = int(seconds)
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"
    except (ValueError, TypeError):
        return "??:??"

def load_tracks_with_validation():
    """Загружает треки с проверкой существования файлов"""
    try:
        # Загружаем треки обычным способом
        tracks_data = load_json(TRACKS_FILE, {})
        
        if not tracks_data:
            logging.info("📁 Файл треков пуст или не существует")
            return {}
        
        # Проверяем существование файлов и очищаем несуществующие
        cleaned_tracks = {}
        total_tracks_before = 0
        total_tracks_after = 0
        
        for user_id, tracks in tracks_data.items():
            if not tracks:
                continue
                
            total_tracks_before += len(tracks)
            valid_tracks = []
            
            for track in tracks:
                if isinstance(track, dict):
                    # Новый формат: проверяем существование файла
                    url = track.get('url', '')
                    if url:
                        file_path = url.replace('file://', '')
                        if os.path.exists(file_path):
                            valid_tracks.append(track)
                        else:
                            title = track.get('title', 'Неизвестный трек')
                            original_url = track.get('original_url', '')
                            logging.warning(f"🗑️ Файл не существует для трека {title}: {file_path}")
                            
                            if original_url and original_url.startswith('http'):
                                logging.info(f"💡 Трек {title} можно перезагрузить по ссылке: {original_url}")
                            else:
                                logging.warning(f"⚠️ Трек {title} потерян - нет оригинальной ссылки")
                    else:
                        logging.warning(f"⚠️ Трек без URL: {track.get('title', 'Без названия')}")
                else:
                    # Старый формат: всегда удаляем
                    logging.warning(f"🗑️ Удаляем трек старого формата: {track}")
            
            if valid_tracks:
                cleaned_tracks[user_id] = valid_tracks
                total_tracks_after += len(valid_tracks)
            else:
                logging.info(f"👤 У пользователя {user_id} не осталось валидных треков")
        
        # Если были удалены треки, сохраняем очищенные данные
        if total_tracks_before != total_tracks_after:
            logging.info(f"🧹 Очистка треков: было {total_tracks_before}, стало {total_tracks_after}")
            
            # Сохраняем очищенные данные
            try:
                with open(TRACKS_FILE, 'w', encoding='utf-8') as f:
                    json.dump(cleaned_tracks, f, ensure_ascii=False, indent=2)
                logging.info("💾 Очищенные данные треков сохранены")
            except Exception as save_error:
                logging.error(f"❌ Ошибка сохранения очищенных треков: {save_error}")
        
        return cleaned_tracks
        
    except Exception as e:
        logging.error(f"❌ Ошибка загрузки треков с валидацией: {e}")
        return load_json(TRACKS_FILE, {})

def check_antispam(user_id: str) -> tuple[bool, float]:
    """
    Проверяет антиспам для пользователя.
    Возвращает (разрешено, время до следующего разрешения).
    """
    try:
        current_time = time.time()
        last_request_time = user_last_request.get(str(user_id), 0)
        
        # Если это первый запрос или прошло достаточно времени
        if current_time - last_request_time >= ANTISPAM_DELAY:
            user_last_request[str(user_id)] = current_time
            return True, 0.0
        
        # Вычисляем время до следующего разрешения
        time_until_next = ANTISPAM_DELAY - (current_time - last_request_time)
        return False, time_until_next
        
    except Exception as e:
        logging.error(f"🌨️ Ошибка проверки антиспама для пользователя {user_id}: {e}")
        # В случае ошибки разрешаем запрос
        return True, 0.0

def cleanup_old_antispam_records():
    """Очищает старые записи антиспама для экономии памяти"""
    try:
        current_time = time.time()
        # Удаляем записи старше 1 часа
        cutoff_time = current_time - 3600
        
        users_to_remove = []
        for user_id, last_time in user_last_request.items():
            if last_time < cutoff_time:
                users_to_remove.append(user_id)
        
        for user_id in users_to_remove:
            del user_last_request[user_id]
            
        if users_to_remove:
            logging.info(f"🧹 Очищено {len(users_to_remove)} старых записей антиспама")
            
    except Exception as e:
        logging.error(f"🌨️ Ошибка очистки антиспама: {e}")

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
    """Проверяет, является ли пользователь премиум"""
    try:
        premium_data = load_json(PREMIUM_USERS_FILE, {"premium_users": [], "premium_usernames": []})
        
        # Отладочная информация
        logging.info(f"🔍 Проверка премиум статуса: user_id={user_id}, username={username}")
        logging.info(f"🔍 Список премиум ID: {premium_data.get('premium_users', [])}")
        logging.info(f"🔍 Список премиум username: {premium_data.get('premium_usernames', [])}")
        
        # Проверяем по ID
        if user_id and str(user_id) in premium_data.get("premium_users", []):
            logging.info(f"✅ Пользователь {user_id} найден в списке премиум по ID")
            return True
            
        # Проверяем по username
        if username and username in premium_data.get("premium_usernames", []):
            logging.info(f"✅ Пользователь {username} найден в списке премиум по username")
            return True
            
        logging.info(f"❌ Пользователь {user_id} ({username}) не найден в списке премиум")
        return False
    except Exception as e:
        logging.error(f"❌ Ошибка проверки премиум статуса: {e}")
        return False

def get_subscription_info(user_id: str) -> dict:
    """Получает информацию о подписке пользователя"""
    try:
        premium_data = load_json(PREMIUM_USERS_FILE, {"subscriptions": {}})
        return premium_data.get("subscriptions", {}).get(str(user_id), {})
    except Exception as e:
        logging.error(f"❌ Ошибка получения информации о подписке: {e}")
        return {}

async def create_payment_invoice(user_id: int, chat_id: int) -> types.LabeledPrice:
    """Создает счет для оплаты (заглушка)"""
    pass

async def create_yoomoney_payment(user_id: str, username: str = None) -> str:
    """Создает платеж через YooMoney и возвращает URL для оплаты"""
    try:
        logging.info(f"🔍 Создание платежа YooMoney для пользователя {user_id} ({username})")
        
        if not YOOMONEY_AVAILABLE or not YOOMONEY_ENABLED:
            logging.error("❌ YooMoney недоступен")
            return ""
        
        logging.info(f"✅ YooMoney доступен: AVAILABLE={YOOMONEY_AVAILABLE}, ENABLED={YOOMONEY_ENABLED}")
        
        # Создаем уникальную метку для платежа
        payment_label = f"premium_{user_id}_{int(time.time())}"
        logging.info(f"🔑 Создана метка платежа: {payment_label}")
        
        # Создаем URL для оплаты
        logging.info(f"🔗 Создание платежного URL: account={YOOMONEY_ACCOUNT}, amount={YOOMONEY_PAYMENT_AMOUNT}")
        payment_url = create_simple_payment_url(
            account=YOOMONEY_ACCOUNT,
            amount=YOOMONEY_PAYMENT_AMOUNT,
            comment=f"Премиум подписка для {username or user_id}",
            label=payment_label
        )
        
        if payment_url:
            logging.info(f"✅ Платежный URL создан успешно: {payment_url[:100]}...")
            
            # Сохраняем информацию о платеже
            payment_data = {
                "user_id": user_id,
                "username": username,
                "label": payment_label,
                "amount": YOOMONEY_PAYMENT_AMOUNT,
                "created_at": datetime.now().isoformat(),
                "status": "pending"
            }
            
            logging.info(f"💾 Сохранение данных платежа: {payment_data}")
            
            # Загружаем существующие платежи
            payments = load_json("payment_requests.json", {"payments": []})
            
            # Проверяем структуру файла
            if "payments" not in payments:
                # Если структура старая, создаем новую
                logging.info("🔄 Обновление структуры файла платежей")
                payments = {"payments": []}
            
            payments["payments"].append(payment_data)
            
            # Сохраняем с проверкой пути
            file_path = "payment_requests.json"
            if save_json(file_path, payments):
                logging.info(f"✅ Данные платежа сохранены в {file_path}")
            else:
                logging.error(f"❌ Не удалось сохранить данные платежа в {file_path}")
            
            logging.info(f"✅ Создан платеж YooMoney для пользователя {user_id}: {payment_label}")
            return payment_url
        else:
            logging.error(f"❌ Не удалось создать платеж YooMoney для пользователя {user_id}")
            return ""
            
    except Exception as e:
        logging.error(f"❌ Ошибка создания платежа YooMoney: {e}")
        logging.exception("Полный стек ошибки:")
        return ""

async def process_successful_payment(pre_checkout_query: types.PreCheckoutQuery):
    """Обрабатывает успешную оплату (заглушка)"""
    pass

def add_premium_user(user_id: str = None, username: str = None) -> bool:
    """Добавляет пользователя в список премиум"""
    try:
        premium_data = load_json(PREMIUM_USERS_FILE, {"premium_users": [], "premium_usernames": []})
        
        # Добавляем по ID
        if user_id and str(user_id) not in premium_data.get("premium_users", []):
            premium_data.setdefault("premium_users", []).append(str(user_id))
            
        # Добавляем по username
        if username and username not in premium_data.get("premium_usernames", []):
            premium_data.setdefault("premium_usernames", []).append(username)
            
        # Добавляем информацию о подписке
        if user_id:
            premium_data.setdefault("subscriptions", {})
            premium_data["subscriptions"][str(user_id)] = {
                "start_date": datetime.now().isoformat(),
                "expiry_date": (datetime.now() + timedelta(days=30)).isoformat(),
                "active": True,
                "payment_method": "ton_payment"
            }
        
        save_json(PREMIUM_USERS_FILE, premium_data)
        logging.info(f"✅ Пользователь {user_id} ({username}) добавлен в премиум")
        return True
        
    except Exception as e:
        logging.error(f"❌ Ошибка добавления премиум пользователя: {e}")
        return False

def remove_premium_user(user_id: str = None, username: str = None) -> bool:
    """Удаляет пользователя из списка премиум"""
    try:
        premium_data = load_json(PREMIUM_USERS_FILE, {"premium_users": [], "premium_usernames": []})
        
        # Удаляем по ID
        if user_id and str(user_id) in premium_data.get("premium_users", []):
            premium_data["premium_users"].remove(str(user_id))
            
        # Удаляем по username
        if username and username in premium_data.get("premium_usernames", []):
            premium_data["premium_usernames"].remove(username)
            
        # Удаляем информацию о подписке
        if user_id and "subscriptions" in premium_data:
            premium_data["subscriptions"].pop(str(user_id), None)
        
        save_json(PREMIUM_USERS_FILE, premium_data)
        logging.info(f"✅ Пользователь {user_id} ({username}) удален из премиум")
        return True
        
    except Exception as e:
        logging.error(f"❌ Ошибка удаления премиум пользователя: {e}")
        return False

async def check_ton_payment(user_id: str, amount: float = 0.60423) -> bool:
    """Автоматическая проверка TON платежа через API"""
    try:
        # Проверяем входные параметры
        if not user_id or not isinstance(user_id, str):
            logging.error("❌ check_ton_payment: некорректный user_id")
            return False
            
        if not TON_WALLET or not TON_API_KEY:
            logging.error("❌ check_ton_payment: отсутствуют настройки TON")
            return False

        async with aiohttp.ClientSession() as session:
            # Используем TON API для проверки последних транзакций
            url = f"https://toncenter.com/api/v2/getTransactions"
            params = {
                "address": TON_WALLET,
                "limit": 10,
                "api_key": TON_API_KEY
            }
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("ok"):
                        transactions = data.get("result", [])
                        
                        if not transactions:
                            logging.info("📊 TON API: транзакции не найдены")
                            return False
                        
                        # Проверяем последние транзакции за последние 24 часа
                        current_time = int(time.time())
                        day_ago = current_time - 86400
                        
                        for tx in transactions:
                            if not tx or not isinstance(tx, dict):
                                continue
                                
                            tx_time = tx.get("utime", 0)
                            if tx_time < day_ago:
                                continue
                                
                            try:
                                tx_amount = float(tx.get("value", 0)) / 1e9  # Конвертируем из наноТОН
                            except (ValueError, TypeError):
                                logging.warning(f"🐻‍❄️ Некорректная сумма транзакции: {tx.get('value')}")
                                continue
                            
                            # Проверяем, что сумма примерно равна 1 USDT (0.302115 TON)
                            # Устанавливаем диапазон ±10% для учета колебаний курса
                            if 0.27 <= tx_amount <= 0.33:
                                # Проверяем комментарий (если есть)
                                comment = tx.get("comment", "")
                                if str(user_id) in comment or not comment:
                                    logging.info(f"🐻‍❄️ Найден подходящий TON платеж: {tx_amount} TON для пользователя {user_id}")
                                    return True
                        
                        logging.info(f"📊 TON API: подходящие платежи не найдены для пользователя {user_id}")
                        return False
                    else:
                        logging.error(f"🌨️ TON API error: {data.get('error')}")
                        return False
                else:
                    logging.error(f"🌨️ TON API HTTP error: {response.status}")
                    return False
                    
    except Exception as e:
        logging.error(f"🌨️ Ошибка проверки TON платежа: {e}")
        return False

async def check_yoomoney_payment(user_id: str) -> bool:
    """Проверяет платеж через YooMoney"""
    try:
        if not YOOMONEY_AVAILABLE or not YOOMONEY_ENABLED:
            return False
        
        # Загружаем информацию о платежах
        payments = load_json("payment_requests.json", {"payments": []})
        
        # Проверяем структуру файла
        if "payments" not in payments:
            # Если структура старая, создаем новую
            payments = {"payments": []}
        
        # Ищем активные платежи пользователя
        user_payments = [p for p in payments["payments"] 
                        if p["user_id"] == user_id and p["status"] == "pending"]
        
        if not user_payments:
            return False
        
        # Проверяем каждый платеж
        for payment in user_payments:
            label = payment["label"]
            expected_amount = payment["amount"]
            
            # Проверяем статус платежа
            if verify_payment_by_label(label, expected_amount):
                # Платеж подтвержден
                payment["status"] = "completed"
                payment["completed_at"] = datetime.now().isoformat()
                
                # Сохраняем обновленные данные
                file_path = "payment_requests.json"
                if save_json(file_path, payments):
                    logging.info(f"🐻‍❄️ Обновленные данные платежа сохранены в {file_path}")
                else:
                    logging.error(f"🌨️ Не удалось сохранить обновленные данные платежа в {file_path}")
                
                logging.info(f"🐻‍❄️ Платеж YooMoney подтвержден для пользователя {user_id}: {label}")
                return True
        
        return False
        
    except Exception as e:
        logging.error(f"🌨️ Ошибка проверки платежа YooMoney: {e}")
        return False
        


def generate_payment_code(user_id: str, username: str) -> str:
    """Генерирует уникальный код для отслеживания платежа"""
    try:
        # Проверяем входные параметры
        if not user_id or not isinstance(user_id, str):
            logging.error("🌨️ generate_payment_code: некорректный user_id")
            user_id = "unknown"
            
        if not username or not isinstance(username, str):
            logging.warning("🐻‍❄️ generate_payment_code: некорректный username")
            username = "unknown"
        
        timestamp = str(int(time.time()))
        random_part = secrets.token_hex(4)
        payment_code = f"{user_id}_{timestamp}_{random_part}"
        
        logging.info(f"🔑 Сгенерирован код оплаты: {payment_code}")
        return payment_code
        
    except Exception as e:
        logging.error(f"❌ Ошибка генерации кода оплаты: {e}")
        # Возвращаем fallback код
        return f"fallback_{int(time.time())}_{secrets.token_hex(2)}"



# Загружаем треки с автоматической очисткой несуществующих файлов
user_tracks = load_tracks_with_validation()
search_cache = load_json(SEARCH_CACHE_FILE, {})


artist_facts = load_json(ARTIST_FACTS_FILE, {"facts": {}})



def save_tracks():
    global user_tracks
    try:
        # Проверяем, что user_tracks не None
        if user_tracks is None:
            logging.warning("🐻‍❄️ save_tracks: user_tracks был None, инициализируем пустым словарем")
            user_tracks = {}
        
        # Проверяем, что user_tracks является словарем
        if not isinstance(user_tracks, dict):
            logging.error(f"🌨️ save_tracks: user_tracks не является словарем: {type(user_tracks)}")
            return False
        
        save_json(TRACKS_FILE, user_tracks)
        logging.info("🐻‍❄️ Треки успешно сохранены")
        return True
        
    except Exception as e:
        logging.error(f"🌨️ Ошибка сохранения треков: {e}")
        return False





# === Экспорт cookies (опционально) ===
def export_cookies():
    try:
        if not COOKIES_FILE:
            logging.error("🌨️ export_cookies: COOKIES_FILE не определен")
            return False
            
        # Проверяем, доступен ли Chrome
        try:
            cj = browser_cookie3.chrome(domain_name=".youtube.com")
            if not cj:
                logging.warning("🐻‍❄️ export_cookies: cookies Chrome не найдены")
                return False
        except Exception as chrome_error:
            logging.warning(f"🐻‍❄️ export_cookies: ошибка доступа к Chrome: {chrome_error}")
            return False
        
        cj_mozilla = MozillaCookieJar()
        cookie_count = 0
        
        for cookie in cj:
            try:
                cj_mozilla.set_cookie(cookie)
                cookie_count += 1
            except Exception as cookie_error:
                logging.warning(f"🐻‍❄️ Ошибка обработки cookie: {cookie_error}")
                continue
        
        if cookie_count == 0:
            logging.warning("🐻‍❄️ export_cookies: не удалось обработать ни одного cookie")
            return False
        
        # Создаем директорию, если она не существует
        os.makedirs(os.path.dirname(COOKIES_FILE), exist_ok=True)
        
        cj_mozilla.save(COOKIES_FILE, ignore_discard=True, ignore_expires=True)
        logging.info(f"🐻‍❄️ Cookies экспортированы: {cookie_count} cookies сохранено в {COOKIES_FILE}")
        return True
        
    except Exception as e:
        logging.error(f"🌨️ Ошибка экспорта cookies: {e}")
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
            logging.warning("🐻‍❄️ check_cookies_file: COOKIES_FILE не определен")
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
                logging.warning("🐻‍❄️ check_cookies_file: cookies не загружены")
                return
                
            names = [c.name for c in cj if c.name]
            if not names:
                logging.warning("🐻‍❄️ check_cookies_file: имена cookies не найдены")
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
    
    # Проверяем премиум статус пользователя
    is_premium = False
    if user_id:
        try:
            # Используем глобальную функцию проверки премиума
            is_premium = is_premium_user(user_id)
        except:
            pass
    
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
                logging.warning(f"🐻‍❄️ auto_cleanup_file: некорректный путь к файлу: {file_path}")
            return False
        
        # Проверяем существование файла
        if not os.path.exists(file_path):
            if CLEANUP_LOGGING:
                logging.warning(f"🐻‍❄️ auto_cleanup_file: файл не существует: {file_path}")
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
            logging.error(f"🌨️ Ошибка планирования автоматической очистки файла {file_path}: {e}")
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
            logging.error(f"🌨️ Ошибка автоматической очистки файла {file_path}: {e}")

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
                logging.warning(f"🐻‍❄️ Нет URL для перезагрузки поврежденного файла: {file_path}")
            return False
        
        if CLEANUP_LOGGING:
            logging.info(f"🔧 Автоперезагрузка поврежденного файла: {file_path}")
        
        # Удаляем поврежденный файл
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            if CLEANUP_LOGGING:
                logging.error(f"🌨️ Ошибка удаления поврежденного файла {file_path}: {e}")
        
        # Перезагружаем файл
        try:
            # Проверяем премиум статус
            is_premium = is_premium_user(user_id)
            
            # Перезагружаем трек (используем глобальную функцию)
            # from music_bot import download_track_from_url_with_priority
            
            # Временно отключаем автоперезагрузку для избежания циклического импорта
            if CLEANUP_LOGGING:
                logging.warning(f"🐻‍❄️ Автоперезагрузка поврежденного файла временно отключена: {file_path}")
            return False
            
            # Автоперезагрузка временно отключена
            return False
                
        except Exception as e:
            if CLEANUP_LOGGING:
                logging.error(f"🌨️ Ошибка перезагрузки поврежденного файла {file_path}: {e}")
            return False
            
    except Exception as e:
        if CLEANUP_LOGGING:
            logging.error(f"🌨️ Критическая ошибка автоперезагрузки файла {file_path}: {e}")
        return False

async def start_premium_monitoring():
    """Запускает мониторинг премиум пользователей"""
    while True:
        try:
            await asyncio.sleep(3600)  # Каждый час
            
            # Проверяем истечение премиума
            await check_premium_expiry()
            
            # Отправляем еженедельные напоминания
            await send_weekly_premium_reminders()
            
        except Exception as e:
            logging.error(f"🌨️ Ошибка в мониторинге премиума: {e}")

async def check_premium_expiry():
    """
    Проверяет истечение премиума и отправляет уведомления.
    """
    try:
        premium_data = load_json(PREMIUM_USERS_FILE, {"subscriptions": {}})
        subscriptions = premium_data.get("subscriptions", {})
        
        current_time = datetime.now()
        
        for user_id, sub_info in subscriptions.items():
            try:
                if not sub_info.get("active", False):
                    continue
                
                expiry_date_str = sub_info.get("expiry_date")
                if not expiry_date_str:
                    continue
                
                expiry_date = datetime.fromisoformat(expiry_date_str)
                time_until_expiry = (expiry_date - current_time).total_seconds()
                
                # Предупреждение за 1 день
                if 0 < time_until_expiry <= PREMIUM_EXPIRY_WARNING:
                    await send_premium_expiry_warning(user_id, time_until_expiry)
                
                # Премиум истек
                elif time_until_expiry <= 0:
                    await handle_premium_expiry(user_id)
                    
            except Exception as e:
                logging.error(f"🌨️ Ошибка проверки премиума для пользователя {user_id}: {e}")
                
    except Exception as e:
        logging.error(f"🌨️ Ошибка проверки истечения премиума: {e}")

async def send_premium_expiry_warning(user_id: str, time_until_expiry: float):
    """
    Отправляет предупреждение об истечении премиума.
    """
    try:
        days_left = int(time_until_expiry / 86400)
        hours_left = int((time_until_expiry % 86400) / 3600)
        
        warning_message = (
            f"🐻‍❄️ **ВНИМАНИЕ! Ваш премиум доступ истекает!**\n\n"
            f"⏰ **Осталось:** {days_left} дней, {hours_left} часов\n\n"
            f"💡 **Что произойдет после истечения:**\n"
            f"• Треки останутся доступными еще 3 дня\n"
            f"• Затем они будут автоматически удалены\n"
            f"• Придется заново скачивать любимую музыку\n\n"
            f"💎 **Продлите премиум сейчас и сохраните коллекцию!**\n\n"
            f"💰 **Стоимость:** 1 USDT\n"
            f"🔗 **Нажмите:** /buy_premium"
        )
        
        try:
            await bot.send_message(user_id, warning_message, parse_mode="Markdown")
            logging.info(f"🐻‍❄️ Предупреждение об истечении премиума отправлено пользователю {user_id}")
        except Exception as e:
            logging.error(f"🌨️ Ошибка отправки предупреждения пользователю {user_id}: {e}")
            
    except Exception as e:
        logging.error(f"🌨️ Ошибка формирования предупреждения для {user_id}: {e}")

async def handle_premium_expiry(user_id: str):
    """
    Обрабатывает истечение премиума пользователя.
    """
    try:
        # Загружаем данные о премиуме
        premium_data = load_json(PREMIUM_USERS_FILE, {"subscriptions": {}})
        subscriptions = premium_data.get("subscriptions", {})
        
        if user_id in subscriptions:
            # Помечаем премиум как неактивный
            subscriptions[user_id]["active"] = False
            subscriptions[user_id]["expired_at"] = datetime.now().isoformat()
            
            # Сохраняем изменения
            save_json(PREMIUM_USERS_FILE, premium_data)
            
            # Планируем удаление файлов через 3 дня
            asyncio.create_task(schedule_premium_cleanup(user_id, PREMIUM_GRACE_PERIOD))
            
            # Отправляем уведомление
            expiry_message = (
                f"❌ **Ваш премиум доступ истек!**\n\n"
                f"💾 **Ваши треки будут доступны еще 3 дня**\n"
                f"⏰ **После этого они будут автоматически удалены**\n\n"
                f"💡 **Рекомендуем:**\n"
                f"• Скачать важные треки на устройство\n"
                f"• Продлить премиум для сохранения коллекции\n\n"
                f"💎 **Продлить премиум:** /buy_premium"
            )
            
            try:
                await bot.send_message(user_id, expiry_message, parse_mode="Markdown")
                logging.info(f"🐻‍❄️ Уведомление об истечении премиума отправлено пользователю {user_id}")
            except Exception as e:
                logging.error(f"🌨️ Ошибка отправки уведомления пользователю {user_id}: {e}")
                
    except Exception as e:
        logging.error(f"🌨️ Ошибка обработки истечения премиума для {user_id}: {e}")

async def schedule_premium_cleanup(user_id: str, delay_seconds: int):
    """
    Планирует очистку файлов премиум пользователя через указанное время.
    """
    try:
        await asyncio.sleep(delay_seconds)
        
        # Загружаем данные о премиуме
        premium_data = load_json(PREMIUM_USERS_FILE, {"subscriptions": {}})
        subscriptions = premium_data.get("subscriptions", {})
        
        # Проверяем, не продлил ли пользователь премиум
        if user_id in subscriptions and subscriptions[user_id].get("active", False):
            logging.info(f"🐻‍❄️ Пользователь {user_id} продлил премиум, очистка отменена")
            return
        
        # Удаляем файлы пользователя
        await cleanup_expired_premium_user(user_id)
        
    except Exception as e:
        logging.error(f"🌨️ Ошибка планирования очистки премиум пользователя {user_id}: {e}")

async def cleanup_expired_premium_user(user_id: str):
    """
    Очищает файлы пользователя после истечения премиума.
    """
    try:
        global user_tracks
        
        if not user_tracks or user_id not in user_tracks:
            return
        
        tracks = user_tracks[user_id]
        if not tracks:
            return
        
        deleted_count = 0
        total_size_freed = 0
        
        for track in tracks:
            try:
                if isinstance(track, dict):
                    file_path = track.get('url', '').replace('file://', '')
                else:
                    file_path = track
                
                if file_path and os.path.exists(file_path):
                    try:
                        file_size = os.path.getsize(file_path)
                        os.remove(file_path)
                        deleted_count += 1
                        total_size_freed += file_size
                        logging.info(f"🧹 Удален файл истекшего премиума: {file_path}")
                    except Exception as e:
                        logging.error(f"❌ Ошибка удаления файла {file_path}: {e}")
                        
            except Exception as e:
                logging.error(f"❌ Ошибка обработки трека: {e}")
        
        # Очищаем коллекцию пользователя
        user_tracks[user_id] = []
        save_tracks()
        
        if deleted_count > 0:
            total_size_mb = total_size_freed / (1024 * 1024)
            logging.info(f"🧹 Очистка истекшего премиума завершена: удалено {deleted_count} файлов, освобождено {total_size_mb:.2f} MB")
            
            # Отправляем финальное уведомление
            final_message = (
                f"🐻‍❄️ **Очистка завершена**\n\n"
                f"❌ **Ваши треки были удалены**\n"
                f"💾 **Освобождено места:** {total_size_mb:.2f} MB\n\n"
                f"💡 **Чтобы восстановить коллекцию:**\n"
                f"• Купите премиум заново\n"
                f"• Заново скачайте любимые треки\n\n"
                f"💎 **Купить премиум:** /buy_premium"
            )
            
            try:
                await bot.send_message(user_id, final_message, parse_mode="Markdown")
            except Exception as e:
                logging.error(f"🌨️ Ошибка отправки финального уведомления пользователю {user_id}: {e}")
                
    except Exception as e:
        logging.error(f"🌨️ Ошибка очистки истекшего премиума для {user_id}: {e}")

async def send_weekly_premium_reminders():
    """
    Отправляет еженедельные напоминания о преимуществах премиума.
    """
    try:
        # Загружаем данные о пользователях
        premium_data = load_json(PREMIUM_USERS_FILE, {"premium_users": [], "premium_usernames": []})
        premium_users = set(premium_data.get("premium_users", []))
        premium_usernames = set(premium_data.get("premium_usernames", []))
        
        # Получаем список всех пользователей
        global user_tracks
        if not user_tracks:
            return
        
        current_time = time.time()
        
        for user_id in user_tracks.keys():
            try:
                # Пропускаем премиум пользователей
                if user_id in premium_users:
                    continue
                
                # Проверяем, не отправляли ли мы напоминание недавно
                last_reminder_key = f"last_premium_reminder_{user_id}"
                last_reminder_time = user_last_request.get(last_reminder_key, 0)
                
                if current_time - last_reminder_time >= PREMIUM_NOTIFICATION_INTERVAL:
                    # Отправляем напоминание
                    reminder_message = (
                        f"💎 **Напоминание о премиум функциях**\n\n"
                        f"🎵 **Ваша коллекция:** {len(user_tracks.get(user_id, []))} треков\n\n"
                        f"⚡ **С премиумом вы получите:**\n"
                        f"• Мгновенный доступ к коллекции\n"
                        f"• Безлимитное хранилище\n"
                        f"• Высокое качество 320 kbps\n"
                        f"• Поиск по жанрам, исполнителям и альбомам\n\n"
                        f"💰 **Всего 1 USDT в месяц!**\n"
                        f"🔗 **Купить:** /buy_premium"
                    )
                    
                    try:
                        await bot.send_message(user_id, reminder_message, parse_mode="Markdown")
                        user_last_request[last_reminder_key] = current_time
                        logging.info(f"🐻‍❄️ Еженедельное напоминание о премиуме отправлено пользователю {user_id}")
                        
                        # Небольшая задержка между отправками
                        await asyncio.sleep(1)
                        
                    except Exception as e:
                        logging.error(f"🌨️ Ошибка отправки напоминания пользователю {user_id}: {e}")
                        
            except Exception as e:
                logging.error(f"🌨️ Ошибка обработки пользователя {user_id} для напоминаний: {e}")
                
    except Exception as e:
        logging.error(f"🌨️ Ошибка отправки еженедельных напоминаний: {e}")

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
                logging.error(f"🌨️ Ошибка в периодической очистке: {e}")

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
                        logging.warning(f"🐻‍❄️ Не удается перезагрузить файл без URL: {damaged_file['file_path']}")
                
                # Каждые 10 файлов делаем паузу
                if (i + 1) % 10 == 0:
                    await asyncio.sleep(0)
                    if CLEANUP_LOGGING:
                        logging.info(f"🔧 Восстановление: обработано {i + 1} из {len(damaged_files)} файлов")
        
        if CLEANUP_LOGGING:
            logging.info(f"🔧 Проверка целостности завершена: обработано {processed_tracks} треков, найдено {len(damaged_files)} поврежденных файлов")
        
    except Exception as e:
        if CLEANUP_LOGGING:
            logging.error(f"🌨️ Ошибка проверки целостности файлов премиум пользователей: {e}")

# === Кэш поиска ===
def get_cached_search(query):
    try:
        if not query or not isinstance(query, str):
            logging.warning("🐻‍❄️ get_cached_search: некорректный запрос")
            return None
            
        # Проверяем, что search_cache не None
        if search_cache is None:
            logging.warning("🐻‍❄️ get_cached_search: search_cache был None")
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
                    logging.info(f"🐻‍❄️ Удален устаревший кэш для запроса: {query}")
            else:
                # Некорректная структура кэша
                logging.warning(f"🐻‍❄️ Некорректная структура кэша для запроса: {query}")
                del search_cache[query_l]
        return None
        
    except Exception as e:
        logging.error(f"🌨️ Ошибка в get_cached_search: {e}")
        return None

def set_cached_search(query, results):
    global search_cache
    try:
        if not query or not isinstance(query, str):
            logging.warning("🐻‍❄️ set_cached_search: некорректный запрос")
            return False
            
        if not results or not isinstance(results, list):
            logging.warning("🐻‍❄️ set_cached_search: некорректные результаты")
            return False
            
        # Проверяем, что search_cache не None
        if search_cache is None:
            logging.warning("🐻‍❄️ set_cached_search: search_cache был None, инициализируем")
            search_cache = {}
        
        # Ограничиваем размер кэша (удаляем старые записи, если их больше 100)
        if len(search_cache) > 100:
            # Удаляем самые старые записи
            sorted_cache = sorted(search_cache.items(), key=lambda x: x[1].get("time", 0))
            items_to_remove = len(sorted_cache) - 80  # Оставляем 80 записей
            for i in range(items_to_remove):
                del search_cache[sorted_cache[i][0]]
            logging.info(f"🐻‍❄️ Очищен кэш поиска, удалено {items_to_remove} старых записей")
        
        search_cache[query.lower()] = {"time": time.time(), "results": results}
        save_json(SEARCH_CACHE_FILE, search_cache)
        logging.info(f"🐻‍❄️ Кэш обновлен для запроса: {query}")
        return True
        
    except Exception as e:
        logging.error(f"🌨️ Ошибка в set_cached_search: {e}")
        return False

# === Асинхронная обёртка для yt_dlp ===
def _ydl_download_blocking(url, outtmpl, cookiefile, is_premium=False):
    """Блокирующая функция для скачивания через yt-dlp"""
    try:
        # Проверяем входные параметры
        if not url or not isinstance(url, str):
            logging.error("🌨️ _ydl_download_blocking: некорректный URL")
            return None
            
        if not outtmpl or not isinstance(outtmpl, str):
            logging.error("🌨️ _ydl_download_blocking: некорректный шаблон имени файла")
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
                logging.warning(f"🐻‍❄️ Ошибка с cookies файлом: {cookie_error}")
        else:
            logging.info("🍪 Cookies файл не найден, используем поиск без авторизации")
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                # Получаем информацию о видео
                info = ydl.extract_info(url, download=True)
                
                if not info:
                    logging.error(f"🌨️ Не удалось получить информацию о видео: {url}")
                    return None
                
                # Получаем имя файла
                filename = ydl.prepare_filename(info)
                if not filename:
                    logging.error(f"🌨️ Не удалось подготовить имя файла для: {url}")
                    return None
                
                # Преобразуем в .mp3
                mp3_filename = os.path.splitext(filename)[0] + ".mp3"
                
                # Проверяем, что файл действительно создался
                if not os.path.exists(mp3_filename):
                    logging.error(f"🌨️ MP3 файл не был создан: {mp3_filename}")
                    return None
                
                # Проверяем размер файла
                try:
                    file_size = os.path.getsize(mp3_filename)
                    if file_size == 0:
                        logging.error(f"🌨️ Созданный файл пустой: {mp3_filename}")
                        return None
                    quality_text = "320 kbps" if is_premium else "192 kbps"
                    logging.info(f"🐻‍❄️ Файл создан успешно: {mp3_filename} ({file_size} байт, {quality_text})")
                except Exception as size_error:
                    logging.error(f"🌨️ Ошибка проверки размера файла: {size_error}")
                    return None
                
                return mp3_filename, info
                
            except Exception as extract_error:
                logging.error(f"🌨️ Ошибка извлечения информации: {extract_error}")
                return None
                
    except Exception as e:
        logging.error(f"🌨️ Критическая ошибка в _ydl_download_blocking: {e}")
        return None

async def download_track_from_url(user_id, url):
    """
    Асинхронно скачивает трек (в отдельном потоке), добавляет путь в user_tracks.
    """
    global user_tracks
    try:
        # Проверяем входные параметры
        if not user_id or not url:
            logging.error("🌨️ download_track_from_url: некорректные параметры")
            return None
            
        # Проверяем, что user_tracks не None
        if user_tracks is None:
            logging.warning("🐻‍❄️ download_track_from_url: user_tracks был None, инициализируем")
            user_tracks = {}
        
        # Определяем источник (YouTube или SoundCloud)
        is_soundcloud = 'soundcloud.com' in url.lower()
        source_text = "SoundCloud" if is_soundcloud else "YouTube"
        
        outtmpl = os.path.join(CACHE_DIR, '%(title)s.%(ext)s')
        logging.info(f"🎵 Начинаю загрузку трека с {source_text} для пользователя {user_id}: {url}")
        
        # Используем Semaphore для ограничения одновременных загрузок
        async with download_semaphore:
            # выполнить blocking ytdl в пуле потоков через ThreadPoolExecutor
            loop = asyncio.get_running_loop()
            fn_info = await loop.run_in_executor(yt_executor, _ydl_download_blocking, url, outtmpl, COOKIES_FILE)
            
        if not fn_info:
            logging.error(f"🌨️ Не удалось получить информацию о треке с {source_text}: {url}")
            return None
            
        filename, info = fn_info
        logging.info(f"📁 Файл загружен с {source_text}: {filename}")
        
        # Проверяем размер файла
        try:
            size_mb = os.path.getsize(filename) / (1024 * 1024)
            if size_mb > MAX_FILE_SIZE_MB:
                try:
                    os.remove(filename)
                    logging.warning(f"🐻‍❄️ Файл превышает максимальный размер {MAX_FILE_SIZE_MB}MB: {size_mb:.2f}MB")
                except:
                    pass
                return None
        except Exception as size_error:
            logging.error(f"🌨️ Ошибка проверки размера файла: {size_error}")
            return None
            
        # Добавляем трек в коллекцию пользователя в новом формате
        track_info = {
            "title": os.path.basename(filename),
            "url": f"file://{filename}",
            "original_url": url,  # Сохраняем оригинальную ссылку для возможности перезагрузки
            "size_mb": round(size_mb, 2),
            "needs_migration": False,
            "source": "sc" if is_soundcloud else "yt"  # Добавляем информацию об источнике
        }
        
        # Инициализируем список треков для пользователя, если его нет
        if str(user_id) not in user_tracks:
            user_tracks[str(user_id)] = []
        elif user_tracks[str(user_id)] is None:
            user_tracks[str(user_id)] = []
            
        user_tracks[str(user_id)].append(track_info)
        save_tracks()
        
        logging.info(f"🎵 Трек с {source_text} успешно добавлен в коллекцию пользователя {user_id}: {filename} ({size_mb:.2f}MB)")
        return filename
        
    except Exception as e:
        logging.exception(f"🌨️ Ошибка скачивания трека {url} для пользователя {user_id}: {e}")
        return None

async def download_track_from_url_for_genre(user_id, url):
    """
    Асинхронно скачивает трек для жанров (в отдельном потоке), НЕ добавляет в user_tracks.
    """
    global user_tracks
    try:
        # Проверяем входные параметры
        if not user_id or not url:
            logging.error("🌨️ download_track_from_url_for_genre: некорректные параметры")
            return None
            
        # Проверяем, что user_tracks не None
        if user_tracks is None:
            logging.warning("🐻‍❄️ download_track_from_url_for_genre: user_tracks был None, инициализируем")
            user_tracks = {}
        
        outtmpl = os.path.join(CACHE_DIR, '%(title)s.%(ext)s')
        
        # Проверяем премиум статус пользователя
        is_premium = is_premium_user(str(user_id))
        quality_text = "320 kbps" if is_premium else "192 kbps"
        
        logging.info(f"💾 Начинаю загрузку трека по жанру для пользователя {user_id}: {url} (качество: {quality_text})")
        
        # Проверяем, что URL валидный (поддерживаем YouTube и SoundCloud)
        if not url or ('youtube.com' not in url and 'soundcloud.com' not in url):
            logging.error(f"🌨️ Неверный URL для загрузки: {url}")
            return None
        
        # Используем Semaphore для ограничения одновременных загрузок
        async with download_semaphore:
            # выполнить blocking ytdl в пуле потоков через ThreadPoolExecutor
            try:
                loop = asyncio.get_running_loop()
                # Для SoundCloud cookies не нужны, для YouTube используем cookies
                cookies_file = COOKIES_FILE if 'youtube.com' in url and os.path.exists(COOKIES_FILE) else None
                fn_info = await loop.run_in_executor(yt_executor, _ydl_download_blocking, url, outtmpl, cookies_file, is_premium)
            except Exception as ytdl_error:
                logging.error(f"🌨️ Ошибка yt-dlp для {url}: {ytdl_error}")
                return None
            
        if not fn_info:
            logging.error(f"🌨️ Не удалось получить информацию о треке: {url}")
            return None
            
        filename, info = fn_info
        logging.info(f"📁 Файл загружен: {filename}")
        
        # Проверяем размер файла
        try:
            size_mb = os.path.getsize(filename) / (1024 * 1024)
            if size_mb > MAX_FILE_SIZE_MB:
                try:
                    os.remove(filename)
                    logging.warning(f"🐻‍❄️ Файл превышает максимальный размер {MAX_FILE_SIZE_MB}MB: {size_mb:.2f}MB")
                except:
                    pass
                return None
        except Exception as size_error:
            logging.error(f"🌨️ Ошибка проверки размера файла: {size_error}")
            return None
            
        # НЕ добавляем трек в коллекцию пользователя - только скачиваем файл
        logging.info(f"🐻‍❄️ Трек по жанру успешно загружен для пользователя {user_id}: {filename} ({size_mb:.2f}MB, {quality_text})")
        return filename
        
    except Exception as e:
        logging.exception(f"🌨️ Ошибка скачивания трека по жанру {url} для пользователя {user_id}: {e}")
        return None

# === Состояния ===
class SearchStates(StatesGroup):
    waiting_for_search = State()
    waiting_for_artist = State()
    waiting_for_album_search = State()
    waiting_for_soundcloud_query = State()  # Новое состояние для ввода запроса SoundCloud



# === Главное меню ===
main_menu = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="🐻‍❄️ Поиск музыки", callback_data="find_track"),
            InlineKeyboardButton(text="🌨️ Моя музыка", callback_data="my_music")
        ],
        [
            InlineKeyboardButton(text="🎯 Для вас", callback_data="for_you")
        ],
        [
            InlineKeyboardButton(text="🧊 Премиум функции", callback_data="premium_features")
        ],
        [
            InlineKeyboardButton(text="❄️ Купить премиум", callback_data="buy_premium")
        ]
    ]
)

# === Премиум меню ===
premium_menu = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="🐻‍❄️ Исполнители", callback_data="search_by_artist")
        ],
        [InlineKeyboardButton(text="⬅ Назад в главное меню", callback_data="back_to_main")]
    ]
)

# === Меню покупки премиума ===
buy_premium_menu = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="🌨️ Оплатить через YooMoney", callback_data="pay_yoomoney"),
            InlineKeyboardButton(text="🧊 Оплатить 1 USDT (TON)", callback_data="pay_premium")
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
    user_id = str(callback.from_user.id)
    
    # Проверяем антиспам
    is_allowed, time_until = check_antispam(user_id)
    if not is_allowed:
        await callback.answer(f"⏳ Подождите {time_until:.1f} сек. перед следующим запросом", show_alert=True)
        return
    
    logging.info(f"🔙 Пользователь {user_id} возвращается в главное меню")
    
    try:
        # Удаляем предыдущее inline-сообщение
        await callback.message.delete()
        
        # Отправляем изображение мишки без текста, только с меню
        await callback.message.answer_photo(
            photo=types.FSInputFile("bear.png"),
            reply_markup=main_menu
        )
    except Exception as e:
        logging.error(f"❌ Ошибка в back_to_main_menu: {e}")
        # Если что-то пошло не так, просто отправляем главное меню
        try:
            await callback.message.answer_photo(
                photo=types.FSInputFile("bear.png"),
                reply_markup=main_menu
            )
        except Exception as photo_error:
            logging.error(f"❌ Ошибка отправки фото: {photo_error}")
            await callback.message.answer("🎵 Главное меню", reply_markup=main_menu)

# === Команды ===
@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    # Отправляем изображение мишки без текста, только с меню
    try:
        await message.answer_photo(
            photo=types.FSInputFile("bear.png"),
            reply_markup=main_menu
        )
    except Exception as e:
        # Если не удалось отправить фото, отправляем обычное сообщение
        logging.error(f"❌ Ошибка отправки фото: {e}")
        await message.answer("🐻 Привет! Я бот для поиска и скачивания музыки с YouTube.", reply_markup=main_menu)

@dp.callback_query(F.data == "premium_features")
async def show_premium_menu(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    username = callback.from_user.username
    
    # Проверяем антиспам
    is_allowed, time_until = check_antispam(user_id)
    if not is_allowed:
        await callback.answer(f"⏳ Подождите {time_until:.1f} сек. перед следующим запросом", show_alert=True)
        return
    
    if not is_premium_user(user_id, username):
        # Отправляем изображение мишки с сообщением об ограниченном доступе
        try:
            await callback.message.edit_media(
                media=types.InputMediaPhoto(
                    media=types.FSInputFile("bear.png"),
                    caption="🔒 Доступ ограничен!\n\n💎 Раздел «Премиум функции» доступен только для премиум пользователей."
                ),
                reply_markup=main_menu
            )
        except Exception as e:
            logging.error(f"❌ Ошибка отправки фото: {e}")
            await callback.message.edit_text(
                "🔒 Доступ ограничен!\n\n💎 Раздел «Премиум функции» доступен только для премиум пользователей.",
                reply_markup=main_menu
            )
        return
    
    premium_features_info = (
        "💎 **Добро пожаловать в премиум раздел!**\n\n"
      )
    
    # Отправляем изображение мишки без текста, только с меню
    try:
        await callback.message.edit_media(
            media=types.InputMediaPhoto(
                media=types.FSInputFile("bear.png")
            ),
            reply_markup=premium_menu
        )
    except Exception as e:
        logging.error(f"❌ Ошибка отправки фото: {e}")
        await callback.message.edit_text(premium_features_info, reply_markup=premium_menu, parse_mode="Markdown")

@dp.callback_query(F.data == "show_genres")
async def show_genres(callback: types.CallbackQuery):
    """Показывает список доступных жанров"""
    user_id = str(callback.from_user.id)
    username = callback.from_user.username
    
    # Проверяем антиспам
    is_allowed, time_until = check_antispam(user_id)
    if not is_allowed:
        await callback.answer(f"⏳ Подождите {time_until:.1f} сек. перед следующим запросом", show_alert=True)
        return
    
    # Проверяем премиум статус
    if not is_premium_user(user_id, username):
        # Отправляем изображение мишки с сообщением об ограниченном доступе
        try:
            await callback.message.edit_media(
                media=types.InputMediaPhoto(
                    media=types.FSInputFile("bear.png"),
                    caption="🔒 Доступ ограничен! Требуется премиум подписка."
                ),
                reply_markup=main_menu
            )
        except Exception as e:
            logging.error(f"❌ Ошибка отправки фото: {e}")
            await callback.message.edit_text("🔒 Доступ ограничен! Требуется премиум подписка.", reply_markup=main_menu)
        return
    
    genres = get_genres()  # Используем get_genres() для получения списка жанров
    
    # Создаем inline клавиатуру с жанрами (по двое в ряд)
    keyboard = []
    genre_list = list(genres.keys())
    
    # Группируем жанры по двое
    for i in range(0, len(genre_list), 2):
        row = [InlineKeyboardButton(text=genre_list[i], callback_data=f"genre:{genre_list[i]}")]
        if i + 1 < len(genre_list):
            row.append(InlineKeyboardButton(text=genre_list[i + 1], callback_data=f"genre:{genre_list[i + 1]}"))
        keyboard.append(row)
    
    # Добавляем кнопку "назад"
    keyboard.append([InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_premium")])
    
    kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    # Отправляем изображение мишки без текста, только с меню
    try:
        await callback.message.edit_media(
            media=types.InputMediaPhoto(
                media=types.FSInputFile("bear.png")
            ),
            reply_markup=kb
        )
    except Exception as e:
        logging.error(f"❌ Ошибка отправки фото: {e}")
        await callback.message.edit_text(
            "🎭 **Выберите жанр музыки:**\n\n"
            "🎵 Я найду и сразу загружу для вас 8-12 случайных треков выбранного жанра!\n\n"
            "💡 При выборе жанра вы получите:\n"
            "• Аудиофайлы для прослушивания прямо в чате\n"
            "• Никаких дополнительных действий не требуется\n"
            "• 🎲 **Каждый раз новые случайные треки!**\n\n"
            "🔄 **Нажмите на жанр еще раз для новых треков!**",
            parse_mode="Markdown",
            reply_markup=kb
        )

@dp.callback_query(F.data == "search_by_artist")
async def show_artist_search(callback: types.CallbackQuery, state: FSMContext):
    """Показывает форму поиска по исполнителю"""
    user_id = str(callback.from_user.id)
    username = callback.from_user.username
    
    # Проверяем антиспам
    is_allowed, time_until = check_antispam(user_id)
    if not is_allowed:
        await callback.answer(f"⏳ Подождите {time_until:.1f} сек. перед следующим запросом", show_alert=True)
        return
    
    # Проверяем премиум статус
    if not is_premium_user(user_id, username):
        # Отправляем изображение мишки с сообщением об ограниченном доступе
        try:
            await callback.message.edit_media(
                media=types.InputMediaPhoto(
                    media=types.FSInputFile("bear.png"),
                    caption="🔒 Доступ ограничен! Требуется премиум подписка."
                ),
                reply_markup=main_menu
            )
        except Exception as e:
            logging.error(f"❌ Ошибка отправки фото: {e}")
            await callback.message.edit_text("🔒 Доступ ограничен! Требуется премиум подписка.", reply_markup=main_menu)
        return
    
    # Устанавливаем состояние ожидания ввода имени исполнителя
    await state.set_state(SearchStates.waiting_for_artist)
    
    # Отправляем изображение мишки с текстом о поиске по исполнителю
    try:
        await callback.message.edit_media(
            media=types.InputMediaPhoto(
                media=types.FSInputFile("bear.png"),
                caption="🎵 Введите название исполнителя или группы, чьи треки хотите найти."
            ),
            reply_markup=back_button
        )
    except Exception as e:
        logging.error(f"❌ Ошибка отправки фото: {e}")
        await callback.message.edit_text(
            "🎵 Введите название исполнителя или группы, чьи треки хотите найти.",
            parse_mode="Markdown",
            reply_markup=back_button
        )

@dp.callback_query(F.data == "buy_premium")
async def show_buy_premium_info(callback: types.CallbackQuery):
    """Показать информацию о премиуме и вариантах покупки"""
    user_id = str(callback.from_user.id)
    username = callback.from_user.username
    
    # Добавляем логирование для отладки
    logging.info(f"🔍 Нажата кнопка 'Купить премиум' пользователем {user_id} ({username})")
    
    # Проверяем антиспам
    is_allowed, time_until = check_antispam(user_id)
    if not is_allowed:
        logging.warning(f"⏳ Антиспам блокирует пользователя {user_id}")
        await callback.answer(f"⏳ Подождите {time_until:.1f} сек. перед следующим запросом", show_alert=True)
        return
    
    logging.info(f"✅ Антиспам проверка пройдена для пользователя {user_id}")
    
    # Проверяем, не является ли пользователь уже премиум
    logging.info(f"🔍 Проверяем премиум статус для пользователя {user_id}")
    is_premium = is_premium_user(user_id, username)
    logging.info(f"✅ Премиум статус пользователя {user_id}: {is_premium}")
    
    if is_premium:
        logging.info(f"💎 Пользователь {user_id} уже имеет премиум доступ")
        # Отправляем изображение мишки с сообщением о существующем премиуме
        try:
            await callback.message.edit_media(
                media=types.InputMediaPhoto(
                    media=types.FSInputFile("bear.png"),
                    caption="💎 У вас уже есть премиум доступ!\n\n"
                ),
                reply_markup=main_menu
            )
        except Exception as e:
            logging.error(f"❌ Ошибка отправки фото: {e}")
            await callback.message.edit_text(
                "💎 У вас уже есть премиум доступ!\n\n",
                reply_markup=main_menu
            )
        return
    
    logging.info(f"📱 Пользователь {user_id} не имеет премиум доступ, показываем информацию")
    
    # Показываем информацию о премиуме
    premium_info = (
                 "🧊 ПРЕМИУМ ДОСТУП\n\n"
         "🐻‍❄️ Ваши эксклюзивные преимущества:\n\n"
         "🧊 МГНОВЕННЫЙ ДОСТУП К КОЛЛЕКЦИИ\n"
         "❄️ КРИСТАЛЬНО ЧИСТОЕ ЗВУЧАНИЕ\n"
         "🌨️ ЭКСКЛЮЗИВНЫЕ ФУНКЦИИ\n"
         "🐻‍❄️ БЕЗЛИМИТНОЕ ХРАНИЛИЩЕ\n" 
         "❄️ РЕАЛЬНАЯ РАЗНИЦА В СКОРОСТИ:\n" 
         "🐻‍❄️ ПОЧЕМУ ПРЕМИУМ ВЫГОДЕН:\n"
         "• 🧊 Всего 100 ₽ в месяц (через YooMoney)\n"
         "• ❄️ Или 1 USDT в месяц (через TON)\n"
         
         "🐻‍❄️ СПОСОБЫ ОПЛАТЫ:\n"
         "• 🧊 YooMoney (В разработке) - банковские карты, СБП, YooMoney\n"
         "• ❄️ TON - криптовалюта Tether USD\n\n"
         "🌨️ Выберите удобный способ оплаты ниже:"
    )
    
    # Показываем изображение мишки с информацией о премиуме
    logging.info(f"🐻‍❄️ Отправляем изображение с информацией о премиуме для пользователя {user_id}")
    try:
        # Сначала пробуем отредактировать медиа
        await callback.message.edit_media(
            media=types.InputMediaPhoto(
                media=types.FSInputFile("bear.png"),
                caption=premium_info
            ),
            reply_markup=buy_premium_menu
        )
        logging.info(f"🐻‍❄️ Информация о премиуме успешно отправлена пользователю {user_id}")
    except Exception as e:
        logging.error(f"🌨️ Ошибка редактирования медиа: {e}")
        logging.info(f"🔄 Пробуем отправить новое сообщение для пользователя {user_id}")
        try:
            # Отправляем новое сообщение вместо редактирования
            await callback.message.answer_photo(
                photo=types.FSInputFile("bear.png"),
                caption=premium_info,
                reply_markup=buy_premium_menu
            )
            logging.info(f"🐻‍❄️ Новое сообщение с премиум информацией отправлено пользователю {user_id}")
        except Exception as photo_error:
            logging.error(f"🌨️ Ошибка отправки фото: {photo_error}")
            logging.info(f"🔄 Пробуем отправить текстовое сообщение для пользователя {user_id}")
            try:
                await callback.message.answer(
                    premium_info, 
                    reply_markup=buy_premium_menu, 
                    parse_mode="Markdown"
                )
                logging.info(f"🐻‍❄️ Текстовая информация о премиуме отправлена пользователю {user_id}")
            except Exception as text_error:
                logging.error(f"🌨️ Ошибка отправки текста: {text_error}")
                # Последняя попытка - просто ответ на callback
                await callback.answer("🧊 Информация о премиуме загружается...", show_alert=True)

@dp.callback_query(F.data == "pay_yoomoney")
async def pay_premium_yoomoney(callback: types.CallbackQuery):
    """Оплата премиума через YooMoney"""
    user_id = str(callback.from_user.id)
    username = callback.from_user.username
    
    # Проверяем антиспам
    is_allowed, time_until = check_antispam(user_id)
    if not is_allowed:
        await callback.answer(f"⏳ Подождите {time_until:.1f} сек. перед следующим запросом", show_alert=True)
        return
    
    # Добавляем логирование для отладки
    logging.info(f"🐻‍❄️ Нажата кнопка 'Оплатить через YooMoney' пользователем {user_id} ({username})")
    
    # Проверяем, не является ли пользователь уже премиум
    if is_premium_user(user_id, username):
        logging.info(f"🐻‍❄️ Пользователь {user_id} уже имеет премиум доступ")
        try:
            await callback.message.edit_media(
                media=types.InputMediaPhoto(
                    media=types.FSInputFile("bear.png"),
                    caption="🧊 У вас уже есть премиум доступ!"
                ),
                reply_markup=main_menu
            )
        except Exception as e:
            logging.error(f"🌨️ Ошибка отправки фото: {e}")
            await callback.message.edit_text(
                "🧊 У вас уже есть премиум доступ!",
                reply_markup=main_menu
            )
        return
    
    # Проверяем доступность YooMoney
    if not YOOMONEY_AVAILABLE or not YOOMONEY_ENABLED:
        await callback.answer("🌨️ Платежи через YooMoney временно недоступны", show_alert=True)
        return
    
    try:
        logging.info(f"🔍 Попытка создания платежа YooMoney для пользователя {user_id}")
        
        # Создаем платеж через YooMoney
        payment_url = await create_yoomoney_payment(user_id, username)
        
        logging.info(f"🔍 Результат создания платежа: {'успешно' if payment_url else 'неудачно'}")
        
        if payment_url:
            # Создаем меню с ссылкой на оплату
            yoomoney_payment_menu = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="💳 Перейти к оплате", url=payment_url)],
                    [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_yoomoney_{user_id}")],
                    [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_buy_premium")]
                ]
            )
            
            # Отправляем информацию о платеже
            payment_info = (
                "🐻‍❄️ ОПЛАТА ЧЕРЕЗ YOOMONEY\n\n"
                f"🧊 Сумма: {YOOMONEY_PAYMENT_AMOUNT} ₽\n"
                "❄️ Способ оплаты: Банковские карты, YooMoney, СБП\n"
                "❄️ Время обработки: Мгновенно\n\n"
                "Инструкция:\n"
                "🧊 Нажмите кнопку «Перейти к оплате»\n"
                "❄️ Введите данные карты или используйте YooMoney\n"
                "🌨️ После оплаты нажмите «Проверить оплату»\n"
                "🐻‍❄️ Премиум доступ активируется автоматически\n\n"
                "🌨️ Безопасно: Все платежи защищены YooMoney"
            )
            
            await callback.message.edit_media(
                media=types.InputMediaPhoto(
                    media=types.FSInputFile("bear.png"),
                    caption=payment_info
                ),
                reply_markup=yoomoney_payment_menu
            )
            
            logging.info(f"🐻‍❄️ Создан платеж YooMoney для пользователя {user_id}")
            
        else:
            logging.error(f"🌨️ Не удалось создать платеж YooMoney для пользователя {user_id}")
            await callback.answer("🌨️ Ошибка создания платежа. Попробуйте позже.", show_alert=True)
            
    except Exception as e:
        logging.error(f"🌨️ Ошибка создания платежа YooMoney: {e}")
        await callback.answer("🌨️ Произошла ошибка. Попробуйте позже.", show_alert=True)

@dp.callback_query(F.data == "pay_premium")
async def pay_premium_direct(callback: types.CallbackQuery):
    """Прямая оплата премиума"""
    user_id = str(callback.from_user.id)
    username = callback.from_user.username
    
    # Проверяем антиспам
    is_allowed, time_until = check_antispam(user_id)
    if not is_allowed:
        await callback.answer(f"⏳ Подождите {time_until:.1f} сек. перед следующим запросом", show_alert=True)
        return
    
    # Добавляем логирование для отладки
    logging.info(f"🐻‍❄️ Нажата кнопка '🧊 Оплатить 1 USDT' пользователем {user_id} ({username})")
    
    # Проверяем, не является ли пользователь уже премиум
    if is_premium_user(user_id, username):
        logging.info(f"🐻‍❄️ Пользователь {user_id} уже имеет премиум доступ")
        try:
            await callback.message.edit_media(
                media=types.InputMediaPhoto(
                    media=types.FSInputFile("bear.png"),
                    caption="🧊 У вас уже есть премиум доступ!"
                ),
                reply_markup=main_menu
            )
        except Exception as e:
            logging.error(f"🌨️ Ошибка отправки фото: {e}")
            await callback.message.edit_text(
                "🧊 У вас уже есть премиум доступ!",
                reply_markup=main_menu
            )
        return
    
    # Генерируем уникальный код для отслеживания
    payment_code = generate_payment_code(user_id, username)
    logging.info(f"🐻‍❄️ Сгенерирован код оплаты: {payment_code}")
    
    # Показываем страницу оплаты с автоматической проверкой
    payment_info = (
        f"🐻‍❄️ **ОПЛАТА ПРЕМИУМ ДОСТУПА**\n\n"
        f"Сумма: 1 USDT\n"
        f"Срок действия: 30 дней\n\n"
        f"TON кошелек для оплаты:\n"
        f"{TON_WALLET}\n\n"
        "Инструкция:\n"
        "🧊 Откройте ваш TON кошелек\n"
        "❄️ Отправьте 1 USDT на указанный адрес\n"
        f"🌨️ В комментарии укажите: `{payment_code}`\n"
        "🐻‍❄️ После отправки нажмите «🐻‍❄️ Проверить оплату»\n\n"
        f"Ваш код: {payment_code}"
    )
    
    # Создаем клавиатуру с автоматической проверкой
    payment_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🐻‍❄️ Проверить оплату", callback_data=f"check_payment:{payment_code}")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_main_from_buy_premium")]
    ])
    
    logging.info(f"🐻‍❄️ Отправляем страницу оплаты пользователю {user_id}")
    try:
        await callback.message.edit_media(
            media=types.InputMediaPhoto(
                media=types.FSInputFile("bear.png"),
                caption=payment_info
            ),
            reply_markup=payment_keyboard
        )
        logging.info(f"🐻‍❄️ Страница оплаты с фото успешно отправлена пользователю {user_id}")
    except Exception as e:
        logging.error(f"🌨️ Ошибка отправки фото: {e}")
        await callback.message.edit_text(payment_info, reply_markup=payment_keyboard, parse_mode="Markdown")
        logging.info(f"🐻‍❄️ Страница оплаты без фото отправлена пользователю {user_id}")



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
    user_id = str(callback.from_user.id)
    
    # Проверяем антиспам
    is_allowed, time_until = check_antispam(user_id)
    if not is_allowed:
        await callback.message.answer(f"⏳ Подождите {time_until:.1f} сек. перед следующим запросом", show_alert=True)
        return
    
    try:
        await callback.message.edit_media(
            media=types.InputMediaPhoto(
                media=types.FSInputFile("bear.png"),
                caption="🧊 Премиум функции"
            ),
            reply_markup=premium_menu
        )
    except Exception as e:
        # Если редактирование не удалось, отправляем новое сообщение
        logging.error(f"🌨️ Ошибка редактирования сообщения в back_to_premium_menu: {e}")
        try:
            await callback.message.answer_photo(
                photo=types.FSInputFile("bear.png"),
                caption="🧊 Премиум функции",
                reply_markup=premium_menu
            )
        except Exception as photo_error:
            logging.error(f"🌨️ Ошибка отправки фото: {photo_error}")
            await callback.message.answer("🧊 Премиум функции", reply_markup=premium_menu)
        await callback.message.delete()

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
    """Возврат к разделу 'Купить премиум' из оплаты YooMoney"""
    user_id = str(callback.from_user.id)
    
    # Проверяем антиспам
    is_allowed, time_until = check_antispam(user_id)
    if not is_allowed:
        await callback.answer(f"⏳ Подождите {time_until:.1f} сек. перед следующим запросом", show_alert=True)
        return
    
    try:
        await callback.message.edit_media(
            media=types.InputMediaPhoto(
                media=types.FSInputFile("bear.png"),
                caption="🧊 ПРЕМИУМ ДОСТУП\n\n"
                "🐻‍❄️ Ваши эксклюзивные преимущества:\n\n"
                "🧊 МГНОВЕННЫЙ ДОСТУП К КОЛЛЕКЦИИ\n"
                "• ❄️ Ваши треки загружаются за секунды\n"
                "• 🌨️ Никаких ожиданий при повторном доступе\n\n"
                
                "❄️ КРИСТАЛЬНО ЧИСТОЕ ЗВУЧАНИЕ\n"
                "• 🧊 Высокое качество 320 kbps для всех треков\n"
                "• 🌨️ Лучшее качество для ваших устройств\n\n"
                
                "🌨️ ЭКСКЛЮЗИВНЫЕ ФУНКЦИИ\n"
                "• 🐻‍❄️ Исполнители - лучшие треки любимых артистов с SoundCloud\n"
                ""
                
                "🐻‍❄️ БЕЗЛИМИТНОЕ ХРАНИЛИЩЕ\n"
                "• 🧊 Все треки сохраняются навсегда\n"
                "• ❄️ Даже 1000+ треков - никаких ограничений\n"
                "• 🌨️ Ваша коллекция в безопасности\n\n"
                
                "❄️ РЕАЛЬНАЯ РАЗНИЦА В СКОРОСТИ:\n"
                "• 🧊 Премиум: 10 треков за 30 секунд 🧊\n"
                "• 🌨️ Бесплатные: 10 треков за 5 минут 🌨️\n\n"
                
                "🐻‍❄️ ПОЧЕМУ ПРЕМИУМ ВЫГОДЕН:\n"
                "• 🧊 Всего 100 ₽ в месяц (через YooMoney)\n"
                "• ❄️ Или 1 USDT в месяц (через TON)\n"
                "• 🐻‍❄️ Максимальное удобство - все работает быстро\n"
                "• 🧊 Дешевле чем на YTMusic и Яндекс Музыке\n\n"
                
                "🐻‍❄️ СПОСОБЫ ОПЛАТЫ:\n"
                "• 🧊 YooMoney (В разработке) - банковские карты, СБП, YooMoney\n"
                "• ❄️ TON - криптовалюта Tether USD\n\n"
                "🌨️ Выберите удобный способ оплаты ниже:"
            ),
            reply_markup=buy_premium_menu
        )
    except Exception as e:
        # Если не удалось отправить фото, отправляем обычное сообщение
        logging.error(f"🌨️ Ошибка отправки фото: {e}")
        await callback.message.edit_text("🧊 ПРЕМИУМ ДОСТУП", reply_markup=buy_premium_menu)

@dp.callback_query(F.data == "back_to_main_from_buy_premium")
async def back_to_main_from_buy_premium_callback(callback: types.CallbackQuery):
    """Возврат в главное меню из inline клавиатуры оплаты"""
    user_id = str(callback.from_user.id)
    
    # Проверяем антиспам
    is_allowed, time_until = check_antispam(user_id)
    if not is_allowed:
        await callback.answer(f"⏳ Подождите {time_until:.1f} сек. перед следующим запросом", show_alert=True)
        return
    
    try:
        await callback.message.edit_media(
            media=types.InputMediaPhoto(
                media=types.FSInputFile("bear.png")
            ),
            reply_markup=main_menu
        )
    except Exception as e:
        # Если не удалось отправить фото, отправляем обычное сообщение
        logging.error(f"🌨️ Ошибка отправки фото: {e}")
        await callback.message.edit_text("🐻‍❄️ Возврат в главное меню", reply_markup=main_menu)



# === Обработчики автоматической оплаты ===
@dp.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: types.PreCheckoutQuery):
    pass

@dp.message(F.successful_payment)
async def successful_payment(message: types.Message):
    pass

@dp.message(Command("add_premium"))
async def add_premium_command(message: types.Message):
    """Команда для добавления премиум доступа пользователю"""
    # Проверяем, является ли отправитель администратором
    user_id = str(message.from_user.id)
    username = message.from_user.username
    
    if not is_admin(user_id, username):
        await message.answer("🌨️ У вас нет прав для выполнения этой команды.")
        return
    
    # Парсим аргументы команды
    args = message.text.split()
    if len(args) < 2:
        await message.answer("🌨️ Использование: /add_premium <user_id или username>")
        return
    
    target = args[1].strip()
    
    # Определяем, это ID или username
    if target.isdigit():
        # Это ID пользователя
        success = add_premium_user(user_id=target)
        if success:
            await message.answer(f"🐻‍❄️ Премиум доступ добавлен пользователю с ID: {target}")
        else:
            await message.answer(f"🌨️ Ошибка при добавлении премиум доступа пользователю: {target}")
    else:
        # Это username
        success = add_premium_user(username=target)
        if success:
            await message.answer(f"🐻‍❄️ Премиум доступ добавлен пользователю: @{target}")
        else:
            await message.answer(f"🌨️ Ошибка при добавлении премиум доступа пользователю: @{target}")

@dp.message(Command("remove_premium"))
async def remove_premium_command(message: types.Message):
    """Команда для удаления премиум доступа у пользователя"""
    # Проверяем, является ли отправитель администратором
    user_id = str(message.from_user.id)
    username = message.from_user.username
    
    if not is_admin(user_id, username):
        await message.answer("🌨️ У вас нет прав для выполнения этой команды.")
        return
    
    # Парсим аргументы команды
    args = message.text.split()
    if len(args) < 2:
        await message.answer("🌨️ Использование: /remove_premium <user_id или username>")
        return
    
    target = args[1].strip()
    
    # Определяем, это ID или username
    if target.isdigit():
        # Это ID пользователя
        success = remove_premium_user(user_id=target)
        if success:
            await message.answer(f"🐻‍❄️ Премиум доступ удален у пользователя с ID: {target}")
        else:
            await message.answer(f"🌨️ Ошибка при удалении премиум доступа у пользователя: {target}")
    else:
        # Это username
        success = remove_premium_user(username=target)
        if success:
            await message.answer(f"🐻‍❄️ Премиум доступ удален у пользователя: @{target}")
        else:
            await message.answer(f"🌨️ Ошибка при удалении премиум доступа у пользователя: @{target}")











# === Поиск ===
@dp.callback_query(F.data == "find_track")
async def ask_track_name(callback: types.CallbackQuery, state: FSMContext):
    user_id = str(callback.from_user.id)
    
    # Проверяем антиспам
    is_allowed, time_until = check_antispam(user_id)
    if not is_allowed:
        await callback.answer(f"⏳ Подождите {time_until:.1f} сек. перед следующим запросом", show_alert=True)
        return
    
    # Отправляем изображение мишки с запросом названия трека
    try:
        await callback.message.edit_media(
            media=types.InputMediaPhoto(
                media=types.FSInputFile("bear.png"),
                caption="🐻‍❄️ Введите название трека"
            ),
            reply_markup=back_button
        )
    except Exception as e:
        # Если не удалось отправить фото, отправляем обычное сообщение
        logging.error(f"🌨️ Ошибка отправки фото: {e}")
        await callback.message.edit_text("🐻‍❄️ Введите название трека", reply_markup=back_button)
    
    await callback.answer()
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
    # Отправляем изображение мишки без текста, только с меню
    try:
        await callback.message.edit_media(
            media=types.InputMediaPhoto(
                media=types.FSInputFile("bear.png")
            ),
            reply_markup=main_menu
        )
    except Exception as e:
        # Если не удалось отправить фото, отправляем обычное сообщение
        logging.error(f"🌨️ Ошибка отправки фото: {e}")
        await callback.message.edit_text("🐻‍❄️ Возврат в главное меню", reply_markup=main_menu)







@dp.message(SearchStates.waiting_for_search, F.text)
async def search_music(message: types.Message, state: FSMContext):
    query = message.text.strip()
    user_id = str(message.from_user.id)
    await state.clear()

    logging.info(f"🔍 Поиск музыки для пользователя {user_id}: '{query}'")

    # Проверяем, что запрос не пустой
    if not query:
        await message.answer("❄️ Пожалуйста, введите название песни или ссылку.", reply_markup=main_menu)
        return

    yt_url_pattern = r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+"
    if re.match(yt_url_pattern, query):
        # асинхронно скачиваем в background (не блокируем основной цикл)
        asyncio.create_task(download_track_from_url(message.from_user.id, query))
        return await message.answer("❄️ Запущена загрузка трека. Он появится в «Моя музыка» когда будет готов.", reply_markup=main_menu)

    search_msg = await message.answer("🔍 Поиск..")

    cached = get_cached_search(query)
    if cached:
        # Удаляем сообщение "Поиск.." если используем кэш
        await search_msg.delete()
        return await send_search_results(message.chat.id, cached)
    try:
        # Выполняем поиск на YouTube и SoundCloud параллельно
        async def search_youtube(q):
            try:
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
                            logging.info(f"🍪 Используем cookies файл: {COOKIES_FILE}")
                        else:
                            logging.warning("⚠️ Cookies файл не найден, поиск может быть ограничен")
                        
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            result = ydl.extract_info(f"ytsearch5:{q}", download=False)
                            if not result:
                                logging.warning(f"⚠️ Пустой результат поиска YouTube для запроса: '{q}'")
                                return None
                            return result
                    except Exception as search_error:
                        logging.error(f"❌ Ошибка в search_block YouTube для запроса '{q}': {search_error}")
                        return None
                
                return await asyncio.to_thread(search_block, q)
            except Exception as e:
                logging.error(f"❌ Ошибка поиска YouTube: {e}")
                return None
        
        # Запускаем поиск на обеих платформах параллельно
        youtube_task = asyncio.create_task(search_youtube(query))
        soundcloud_task = asyncio.create_task(search_soundcloud(query))
        
        # Ждем результаты от обеих платформ
        youtube_info, soundcloud_results = await asyncio.gather(
            youtube_task, soundcloud_task, return_exceptions=True
        )
        
        # Обрабатываем результаты YouTube
        youtube_results = []
        if isinstance(youtube_info, Exception):
            logging.error(f"❌ Ошибка поиска YouTube: {youtube_info}")
        elif youtube_info:
            results = youtube_info.get("entries", [])
            if results:
                # Фильтруем невалидные результаты и треки длиннее 10 минут
                for result in results:
                    if result and result.get('id') and result.get('title'):
                        # Проверяем длительность трека
                        duration = result.get('duration', 0)
                        if duration and duration > 600:  # 600 секунд = 10 минут
                            logging.info(f"⏱️ Пропускаем YouTube трек '{result.get('title')}' - длительность {duration} сек (> 10 мин)")
                            continue
                        # Добавляем источник
                        result['source'] = 'yt'
                        youtube_results.append(result)
        
        # Обрабатываем результаты SoundCloud
        soundcloud_processed = []
        if isinstance(soundcloud_results, Exception):
            logging.error(f"❌ Ошибка поиска SoundCloud: {soundcloud_results}")
        elif soundcloud_results:
            for result in soundcloud_results:
                if result and result.get('url') and result.get('title'):
                    # Проверяем длительность трека
                    duration = result.get('duration', 0)
                    if duration and duration > 600:  # 600 секунд = 10 минут
                        logging.info(f"⏱️ Пропускаем SoundCloud трек '{result.get('title')}' - длительность {duration} сек (> 10 мин)")
                        continue
                    # Добавляем источник
                    result['source'] = 'sc'
                    soundcloud_processed.append(result)
        
        # Объединяем результаты
        all_results = youtube_results + soundcloud_processed
        
        if not all_results:
            await search_msg.delete()
            await message.answer("❄️ Ничего не нашёл. Попробуйте изменить запрос.", reply_markup=main_menu)
            return
        
        # Сортируем по релевантности (простая эвристика - сначала короткие названия)
        all_results.sort(key=lambda x: len(x.get('title', '')))
        
        # Ограничиваем общим числом результатов (5)
        final_results = all_results[:5]
        
        # Удаляем сообщение "Поиск.." перед отправкой результатов
        await search_msg.delete()
        
        logging.info(f"🔍 Поиск завершен для '{query}': найдено {len(final_results)} треков (YouTube: {len(youtube_results)}, SoundCloud: {len(soundcloud_processed)})")
        logging.info(f"🔍 Первый результат: {final_results[0] if final_results else 'Нет результатов'}")
        logging.info(f"🔍 Тип первого результата: {type(final_results[0]) if final_results else 'Нет результатов'}")
        logging.info(f"🔍 Ключи первого результата: {list(final_results[0].keys()) if final_results else 'Нет результатов'}")
            
        set_cached_search(query, final_results)
        await send_search_results(message.chat.id, final_results)
        
    except Exception as e:
        logging.exception(f"❌ Критическая ошибка поиска для пользователя {user_id}: {e}")
        await message.answer("❄️ Произошла ошибка при поиске. Попробуйте еще раз позже.", reply_markup=main_menu)



@dp.message(SearchStates.waiting_for_artist, F.text)
async def search_by_artist_input(message: types.Message, state: FSMContext):
    """Обрабатывает ввод имени исполнителя"""
    artist_name = message.text.strip()
    user_id = str(message.from_user.id)
    await state.clear()

    logging.info(f"👤 Поиск по исполнителю для пользователя {user_id}: '{artist_name}'")

    # Отправляем изображение мишки с сообщением о начале поиска
    try:
        search_msg = await message.answer_photo(
            photo=types.FSInputFile("bear.png"),
            caption=f"🔍 **Поиск треков исполнителя {artist_name}...**\n\n"
                    "🎵 Ищу лучшие треки на SoundCloud...\n"
                    "⏳ Это может занять несколько минут.",
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"❌ Ошибка отправки фото: {e}")
        search_msg = await message.answer(
            f"🔍 **Поиск треков исполнителя {artist_name}...**\n\n"
            "🎵 Ищу лучшие треки на SoundCloud...\n"
            "⏳ Это может занять несколько минут.",
            parse_mode="Markdown"
        )

    try:
                # Ищем треки исполнителя
        results = await asyncio.to_thread(search_artist_tracks, artist_name, 10)
        
        if not results:
            try:
                await search_msg.edit_media(
                    media=types.InputMediaPhoto(
                        media=types.FSInputFile("bear.png"),
                        caption=f"❌ **Ничего не найдено**\n\n"
                                f"🚫 По исполнителю '{artist_name}' ничего не найдено на SoundCloud.\n"
                                "💡 Возможные причины:\n"
                                "• Неправильное написание имени\n"
                                "• Исполнитель не представлен на SoundCloud\n"
                                "• Ограничения по региону\n\n"
                                "🔍 Попробуйте:\n"
                                "• Проверить правильность написания\n"
                                "• Использовать другое имя\n"
                                "• Поискать альтернативные варианты"
                    ),
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_main")]
                    ])
                )
            except Exception as e:
                logging.error(f"❌ Ошибка отправки фото: {e}")
                await search_msg.edit_text(
                    f"❌ **Ничего не найдено**\n\n"
                    f"🚫 По исполнителю '{artist_name}' ничего не найдено на SoundCloud.\n"
                    "💡 Возможные причины:\n"
                    "• Неправильное написание имени\n"
                    "• Исполнитель не представлен на SoundCloud\n"
                                "• Ограничения по региону\n\n"
                                "🔍 Попробуйте:\n"
                                "• Проверить правильность написания\n"
                                "• Использовать другое имя\n"
                                "• Поискать альтернативные варианты",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_main")]
                    ])
                )
            return

        # Обновляем сообщение о начале загрузки
        try:
            await search_msg.edit_media(
                media=types.InputMediaPhoto(
                    media=types.FSInputFile("bear.png"),
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
                        media=types.InputMediaPhoto(
                            media=types.FSInputFile("bear.png"),
                            caption=f"⏳ Загружаю трек {i}/{len(results)} исполнителя {artist_name}..."
                        ),
                        parse_mode="Markdown"
                    )
                except Exception as edit_error:
                    logging.error(f"❌ Ошибка обновления прогресса: {edit_error}")

                # Скачиваем трек
                url = track.get('url', '')
                if not url:
                    logging.error(f"❌ Нет URL для трека {track.get('title', 'Без названия')}")
                    failed_tracks.append(f"{track.get('title', 'Без названия')} (нет URL)")
                    continue
                
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
                        
                        # Планируем автоматическую очистку файла после отправки
                        # Это временный файл для жанровых треков - удаляем его
                        await auto_cleanup_file(filename, is_collection_track=False)
                        
                    except Exception as audio_error:
                        logging.error(f"❌ Ошибка отправки аудиофайла {track.get('title', 'Без названия')}: {audio_error}")
                        # Если не удалось отправить как аудио, отправляем как документ
                        try:
                            await message.answer_document(
                                types.FSInputFile(filename)
                            )
                            logging.info(f"✅ Файл отправлен как документ: {track.get('title', 'Без названия')}")
                            
                            # Планируем автоматическую очистку файла после отправки
                            # Это временный файл для жанровых треков - удаляем его
                            await auto_cleanup_file(filename, is_collection_track=False)
                            
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

        message_text = f"✅ Загрузка треков исполнителя {artist_name} завершена!"

        # Создаем клавиатуру с опциями
        keyboard_buttons = []

        if failed_count > 0:
            keyboard_buttons.append([InlineKeyboardButton(text="🔄 Попробовать снова", callback_data=f"search_artist_retry:{artist_name}")])

        keyboard_buttons.extend([
            [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_main")]
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

        try:
            # Обновляем изображение мишки с итоговым сообщением
            await search_msg.edit_media(
                media=types.InputMediaPhoto(
                    media=types.FSInputFile("bear.png"),
                    caption=message_text
                ),
                reply_markup=keyboard
            )
        except Exception as edit_error:
            logging.error(f"❌ Ошибка редактирования итогового сообщения: {edit_error}")
            # Пытаемся отправить новое сообщение
            try:
                await message.answer_photo(
                    photo=types.FSInputFile("bear.png"),
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
                        [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_main")]
                    ])
                )
            except Exception as last_error:
                logging.error(f"❌ Полная потеря связи с пользователем {user_id}: {last_error}")

async def send_search_results(chat_id, results):
    try:
        logging.info(f"🔍 send_search_results: начало обработки для чата {chat_id}")
        logging.info(f"🔍 send_search_results: получены результаты: {results}")
        logging.info(f"🔍 send_search_results: тип результатов: {type(results)}")
        
        # Проверяем входные параметры
        if not results or not isinstance(results, list):
            logging.error(f"❌ send_search_results: некорректные результаты: {type(results)}")
            await bot.send_message(chat_id, "❌ Ошибка отображения результатов поиска.", reply_markup=main_menu)
            return
        
        logging.info(f"🔍 send_search_results: результаты прошли проверку, начинаем фильтрацию")
        
        # Фильтруем валидные результаты
        valid_results = []
        for i, video in enumerate(results[:5]):  # Берем только первые 5 результатов
            logging.info(f"🔍 send_search_results: обработка видео {i+1}: {video}")
            
            # Проверяем, является ли это результатом SoundCloud
            if video and isinstance(video, dict) and video.get('source') == 'sc':
                # SoundCloud результат
                if video.get('url') and video.get('title'):
                    valid_results.append(video)
                    logging.info(f"🔍 send_search_results: SoundCloud трек {i+1} добавлен в валидные")
                else:
                    logging.warning(f"⚠️ send_search_results: SoundCloud трек {i+1} не прошел валидацию: {video}")
            elif video and isinstance(video, dict) and video.get('id') and video.get('title'):
                # YouTube результат
                valid_results.append(video)
                logging.info(f"🔍 send_search_results: YouTube видео {i+1} добавлено в валидные")
            else:
                logging.warning(f"⚠️ send_search_results: результат {i+1} не прошел валидацию: {video}")
        
        logging.info(f"🔍 send_search_results: найдено валидных результатов: {len(valid_results)}")
        
        if not valid_results:
            logging.warning(f"⚠️ send_search_results: нет валидных результатов для чата {chat_id}")
            await bot.send_message(chat_id, "❌ Не найдено подходящих треков для скачивания.", reply_markup=main_menu)
            return
        
        logging.info(f"🔍 send_search_results: начинаем создание клавиатуры")
        
        # Создаем клавиатуру
        keyboard = []
        for i, video in enumerate(valid_results):
            title = video.get("title", "Без названия")
            duration = video.get("duration", 0)
            source = video.get("source", "yt")  # По умолчанию YouTube
            
            # Безопасная обработка длительности
            try:
                duration_text = format_duration(duration)
            except Exception as dur_error:
                logging.warning(f"⚠️ send_search_results: ошибка форматирования длительности: {dur_error}")
                duration_text = "??:??"
            
            logging.info(f"🔍 send_search_results: создание кнопки {i+1}: title='{title}', duration={duration}, duration_text='{duration_text}', source='{source}'")
            
            # Формируем текст кнопки с названием и длительностью
            if duration and duration > 0:
                button_text = f"{title[:45]}... ⏱ {duration_text}" if len(title) > 45 else f"{title} ⏱ {duration_text}"
            else:
                button_text = title[:55] + "..." if len(title) > 55 else title
            
            # Добавляем индикатор источника
            if source == 'sc':
                button_text += " 🎵"
            
            logging.info(f"🔍 send_search_results: текст кнопки {i+1}: '{button_text}'")
            
            # Создаем callback_data в зависимости от источника
            if source == 'sc':
                # SoundCloud: передаем URL трека для общего поиска
                url = video.get('url', '')
                if url:
                    # Кодируем URL для безопасной передачи в callback_data
                    encoded_url = urllib.parse.quote(url, safe='')
                    keyboard.append([InlineKeyboardButton(text=button_text, callback_data=f"dl_sc:{encoded_url}")])
                else:
                    logging.warning(f"⚠️ send_search_results: у SoundCloud трека {i+1} отсутствует URL, пропускаем")
                    continue
            else:
                # YouTube: передаем ID видео
                video_id = video.get('id', '')
                if not video_id:
                    logging.warning(f"⚠️ send_search_results: у YouTube видео {i+1} отсутствует ID, пропускаем")
                    continue
                keyboard.append([InlineKeyboardButton(text=button_text, callback_data=f"dl:{video_id}")])
        
        # Добавляем кнопку "назад" для возврата в главное меню
        keyboard.append([InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_main")])
        
        logging.info(f"🔍 send_search_results: клавиатура создана, отправляем сообщение")
        
        # Отправляем результаты с минимальным текстом (Telegram не позволяет пустые сообщения)
        await bot.send_message(
            chat_id, 
            "🐻‍❄️ Результат", 
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        
        logging.info(f"✅ Результаты поиска успешно отправлены в чат {chat_id}: {len(valid_results)} треков")
        
    except Exception as e:
        logging.error(f"❌ Ошибка в send_search_results для чата {chat_id}: {e}")
        logging.error(f"❌ Детали ошибки: results={results}, type={type(results)}")
        logging.error(f"❌ Полный traceback ошибки:", exc_info=True)
        try:
            await bot.send_message(chat_id, "❌ Произошла ошибка при отображении результатов поиска.", reply_markup=main_menu)
        except Exception as send_error:
            logging.error(f"❌ Критическая ошибка отправки сообщения об ошибке: {send_error}")

# Обработчик back_to_search больше не нужен, так как кнопка "Назад" ведет в главное меню

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
            await callback.answer("❄️ Некорректный ID видео.", show_alert=True)
            return
            
        url = f"https://www.youtube.com/watch?v={video_id}"
        
        # Проверяем премиум статус пользователя
        is_premium = is_premium_user(user_id, callback.from_user.username)
        
        # Добавляем задачу в соответствующую очередь
        priority = 0 if is_premium else 1  # Премиум пользователи имеют приоритет 0 (выше)
        await add_to_download_queue(user_id, url, is_premium, priority)
        
        # Показываем popup сообщение
        await callback.answer("❄️ Трек будет добавлен в Моя музыка", show_alert=True)
        
    except ValueError as e:
        logging.error(f"❌ Ошибка парсинга video_id: {e}")
        await callback.answer("❌ Ошибка ID видео.", show_alert=True)
    except Exception as e:
        logging.error(f"❌ Критическая ошибка в download_track: {e}")
        await callback.answer("❌ Произошла ошибка при запуске загрузки.", show_alert=True)

# === Callback: скачивание SoundCloud трека из общего поиска ===
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
        url = urllib.parse.unquote(encoded_url)
        
        logging.info(f"🎵 Пользователь {user_id} скачивает SoundCloud трек из поиска: {url}")
        
        # Проверяем премиум статус пользователя
        is_premium = is_premium_user(user_id, callback.from_user.username)
        
        # Добавляем задачу в соответствующую очередь
        priority = 0 if is_premium else 1  # Премиум пользователи имеют приоритет 0 (выше)
        await add_to_download_queue(user_id, url, is_premium, priority)
        
        # Показываем popup сообщение (как для YouTube)
        await callback.answer("❄️ Трек будет добавлен в Моя музыка", show_alert=True)
        
    except Exception as e:
        logging.error(f"❌ Ошибка скачивания SoundCloud трека из поиска: {e}")
        await callback.answer("❌ Произошла ошибка при запуске загрузки.", show_alert=True)



# === Вспомог: строим клавиатуру для страницы треков пользователя ===
def build_tracks_keyboard(tracks, page=0, owner_for_buttons=None):
    try:
        # Проверяем входные параметры
        if tracks is None:
            tracks = []
            logging.warning("⚠️ build_tracks_keyboard: tracks был None, инициализируем пустым списком")
        
        if not isinstance(tracks, list):
            logging.error(f"❌ build_tracks_keyboard: tracks не является списком: {type(tracks)}")
            tracks = []
        
        kb = []
        start = page * PAGE_SIZE
        end = start + PAGE_SIZE
        
        # Отладочная информация
        total_pages = (len(tracks) + PAGE_SIZE - 1) // PAGE_SIZE if tracks else 0
        logging.info(f"🔍 build_tracks_keyboard: треков={len(tracks)}, страница={page+1}/{total_pages}, start={start}, end={end}")
        
        # Проверяем валидность страницы
        if page < 0 or (total_pages > 0 and page >= total_pages):
            logging.warning(f"⚠️ build_tracks_keyboard: некорректная страница {page}, корректируем на 0")
            page = 0
            start = 0
            end = PAGE_SIZE
        
        # Проверяем формат треков
        if tracks and isinstance(tracks[0], dict):
            # Новый формат: массив объектов
            for i, track_info in enumerate(tracks[start:end], start=start):
                if not track_info or not isinstance(track_info, dict):
                    continue
                    
                title = track_info.get('title', 'Неизвестный трек')
                if not title:
                    title = 'Неизвестный трек'
                    
                # Убираем расширение .mp3 из названия
                if title.endswith('.mp3'):
                    title = title[:-4]
                
                # Получаем длительность трека
                duration = track_info.get('duration', 0)
                duration_text = format_duration(duration) if duration and duration > 0 else ""
                
                # Формируем текст кнопки с названием и длительностью
                if duration_text:
                    button_text = f"{title[:30]}... ⏱ {duration_text}" if len(title) > 30 else f"{title} ⏱ {duration_text}"
                else:
                    button_text = (title[:35] + '...') if len(title) > 38 else title
                
                row = []
                if owner_for_buttons:
                    row.append(InlineKeyboardButton(text=button_text,
                                                    callback_data=f"play_shared:{owner_for_buttons}:{i}"))
                else:
                    row.append(InlineKeyboardButton(text=button_text,
                                                    callback_data=f"play:{i}"))
                    row.append(InlineKeyboardButton(text="🗑", callback_data=f"del:{i}"))
                kb.append(row)
        else:
            # Старый формат: массив путей
            for i, path in enumerate(tracks[start:end], start=start):
                if not path or not isinstance(path, str):
                    continue
                    
                title = os.path.basename(path)
                if not title:
                    title = 'Неизвестный трек'
                
                # Убираем расширение .mp3 из названия
                if title.endswith('.mp3'):
                    title = title[:-4]
                
                # Для старых треков длительность неизвестна, показываем только название
                button_text = (title[:35] + '...') if len(title) > 38 else title
                
                row = []
                if owner_for_buttons:
                    row.append(InlineKeyboardButton(text=button_text,
                                                    callback_data=f"play_shared:{owner_for_buttons}:{i}"))
                else:
                    row.append(InlineKeyboardButton(text=button_text,
                                                    callback_data=f"play:{i}"))
                    row.append(InlineKeyboardButton(text="🗑", callback_data=f"del:{i}"))
                kb.append(row)
        
        # Навигация
        nav = []
        if page > 0:
            if owner_for_buttons:
                nav.append(InlineKeyboardButton(text="◀ Пред", callback_data=f"shared_page:{owner_for_buttons}:{page-1}"))
            else:
                nav.append(InlineKeyboardButton(text="◀ Пред", callback_data=f"music_page:{page-1}"))
        
        # Проверяем, есть ли следующая страница
        if page < total_pages - 1:
            if owner_for_buttons:
                nav.append(InlineKeyboardButton(text="След ▶", callback_data=f"shared_page:{owner_for_buttons}:{page+1}"))
            else:
                nav.append(InlineKeyboardButton(text="След ▶", callback_data=f"music_page:{page+1}"))
        
        if nav:
            kb.append(nav)
            
        # Кнопки действий
        if owner_for_buttons:
            kb.append([InlineKeyboardButton(text="📥 Скачать все", callback_data=f"download_all_shared:{owner_for_buttons}")])
        else:
            kb.append([InlineKeyboardButton(text="📥 Скачать все", callback_data="download_all")])
        
        # Добавляем кнопку "назад" для возврата в главное меню
        kb.append([InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_main")])
        
        return InlineKeyboardMarkup(inline_keyboard=kb)
        
    except Exception as e:
        logging.error(f"❌ Критическая ошибка в build_tracks_keyboard: {e}")
        # Возвращаем простую клавиатуру с кнопкой "назад"
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_main")]
        ])

# === Моя музыка (показ первой страницы) ===
@dp.callback_query(F.data == "my_music")
async def my_music(callback: types.CallbackQuery):
    global user_tracks
    user_id = str(callback.from_user.id)
    
    # Проверяем антиспам
    is_allowed, time_until = check_antispam(user_id)
    if not is_allowed:
        await callback.answer(f"⏳ Подождите {time_until:.1f} сек. перед следующим запросом", show_alert=True)
        return
    
    # Проверяем, что user_tracks не None
    if user_tracks is None:
        user_tracks = {}
        logging.warning(f"⚠️ user_tracks был None для пользователя {user_id}, инициализируем пустым словарем")
    
    tracks = user_tracks.get(user_id, [])
    
    # Проверяем, что tracks не None и является списком
    if tracks is None:
        tracks = []
        user_tracks[user_id] = tracks
        logging.warning(f"⚠️ tracks был None для пользователя {user_id}, инициализируем пустым списком")
    
    if not tracks:
        # Отправляем изображение мишки с текстом о том, что треков нет
        try:
            await callback.message.edit_media(
                media=types.InputMediaPhoto(
                    media=types.FSInputFile("bear.png"),
                    caption="📂 У тебя нет треков."
                ),
                reply_markup=main_menu
            )
        except Exception as e:
            logging.error(f"❌ Ошибка отправки фото: {e}")
            await callback.message.edit_text("📂 У тебя нет треков.", reply_markup=main_menu)
        return
        
    try:
        kb = build_tracks_keyboard(tracks, page=0, owner_for_buttons=None)
        # Отправляем изображение мишки с информацией о треках
        try:
            await callback.message.edit_media(
                media=types.InputMediaPhoto(
                    media=types.FSInputFile("bear.png"),
                    caption=f"❄️ Твои треки (страница 1):"
                ),
                reply_markup=kb
            )
        except Exception as e:
            logging.error(f"❌ Ошибка отправки фото: {e}")
            await callback.message.edit_text("❄️ Твои треки (страница 1):", reply_markup=kb)
    except Exception as e:
        logging.error(f"❌ Ошибка создания клавиатуры для пользователя {user_id}: {e}")
        await callback.message.edit_text("❌ Ошибка отображения треков. Попробуйте еще раз.", reply_markup=main_menu)

# === Callback: перелистывание страницы своей музыки ===
@dp.callback_query(F.data.startswith("music_page:"))
async def music_page_cb(callback: types.CallbackQuery):
    global user_tracks
    try:
        user_id = str(callback.from_user.id)
        
        # Проверяем антиспам
        is_allowed, time_until = check_antispam(user_id)
        if not is_allowed:
            await callback.answer(f"⏳ Подождите {time_until:.1f} сек. перед следующим запросом", show_alert=True)
            return
        
        page = int(callback.data.split(":")[1])
        
        # Проверяем, что user_tracks не None
        if user_tracks is None:
            user_tracks = {}
            logging.warning(f"⚠️ user_tracks был None для пользователя {user_id}, инициализируем пустым словарем")
        
        tracks = user_tracks.get(user_id, [])
        
        # Проверяем, что tracks не None и является списком
        if tracks is None:
            tracks = []
            user_tracks[user_id] = tracks
            logging.warning(f"⚠️ tracks был None для пользователя {user_id}, инициализируем пустым списком")
        
        logging.info(f"🔍 music_page_cb: пользователь {user_id}, страница {page+1}, треков {len(tracks)}")
        
        if not tracks:
            await callback.message.edit_text("❄️ У вас нет треков", reply_markup=main_menu)
            return
        
        # Проверяем валидность страницы
        total_pages = (len(tracks) + PAGE_SIZE - 1) // PAGE_SIZE if tracks else 0
        if page < 0 or page >= total_pages:
            logging.warning(f"⚠️ Некорректная страница {page} для пользователя {user_id}, перенаправляем на страницу 0")
            page = 0
        
        kb = build_tracks_keyboard(tracks, page=page, owner_for_buttons=None)
        # Обновляем изображение мишки с новой страницей треков
        try:
            await callback.message.edit_media(
                media=types.InputMediaPhoto(
                    media=types.FSInputFile("bear.png"),
                    caption=f"❄️ Твои треки (страница {page+1}):"
                ),
                reply_markup=kb
            )
        except Exception as e:
            logging.error(f"❌ Ошибка отправки фото: {e}")
            await callback.message.edit_text(f"❄️ Твои треки (страница {page+1}):", reply_markup=main_menu)
        
    except ValueError as e:
        logging.error(f"❌ Ошибка парсинга номера страницы: {e}")
        await callback.answer("❌ Ошибка номера страницы.", show_alert=True)
    except Exception as e:
        logging.error(f"❌ Ошибка в music_page_cb для пользователя {user_id}: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте еще раз.", show_alert=True)

# === Callback: Для вас ===
@dp.callback_query(F.data == "for_you")
async def for_you_recommendations(callback: types.CallbackQuery):
    """Показывает рекомендуемые треки для пользователя"""
    user_id = str(callback.from_user.id)
    
    # Проверяем антиспам
    is_allowed, time_until = check_antispam(user_id)
    if not is_allowed:
        await callback.answer(f"⏳ Подождите {time_until:.1f} сек. перед следующим запросом", show_alert=True)
        return
    
    try:
        # Отправляем сообщение "Пожалуйста, подождите..."
        await callback.message.edit_media(
            media=types.InputMediaPhoto(
                media=types.FSInputFile("bear.png"),
                caption="⏳ Пожалуйста, подождите.."
            ),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅ Назад в главное меню", callback_data="back_to_main")]
            ])
        )
        
        # Получаем рекомендуемые треки
        recommended_tracks = await get_recommended_tracks(user_id)
        
        if not recommended_tracks:
            # Если не удалось получить рекомендации
            await callback.message.edit_media(
                media=types.InputMediaPhoto(
                    media=types.FSInputFile("bear.png"),
                    caption="❌ **Не удалось подобрать треки**\n\nПопробуйте позже или обратитесь в поддержку."
                ),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="for_you")],
                    [InlineKeyboardButton(text="⬅ Назад в главное меню", callback_data="back_to_main")]
                ])
            )
            return
        
        # Обновляем сообщение о начале загрузки
        await callback.message.edit_media(
            media=types.InputMediaPhoto(
                media=types.FSInputFile("bear.png"),
                caption=f"⏳ **Загружаю {len(recommended_tracks)} рекомендуемых треков...**\n\n"
                        "🎵 Скачиваю аудиофайлы для прослушивания...\n"
                        "💡 Это может занять несколько минут."
            ),
            parse_mode="Markdown"
        )

        # Скачиваем треки и отправляем их как аудиофайлы
        downloaded_tracks = []
        failed_tracks = []

        for i, track in enumerate(recommended_tracks, 1):
            try:
                # Обновляем прогресс
                try:
                    await callback.message.edit_media(
                        media=types.InputMediaPhoto(
                            media=types.FSInputFile("bear.png"),
                            caption=f"⏳ Загружаю рекомендуемый трек {i}/{len(recommended_tracks)}..."
                        ),
                        parse_mode="Markdown"
                    )
                except Exception as edit_error:
                    logging.error(f"❌ Ошибка обновления прогресса: {edit_error}")

                # Скачиваем трек
                url = track.get('url', '')
                if not url:
                    logging.error(f"❌ Нет URL для трека {track.get('title', 'Без названия')}")
                    failed_tracks.append(f"{track.get('title', 'Без названия')} (нет URL)")
                    continue
                
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
                            performer="SoundCloud",
                            duration=track.get('duration', 0)
                        )
                        logging.info(f"✅ Рекомендуемый аудиофайл отправлен: {track.get('title', 'Без названия')}")
                        
                        # Планируем автоматическую очистку файла после отправки
                        await auto_cleanup_file(filename, is_collection_track=False, user_id=user_id)
                        
                    except Exception as audio_error:
                        logging.error(f"❌ Ошибка отправки аудиофайла {track.get('title', 'Без названия')}: {audio_error}")
                        # Если не удалось отправить как аудио, отправляем как документ
                        try:
                            await callback.message.answer_document(
                                types.FSInputFile(filename)
                            )
                            logging.info(f"✅ Рекомендуемый файл отправлен как документ: {track.get('title', 'Без названия')}")
                            
                            # Планируем автоматическую очистку файла после отправки
                            await auto_cleanup_file(filename, is_collection_track=False, user_id=user_id)
                            
                        except Exception as doc_error:
                            logging.error(f"❌ Ошибка отправки документа {track.get('title', 'Без названия')}: {doc_error}")
                            failed_tracks.append(track.get('title', 'Без названия'))
                            continue

                    # Небольшая задержка между отправками
                    await asyncio.sleep(0.5)

                else:
                    failed_tracks.append(track.get('title', 'Без названия'))

            except Exception as e:
                logging.error(f"❌ Ошибка загрузки рекомендуемого трека {track.get('title', 'Без названия')}: {e}")
                failed_tracks.append(track.get('title', 'Без названия'))
                continue

        # Формируем итоговое сообщение
        message_text = "✅ Загрузка рекомендуемых треков завершена!"

        # Отправляем итоговое сообщение
        await callback.message.edit_media(
            media=types.InputMediaPhoto(
                media=types.FSInputFile("bear.png"),
                caption=message_text
            ),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить рекомендации", callback_data="for_you")],
                [InlineKeyboardButton(text="⬅ Назад в главное меню", callback_data="back_to_main")]
            ])
        )
        
        logging.info(f"🎯 Рекомендации отправлены пользователю {user_id}: {len(recommended_tracks)} треков")
        
    except Exception as e:
        logging.error(f"❌ Ошибка в for_you_recommendations для пользователя {user_id}: {e}")
        await callback.message.edit_media(
            media=types.InputMediaPhoto(
                media=types.FSInputFile("bear.png"),
                caption="❌ **Произошла ошибка**\n\nНе удалось подобрать треки. Попробуйте позже."
            ),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="for_you")],
                [InlineKeyboardButton(text="⬅ Назад в главное меню", callback_data="back_to_main")]
            ])
        )

# === Callback: play / play_shared ===
@dp.callback_query(F.data.startswith("play:"))
async def play_track(callback: types.CallbackQuery):
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
            logging.warning(f"⚠️ play_track: user_tracks был None для пользователя {user_id}, инициализируем пустым словарем")
        
        tracks = user_tracks.get(user_id, [])
        
        # Проверяем, что tracks не None и является списком
        if tracks is None:
            tracks = []
            user_tracks[user_id] = tracks
            logging.warning(f"⚠️ play_track: tracks был None для пользователя {user_id}, инициализируем пустым списком")
        
        if not tracks:
            await callback.answer("📂 У вас нет треков.", show_alert=True)
            return
        
        if not (0 <= idx < len(tracks)):
            await callback.answer("❄️ Трек не найден.", show_alert=True)
            return
        
        track = tracks[idx]
        
        # Проверяем формат трека
        if isinstance(track, dict):
            # Новый формат: объект с информацией о треке
            file_path = track.get('url', '').replace('file://', '')
            title = track.get('title', 'Неизвестный трек')
            
            if not file_path:
                await callback.answer("❄️ Путь к файлу не найден.", show_alert=True)
                return
            
            # Проверяем премиум статус пользователя
            user_id_str = str(user_id)
            is_premium = is_premium_user(user_id_str, callback.from_user.username)
            
            if is_premium:
                # Премиум: проверяем существование файла и отправляем
                if os.path.exists(file_path):
                    try:
                        await callback.message.answer_audio(types.FSInputFile(file_path), title=title)
                        logging.info(f"✅ Трек воспроизведен: {title} для премиум пользователя {user_id}")
                        
                        # Планируем автоматическую очистку файла после отправки
                        await auto_cleanup_file(file_path, is_collection_track=True, user_id=user_id_str)
                        
                    except Exception as audio_error:
                        logging.error(f"❌ Ошибка воспроизведения аудио {title}: {audio_error}")
                        await callback.answer("❌ Ошибка воспроизведения трека.", show_alert=True)
                else:
                    logging.warning(f"⚠️ Файл не найден для премиум пользователя: {file_path}")
                    await callback.answer("❌ Файл не найден на диске.", show_alert=True)
            else:
                # Бесплатные: скачиваем трек заново, отправляем и сразу удаляем
                original_url = track.get('original_url', '')
                
                if original_url and original_url.startswith('http'):
                    try:
                        await callback.message.edit_text("⏳ Скачиваю трек...")
                        
                        logging.info(f"📥 Скачиваю трек для бесплатного пользователя: {title} по ссылке: {original_url}")
                        
                        # Загружаем трек без добавления в коллекцию (он уже там есть)
                        download_result = await download_track_from_url_with_priority(user_id_str, original_url, is_premium, add_to_collection=False)
                        
                        if download_result:
                            # Трек успешно загружен, отправляем пользователю
                            try:
                                await callback.message.answer_audio(types.FSInputFile(download_result), title=title)
                                logging.info(f"✅ Трек отправлен бесплатному пользователю: {title}")
                                
                                # Сразу удаляем файл для бесплатного пользователя
                                try:
                                    os.remove(download_result)
                                    logging.info(f"🧹 Файл сразу удален для бесплатного пользователя: {download_result}")
                                except Exception as cleanup_error:
                                    logging.error(f"❌ Ошибка при удалении файла {download_result}: {cleanup_error}")
                                
                                # Возвращаем сообщение к исходному состоянию
                                await callback.message.edit_text("✅ Трек отправлен!", reply_markup=callback.message.reply_markup)
                                
                            except Exception as audio_error:
                                logging.error(f"❌ Ошибка отправки трека {title}: {audio_error}")
                                await callback.message.edit_text("❌ Ошибка отправки трека.", reply_markup=callback.message.reply_markup)
                        else:
                            logging.error(f"❌ Не удалось скачать трек: {title}")
                            await callback.message.edit_text("❌ Не удалось скачать трек.", reply_markup=callback.message.reply_markup)
                            
                    except Exception as download_error:
                        logging.error(f"❌ Ошибка при скачивании трека {title}: {download_error}")
                        await callback.message.edit_text("❌ Ошибка при скачивании трека.", reply_markup=callback.message.reply_markup)
                else:
                    logging.warning(f"⚠️ Не удалось найти валидную ссылку для трека: {title}")
                    await callback.answer("❌ Не удалось найти ссылку для скачивания трека.", show_alert=True)

        else:
            # Старый формат: путь к файлу
            if not track or not isinstance(track, str):
                await callback.answer("❌ Некорректный формат трека.", show_alert=True)
                return
            
            # Для старых треков у бесплатных пользователей нет оригинальной ссылки
            # Поэтому просто показываем сообщение об ошибке
            title = os.path.basename(track)
            logging.warning(f"⚠️ Старый формат трека без оригинальной ссылки: {title}")
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
        
        if not tracks:
            await callback.message.answer("❄️ У тебя нет треков.", reply_markup=main_menu)
            return
        
        await callback.message.answer("📥 Отправляю все треки...")
        
        success_count = 0
        failed_count = 0
        

        
        for track in tracks:
            try:
                # Проверяем формат трека
                if isinstance(track, dict):
                    # Новый формат: объект с информацией о треке
                    file_path = track.get('url', '').replace('file://', '')
                    title = track.get('title', 'Неизвестный трек')
                    original_url = track.get('original_url', '')
                    
                    if not file_path:
                        logging.warning(f"⚠️ Пустой путь к файлу для трека: {title}")
                        failed_count += 1
                        continue
                else:
                    # Старый формат: путь к файлу
                    if not track or not isinstance(track, str):
                        logging.warning(f"⚠️ Некорректный формат трека: {track}")
                        failed_count += 1
                        continue
                        
                    file_path = track
                    title = os.path.basename(track)
                    original_url = title  # Для старых треков используем название
                
                # Проверяем премиум статус пользователя
                user_id_str = str(callback.from_user.id)
                is_premium = is_premium_user(user_id_str, callback.from_user.username)
                
                if is_premium:
                    # Премиум: проверяем существование файла и отправляем
                    if os.path.exists(file_path):
                        try:
                            await callback.message.answer_audio(types.FSInputFile(file_path), title=title)
                            success_count += 1
                            logging.info(f"💎 Файл отправлен для премиум пользователя: {file_path}")
                            await asyncio.sleep(0.4)
                        except Exception as audio_error:
                            logging.error(f"❌ Ошибка отправки аудио {title}: {audio_error}")
                            failed_count += 1
                    else:
                        logging.warning(f"⚠️ Файл не найден для премиум пользователя: {file_path}")
                        failed_count += 1
                else:
                    # Бесплатные: всегда скачиваем трек заново
                    if original_url and original_url.startswith('http'):
                        try:
                            logging.info(f"📥 Скачиваю трек для бесплатного пользователя: {title} по ссылке: {original_url}")
                            
                            # Загружаем трек без добавления в коллекцию (он уже там есть)
                            download_result = await download_track_from_url_with_priority(user_id_str, original_url, is_premium, add_to_collection=False)
                            
                            if download_result:
                                # Трек успешно загружен, отправляем пользователю
                                try:
                                    await callback.message.answer_audio(types.FSInputFile(download_result), title=title)
                                    success_count += 1
                                    
                                    # Сразу удаляем файл для бесплатного пользователя
                                    try:
                                        os.remove(download_result)
                                        logging.info(f"🧹 Файл сразу удален для бесплатного пользователя: {download_result}")
                                    except Exception as cleanup_error:
                                        logging.error(f"❌ Ошибка при удалении файла {download_result}: {cleanup_error}")
                                    
                                    await asyncio.sleep(0.4)
                                except Exception as audio_error:
                                    logging.error(f"❌ Ошибка отправки трека {title}: {audio_error}")
                                    failed_count += 1
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
        


        
    except Exception as e:
        logging.error(f"❌ Критическая ошибка в download_all_tracks для пользователя {user_id}: {e}")
        await callback.message.answer("❌ Произошла ошибка при скачивании всех треков.", reply_markup=main_menu)



# === Удаление трека ===
@dp.callback_query(F.data.startswith("del:"))
async def delete_track(callback: types.CallbackQuery):
    global user_tracks
    try:
        user_id = str(callback.from_user.id)
        
        logging.info(f"🔍 === НАЧАЛО УДАЛЕНИЯ ТРЕКА ===")
        logging.info(f"🔍 Пользователь: {user_id}")
        logging.info(f"🔍 Индекс трека: {callback.data}")
        logging.info(f"🔍 Глобальный user_tracks до удаления: {user_tracks}")
        
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
            await callback.answer("❄️ Трек не найден.", show_alert=True)
            return
        
        track = tracks[idx]
        
        # Проверяем формат трека
        if isinstance(track, dict):
            # Новый формат: объект с информацией о треке
            file_path = track.get('url', '').replace('file://', '')
            title = track.get('title', 'Неизвестный трек')
        else:
            # Старый формат: путь к файлу
            file_path = track
            title = os.path.basename(track)
        
        # Удаляем файл с диска, если он существует
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                logging.info(f"✅ Удален файл: {file_path}")
            except Exception as e:
                logging.error(f"❌ Ошибка удаления файла {file_path}: {e}")
                # Не прерываем удаление трека из списка, даже если файл не удалился
        
        # Удаляем трек из списка (независимо от того, удалился ли файл)
        tracks.pop(idx)
        # Обновляем глобальный user_tracks
        user_tracks[user_id] = tracks
        save_tracks()
        logging.info(f"✅ Трек удален из списка: {title}")
        logging.info(f"🔍 После удаления: всего треков у пользователя {user_id}: {len(tracks)}")
        logging.info(f"🔍 Обновленный user_tracks для пользователя {user_id}: {user_tracks.get(user_id, [])}")
        logging.info(f"🔍 Глобальный user_tracks после обновления: {user_tracks}")
        
        # Проверяем, что изменения сохранились
        if save_tracks():
            logging.info(f"✅ Треки успешно сохранены в файл")
        else:
            logging.error(f"❌ Ошибка сохранения треков в файл")
        
        # Обновляем интерфейс
        if not tracks:
            # Отправляем изображение мишки без текста, только с меню
            try:
                await callback.message.edit_media(
                    media=types.InputMediaPhoto(
                        media=types.FSInputFile("bear.png")
                    ),
                    reply_markup=main_menu
                )
            except Exception as e:
                logging.error(f"❌ Ошибка отправки фото: {e}")
                await callback.message.edit_text("❄️ У тебя нет треков.", reply_markup=main_menu)
        else:
            # Определяем текущую страницу на основе индекса удаленного трека
            current_page = idx // PAGE_SIZE
            
            # Проверяем, не вышли ли мы за пределы страниц
            total_pages = (len(tracks) + PAGE_SIZE - 1) // PAGE_SIZE if tracks else 0
            if current_page >= total_pages:
                current_page = max(0, total_pages - 1)
            
            # Если текущая страница пустая, переходим на предыдущую
            if current_page > 0 and len(tracks) <= current_page * PAGE_SIZE:
                current_page = max(0, current_page - 1)
            
            try:
                logging.info(f"🔍 Создаем клавиатуру для страницы {current_page+1}, треков: {len(tracks)}")
                kb = build_tracks_keyboard(tracks, page=current_page, owner_for_buttons=None)
                
                # Проверяем, что клавиатура создана корректно
                if not kb:
                    logging.warning(f"⚠️ Клавиатура пустая для страницы {current_page+1}")
                    # Если клавиатура пустая, переходим на предыдущую страницу
                    if current_page > 0:
                        current_page = current_page - 1
                        logging.info(f"🔍 Переходим на предыдущую страницу: {current_page+1}")
                        kb = build_tracks_keyboard(tracks, page=current_page, owner_for_buttons=None)
                
                # Обновляем изображение мишки с новой страницей треков
                try:
                    await callback.message.edit_media(
                        media=types.InputMediaPhoto(
                            media=types.FSInputFile("bear.png"),
                            caption=f"❄️ Твои треки (страница {current_page+1})"
                        ),
                        reply_markup=kb
                    )
                except Exception as e:
                    logging.error(f"❌ Ошибка отправки фото: {e}")
                    await callback.message.edit_text(f"❄️ Твои треки (страница {current_page+1})", reply_markup=kb)
            except Exception as kb_error:
                logging.error(f"❌ Ошибка создания клавиатуры после удаления: {kb_error}")
                await callback.message.edit_text("❄️ Твои треки (обновлено)", reply_markup=main_menu)
        
        await callback.answer("✅ Трек удален.")
        
        logging.info(f"🔍 === КОНЕЦ УДАЛЕНИЯ ТРЕКА ===")
        logging.info(f"🔍 Финальный user_tracks: {user_tracks}")
        logging.info(f"🔍 Треки пользователя {user_id}: {user_tracks.get(user_id, [])}")
        
    except ValueError as e:
        logging.error(f"❌ Ошибка парсинга индекса трека: {e}")
        await callback.answer("❌ Ошибка индекса трека.", show_alert=True)
    except Exception as e:
        logging.error(f"❌ Критическая ошибка в delete_track: {e}")
        await callback.answer("❌ Произошла ошибка при удалении трека.", show_alert=True)







# === Функции для работы с жанрами ===
def get_randomized_genres():
    """Возвращает случайные подмножества поисковых запросов для каждого жанра"""
    base_genres = get_genres()
    randomized_genres = {}
    
    for genre_name, queries in base_genres.items():
        # Перемешиваем запросы
        shuffled_queries = list(queries)
        random.shuffle(shuffled_queries)
        
        # Выбираем случайное количество запросов (от 80% до 100% от общего количества)
        min_queries = max(10, int(len(shuffled_queries) * 0.8))
        max_queries = len(shuffled_queries)
        num_queries = random.randint(min_queries, max_queries)
        
        # Берем случайное подмножество
        selected_queries = random.sample(shuffled_queries, num_queries)
        randomized_genres[genre_name] = selected_queries
        
        logging.info(f"🎲 Жанр {genre_name}: выбрано {num_queries} из {len(queries)} запросов")
    
    return randomized_genres

def get_genres():
    """Возвращает список доступных жанров с поисковыми запросами для случайного поиска"""
    return {
        "🎵 Поп": [
            "pop music 2024 official audio",
            "popular pop songs official",
            "best pop hits official audio",
            "top pop music tracks",
            "pop songs today official",
            "latest pop music official",
            "pop music playlist official",
            "pop hits 2024 official audio",
            "pop music new releases",
            "pop songs popular official",
            "pop music trending tracks",
            "pop hits today official",
            "pop music latest official",
            "pop songs hits official",
            "pop music best tracks",
            "pop hits playlist official",
            "pop music top tracks",
            "pop songs 2024 official",
            "pop music current tracks",
            "pop hits new releases",
            "pop music trending songs",
            "pop songs latest official",
            "pop music popular tracks",
            "pop hits current official",
            "pop music today songs",
            "pop songs trending official",
            "pop music hits official",
            "pop hits latest tracks",
            "pop music current songs",
            "pop songs best official",
            "pop music new hits official"
        ],
        "🎸 Рок": [
            "rock music 2024 official audio",
            "best rock songs official",
            "rock hits today official",
            "popular rock music tracks",
            "rock songs playlist official",
            "top rock hits official audio",
            "rock music latest official",
            "rock songs 2024 official",
            "rock hits playlist official",
            "rock music popular tracks",
            "rock songs trending official",
            "rock music best tracks",
            "rock hits latest official",
            "rock music new releases",
            "rock songs hits official",
            "rock music current tracks",
            "rock hits new releases",
            "rock music trending songs",
            "rock songs latest official",
            "rock music top tracks",
            "rock hits current official",
            "rock music today songs",
            "rock songs popular official",
            "rock music hits official",
            "rock hits trending tracks",
            "rock music playlist official",
            "rock songs best official",
            "rock music new hits official",
            "rock hits today official",
            "rock music latest hits official"
        ],
        "🎤 Хип-хоп": [
            "hip hop music 2024 official audio",
            "rap songs today official",
            "best hip hop hits official audio",
            "hip hop music latest tracks",
            "rap music popular songs official",
            "hip hop songs playlist official",
            "top rap hits official audio",
            "hip hop music trending tracks",
            "rap songs 2024 official",
            "hip hop hits playlist music",
            "rap music best tracks official",
            "hip hop songs latest official",
            "rap music new releases",
            "hip hop hits today music",
            "rap songs popular official",
            "hip hop music current tracks",
            "rap hits new releases",
            "hip hop music trending songs",
            "rap songs latest official",
            "hip hop music top tracks",
            "rap hits current music",
            "hip hop music today songs",
            "rap songs hits official",
            "hip hop hits trending tracks",
            "rap music playlist official",
            "hip hop songs best music",
            "rap music new hits official",
            "hip hop hits latest tracks",
            "rap music current songs",
            "hip hop songs trending official"
        ],
        "🎹 Электроника": [
            "electronic music 2024",
            "edm songs today",
            "best electronic music",
            "electronic hits latest",
            "edm music popular",
            "electronic songs playlist",
            "top edm hits",
            "electronic music trending",
            "edm songs 2024",
            "electronic hits playlist",
            "edm music best",
            "electronic songs latest",
            "edm music new",
            "electronic hits today",
            "edm songs popular",
            "electronic music current",
            "edm hits new",
            "electronic music trending",
            "edm songs latest",
            "electronic music top",
            "edm hits current",
            "electronic music today",
            "edm songs hits",
            "electronic hits trending",
            "edm music playlist",
            "electronic songs best",
            "edm music new hits",
            "electronic hits latest",
            "edm music current",
            "electronic songs trending"
        ],
        "🎷 Джаз": [
            "jazz music 2024",
            "best jazz songs",
            "jazz hits today",
            "popular jazz music",
            "jazz songs playlist",
            "top jazz hits",
            "jazz music latest",
            "jazz songs 2024",
            "jazz hits playlist",
            "jazz music popular",
            "jazz songs trending",
            "jazz music best",
            "jazz hits latest",
            "jazz music new",
            "jazz songs hits",
            "jazz music current",
            "jazz hits new",
            "jazz music trending",
            "jazz songs latest",
            "jazz music top",
            "jazz hits current",
            "jazz music today",
            "jazz songs popular",
            "jazz music hits",
            "jazz hits trending",
            "jazz music playlist",
            "jazz songs best",
            "jazz music new hits",
            "jazz hits latest",
            "jazz music current",
            "jazz songs trending"
        ],
        "🎻 Классика": [
            "classical music 2024",
            "best classical music",
            "classical hits today",
            "popular classical music",
            "classical music playlist",
            "top classical hits",
            "classical music latest",
            "classical music 2024",
            "classical hits playlist",
            "classical music popular",
            "classical music trending",
            "classical music best",
            "classical hits latest",
            "classical music new",
            "classical music hits",
            "classical music current",
            "classical hits new",
            "classical music trending",
            "classical music latest",
            "classical music top",
            "classical hits current",
            "classical music today",
            "classical music popular",
            "classical music hits",
            "classical hits trending",
            "classical music playlist",
            "classical music best",
            "classical music new hits",
            "classical hits latest",
            "classical music current",
            "classical music trending"
        ],
        "🎺 Блюз": [
            "blues music 2024",
            "best blues songs",
            "blues hits today",
            "popular blues music",
            "blues songs playlist",
            "top blues hits",
            "blues music latest",
            "blues songs 2024",
            "blues hits playlist",
            "blues music popular",
            "blues songs trending",
            "blues music best",
            "blues hits latest",
            "blues music new",
            "blues songs hits",
            "blues music current",
            "blues hits new",
            "blues music trending",
            "blues songs latest",
            "blues music top",
            "blues hits current",
            "blues music today",
            "blues songs popular",
            "blues music hits",
            "blues hits trending",
            "blues music playlist",
            "blues songs best",
            "blues music new hits",
            "blues hits latest",
            "blues music current",
            "blues songs trending"
        ],
        "🎼 Кантри": [
            "country music 2024",
            "best country songs",
            "country hits today",
            "popular country music",
            "country songs playlist",
            "top country hits",
            "country music latest",
            "country songs 2024",
            "country hits playlist",
            "country music popular",
            "country songs trending",
            "country music best",
            "country hits latest",
            "country music new",
            "country songs hits",
            "country music current",
            "country hits new",
            "country music trending",
            "country songs latest",
            "country music top",
            "country hits current",
            "country music today",
            "country songs popular",
            "country music hits",
            "country hits trending",
            "country music playlist",
            "country songs best",
            "country music new hits",
            "country hits latest",
            "country music current",
            "country songs trending"
        ],
        "🎭 Рэгги": [
            "reggae music 2024",
            "best reggae songs",
            "reggae hits today",
            "popular reggae music",
            "reggae songs playlist",
            "top reggae hits",
            "reggae music latest",
            "reggae songs 2024",
            "reggae hits playlist",
            "reggae music popular",
            "reggae songs trending",
            "reggae music best",
            "reggae hits latest",
            "reggae music new",
            "reggae songs hits",
            "reggae music current",
            "reggae hits new",
            "reggae music trending",
            "reggae songs latest",
            "reggae music top",
            "reggae hits current",
            "reggae music today",
            "reggae songs popular",
            "reggae music hits",
            "reggae hits trending",
            "reggae music playlist",
            "reggae songs best",
            "reggae music new hits",
            "reggae hits latest",
            "reggae music current",
            "reggae songs trending"
        ],
        "🎪 Фолк": [
            "folk music 2024",
            "best folk songs",
            "folk hits today",
            "popular folk music",
            "folk songs playlist",
            "top folk hits",
            "folk music latest",
            "folk songs 2024",
            "folk hits playlist",
            "folk music popular",
            "folk songs trending",
            "folk music best",
            "folk hits latest",
            "folk music new",
            "folk songs hits",
            "folk music current",
            "folk hits new",
            "folk music trending",
            "folk songs latest",
            "folk music top",
            "folk hits current",
            "folk music today",
            "folk songs popular",
            "folk music hits",
            "folk hits trending",
            "folk music playlist",
            "folk songs best",
            "folk music new hits",
            "folk hits latest",
            "folk music current",
            "folk songs trending"
        ],
        "🎨 Альтернатива": [
            "alternative music 2024",
            "best alternative songs",
            "alternative hits today",
            "popular alternative music",
            "alternative songs playlist",
            "top alternative hits",
            "alternative music latest",
            "alternative songs 2024",
            "alternative hits playlist",
            "alternative music popular",
            "alternative songs trending",
            "alternative music best",
            "alternative hits latest",
            "alternative music new",
            "alternative songs hits",
            "alternative music current",
            "alternative hits new",
            "alternative music trending",
            "alternative songs latest",
            "alternative music top",
            "alternative hits current",
            "alternative music today",
            "alternative songs popular",
            "alternative music hits",
            "alternative hits trending",
            "alternative music playlist",
            "alternative songs best",
            "alternative music new hits",
            "alternative hits latest",
            "alternative music current",
            "alternative songs trending"
        ],
        "🎬 Саундтреки": [
            "soundtrack music 2024",
            "best soundtrack songs",
            "soundtrack hits today",
            "popular soundtrack music",
            "soundtrack songs playlist",
            "top soundtrack hits",
            "soundtrack music latest",
            "soundtrack songs 2024",
            "soundtrack hits playlist",
            "soundtrack music popular",
            "soundtrack songs trending",
            "soundtrack music best",
            "soundtrack hits latest",
            "soundtrack music new",
            "soundtrack songs hits",
            "soundtrack music current",
            "soundtrack hits new",
            "soundtrack music trending",
            "soundtrack songs latest",
            "soundtrack music top",
            "soundtrack hits current",
            "soundtrack music today",
            "soundtrack songs popular",
            "soundtrack music hits",
            "soundtrack hits trending",
            "soundtrack music playlist",
            "soundtrack songs best",
            "soundtrack music new hits",
            "soundtrack hits latest",
            "soundtrack music current",
            "soundtrack songs trending"
        ]
    }

def search_genre_tracks(genre_queries, limit=20):
    """Ищет треки по жанру используя случайные поисковые запросы для разнообразия"""
    all_results = []
    
    try:
        # Перемешиваем запросы для случайности
        shuffled_queries = list(genre_queries)
        random.shuffle(shuffled_queries)
        
        # Берем случайное подмножество запросов для разнообразия
        # Если запросов больше 20, берем случайные 20-35 для большего разнообразия
        if len(shuffled_queries) > 20:
            num_queries = random.randint(20, min(35, len(shuffled_queries)))
            selected_queries = random.sample(shuffled_queries, num_queries)
        else:
            selected_queries = shuffled_queries
        
        # Добавляем fallback запросы для популярных жанров (более специфичные для музыки)
        fallback_queries = [
            "rap music official audio",
            "hip hop songs official",
            "popular rap music",
            "best hip hop tracks",
            "rap hits official",
            "hip hop classics official audio"
        ]
        
        # Добавляем fallback запросы к основным
        selected_queries.extend(fallback_queries)
        logging.info(f"🎲 Добавлено {len(fallback_queries)} fallback запросов")
        
        logging.info(f"🎲 Выбрано {len(selected_queries)} случайных запросов из {len(genre_queries)} доступных")
        
        for query in selected_queries:
            try:
                # Пробуем разные стратегии поиска (более направленные на музыку)
                search_strategies = [
                    f"ytsearch3:{query} official audio",  # Ищем официальные аудио
                    f"ytsearch3:{query} music",  # Ищем с ключевым словом "music"
                    f"ytsearch3:{query}",  # Ищем 3 результата
                    f"ytsearch5:{query}",  # Ищем 5 результатов
                ]
                
                # Если запрос сложный, добавляем упрощенные версии
                if " - " in query:
                    artist, song = query.split(" - ", 1)
                    search_strategies.extend([
                        f"ytsearch3:{artist} {song}",
                        f"ytsearch3:{artist}",
                        f"ytsearch3:{song}"
                    ])
                
                query_success = False
                
                for strategy in search_strategies:
                    if query_success:
                        break
                        
                    try:
                        # Выполняем поиск для каждого конкретного трека
                        ydl_opts = {
                            'format': 'bestaudio/best',
                            'noplaylist': True,
                            'quiet': True,
                            'cookiefile': COOKIES_FILE if os.path.exists(COOKIES_FILE) else None,
                            'extract_flat': True,  # Добавляем для более быстрого поиска
                            'no_warnings': True,
                            'ignoreerrors': True,  # Игнорируем ошибки для отдельных запросов
                            'timeout': 30,  # Увеличиваем таймаут
                            'retries': 3,  # Количество попыток
                        }
                        
                        # Проверяем cookies
                        if os.path.exists(COOKIES_FILE):
                            logging.info(f"🍪 Используем cookies файл: {COOKIES_FILE}")
                        else:
                            logging.warning("⚠️ Cookies файл не найден, поиск может быть ограничен")
                        
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            try:
                                # Пробуем текущую стратегию
                                info = ydl.extract_info(strategy, download=False)
                                
                                if not info:
                                    logging.warning(f"⚠️ Пустой результат поиска для '{query}' (стратегия: {strategy})")
                                    continue
                                    
                                results = info.get("entries", [])
                                
                                if results:
                                    # Фильтруем результаты, чтобы избежать сборников и нарезок
                                    valid_results = []
                                    for result in results:
                                        if not result:
                                            continue
                                            
                                        title = result.get('title', '').lower()
                                        duration = result.get('duration', 0)
                                        video_id = result.get('id')
                                        
                                        # Улучшенная фильтрация для поиска только музыкальных треков
                                        if (duration and duration > 60 and  # Трек должен быть длиннее 1 минуты
                                            duration < 600 and  # И не слишком длинный (не более 10 минут)
                                            video_id and  # Убеждаемся, что есть ID видео
                                            # Исключаем сборники, нарезки, обзоры
                                            'mix' not in title and 
                                            'compilation' not in title and
                                            'collection' not in title and
                                            'best of' not in title and
                                            'greatest hits' not in title and
                                            'remix' not in title and
                                            'cover' not in title and
                                            'karaoke' not in title and
                                            'instrumental' not in title and
                                            'live' not in title and  # Избегаем живых выступлений
                                            'concert' not in title and
                                            'performance' not in title and
                                            # Исключаем обзоры, интервью, документалки
                                            'review' not in title and
                                            'interview' not in title and
                                            'documentary' not in title and
                                            'analysis' not in title and
                                            'reaction' not in title and
                                            'commentary' not in title and
                                            'podcast' not in title and
                                            'news' not in title and
                                            'behind the scenes' not in title and
                                            'making of' not in title and
                                            'studio session' not in title and
                                            # Исключаем клипы с длинными названиями (обычно это обзоры)
                                            len(title) < 100 and
                                            # Проверяем, что в названии есть музыкальные ключевые слова
                                            any(keyword in title for keyword in [
                                                'music', 'song', 'track', 'audio', 'beat', 'melody',
                                                'rap', 'hip hop', 'pop', 'rock', 'jazz', 'blues',
                                                'electronic', 'folk', 'country', 'reggae', 'alternative'
                                            ]) and
                                            # Дополнительная проверка: исключаем названия, которые выглядят как обзоры
                                            not any(pattern in title for pattern in [
                                                'vs ', 'versus', 'comparison', 'review', 'analysis',
                                                'breakdown', 'explanation', 'tutorial', 'guide',
                                                'how to', 'what is', 'why ', 'when ', 'where ',
                                                'interview', 'podcast', 'news', 'update', 'announcement'
                                            ])):
                                            
                                            valid_results.append(result)
                                    
                                    # Добавляем случайное количество результатов (1-5) для большего разнообразия
                                    if valid_results:
                                        # Исправляем ошибку randrange - проверяем минимальное количество
                                        min_count = min(2, len(valid_results))
                                        max_count = min(5, len(valid_results))
                                        
                                        if min_count <= max_count:
                                            num_to_add = random.randint(min_count, max_count)
                                            selected_results = random.sample(valid_results, num_to_add)
                                            all_results.extend(selected_results)
                                            logging.info(f"✅ Добавлено {num_to_add} треков из запроса '{query}' (стратегия: {strategy})")
                                            query_success = True
                                            break
                                        else:
                                            logging.warning(f"⚠️ Недостаточно результатов для выбора: {len(valid_results)}")
                                    else:
                                        logging.warning(f"⚠️ Нет валидных результатов для '{query}' (стратегия: {strategy})")
                                else:
                                    logging.warning(f"⚠️ Нет результатов для запроса '{query}' (стратегия: {strategy})")
                                    
                            except Exception as search_error:
                                logging.error(f"❌ Ошибка поиска для запроса '{query}' (стратегия: {strategy}): {search_error}")
                                continue
                                
                    except Exception as e:
                        logging.error(f"❌ Ошибка создания yt-dlp для запроса '{query}' (стратегия: {strategy}): {e}")
                        continue
                
                if not query_success:
                    logging.warning(f"⚠️ Все стратегии поиска не удались для запроса '{query}'")
                        
            except Exception as e:
                logging.error(f"❌ Критическая ошибка обработки запроса '{query}': {e}")
                continue
        
        # Убираем дубликаты по ID
        unique_results = []
        seen_ids = set()
        
        for result in all_results:
            if result and result.get('id') and result['id'] not in seen_ids:
                unique_results.append(result)
                seen_ids.add(result['id'])
        
        logging.info(f"✅ Найдено {len(unique_results)} уникальных треков по жанру")
        
        # Перемешиваем результаты для дополнительной случайности
        random.shuffle(unique_results)
        
        # Возвращаем только нужное количество треков
        return unique_results[:limit]
        
    except Exception as e:
        logging.error(f"❌ Критическая ошибка поиска по жанру: {e}")
        return []

def search_artist_tracks(artist_name, limit=10):
    """Ищет треки конкретного исполнителя на SoundCloud"""
    try:
        logging.info(f"👤 Поиск треков исполнителя на SoundCloud: {artist_name}")
        
        # Формируем поисковый запрос с префиксом scsearch для SoundCloud
        # Запрашиваем больше треков, чтобы после фильтрации осталось нужное количество
        search_query = f"scsearch{limit * 3}:{artist_name}"
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'quiet': True,
            'extract_flat': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'timeout': 30,
            'retries': 3,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Ищем треки исполнителя на SoundCloud
            info = ydl.extract_info(search_query, download=False)
            
            if not info:
                logging.warning(f"⚠️ Пустой результат поиска для исполнителя '{artist_name}' на SoundCloud")
                return []
                
            results = info.get("entries", [])
            
            if not results:
                logging.warning(f"⚠️ Нет результатов для исполнителя '{artist_name}' на SoundCloud")
                return []
            
            logging.info(f"🔍 Найдено {len(results)} треков для исполнителя {artist_name} на SoundCloud")
            
            # Фильтруем результаты
            valid_results = []
            for result in results:
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
                    'live' not in title and  # Избегаем живые выступления
                    'concert' not in title and
                    'performance' not in title and
                    url and 'soundcloud.com' in url):  # Убеждаемся, что это SoundCloud
                    
                    valid_results.append(result)
            
            logging.info(f"✅ После фильтрации осталось {len(valid_results)} подходящих треков")
            
            # Убираем дубликаты по URL
            unique_results = []
            seen_urls = set()
            
            for result in valid_results:
                if result and result.get('url') and result['url'] not in seen_urls:
                    unique_results.append(result)
                    seen_urls.add(result['url'])
            
            logging.info(f"✅ Найдено {len(unique_results)} уникальных треков исполнителя {artist_name} на SoundCloud")
            
            # Перемешиваем результаты для разнообразия
            random.shuffle(unique_results)
            
            # Возвращаем нужное количество треков
            return unique_results[:limit]
            
    except Exception as e:
        logging.error(f"❌ Ошибка поиска треков исполнителя {artist_name} на SoundCloud: {e}")
        return []

@dp.callback_query(F.data.startswith("genre:"))
async def handle_genre_selection(callback: types.CallbackQuery):
    """Обрабатывает выбор жанра и сразу отправляет аудиофайлы для прослушивания"""
    genre_name = callback.data.split(":", 1)[1]
    user_id = str(callback.from_user.id)
    username = callback.from_user.username
    
    # Проверяем премиум статус
    if not is_premium_user(user_id, username):
        await callback.answer("🔒 Доступ ограничен! Требуется премиум подписка.", show_alert=True)
        return
    
    logging.info(f"🎭 Пользователь {user_id} выбрал жанр: {genre_name}")
    
    try:
        # Обновляем сообщение, показывая что поиск и загрузка начались
        await callback.message.edit_text(
            f"🔍 **Поиск и загрузка треков по жанру {genre_name}...**\n\n"
            "🎵 Ищу лучшие треки и скачиваю их для вас...\n"
            "⏳ Это может занять несколько минут.",
            parse_mode="Markdown"
        )
    except Exception as edit_error:
        logging.error(f"❌ Ошибка редактирования сообщения: {edit_error}")
        # Пытаемся отправить новое сообщение
        try:
            await callback.message.answer(
                f"🔍 **Поиск и загрузка треков по жанру {genre_name}...**\n\n"
                "🎵 Ищу лучшие треки и скачиваю их для вас...\n"
                "⏳ Это может занять несколько минут.",
                parse_mode="Markdown"
            )
        except Exception as send_error:
            logging.error(f"❌ Критическая ошибка отправки сообщения: {send_error}")
            return
    
    try:
        # Получаем случайные поисковые запросы для выбранного жанра
        genres = get_randomized_genres()
        genre_queries = genres.get(genre_name, [])
        
        if not genre_queries:
            await callback.message.edit_text(
                f"❌ **Ошибка**\n\n"
                f"🚫 Не удалось найти поисковые запросы для жанра {genre_name}.\n"
                "💡 Попробуйте выбрать другой жанр.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🎭 Выбрать другой жанр", callback_data="show_genres")],
                    [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_premium")]
                ])
            )
            return
        
        # Добавляем случайность в количество искомых треков (15-25 для большего разнообразия)
        random_limit = random.randint(15, 25)
        logging.info(f"🎲 Случайное количество треков для поиска: {random_limit}")
        
        # Ищем треки по жанру
        try:
            results = await asyncio.to_thread(search_genre_tracks, genre_queries, random_limit)
            
        except Exception as search_error:
            logging.error(f"❌ Ошибка поиска по жанру {genre_name}: {search_error}")
            await callback.message.edit_text(
                f"❌ **Ошибка поиска**\n\n"
                f"🚫 Не удалось выполнить поиск по жанру {genre_name}.\n"
                "💡 Попробуйте еще раз или выберите другой жанр.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data=f"genre:{genre_name}")],
                    [InlineKeyboardButton(text="🎭 Выбрать другой жанр", callback_data="show_genres")],
                    [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_premium")]
                ])
            )
            return
        
        if not results:
            await callback.message.edit_text(
                f"❌ **Ничего не найдено**\n\n"
                f"🚫 По жанру {genre_name} ничего не найдено.\n"
                "💡 Попробуйте выбрать другой жанр или попробовать позже.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🎭 Выбрать другой жанр", callback_data="show_genres")],
                    [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_premium")]
                ])
            )
            return
        
        # Обновляем сообщение о начале загрузки
        try:
            await callback.message.edit_text(
                f"⏳ **Загружаю {len(results)} треков по жанру {genre_name}...**\n\n"
                "🎵 Скачиваю аудиофайлы для прослушивания...\n"
                "💡 Это может занять несколько минут.",
                parse_mode="Markdown"
            )
        except Exception as edit_error:
            logging.error(f"❌ Ошибка редактирования сообщения о загрузке: {edit_error}")
        
        # Скачиваем треки и отправляем их как аудиофайлы
        downloaded_tracks = []
        failed_tracks = []
        
        for i, track in enumerate(results, 1):
            try:
                # Обновляем прогресс
                try:
                    await callback.message.edit_text(
                        f"⏳ **Загружаю трек {i}/{len(results)} по жанру {genre_name}...**",
                        parse_mode="Markdown"
                    )
                except Exception as edit_error:
                    logging.error(f"❌ Ошибка обновления прогресса: {edit_error}")
                
                # Скачиваем трек с таймаутом
                url = track.get('url', '')
                if not url:
                    logging.error(f"❌ Нет URL для трека {track.get('title', 'Без названия')}")
                    failed_tracks.append(f"{track.get('title', 'Без названия')} (нет URL)")
                    continue
                
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
                    # Проверяем размер файла перед отправкой
                    try:
                        file_size = os.path.getsize(filename)
                        file_size_mb = file_size / (1024 * 1024)
                        
                        if file_size_mb > MAX_FILE_SIZE_MB:
                            logging.warning(f"⚠️ Файл слишком большой для отправки: {file_size_mb:.2f}MB > {MAX_FILE_SIZE_MB}MB")
                            failed_tracks.append(f"{track.get('title', 'Без названия')} (слишком большой файл)")
                            # Удаляем слишком большой файл
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
                    
                    # Отправляем аудиофайл для прослушивания
                    try:
                        await callback.message.answer_audio(
                            types.FSInputFile(filename),
                            title=track.get('title', 'Без названия'),
                            performer=f"Жанр: {genre_name}",
                            duration=track.get('duration', 0)
                        )
                        logging.info(f"✅ Аудиофайл отправлен: {track.get('title', 'Без названия')}")
                    except Exception as audio_error:
                        logging.error(f"❌ Ошибка отправки аудиофайла {track.get('title', 'Без названия')}: {audio_error}")
                        # Если не удалось отправить как аудио, отправляем как документ
                        try:
                            await callback.message.answer_document(
                                types.FSInputFile(filename),
                                caption=f"🎵 **{track.get('title', 'Без названия')}**\n🎭 Жанр: {genre_name}"
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
        
        message_text = f"✅ **Загрузка треков по жанру {genre_name} завершена!**\n\n"
        message_text += f"🎵 **Успешно загружено:** {success_count} треков\n"
        
        if success_count > 0:
            total_size = sum(track.get('size_mb', 0) for track in downloaded_tracks)
            message_text += f"💾 **Общий размер:** {total_size:.1f} MB\n\n"
        
        if failed_count > 0:
            message_text += f"❌ **Не удалось загрузить:** {failed_count} треков\n\n"
            message_text += "💡 Некоторые треки могли быть:\n"
            message_text += "• Недоступны на SoundCloud\n"
            message_text += "• Слишком большими для отправки\n"
            message_text += "• Защищены авторскими правами\n"
            message_text += "• Превысили таймаут загрузки\n\n"
        
        message_text += "🎵 Все загруженные треки доступны для прослушивания\n"
        message_text += "🎵 Аудиофайлы отправлены выше для прослушивания\n\n"
        message_text += "💡 Теперь вы можете:\n"
        message_text += "• Слушать треки прямо здесь\n"
        message_text += "• Выбрать другой жанр\n"
        message_text += "• 🎲 **Нажать на этот же жанр еще раз для новых треков!**"
        
        # Создаем клавиатуру с опциями
        keyboard_buttons = []
        
        if failed_count > 0:
            keyboard_buttons.append([InlineKeyboardButton(text="🔄 Попробовать снова", callback_data=f"genre:{genre_name}")])
        

        
        keyboard_buttons.extend([
            [InlineKeyboardButton(text="🎲 Еще треки этого жанра", callback_data=f"genre:{genre_name}")],
            [InlineKeyboardButton(text="🎭 Выбрать другой жанр", callback_data="show_genres")],
            [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_premium")]
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        try:
            await callback.message.edit_text(
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
        
        logging.info(f"✅ Загружено {success_count} треков по жанру {genre_name} для пользователя {user_id}")
        
    except Exception as e:
        logging.error(f"❌ Критическая ошибка поиска по жанру {genre_name}: {e}")
        
        try:
            await callback.message.edit_text(
                f"❌ **Критическая ошибка**\n\n"
                f"🚫 Произошла критическая ошибка при поиске треков по жанру {genre_name}.\n"
                f"🔍 Ошибка: {str(e)[:100]}...\n\n"
                "💡 Попробуйте еще раз или выберите другой жанр.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data=f"genre:{genre_name}")],
                    [InlineKeyboardButton(text="🎭 Выбрать другой жанр", callback_data="show_genres")],
                    [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_premium")]
                ])
            )
        except Exception as final_error:
            logging.error(f"❌ Критическая ошибка отправки сообщения об ошибке: {final_error}")
            # Последняя попытка - отправляем простое сообщение
            try:
                await callback.message.answer(
                    f"❌ Произошла критическая ошибка при поиске по жанру {genre_name}. Попробуйте еще раз.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🎭 Выбрать другой жанр", callback_data="show_genres")],
                        [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_premium")]
                    ])
                )
            except Exception as last_error:
                logging.error(f"❌ Полная потеря связи с пользователем {user_id}: {last_error}")

@dp.callback_query(F.data == "show_genres")
async def show_genres_callback(callback: types.CallbackQuery):
    """Показывает список жанров через callback"""
    user_id = str(callback.from_user.id)
    username = callback.from_user.username
    
    # Проверяем премиум статус
    if not is_premium_user(user_id, username):
        await callback.answer("🔒 Доступ ограничен! Требуется премиум подписка.", show_alert=True)
        return
    
    genres = get_genres()
    
    # Создаем inline клавиатуру с жанрами (по двое в ряд)
    keyboard = []
    genre_list = list(genres.keys())
    
    # Группируем жанры по двое
    for i in range(0, len(genre_list), 2):
        row = [InlineKeyboardButton(text=genre_list[i], callback_data=f"genre:{genre_list[i]}")]
        if i + 1 < len(genre_list):
            row.append(InlineKeyboardButton(text=genre_list[i + 1], callback_data=f"genre:{genre_list[i + 1]}"))
        keyboard.append(row)
    
    # Добавляем кнопку "назад"
    keyboard.append([InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_premium")])
    
    kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback.message.edit_text(
        "🎭 **Выберите жанр музыки:**\n\n"
        "🎵 Я найду и сразу загружу для вас 8-12 случайных треков выбранного жанра!\n\n"
        "💡 При выборе жанра вы получите:\n"
        "• Аудиофайлы для прослушивания прямо в чате\n"
        "• Никаких дополнительных действий не требуется\n"
        "• 🎲 **Каждый раз новые случайные треки!**\n\n"
        "🔄 **Нажмите на жанр еще раз для новых треков!**",
        parse_mode="Markdown",
        reply_markup=kb
    )







@dp.callback_query(F.data == "back_to_main")
async def back_to_main_menu(callback: types.CallbackQuery):
    """Возвращает пользователя в главное меню из inline-меню"""
    user_id = str(callback.from_user.id)
    
    logging.info(f"🔙 Пользователь {user_id} возвращается в главное меню")
    
    try:
        # Отправляем изображение мишки без текста, только с меню
        await callback.message.edit_media(
            media=types.InputMediaPhoto(
                media=types.FSInputFile("bear.png")
            ),
            reply_markup=main_menu
        )
    except Exception as e:
        logging.error(f"❌ Ошибка в back_to_main_menu: {e}")
        # Если что-то пошло не так, просто отправляем главное меню
        try:
            await callback.message.edit_media(
                media=types.InputMediaPhoto(
                    media=types.FSInputFile("bear.png")
                ),
                reply_markup=main_menu
            )
        except Exception as photo_error:
            logging.error(f"❌ Ошибка отправки фото: {photo_error}")
            await callback.message.edit_text("🎵 Главное меню", reply_markup=main_menu)

@dp.callback_query(F.data == "search_artist_again")
async def search_artist_again_callback(callback: types.CallbackQuery, state: FSMContext):
    """Повторный поиск по исполнителю"""
    user_id = str(callback.from_user.id)
    username = callback.from_user.username
    
    # Проверяем премиум статус
    if not is_premium_user(user_id, username):
        await callback.answer("🔒 Доступ ограничен! Требуется премиум подписка.", show_alert=True)
        return
    
    try:
        await callback.message.edit_media(
            media=types.InputMediaPhoto(
                media=types.FSInputFile("bear.png"),
                caption="🎵 Введите название исполнителя или группы, чьи треки хотите найти."
            ),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_premium")]
            ])
        )
    except Exception as e:
        logging.error(f"❌ Ошибка отправки фото: {e}")
        await callback.message.edit_text(
            "🎵 Введите название исполнителя или группы, чьи треки хотите найти.",
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
    
    # Проверяем премиум статус
    if not is_premium_user(user_id, username):
        await callback.answer("🔒 Доступ ограничен! Требуется премиум подписка.", show_alert=True)
        return
    
    logging.info(f"🔄 Повторная попытка поиска по исполнителю для пользователя {user_id}: '{artist_name}'")
    
    # Отправляем сообщение о начале повторного поиска
    try:
        search_msg = await callback.message.edit_media(
            media=types.InputMediaPhoto(
                media=types.FSInputFile("bear.png"),
                caption=f"🔄 **Повторный поиск треков исполнителя {artist_name}...**\n\n"
                        "🎵 Ищу лучшие треки на SoundCloud...\n"
                        "⏳ Это может занять несколько минут."
            ),
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"❌ Ошибка отправки фото: {e}")
        search_msg = await callback.message.edit_text(
            f"🔄 **Повторный поиск треков исполнителя {artist_name}...**\n\n"
            "🎵 Ищу лучшие треки на SoundCloud...\n"
            "⏳ Это может занять несколько минут.",
            parse_mode="Markdown"
        )
    
    try:
        # Ищем треки исполнителя
        results = await asyncio.to_thread(search_artist_tracks, artist_name, 10)
        
        if not results:
            await search_msg.edit_text(
                f"❌ **Ничего не найдено**\n\n"
                f"🚫 По исполнителю '{artist_name}' ничего не найдено на SoundCloud.\n"
                "💡 Возможные причины:\n"
                "• Неправильное написание имени\n"
                "• Исполнитель не представлен на SoundCloud\n"
                "• Ограничения по региону\n\n"
                "🔍 Попробуйте:\n"
                "• Проверить правильность написания\n"
                "• Использовать другое имя\n"
                "• Поискать альтернативные варианты",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
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
                        f"⏳ Загружаю трек {i}/{len(results)} исполнителя {artist_name}...",
                        parse_mode="Markdown"
                    )
                except Exception as edit_error:
                    logging.error(f"❌ Ошибка обновления прогресса: {edit_error}")
                
                # Скачиваем трек
                url = track.get('url', '')
                if not url:
                    logging.error(f"❌ Нет URL для трека {track.get('title', 'Без названия')}")
                    failed_tracks.append(f"{track.get('title', 'Без названия')} (нет URL)")
                    continue
                
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
                                types.FSInputFile(filename)
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
        
        message_text = f"✅ Загрузка треков исполнителя {artist_name} завершена!"
        
        # Создаем клавиатуру с опциями
        keyboard_buttons = []
        
        if failed_count > 0:
            keyboard_buttons.append([InlineKeyboardButton(text="🔄 Попробовать снова", callback_data=f"search_artist_retry:{artist_name}")])
        
        keyboard_buttons.extend([
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
                    media=types.InputMediaPhoto(
                        media=types.FSInputFile("bear.png"),
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
                "• 👤 Исполнители\n"
                ""
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
        
        task_info = {
            'user_id': user_id,
            'url': url,
            'is_premium': is_premium,
            'timestamp': time.time(),
            'priority': priority
        }
        
        if is_premium:
            # Премиум пользователи идут в приоритетную очередь
            await PREMIUM_QUEUE.put((priority, task_info))
            logging.info(f"💎 Задача добавлена в премиум очередь для пользователя {user_id}")
        else:
            # Обычные пользователи идут в обычную очередь
            REGULAR_QUEUE.append(task_info)
            logging.info(f"📱 Задача добавлена в обычную очередь для пользователя {user_id}")
        
        # Запускаем обработчик очереди, если он еще не запущен
        asyncio.create_task(process_download_queue())
        return True
        
    except Exception as e:
        logging.error(f"❌ Ошибка добавления задачи в очередь: {e}")
        return False

async def process_download_queue():
    """Обрабатывает очередь загрузок с приоритетом для премиум пользователей"""
    global ACTIVE_DOWNLOADS
    
    while True:
        try:
            # Проверяем, можем ли мы запустить новую загрузку
            if ACTIVE_DOWNLOADS >= MAX_CONCURRENT_DOWNLOADS:
                await asyncio.sleep(1)
                continue
            
            # Сначала обрабатываем премиум очередь
            if not PREMIUM_QUEUE.empty():
                try:
                    priority, task_info = await PREMIUM_QUEUE.get()
                    
                    # Проверяем валидность задачи
                    if not task_info or not isinstance(task_info, dict):
                        logging.error("❌ process_download_queue: некорректная задача в премиум очереди")
                        continue
                        
                    user_id = task_info.get('user_id')
                    if not user_id:
                        logging.error("❌ process_download_queue: отсутствует user_id в задаче")
                        continue
                        
                    ACTIVE_DOWNLOADS += 1
                    logging.info(f"💎 Запускаем премиум загрузку для пользователя {user_id}")
                    
                    # Запускаем загрузку в фоне
                    asyncio.create_task(execute_download_task(task_info))
                    continue
                    
                except Exception as premium_error:
                    logging.error(f"❌ Ошибка обработки премиум задачи: {premium_error}")
                    continue
            
            # Если премиум очередь пуста, обрабатываем обычную
            if REGULAR_QUEUE:
                try:
                    task_info = REGULAR_QUEUE.popleft()
                    
                    # Проверяем валидность задачи
                    if not task_info or not isinstance(task_info, dict):
                        logging.error("❌ process_download_queue: некорректная задача в обычной очереди")
                        continue
                        
                    user_id = task_info.get('user_id')
                    if not user_id:
                        logging.error("❌ process_download_queue: отсутствует user_id в задаче")
                        continue
                        
                    ACTIVE_DOWNLOADS += 1
                    logging.info(f"📱 Запускаем обычную загрузку для пользователя {user_id}")
                    
                    # Запускаем загрузку в фоне
                    asyncio.create_task(execute_download_task(task_info))
                    continue
                    
                except Exception as regular_error:
                    logging.error(f"❌ Ошибка обработки обычной задачи: {regular_error}")
                    continue
            
            # Если обе очереди пусты, ждем
            await asyncio.sleep(1)
            
        except Exception as e:
            logging.error(f"❌ Ошибка в обработчике очереди: {e}")
            await asyncio.sleep(1)

async def execute_download_task(task_info: dict):
    """Выполняет задачу загрузки"""
    global ACTIVE_DOWNLOADS
    
    try:
        # Проверяем входные параметры
        if not task_info or not isinstance(task_info, dict):
            logging.error("❌ execute_download_task: некорректная задача")
            return
            
        user_id = task_info.get('user_id')
        url = task_info.get('url')
        is_premium = task_info.get('is_premium', False)
        
        if not user_id or not url:
            logging.error("❌ execute_download_task: отсутствуют обязательные параметры")
            return
        
        logging.info(f"🚀 Начинаем загрузку: пользователь {user_id}, премиум: {is_premium}")
        
        # Выполняем загрузку
        result = await download_track_from_url_with_priority(user_id, url, is_premium)
        
        if result:
            logging.info(f"✅ Загрузка завершена успешно для пользователя {user_id}")
        else:
            logging.error(f"❌ Загрузка завершилась с ошибкой для пользователя {user_id}")
            
    except Exception as e:
        logging.error(f"❌ Ошибка выполнения задачи загрузки: {e}")
    finally:
        ACTIVE_DOWNLOADS = max(0, ACTIVE_DOWNLOADS - 1)  # Не позволяем счетчику уйти в минус
        logging.info(f"📊 Активных загрузок: {ACTIVE_DOWNLOADS}")

async def download_track_from_url_with_priority(user_id: str, url: str, is_premium: bool = False, add_to_collection: bool = True):
    """Загружает трек с учетом приоритета и качества"""
    global user_tracks
    try:
        # Проверяем входные параметры
        if not user_id or not url:
            logging.error("❌ download_track_from_url_with_priority: некорректные параметры")
            return None
            
        # Проверяем, что user_tracks не None
        if user_tracks is None:
            logging.warning("⚠️ download_track_from_url_with_priority: user_tracks был None, инициализируем")
            user_tracks = {}
        
        outtmpl = os.path.join(CACHE_DIR, '%(title)s.%(ext)s')
        quality_text = "320 kbps" if is_premium else "192 kbps"
        logging.info(f"💾 Начинаю загрузку трека для пользователя {user_id}: {url} (качество: {quality_text})")
        
        # Используем Semaphore для ограничения одновременных загрузок
        async with download_semaphore:
            # Выполняем загрузку с соответствующим качеством через ThreadPoolExecutor
            loop = asyncio.get_running_loop()
            fn_info = await loop.run_in_executor(yt_executor, _ydl_download_blocking, url, outtmpl, COOKIES_FILE, is_premium)
        if not fn_info:
            logging.error(f"❌ Не удалось получить информацию о треке: {url}")
            return None
            
        filename, info = fn_info
        logging.info(f"📁 Файл загружен: {filename}")
        
        # Проверяем размер файла
        try:
            size_mb = os.path.getsize(filename) / (1024 * 1024)
            if size_mb > MAX_FILE_SIZE_MB:
                try:
                    os.remove(filename)
                    logging.warning(f"❌ Файл превышает максимальный размер {MAX_FILE_SIZE_MB}MB: {size_mb:.2f}MB")
                except:
                    pass
                return None
        except Exception as size_error:
            logging.error(f"❌ Ошибка проверки размера файла: {size_error}")
            return None
            
        # Добавляем трек в коллекцию пользователя только если это требуется
        if add_to_collection:
            track_info = {
                "title": os.path.basename(filename),
                "url": f"file://{filename}",
                "original_url": url,  # Сохраняем оригинальную ссылку для возможности перезагрузки
                "size_mb": round(size_mb, 2),
                "needs_migration": False
            }
            
            # Инициализируем список треков для пользователя, если его нет
            if str(user_id) not in user_tracks:
                user_tracks[str(user_id)] = []
            elif user_tracks[str(user_id)] is None:
                user_tracks[str(user_id)] = []
                
            user_tracks[str(user_id)].append(track_info)
            save_tracks()
            
            logging.info(f"✅ Трек успешно добавлен в коллекцию пользователя {user_id}: {filename} ({size_mb:.2f}MB, {quality_text})")
        else:
            logging.info(f"📁 Трек загружен без добавления в коллекцию: {filename} ({size_mb:.2f}MB, {quality_text})")
        
        return filename
        
    except Exception as e:
        logging.exception(f"❌ Ошибка скачивания трека {url} для пользователя {user_id}: {e}")
        return None

@dp.callback_query(F.data.startswith("add_genre_to_collection:"))
async def add_genre_tracks_to_collection(callback: types.CallbackQuery):
    """Добавляет все треки жанра в коллекцию пользователя"""
    try:
        # Парсим данные из callback
        data_parts = callback.data.split(":")
        if len(data_parts) != 3:
            await callback.answer("❌ Ошибка данных", show_alert=True)
            return
            
        genre_name = data_parts[1]
        track_count = int(data_parts[2])
        user_id = str(callback.from_user.id)
        
        logging.info(f"💾 Пользователь {user_id} добавляет {track_count} треков жанра {genre_name} в коллекцию")
        
        # Обновляем сообщение, показывая что началось добавление
        await callback.message.edit_text(
            f"💾 **Добавляю {track_count} треков жанра {genre_name} в вашу коллекцию...**\n\n"
            "🎵 Это может занять несколько минут...",
            parse_mode="Markdown"
        )
        
        # Получаем список файлов в папке cache
        cache_files = []
        for filename in os.listdir(CACHE_DIR):
            if filename.endswith('.mp3'):
                file_path = os.path.join(CACHE_DIR, filename)
                if os.path.exists(file_path):
                    # Проверяем, что файл не уже в коллекции пользователя
                    if not is_file_in_collection(file_path):
                        cache_files.append(file_path)
        
        # Берем последние N файлов (где N = track_count)
        recent_files = cache_files[-track_count:] if len(cache_files) >= track_count else cache_files
        
        added_count = 0
        total_size = 0
        
        for file_path in recent_files:
            try:
                if os.path.exists(file_path):
                    # Получаем размер файла
                    file_size = os.path.getsize(file_path)
                    file_size_mb = file_size / (1024 * 1024)
                    
                    # Создаем информацию о треке
                    track_info = {
                        "title": os.path.basename(file_path),
                        "url": f"file://{file_path}",
                        "original_url": "",  # Для треков по жанрам/исполнителям/альбомам URL неизвестен
                        "size_mb": round(file_size_mb, 2),
                        "needs_migration": False
                    }
                    
                    # Добавляем трек в коллекцию пользователя
                    if str(user_id) not in user_tracks:
                        user_tracks[str(user_id)] = []
                    elif user_tracks[str(user_id)] is None:
                        user_tracks[str(user_id)] = []
                    
                    user_tracks[str(user_id)].append(track_info)
                    added_count += 1
                    total_size += file_size_mb
                    
                    logging.info(f"✅ Трек добавлен в коллекцию: {os.path.basename(file_path)}")
                    
            except Exception as e:
                logging.error(f"❌ Ошибка добавления трека {file_path}: {e}")
                continue
        
        # Сохраняем обновленную коллекцию
        save_tracks()
        
        # Формируем итоговое сообщение
        message_text = f"✅ **Треки добавлены в вашу коллекцию!**\n\n"
        message_text += f"🎵 **Добавлено треков:** {added_count}\n"
        message_text += f"💾 **Общий размер:** {total_size:.1f} MB\n"
        message_text += f"🎭 **Жанр:** {genre_name}\n\n"
        message_text += "💡 Теперь вы можете:\n"
        message_text += "• Просматривать треки в разделе «Моя музыка»\n"
        message_text += "• Слушать их в любое время\n"
        message_text += "• Добавлять новые треки\n\n"
        message_text += "🎵 **Все треки сохранены в вашей коллекции!**"
        
        # Создаем клавиатуру
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎼 Моя музыка", callback_data="my_music")],
            [InlineKeyboardButton(text="🎲 Еще треки этого жанра", callback_data=f"genre:{genre_name}")],
            [InlineKeyboardButton(text="🎭 Выбрать другой жанр", callback_data="show_genres")],
            [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_premium")]
        ])
        
        await callback.message.edit_text(
            message_text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        
        logging.info(f"✅ Пользователь {user_id} добавил {added_count} треков жанра {genre_name} в коллекцию")
        
    except Exception as e:
        logging.error(f"❌ Ошибка добавления треков жанра в коллекцию: {e}")
        await callback.answer("❌ Произошла ошибка при добавлении треков", show_alert=True)

@dp.callback_query(F.data.startswith("add_artist_to_collection:"))
async def add_artist_tracks_to_collection(callback: types.CallbackQuery):
    """Добавляет все треки исполнителя в коллекцию пользователя"""
    try:
        # Парсим данные из callback
        data_parts = callback.data.split(":")
        if len(data_parts) != 3:
            await callback.answer("❌ Ошибка данных", show_alert=True)
            return
            
        artist_name = data_parts[1]
        track_count = int(data_parts[2])
        user_id = str(callback.from_user.id)
        
        logging.info(f"💾 Пользователь {user_id} добавляет {track_count} треков исполнителя {artist_name} в коллекцию")
        
        # Обновляем сообщение, показывая что началось добавление
        await callback.message.edit_text(
            f"💾 **Добавляю {track_count} треков исполнителя {artist_name} в вашу коллекцию...**\n\n"
            "🎵 Это может занять несколько минут...",
            parse_mode="Markdown"
        )
        
        # Получаем список файлов в папке cache
        cache_files = []
        for filename in os.listdir(CACHE_DIR):
            if filename.endswith('.mp3'):
                file_path = os.path.join(CACHE_DIR, filename)
                if os.path.exists(file_path):
                    # Проверяем, что файл не уже в коллекции пользователя
                    if not is_file_in_collection(file_path):
                        cache_files.append(file_path)
        
        # Берем последние N файлов (где N = track_count)
        recent_files = cache_files[-track_count:] if len(cache_files) >= track_count else cache_files
        
        added_count = 0
        total_size = 0
        
        for file_path in recent_files:
            try:
                if os.path.exists(file_path):
                    # Получаем размер файла
                    file_size = os.path.getsize(file_path)
                    file_size_mb = file_size / (1024 * 1024)
                    
                    # Создаем информацию о треке
                    track_info = {
                        "title": os.path.basename(file_path),
                        "url": f"file://{file_path}",
                        "original_url": "",  # Для треков по исполнителям URL неизвестен
                        "size_mb": round(file_size_mb, 2),
                        "needs_migration": False
                    }
                    
                    # Добавляем трек в коллекцию пользователя
                    if str(user_id) not in user_tracks:
                        user_tracks[str(user_id)] = []
                    elif user_tracks[str(user_id)] is None:
                        user_tracks[str(user_id)] = []
                    
                    user_tracks[str(user_id)].append(track_info)
                    added_count += 1
                    total_size += file_size_mb
                    
                    logging.info(f"✅ Трек добавлен в коллекцию: {os.path.basename(file_path)}")
                    
            except Exception as e:
                logging.error(f"❌ Ошибка добавления трека {file_path}: {e}")
                continue
        
        # Сохраняем обновленную коллекцию
        save_tracks()
        
        # Формируем итоговое сообщение
        message_text = f"✅ **Треки добавлены в вашу коллекцию!**\n\n"
        message_text += f"🎵 **Добавлено треков:** {added_count}\n"
        message_text += f"💾 **Общий размер:** {total_size:.1f} MB\n"
        message_text += f"👤 **Исполнитель:** {artist_name}\n\n"
        message_text += "💡 Теперь вы можете:\n"
        message_text += "• Просматривать треки в разделе «Моя музыка»\n"
        message_text += "• Слушать их в любое время\n"
        message_text += "• Добавлять новые треки\n\n"
        message_text += "🎵 **Все треки сохранены в вашей коллекции!**"
        
        # Создаем клавиатуру
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎼 Моя музыка", callback_data="my_music")],
            [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_main")]
        ])
        
        await callback.message.edit_text(
            message_text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        
        logging.info(f"✅ Пользователь {user_id} добавил {added_count} треков исполнителя {artist_name} в коллекцию")
        
    except Exception as e:
        logging.error(f"❌ Ошибка добавления треков исполнителя в коллекцию: {e}")
        await callback.answer("❌ Произошла ошибка при добавлении треков", show_alert=True)

@dp.callback_query(F.data == "soundcloud_search")
async def soundcloud_search_menu(callback: types.CallbackQuery):
    """Показывает меню поиска на SoundCloud"""
    user_id = str(callback.from_user.id)
    
    # Проверяем антиспам
    is_allowed, time_until = check_antispam(user_id)
    if not is_allowed:
        await callback.answer(f"⏳ Подождите {time_until:.1f} сек. перед следующим запросом", show_alert=True)
        return
    
    try:
        await callback.message.edit_media(
            media=types.InputMediaPhoto(
                media=types.FSInputFile("bear.png"),
                caption="🎵 **Поиск на SoundCloud**\n\n"
                        "🔍 **Выберите способ поиска:**\n\n"
                        "💡 **Быстрый поиск:**\n"
                        "• Готовые категории музыки\n"
                        "• Популярные жанры\n"
                        "• Мгновенные результаты\n\n"
                        "🔍 **Свой запрос:**\n"
                        "• Введите любой поисковый запрос\n"
                        "• Найдите именно то, что ищете\n\n"
                        "🎵 **SoundCloud - лучшие треки от независимых исполнителей!**"
            ),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔍 Быстрый поиск", callback_data="soundcloud_try_search")],
                [InlineKeyboardButton(text="🔍 Свой запрос", callback_data="sc_custom_search")],
                [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_main")]
            ])
        )
    except Exception as e:
        logging.error(f"❌ Ошибка отправки фото: {e}")
        await callback.message.edit_text(
            "🎵 **Поиск на SoundCloud**\n\n"
            "🔍 **Выберите способ поиска:**\n\n"
            "💡 **Быстрый поиск:**\n"
            "• Готовые категории музыки\n"
            "• Популярные жанры\n"
            "• Мгновенные результаты\n\n"
            "🔍 **Свой запрос:**\n"
            "• Введите любой поисковый запрос\n"
            "• Найдите именно то, что ищете\n\n"
            "🎵 **SoundCloud - лучшие треки от независимых исполнителей!**",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔍 Быстрый поиск", callback_data="soundcloud_try_search")],
                [InlineKeyboardButton(text="🔍 Свой запрос", callback_data="sc_custom_search")],
                [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_main")]
            ])
        )

@dp.callback_query(F.data == "soundcloud_try_search")
async def soundcloud_try_search_callback(callback: types.CallbackQuery):
    """Показывает меню поиска на SoundCloud"""
    user_id = str(callback.from_user.id)
    
    # Проверяем антиспам
    is_allowed, time_until = check_antispam(user_id)
    if not is_allowed:
        await callback.answer(f"⏳ Подождите {time_until:.1f} сек. перед следующим запросом", show_alert=True)
        return
    
    try:
        await callback.message.edit_media(
            media=types.InputMediaPhoto(
                media=types.FSInputFile("bear.png"),
                caption="🎵 **Поиск на SoundCloud**\n\n"
                        "🔍 **Выберите категорию или введите свой запрос:**\n\n"
                        "💡 **Популярные категории:**\n"
                        "• Electronic Music\n"
                        "• Hip Hop Beats\n"
                        "• Ambient Sounds\n"
                        "• Rock Instrumental\n"
                        "• Chill Music\n"
                        "• Dance Music",
                parse_mode="Markdown"
            ),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎵 Electronic Music", callback_data="sc_search:electronic music")],
                [InlineKeyboardButton(text="🎵 Hip Hop Beats", callback_data="sc_search:hip hop beats")],
                [InlineKeyboardButton(text="🎵 Ambient Sounds", callback_data="sc_search:ambient sounds")],
                [InlineKeyboardButton(text="🎵 Rock Instrumental", callback_data="sc_search:rock instrumental")],
                [InlineKeyboardButton(text="🎵 Chill Music", callback_data="sc_search:chill music")],
                [InlineKeyboardButton(text="🎵 Dance Music", callback_data="sc_search:dance music")],
                [InlineKeyboardButton(text="🔍 Свой запрос", callback_data="sc_custom_search")],
                [InlineKeyboardButton(text="⬅ Назад", callback_data="soundcloud_search")]
            ])
        )
    except Exception as e:
        logging.error(f"❌ Ошибка отправки фото: {e}")
        await callback.message.edit_text(
            "🎵 **Поиск на SoundCloud**\n\n"
            "🔍 **Выберите категорию или введите свой запрос:**\n\n"
            "💡 **Популярные категории:**\n"
            "• Electronic Music\n"
            "• Hip Hop Beats\n"
            "• Ambient Sounds\n"
            "• Rock Instrumental\n"
            "• Chill Music\n"
            "• Dance Music",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎵 Electronic Music", callback_data="sc_search:electronic music")],
                [InlineKeyboardButton(text="🎵 Hip Hop Beats", callback_data="sc_search:hip hop beats")],
                [InlineKeyboardButton(text="🎵 Ambient Sounds", callback_data="sc_search:ambient sounds")],
                [InlineKeyboardButton(text="🎵 Rock Instrumental", callback_data="sc_search:rock instrumental")],
                [InlineKeyboardButton(text="🎵 Chill Music", callback_data="sc_search:chill music")],
                [InlineKeyboardButton(text="🎵 Dance Music", callback_data="sc_search:dance music")],
                [InlineKeyboardButton(text="🔍 Свой запрос", callback_data="sc_custom_search")],
                [InlineKeyboardButton(text="⬅ Назад", callback_data="soundcloud_search")]
            ])
        )

# === Обработчики быстрого поиска по категориям SoundCloud ===
@dp.callback_query(F.data.startswith("sc_search:"))
async def quick_soundcloud_search(callback: types.CallbackQuery):
    """Быстрый поиск по категории SoundCloud"""
    try:
        user_id = str(callback.from_user.id)
        
        # Проверяем антиспам
        is_allowed, time_until = check_antispam(user_id)
        if not is_allowed:
            await callback.answer(f"⏳ Подождите {time_until:.1f} сек. перед следующим запросом", show_alert=True)
            return
        
        # Извлекаем поисковый запрос
        query = callback.data.split(":", 1)[1]
        
        logging.info(f"🎵 Пользователь {user_id} выполняет быстрый поиск SoundCloud: '{query}'")
        
        # Обновляем сообщение, показывая что начался поиск
        await callback.message.edit_text(
            f"🔍 **Быстрый поиск на SoundCloud...**\n\n"
            f"🎵 Ищу треки по категории: `{query}`\n"
            "⏳ Это может занять несколько секунд...",
            parse_mode="Markdown"
        )
        
        # Выполняем поиск
        results = await search_soundcloud(query)
        
        if results and len(results) > 0:
            await send_search_results(callback.message.chat.id, results)
            logging.info(f"✅ Найдено {len(results)} треков для быстрого поиска '{query}'")
        else:
            await callback.message.edit_text(
                f"❌ **Ничего не найдено**\n\n"
                f"🔍 По категории `{query}` ничего не найдено.\n\n"
                "💡 **Попробуйте:**\n"
                "• Другую категорию\n"
                "• Более общий запрос\n"
                "• Проверить правильность написания",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Попробовать другую категорию", callback_data="soundcloud_try_search")],
                    [InlineKeyboardButton(text="⬅ Назад", callback_data="soundcloud_search")]
                ])
            )
            logging.info(f"❌ Ничего не найдено для быстрого поиска '{query}'")
            
    except Exception as e:
        logging.error(f"❌ Ошибка быстрого поиска SoundCloud: {e}")
        await callback.answer("❌ Произошла ошибка при поиске", show_alert=True)

@dp.callback_query(F.data == "sc_custom_search")
async def custom_soundcloud_search(callback: types.CallbackQuery, state: FSMContext):
    """Переводит пользователя в состояние ввода поискового запроса"""
    user_id = str(callback.from_user.id)
    
    # Проверяем антиспам
    is_allowed, time_until = check_antispam(user_id)
    if not is_allowed:
        await callback.answer(f"⏳ Подождите {time_until:.1f} сек. перед следующим запросом", show_alert=True)
        return
    
    try:
        # Переводим пользователя в состояние ввода запроса
        await state.set_state(SearchStates.waiting_for_soundcloud_query)
        
        await callback.message.edit_media(
            media=types.InputMediaPhoto(
                media=types.FSInputFile("bear.png"),
                caption="🎵 **Введите поисковый запрос**\n\n"
                        "🔍 **Что искать:**\n"
                        "• Название трека\n"
                        "• Имя исполнителя\n"
                        "• Жанр музыки\n"
                        "• Любое описание\n\n"
                        "💡 **Советы:**\n"
                        "• Используйте английские слова\n"
                        "• Добавляйте жанр музыки\n"
                        "• Будьте конкретными\n\n"
                        "🎵 **Просто напишите ваш запрос в чат!**",
                parse_mode="Markdown"
            ),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅ Назад к SoundCloud", callback_data="soundcloud_search")],
                [InlineKeyboardButton(text="⬅ В главное меню", callback_data="back_to_main")]
            ])
        )
        
        logging.info(f"🎵 Пользователь {user_id} переведен в состояние ввода SoundCloud запроса")
        
    except Exception as e:
        logging.error(f"❌ Ошибка в custom_soundcloud_search: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)

@dp.callback_query(F.data == "search_soundcloud_again")
async def search_soundcloud_again_callback(callback: types.CallbackQuery):
    """Повторный поиск на SoundCloud"""
    user_id = str(callback.from_user.id)
    
    # Проверяем антиспам
    is_allowed, time_until = check_antispam(user_id)
    if not is_allowed:
        await callback.answer(f"⏳ Подождите {time_until:.1f} сек. перед следующим запросом", show_alert=True)
        return
    
    try:
        await callback.message.edit_media(
            media=types.InputMediaPhoto(
                media=types.FSInputFile("bear.png"),
                caption="🎵 **Поиск на SoundCloud**\n\n"
                        "🔍 **Выберите способ поиска:**\n\n"
                        "💡 **Быстрый поиск:**\n"
                        "• Готовые категории музыки\n"
                        "• Популярные жанры\n"
                        "• Мгновенные результаты\n\n"
                        "🔍 **Свой запрос:**\n"
                        "• Введите любой поисковый запрос\n"
                        "• Найдите именно то, что ищете\n\n"
                        "🎵 **SoundCloud - лучшие треки от независимых исполнителей!**"
            ),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔍 Быстрый поиск", callback_data="soundcloud_try_search")],
                [InlineKeyboardButton(text="🔍 Свой запрос", callback_data="sc_custom_search")],
                [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_main")]
            ])
        )
    except Exception as e:
        logging.error(f"❌ Ошибка отправки фото: {e}")
        await callback.message.edit_text(
            "🎵 **Поиск на SoundCloud**\n\n"
            "🔍 **Выберите способ поиска:**\n\n"
            "💡 **Быстрый поиск:**\n"
            "• Готовые категории музыки\n"
            "• Популярные жанры\n"
            "• Мгновенные результаты\n\n"
            "🔍 **Свой запрос:**\n"
            "• Введите любой поисковый запрос\n"
            "• Найдите именно то, что ищете\n\n"
            "🎵 **SoundCloud - лучшие треки от независимых исполнителей!**",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔍 Быстрый поиск", callback_data="soundcloud_try_search")],
                [InlineKeyboardButton(text="🔍 Свой запрос", callback_data="sc_custom_search")],
                [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_main")]
            ])
        )

@dp.callback_query(F.data.startswith("sc:"))
async def download_soundcloud_track(callback: types.CallbackQuery):
    """Скачивает трек с SoundCloud"""
    try:
        # Парсим данные из callback - используем split только по первому двоеточию
        callback_data = callback.data
        if not callback_data.startswith("sc:"):
            await callback.answer("❌ Неверный формат данных", show_alert=True)
            return
            
        # Извлекаем URL после "sc:" и декодируем его
        encoded_url = callback_data[3:]  # Убираем "sc:" в начале
        
        if not encoded_url:
            await callback.answer("❌ URL не найден", show_alert=True)
            return
            
        # Декодируем URL
        url = urllib.parse.unquote(encoded_url)
        
        logging.info(f"🔗 Декодированный URL: {url}")
        user_id = str(callback.from_user.id)
        
        logging.info(f"🎵 Пользователь {user_id} скачивает трек с SoundCloud: {url}")
        
        # Обновляем сообщение, показывая что началось скачивание
        await callback.message.edit_text(
            f"💾 **Скачиваю трек с SoundCloud...**\n\n"
            "🎵 Это может занять несколько минут...",
            parse_mode="Markdown"
        )
        
        # Скачиваем трек используя существующую функцию
        filename = await download_track_from_url(user_id, url)
        
        if filename:
            # Отправляем трек пользователю
            success = await send_audio_file(callback.message, filename, auto_cleanup=True, user_id=user_id)
            
            if success:
                # Формируем итоговое сообщение
                message_text = f"✅ **Трек с SoundCloud скачан и добавлен в вашу коллекцию!**\n\n"
                message_text += "💡 Теперь вы можете:\n"
                message_text += "• Просматривать треки в разделе «Моя музыка»\n"
                message_text += "• Слушать их в любое время\n"
                message_text += "• Добавлять новые треки\n\n"
                message_text += "🎵 **Все треки сохранены в вашей коллекции!**"
                
                # Создаем клавиатуру
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🎼 Моя музыка", callback_data="my_music")],
                    [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_main")]
                ])
                
                await callback.message.edit_text(
                    message_text,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
                
                logging.info(f"✅ Пользователь {user_id} успешно скачал трек с SoundCloud: {url}")
            else:
                await callback.message.edit_text(
                    "❌ **Ошибка отправки трека**\n\n"
                    "Трек был скачан, но не удалось отправить его.\n"
                    "Проверьте раздел «Моя музыка».",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🎼 Моя музыка", callback_data="my_music")],
                        [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_main")]
                    ])
                )
        else:
            await callback.message.edit_text(
                "❌ **Ошибка скачивания**\n\n"
                "Не удалось скачать трек с SoundCloud.\n"
                "Возможные причины:\n"
                "• Трек недоступен\n"
                "• Ошибка сети\n"
                "• Ограничения SoundCloud",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data=callback.data)],
                    [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_main")]
                ])
            )
            
    except Exception as e:
        logging.error(f"❌ Ошибка скачивания трека с SoundCloud: {e}")
        await callback.answer("❌ Произошла ошибка при скачивании трека", show_alert=True)

@dp.message(Command("sc"))
async def search_soundcloud_command(message: types.Message):
    """Поиск и скачивание музыки с SoundCloud"""
    try:
        # Проверяем, что команда содержит поисковый запрос
        if len(message.text.split()) < 2:
            await message.answer(
                "🎵 **Поиск на SoundCloud**\n\n"
                "💡 Использование: `/sc <запрос>`\n\n"
                "🔍 **Примеры:**\n"
                "• `/sc electronic music`\n"
                "• `/sc hip hop beats`\n"
                "• `/sc ambient sounds`\n"
                "• `/sc rock instrumental`\n\n"
                "🎵 Я найду для вас лучшие треки на SoundCloud!",
                parse_mode="Markdown"
            )
            return
        
        query = message.text.split(" ", 1)[1].strip()
        user_id = str(message.from_user.id)
        
        logging.info(f"🎵 Пользователь {user_id} ищет на SoundCloud: '{query}'")
        
        # Отправляем сообщение о начале поиска
        search_msg = await message.answer(
            f"🔍 **Поиск на SoundCloud...**\n\n"
            f"🎵 Ищу треки по запросу: `{query}`\n"
            "⏳ Это может занять несколько секунд...",
            parse_mode="Markdown"
        )
        
        # Ищем на SoundCloud
        results = await search_soundcloud(query)
        
        if results and len(results) > 0:
            # Удаляем сообщение о поиске
            await search_msg.delete()
            
            # Отправляем результаты поиска
            await send_search_results(message.chat.id, results)
            
            logging.info(f"✅ Найдено {len(results)} треков на SoundCloud для пользователя {user_id}")
        else:
            # Обновляем сообщение о поиске
            await search_msg.edit_text(
                f"❌ **Ничего не найдено на SoundCloud**\n\n"
                f"🔍 По запросу `{query}` ничего не найдено.\n\n"
                "💡 **Попробуйте:**\n"
                "• Изменить поисковый запрос\n"
                "• Использовать английские слова\n"
                "• Добавить жанр музыки\n"
                "• Проверить правильность написания",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Попробовать другой запрос", callback_data="search_soundcloud_again")],
                    [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_main")]
                ])
            )
            
            logging.info(f"❌ Ничего не найдено на SoundCloud для пользователя {user_id}: '{query}'")
            
    except Exception as e:
        logging.error(f"❌ Ошибка поиска на SoundCloud: {e}")
        await message.answer(
            "❌ **Ошибка поиска**\n\n"
            "Произошла ошибка при поиске на SoundCloud.\n"
            "Попробуйте позже или обратитесь в поддержку.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="search_soundcloud_again")],
                [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_main")]
            ])
        )

# === Обработчик текстовых сообщений для SoundCloud поиска ===
@dp.message(SearchStates.waiting_for_soundcloud_query)
async def handle_soundcloud_query_input(message: types.Message, state: FSMContext):
    """Обрабатывает ввод поискового запроса для SoundCloud"""
    try:
        user_id = str(message.from_user.id)
        query = message.text.strip()
        
        # Проверяем антиспам
        is_allowed, time_until = check_antispam(user_id)
        if not is_allowed:
            await message.answer(f"⏳ Подождите {time_until:.1f} сек. перед следующим запросом")
            return
        
        if not query or len(query) < 2:
            await message.answer(
                "❌ **Слишком короткий запрос**\n\n"
                "💡 Введите более длинный поисковый запрос (минимум 2 символа).",
                parse_mode="Markdown"
            )
            return
        
        logging.info(f"🎵 Пользователь {user_id} ввел поисковый запрос SoundCloud: '{query}'")
        
        # Сбрасываем состояние
        await state.clear()
        
        # Отправляем сообщение о начале поиска
        search_msg = await message.answer(
            f"🔍 **Поиск на SoundCloud...**\n\n"
            f"🎵 Ищу треки по запросу: `{query}`\n"
            "⏳ Это может занять несколько секунд...",
            parse_mode="Markdown"
        )
        
        # Ищем на SoundCloud
        results = await search_soundcloud(query)
        
        if results and len(results) > 0:
            # Удаляем сообщение о поиске
            await search_msg.delete()
            
            # Отправляем результаты поиска
            await send_search_results(message.chat.id, results)
            
            logging.info(f"✅ Найдено {len(results)} треков для пользователя {user_id}")
        else:
            # Обновляем сообщение о поиске
            await search_msg.edit_text(
                f"❌ **Ничего не найдено на SoundCloud**\n\n"
                f"🔍 По запросу `{query}` ничего не найдено.\n\n"
                "💡 **Попробуйте:**\n"
                "• Изменить поисковый запрос\n"
                "• Использовать английские слова\n"
                "• Добавить жанр музыки\n"
                "• Проверить правильность написания",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Попробовать другой запрос", callback_data="soundcloud_try_search")],
                    [InlineKeyboardButton(text="⬅ Назад", callback_data="soundcloud_search")]
                ])
            )
            
            logging.info(f"❌ Ничего не найдено для пользователя {user_id}: '{query}'")
            
    except Exception as e:
        logging.error(f"❌ Ошибка обработки SoundCloud запроса: {e}")
        await message.answer(
            "❌ **Ошибка поиска**\n\n"
            "Произошла ошибка при поиске на SoundCloud.\n"
            "Попробуйте позже или обратитесь в поддержку.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="soundcloud_try_search")],
                [InlineKeyboardButton(text="⬅ Назад", callback_data="soundcloud_search")]
            ])
        )
        # Сбрасываем состояние в случае ошибки
        await state.clear()

async def get_recommended_tracks(user_id):
    """Получает рекомендуемые треки для пользователя на основе его коллекции или популярных треков"""
    try:
        global user_tracks, user_recommendation_history
        
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
                remaining_tracks = [t for t in results if t not in new_tracks]
                random.shuffle(remaining_tracks)
                new_tracks.extend(remaining_tracks[:10-len(new_tracks)])
            
            # Обновляем историю показанных треков
            for track in new_tracks:
                track_id = f"{track.get('title', '')}_{track.get('url', '')}"
                history['shown_tracks'].add(track_id)
            
            # Ограничиваем размер истории (максимум 100 треков)
            if len(history['shown_tracks']) > 100:
                history['shown_tracks'] = set(list(history['shown_tracks'])[-50:])
            
            return new_tracks[:10]
        
        return []
        
    except Exception as e:
        logging.error(f"❌ Ошибка получения рекомендаций для пользователя {user_id}: {e}")
        return []

async def search_soundcloud(query):
    """Поиск на SoundCloud через yt-dlp"""
    try:
        logging.info(f"🔍 Поиск на SoundCloud: {query}")
        
        # Формируем поисковый запрос с префиксом scsearch
        search_query = f"scsearch{SOUNDCLOUD_SEARCH_LIMIT}:{query}"
        
        # Используем yt-dlp для поиска
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,  # Извлекаем только метаданные, без скачивания
            'ignoreerrors': True,
            'no_warnings': True,
            'timeout': 30,
            'retries': 3,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_query, download=False)
            
        if info and 'entries' in info:
            results = []
            for entry in info['entries']:
                if entry and isinstance(entry, dict):
                    title = entry.get('title', 'Без названия')
                    url = entry.get('url', '')
                    duration = entry.get('duration', 0)
                    
                    if url and title:
                        results.append({
                            'title': title,
                            'url': url,
                            'duration': duration,
                            'source': 'sc',  # Используем 'sc' для SoundCloud
                        })
            
            logging.info(f"🔍 Найдено {len(results)} треков на SoundCloud для запроса: {query}")
            
            # Сохраняем результаты в кэш с префиксом SoundCloud
            cache_key = f"{SOUNDCLOUD_CACHE_PREFIX}:{query}"
            set_cached_search(cache_key, results)
            
            return results
        
        logging.warning(f"🔍 Ничего не найдено на SoundCloud: {query}")
        return []
    except Exception as e:
        logging.error(f"❌ Ошибка поиска на SoundCloud: {e}")
        return []

async def send_audio_file(message, file_path, auto_cleanup=True, user_id=None):
    """Отправляет аудиофайл пользователю с автоматической очисткой"""
    try:
        if not os.path.exists(file_path):
            logging.error(f"❌ Файл не найден: {file_path}")
            return False
        
        # Получаем информацию о файле
        file_size = os.path.getsize(file_path)
        file_size_mb = file_size / (1024 * 1024)
        
        # Проверяем размер файла
        if file_size_mb > MAX_FILE_SIZE_MB:
            logging.warning(f"⚠️ Файл слишком большой для отправки: {file_size_mb:.2f}MB > {MAX_FILE_SIZE_MB}MB")
            return False
        
        # Отправляем аудиофайл
        try:
            await message.answer_audio(
                types.FSInputFile(file_path),
                title=os.path.basename(file_path).replace('.mp3', ''),
                performer="SoundCloud",
                duration=0  # Длительность будет определена автоматически
            )
            logging.info(f"✅ Аудиофайл отправлен: {file_path}")
            
            # Планируем автоматическую очистку файла после отправки
            if auto_cleanup and user_id:
                await auto_cleanup_file(file_path, is_collection_track=False, user_id=user_id)
            
            return True
            
        except Exception as audio_error:
            logging.error(f"❌ Ошибка отправки аудиофайла: {audio_error}")
            
            # Если не удалось отправить как аудио, отправляем как документ
            try:
                await message.answer_document(
                    types.FSInputFile(file_path)
                )
                logging.info(f"✅ Файл отправлен как документ: {file_path}")
                
                # Планируем автоматическую очистку файла после отправки
                if auto_cleanup and user_id:
                    await auto_cleanup_file(file_path, is_collection_track=False, user_id=user_id)
                
                return True
                
            except Exception as doc_error:
                logging.error(f"❌ Ошибка отправки документа: {doc_error}")
                return False
                
    except Exception as e:
        logging.error(f"❌ Ошибка в send_audio_file: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(main())