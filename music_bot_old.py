import logging
import os
import asyncio
import json
import time
import random
import yt_dlp
import browser_cookie3
from http.cookiejar import MozillaCookieJar
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
import secrets
import re
from functools import partial

# === НАСТРОЙКИ ===
API_TOKEN = os.getenv("BOT_TOKEN", "8421693077:AAGkkuoHSp9-P2vQ369ZGjaNAizs4z54Zho")
MAX_FILE_SIZE_MB = 50
CACHE_DIR = "cache"
COOKIES_FILE = os.path.join(os.path.dirname(__file__), "cookies.txt")
TRACKS_FILE = os.path.join(os.path.dirname(__file__), "tracks.json")
SEARCH_CACHE_FILE = os.path.join(os.path.dirname(__file__), "search_cache.json")
SHARED_FILE = os.path.join(os.path.dirname(__file__), "shared_playlists.json")


ARTIST_FACTS_FILE = os.path.join(os.path.dirname(__file__), "artist_facts.json")
PREMIUM_USERS_FILE = os.path.join(os.path.dirname(__file__), "premium_users.json")
SEARCH_CACHE_TTL = 600
SHARE_TTL = 86400
PAGE_SIZE = 10  # для постраничной навигации



logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
os.makedirs(CACHE_DIR, exist_ok=True)

# === JSON функции ===
def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"❌ Ошибка загрузки {path}: {e}")
            return default
    return default

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"❌ Ошибка сохранения {path}: {e}")

# 🔧 НОВАЯ ФУНКЦИЯ: Асинхронное сохранение JSON для устранения лагов
async def save_json_async(path, data):
    """Асинхронное сохранение JSON - не блокирует event loop"""
    try:
        # Используем aiofiles для асинхронной записи
        try:
            import aiofiles
            async with aiofiles.open(path, "w", encoding="utf-8") as f:
                await f.write(json.dumps(data, ensure_ascii=False, indent=2))
        except ImportError:
            # Fallback на синхронную запись если aiofiles не установлен
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        
        logging.info(f"✅ Данные успешно сохранены асинхронно в {path}")
        return True
        
    except Exception as e:
        logging.error(f"❌ Ошибка асинхронного сохранения {path}: {e}")
        return False

def is_premium_user(user_id: str, username: str = None) -> bool:
    """Проверяет, является ли пользователь премиум по ID или username"""
    try:
        premium_data = load_json(PREMIUM_USERS_FILE, {"premium_users": [], "premium_usernames": []})
        
        # Проверяем по ID
        if str(user_id) in premium_data.get("premium_users", []):
            return True
        
        # Проверяем по username (если передан)
        if username and username in premium_data.get("premium_usernames", []):
            return True
            
        return False
    except Exception as e:
        logging.error(f"❌ Ошибка проверки премиум статуса для {user_id} (username: {username}): {e}")
        return False

def add_premium_user(user_id: str = None, username: str = None) -> bool:
    """Добавляет пользователя в список премиум по ID или username"""
    try:
        premium_data = load_json(PREMIUM_USERS_FILE, {"premium_users": [], "premium_usernames": []})
        
        if user_id:
            if str(user_id) not in premium_data.get("premium_users", []):
                premium_data["premium_users"].append(str(user_id))
                save_json(PREMIUM_USERS_FILE, premium_data)
                logging.info(f"✅ Пользователь {user_id} добавлен в премиум")
                return True
            else:
                logging.info(f"ℹ️ Пользователь {user_id} уже в премиум списке")
                return False
                
        elif username:
            if username not in premium_data.get("premium_usernames", []):
                premium_data["premium_usernames"].append(username)
                save_json(PREMIUM_USERS_FILE, premium_data)
                logging.info(f"✅ Пользователь @{username} добавлен в премиум")
                return True
            else:
                logging.info(f"ℹ️ Пользователь @{username} уже в премиум списке")
                return False
        else:
            logging.error("❌ Не указан ни user_id, ни username")
            return False
            
    except Exception as e:
        logging.error(f"❌ Ошибка добавления пользователя в премиум: {e}")
        return False

def remove_premium_user(user_id: str = None, username: str = None) -> bool:
    """Удаляет пользователя из списка премиум по ID или username"""
    try:
        premium_data = load_json(PREMIUM_USERS_FILE, {"premium_users": [], "premium_usernames": []})
        
        if user_id:
            if str(user_id) in premium_data.get("premium_users", []):
                premium_data["premium_users"].remove(str(user_id))
                save_json(PREMIUM_USERS_FILE, premium_data)
                logging.info(f"✅ Пользователь {user_id} удален из премиум")
                return True
            else:
                logging.info(f"ℹ️ Пользователь {user_id} не найден в премиум списке")
                return False
                
        elif username:
            if username in premium_data.get("premium_usernames", []):
                premium_data["premium_usernames"].remove(username)
                save_json(PREMIUM_USERS_FILE, premium_data)
                logging.info(f"✅ Пользователь @{username} удален из премиум")
                return True
            else:
                logging.info(f"ℹ️ Пользователь @{username} не найден в премиум списке")
                return False
        else:
            logging.error("❌ Не указан ни user_id, ни username")
            return False
            
    except Exception as e:
        logging.error(f"❌ Ошибка удаления пользователя из премиум: {e}")
        return False



user_tracks = load_json(TRACKS_FILE, {})
search_cache = load_json(SEARCH_CACHE_FILE, {})
shared_playlists = load_json(SHARED_FILE, {})


artist_facts = load_json(ARTIST_FACTS_FILE, {"facts": {}})



def save_tracks():
    save_json(TRACKS_FILE, user_tracks)

# 🔧 НОВАЯ ФУНКЦИЯ: Асинхронное сохранение треков для устранения лагов
async def save_tracks_async():
    """Асинхронное сохранение треков - не блокирует event loop"""
    return await save_json_async(TRACKS_FILE, user_tracks)

def save_shared():
    save_json(SHARED_FILE, shared_playlists)

# 🔧 НОВАЯ ФУНКЦИЯ: Асинхронное сохранение shared для устранения лагов
async def save_shared_async():
    """Асинхронное сохранение shared - не блокирует event loop"""
    return await save_json_async(SHARED_FILE, shared_playlists)





# === Экспорт cookies (опционально) ===
def export_cookies():
    try:
        cj = browser_cookie3.chrome(domain_name=".youtube.com")
        cj_mozilla = MozillaCookieJar()
        for cookie in cj:
            cj_mozilla.set_cookie(cookie)
        cj_mozilla.save(COOKIES_FILE, ignore_discard=True, ignore_expires=True)
        logging.info("✅ Cookies экспортированы")
    except Exception as e:
        logging.error(f"❌ Ошибка экспорта cookies: {e}")

# попробовать экспортировать, не критично если не сработает
try:
    export_cookies()
except Exception:
    pass

# небольшой diagnostic: проверим, что cookies.txt существует и можно загрузить его имена
def check_cookies_file():
    if not os.path.exists(COOKIES_FILE):
        logging.warning("Cookies файл не найден: %s", COOKIES_FILE)
        return
    try:
        cj = MozillaCookieJar()
        cj.load(COOKIES_FILE, ignore_discard=True, ignore_expires=True)
        names = [c.name for c in cj]
        logging.info("Cookies загружены (%d): %s", len(names), ", ".join(names[:10]) + ("..." if len(names) > 10 else ""))
    except Exception as e:
        logging.warning("Не удалось загрузить cookies.txt: %s", e)

check_cookies_file()



# === НАСТРОЙКИ ПЕРИОДИЧЕСКОЙ ОЧИСТКИ ===
MP3_CLEANUP_INTERVAL = 600  # Интервал очистки MP3 файлов (10 минут)
MP3_FILE_MAX_AGE = 15  # Максимальный возраст MP3 файла в минутах перед удалением

# 🔧 НОВАЯ ФУНКЦИЯ: Периодическая очистка MP3 файлов для устранения лагов
async def periodic_mp3_cleanup():
    """Периодически очищает все MP3 файлы раз в 10 минут"""
    while True:
        try:
            await asyncio.sleep(MP3_CLEANUP_INTERVAL)
            
            logging.info("🧹 Запуск периодической очистки MP3 файлов...")
            
            cache_dir = CACHE_DIR
            if not os.path.exists(cache_dir):
                logging.info("📁 Папка cache не существует, пропускаем очистку")
                continue
            
            # Получаем список всех файлов в cache
            files_to_remove = []
            current_time = time.time()
            
            for filename in os.listdir(cache_dir):
                file_path = os.path.join(cache_dir, filename)
                
                # Проверяем только MP3 файлы
                if filename.lower().endswith('.mp3'):
                    try:
                        # Получаем время создания файла
                        file_creation_time = os.path.getctime(file_path)
                        file_age_minutes = (current_time - file_creation_time) / 60
                        
                        # Удаляем файлы старше указанного возраста
                        if file_age_minutes > MP3_FILE_MAX_AGE:
                            files_to_remove.append((file_path, file_age_minutes))
                            
                    except Exception as e:
                        logging.warning(f"⚠️ Не удалось проверить файл {filename}: {e}")
            
            # Удаляем старые MP3 файлы
            removed_count = 0
            total_size_mb = 0
            
            for file_path, age_minutes in files_to_remove:
                try:
                    # Получаем размер файла перед удалением
                    file_size = os.path.getsize(file_path)
                    file_size_mb = file_size / (1024 * 1024)
                    total_size_mb += file_size_mb
                    
                    # Удаляем файл
                    os.remove(file_path)
                    removed_count += 1
                    
                    logging.info(f"🧹 Удален старый MP3 файл: {os.path.basename(file_path)} (возраст: {age_minutes:.1f} мин, размер: {file_size_mb:.2f} MB)")
                    
                except Exception as e:
                    logging.error(f"❌ Ошибка удаления файла {file_path}: {e}")
            
            if removed_count > 0:
                logging.info(f"🧹 Периодическая очистка завершена: удалено {removed_count} MP3 файлов, освобождено {total_size_mb:.2f} MB")
            else:
                logging.info("🧹 Периодическая очистка: старых MP3 файлов не найдено")
                
        except Exception as e:
            logging.error(f"❌ Ошибка в периодической очистке MP3: {e}")
            await asyncio.sleep(60)  # Пауза при ошибке

# === Кэш поиска ===
def get_cached_search(query):
    query_l = query.lower()
    if query_l in search_cache:
        data = search_cache[query_l]
        if time.time() - data["time"] < SEARCH_CACHE_TTL:
            return data["results"]
    return None

def set_cached_search(query, results):
    search_cache[query.lower()] = {"time": time.time(), "results": results}
    save_json(SEARCH_CACHE_FILE, search_cache)

# === Асинхронная обёртка для yt_dlp ===
def _ydl_download_blocking(url, outtmpl, cookiefile):
    """Блокирующая функция для скачивания через yt-dlp"""
    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': outtmpl,
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'extract_flat': False,  # Для загрузки нужно False
        }
        
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
                
                # Получаем имя файла
                filename = ydl.prepare_filename(info)
                if not filename:
                    logging.error(f"❌ Не удалось подготовить имя файла для: {url}")
                    return None
                
                # Преобразуем в .mp3
                mp3_filename = os.path.splitext(filename)[0] + ".mp3"
                
                # Проверяем, что файл действительно создался
                if not os.path.exists(mp3_filename):
                    logging.error(f"❌ MP3 файл не был создан: {mp3_filename}")
                    return None
                
                # Проверяем размер файла
                try:
                    file_size = os.path.getsize(mp3_filename)
                    if file_size == 0:
                        logging.error(f"❌ Созданный файл пустой: {mp3_filename}")
                        return None
                    logging.info(f"✅ Файл создан успешно: {mp3_filename} ({file_size} байт)")
                except Exception as size_error:
                    logging.error(f"❌ Ошибка проверки размера файла: {size_error}")
                    return None
                
                return mp3_filename, info
                
            except Exception as extract_error:
                logging.error(f"❌ Ошибка извлечения информации: {extract_error}")
                return None
                
    except Exception as e:
        logging.error(f"❌ Критическая ошибка в _ydl_download_blocking: {e}")
        return None

async def download_track_from_url(user_id, url):
    """
    Асинхронно скачивает трек (в отдельном потоке), добавляет путь в user_tracks.
    """
    outtmpl = os.path.join(CACHE_DIR, '%(title)s.%(ext)s')
    try:
        logging.info(f"💾 Начинаю загрузку трека для пользователя {user_id}: {url}")
        
        # выполнить blocking ytdl в пуле потоков
        fn_info = await asyncio.to_thread(_ydl_download_blocking, url, outtmpl, COOKIES_FILE)
        if not fn_info:
            logging.error(f"❌ Не удалось получить информацию о треке: {url}")
            return None
            
        filename, info = fn_info
        logging.info(f"📁 Файл загружен: {filename}")
        
        # Проверяем размер файла
        size_mb = os.path.getsize(filename) / (1024 * 1024)
        if size_mb > MAX_FILE_SIZE_MB:
            try:
                os.remove(filename)
                logging.warning(f"❌ Файл превышает максимальный размер {MAX_FILE_SIZE_MB}MB: {size_mb:.2f}MB")
            except:
                pass
            return None
            
        # Добавляем трек в коллекцию пользователя
        user_tracks.setdefault(str(user_id), []).append(filename)
        # 🔧 ИСПРАВЛЕНИЕ: Сохраняем в фоне без блокировки
        asyncio.create_task(save_tracks_async())
        
        logging.info(f"✅ Трек успешно добавлен в коллекцию пользователя {user_id}: {filename} ({size_mb:.2f}MB)")
        return filename
        
    except Exception as e:
        logging.exception(f"❌ Ошибка скачивания трека {url} для пользователя {user_id}: {e}")
        return None

async def download_track_from_url_for_genre(user_id, url):
    """
    Асинхронно скачивает трек для жанров (в отдельном потоке), НЕ добавляет в user_tracks.
    """
    outtmpl = os.path.join(CACHE_DIR, '%(title)s.%(ext)s')
    try:
        logging.info(f"💾 Начинаю загрузку трека по жанру для пользователя {user_id}: {url}")
        
        # Проверяем, что URL валидный
        if not url or 'youtube.com' not in url:
            logging.error(f"❌ Неверный URL для загрузки: {url}")
            return None
        
        # выполнить blocking ytdl в пуле потоков
        try:
            fn_info = await asyncio.to_thread(_ydl_download_blocking, url, outtmpl, COOKIES_FILE)
        except Exception as ytdl_error:
            logging.error(f"❌ Ошибка yt-dlp для {url}: {ytdl_error}")
            return None
            
        if not fn_info:
            logging.error(f"❌ Не удалось получить информацию о треке: {url}")
            return None
            
        filename, info = fn_info
        
        # Проверяем, что файл действительно создался
        if not filename or not os.path.exists(filename):
            logging.error(f"❌ Файл не был создан: {filename}")
            return None
            
        logging.info(f"📁 Файл загружен: {filename}")
        
        # Проверяем размер файла
        try:
            size_mb = os.path.getsize(filename) / (1024 * 1024)
            if size_mb > MAX_FILE_SIZE_MB:
                try:
                    os.remove(filename)
                    logging.warning(f"❌ Файл превышает максимальный размер {MAX_FILE_SIZE_MB}MB: {size_mb:.2f}MB")
                except Exception as remove_error:
                    logging.error(f"❌ Не удалось удалить слишком большой файл {filename}: {remove_error}")
                return None
                
            # Проверяем, что файл не пустой
            if size_mb < 0.1:  # Меньше 100KB
                try:
                    os.remove(filename)
                    logging.warning(f"❌ Файл слишком маленький: {size_mb:.2f}MB")
                except Exception as remove_error:
                    logging.error(f"❌ Не удалось удалить слишком маленький файл {filename}: {remove_error}")
                return None
                
        except Exception as size_error:
            logging.error(f"❌ Ошибка проверки размера файла {filename}: {size_error}")
            # Удаляем файл с ошибкой
            try:
                os.remove(filename)
            except:
                pass
            return None
            
        # НЕ добавляем трек в коллекцию пользователя для жанров
        logging.info(f"✅ Трек по жанру успешно загружен для пользователя {user_id}: {filename} ({size_mb:.2f}MB)")
        return filename
        
    except Exception as e:
        logging.exception(f"❌ Критическая ошибка скачивания трека по жанру {url} для пользователя {user_id}: {e}")
        # Пытаемся очистить возможные частично загруженные файлы
        try:
            if 'filename' in locals() and filename and os.path.exists(filename):
                os.remove(filename)
                logging.info(f"🧹 Очищен частично загруженный файл: {filename}")
        except:
            pass
        return None

# === Состояния ===
class SearchStates(StatesGroup):
    waiting_for_search = State()
    waiting_for_artist = State()

class ShareStates(StatesGroup):
    waiting_for_code = State()



# === Главное меню ===
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="▶️ Найти трек на YouTube")],
        [KeyboardButton(text="🎼 Моя музыка")],
        [KeyboardButton(text="💎 Премиум функции"), KeyboardButton(text="🛒 Купить премиум")]
    ],
    resize_keyboard=True
)

# === Премиум меню ===
premium_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🎭 По жанрам"), KeyboardButton(text="👤 По исполнителям")],
        [KeyboardButton(text="📤 Поделиться плейлистом"), KeyboardButton(text="📥 Открыть плейлист")],
        [KeyboardButton(text="🚫 Отменить доступ")],
        [KeyboardButton(text="⬅ Назад в главное меню")]
    ],
    resize_keyboard=True
)

# === Меню для не премиум пользователей ===
non_premium_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🛒 Купить премиум")],
        [KeyboardButton(text="⬅ Назад в главное меню")]
    ],
    resize_keyboard=True
)

# === Меню для раздела покупки премиума ===
buy_premium_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💳 Перейти к оплате")],
        [KeyboardButton(text="⬅ Назад в главное меню")]
    ],
    resize_keyboard=True
)

back_button = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="⬅ Назад")]],
    resize_keyboard=True
)

# === Глобальная кнопка "Назад" ===
@dp.message(F.text == "⬅ Назад")
async def global_back(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("🔙 Возврат в главное меню", reply_markup=main_menu)

# === Команды ===
@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.answer("🎵 Привет! Я бот для поиска и скачивания музыки с YouTube.", reply_markup=main_menu)

@dp.message(F.text == "💎 Премиум функции")
async def show_premium_menu(message: types.Message):
    user_id = str(message.from_user.id)
    username = message.from_user.username
    
    if not is_premium_user(user_id, username):
        await message.answer("🔒 Доступ ограничен!\n\n💎 Раздел «Премиум функции» доступен только для премиум пользователей.\n\n🛒 Нажмите кнопку «Купить премиум» для получения доступа к расширенным функциям!", reply_markup=non_premium_menu)
        return
    
    await message.answer("💎 Добро пожаловать в премиум раздел!\n\nЗдесь доступны расширенные функции:\n• 🎭 Поиск по жанрам\n• 👤 Поиск по исполнителям\n• 📤 Поделиться плейлистом\n• 📥 Открыть плейлист\n• 🚫 Отменить доступ", reply_markup=premium_menu)

@dp.message(F.text == "🛒 Купить премиум")
async def go_to_payment(message: types.Message):
    await show_buy_premium(message)

@dp.message(F.text == "💳 Перейти к оплате")
async def go_to_payment_from_buy_menu(message: types.Message):
    await message.answer("💳 Переход к оплате\n\n🔗 Здесь будет ссылка на платежную систему или инструкции по оплате.", reply_markup=buy_premium_menu)

@dp.message(F.text == "🛒 Купить премиум")
async def show_buy_premium(message: types.Message):
    user_id = str(message.from_user.id)
    username = message.from_user.username
    
    if is_premium_user(user_id, username):
        await message.answer("🎉 Поздравляем! У вас уже есть премиум доступ!\n\n💎 Вы можете использовать все премиум функции бота.", reply_markup=main_menu)
        return
    
    await message.answer("🛒 Купить премиум доступ\n\n💎 Премиум функции включают:\n• 🎭 Поиск музыки по жанрам\n• 👤 Поиск по исполнителям\n• 📤 Возможность делиться плейлистами\n• 📥 Открытие чужих плейлистов\n\n💰 Стоимость подписки 2$/месяц", reply_markup=buy_premium_menu)

@dp.message(F.text == "⬅ Назад в главное меню")
async def back_to_main_from_premium(message: types.Message):
    await message.answer("🔙 Возврат в главное меню", reply_markup=main_menu)

@dp.callback_query(F.data == "back_to_premium")
async def back_to_premium_menu(callback: types.CallbackQuery):
    try:
        await callback.message.edit_text("💎 Премиум функции", reply_markup=premium_menu)
    except Exception as e:
        # Если редактирование не удалось, отправляем новое сообщение
        logging.error(f"❌ Ошибка редактирования сообщения в back_to_premium_menu: {e}")
        await callback.message.answer("💎 Премиум функции", reply_markup=premium_menu)
        await callback.message.delete()









@dp.message(Command("add_premium"))
async def add_premium_command(message: types.Message):
    """Команда для добавления пользователя в премиум (только для администраторов)"""
    user_id = str(message.from_user.id)
    username = message.from_user.username
    
    # Проверяем, является ли отправитель администратором
    admin_ids = ["123456789"]  # Замените на реальные ID администраторов
    admin_usernames = ["wtfguys4"]  # Замените на реальные username администраторов
    
    is_admin = (user_id in admin_ids) or (username in admin_usernames)
    
    if not is_admin:
        await message.answer("❌ У вас нет прав для выполнения этой команды.", reply_markup=main_menu)
        return
    
    # Парсим команду: /add_premium <user_id или @username>
    command_parts = message.text.split()
    if len(command_parts) != 2:
        await message.answer("❌ Неверный формат команды.\n\nИспользуйте:\n• /add_premium <user_id>\n• /add_premium @username", reply_markup=main_menu)
        return
    
    target = command_parts[1]
    
    # Определяем, это ID или username
    if target.startswith("@"):
        # Это username
        target_username = target[1:]  # Убираем @
        if add_premium_user(username=target_username):
            await message.answer(f"✅ Пользователь @{target_username} успешно добавлен в премиум!", reply_markup=main_menu)
        else:
            await message.answer(f"❌ Ошибка при добавлении пользователя @{target_username} в премиум.", reply_markup=main_menu)
    else:
        # Это ID
        if add_premium_user(user_id=target):
            await message.answer(f"✅ Пользователь {target} успешно добавлен в премиум!", reply_markup=main_menu)
        else:
            await message.answer(f"❌ Ошибка при добавлении пользователя {target} в премиум.", reply_markup=main_menu)

@dp.message(Command("remove_premium"))
async def remove_premium_command(message: types.Message):
    """Команда для удаления пользователя из премиум (только для администраторов)"""
    user_id = str(message.from_user.id)
    username = message.from_user.username
    
    # Проверяем, является ли отправитель администратором
    admin_ids = ["123456789"]  # Замените на реальные ID администраторов
    admin_usernames = ["wtfguys4"]  # Замените на реальные username администраторов
    
    is_admin = (user_id in admin_ids) or (username in admin_usernames)
    
    if not is_admin:
        await message.answer("❌ У вас нет прав для выполнения этой команды.", reply_markup=main_menu)
        return
    
    # Парсим команду: /remove_premium <user_id или @username>
    command_parts = message.text.split()
    if len(command_parts) != 2:
        await message.answer("❌ Неверный формат команды.\n\nИспользуйте:\n• /remove_premium <user_id>\n• /remove_premium @username", reply_markup=main_menu)
        return
    
    target = command_parts[1]
    
    # Определяем, это ID или username
    if target.startswith("@"):
        # Это username
        target_username = target[1:]  # Убираем @
        if remove_premium_user(username=target_username):
            await message.answer(f"✅ Пользователь @{target_username} успешно удален из премиум!", reply_markup=main_menu)
        else:
            await message.answer(f"❌ Ошибка при удалении пользователя @{target_username} из премиум.", reply_markup=main_menu)
    else:
        # Это ID
        if remove_premium_user(user_id=target):
            await message.answer(f"✅ Пользователь {target} успешно удален из премиум!", reply_markup=main_menu)
        else:
            await message.answer(f"❌ Ошибка при удалении пользователя {target} из премиум.", reply_markup=main_menu)

@dp.message(Command("check_premium"))
async def check_premium_command(message: types.Message):
    """Команда для проверки премиум статуса пользователя"""
    user_id = str(message.from_user.id)
    username = message.from_user.username
    
    if is_premium_user(user_id, username):
        await message.answer("💎 У вас есть премиум доступ!", reply_markup=main_menu)
    else:
        await message.answer("🔒 У вас нет премиум доступа.", reply_markup=main_menu)

@dp.message(Command("list_premium"))
async def list_premium_command(message: types.Message):
    """Команда для просмотра списка премиум пользователей (только для администраторов)"""
    user_id = str(message.from_user.id)
    username = message.from_user.username
    
    # Проверяем, является ли отправитель администратором
    admin_ids = ["123456789"]  # Замените на реальные ID администраторов
    admin_usernames = ["admin"]  # Замените на реальные username администраторов
    
    is_admin = (user_id in admin_ids) or (username in admin_usernames)
    
    if not is_admin:
        await message.answer("❌ У вас нет прав для выполнения этой команды.", reply_markup=main_menu)
        return
    
    try:
        premium_data = load_json(PREMIUM_USERS_FILE, {"premium_users": [], "premium_usernames": []})
        premium_users = premium_data.get("premium_users", [])
        premium_usernames = premium_data.get("premium_usernames", [])
        
        total_premium = len(premium_users) + len(premium_usernames)
        
        if total_premium > 0:
            message_text = f"💎 Список премиум пользователей ({total_premium}):\n\n"
            
            if premium_users:
                message_text += "🆔 **По ID:**\n"
                message_text += "\n".join([f"• {user_id}" for user_id in premium_users]) + "\n\n"
            
            if premium_usernames:
                message_text += "👤 **По username:**\n"
                message_text += "\n".join([f"• @{username}" for username in premium_usernames])
            
            await message.answer(message_text, reply_markup=main_menu)
        else:
            await message.answer("📭 Список премиум пользователей пуст.", reply_markup=main_menu)
    except Exception as e:
        await message.answer(f"❌ Ошибка при получении списка премиум пользователей: {e}", reply_markup=main_menu)

@dp.message(F.text == "🎭 По жанрам")
async def show_genres(message: types.Message):
    """Показывает список доступных жанров"""
    user_id = str(message.from_user.id)
    username = message.from_user.username
    
    if not is_premium_user(user_id, username):
        await message.answer("🔒 Доступ ограничен!\n\n💎 Функция «Поиск по жанрам» доступна только для премиум пользователей.", reply_markup=main_menu)
        return
    
    genres = get_genres()
    
    # Создаем inline клавиатуру с жанрами
    keyboard = []
    for genre_name in genres.keys():
        keyboard.append([InlineKeyboardButton(text=genre_name, callback_data=f"genre:{genre_name}")])
    
    # Добавляем кнопку "назад"
    keyboard.append([InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_premium")])
    
    kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await message.answer(
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

@dp.message(F.text == "👤 По исполнителям")
async def ask_artist_name(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    username = message.from_user.username
    
    if not is_premium_user(user_id, username):
        await message.answer("🔒 Доступ ограничен!\n\n💎 Функция «Поиск по исполнителям» доступна только для премиум пользователей.", reply_markup=main_menu)
        return
    
    await state.set_state(SearchStates.waiting_for_artist)
    # Создаем специальную клавиатуру для возврата в премиум меню
    premium_back_keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⬅ Назад в премиум")]],
        resize_keyboard=True
    )
    await message.answer("👤 Введите имя исполнителя или группы:", reply_markup=premium_back_keyboard)

@dp.message(SearchStates.waiting_for_artist, F.text == "⬅ Назад в премиум")
async def back_from_artist_search(message: types.Message, state: FSMContext):
    """Возврат из поиска по исполнителю в премиум меню"""
    await state.clear()
    await message.answer("🔙 Возврат в премиум меню", reply_markup=premium_menu)











# === Поиск ===
@dp.message(F.text == "▶️ Найти трек на YouTube")
async def ask_track_name(message: types.Message, state: FSMContext):
    await message.answer("Напиши название песни или вставь ссылку:", reply_markup=back_button)
    await state.set_state(SearchStates.waiting_for_search)

@dp.message(SearchStates.waiting_for_search, F.text == "⬅ Назад")
async def back_from_track_search(message: types.Message, state: FSMContext):
    """Возврат из поиска трека в главное меню"""
    await state.clear()
    await message.answer("🔙 Возврат в главное меню", reply_markup=main_menu)







@dp.message(SearchStates.waiting_for_search, F.text)
async def search_music(message: types.Message, state: FSMContext):
    query = message.text.strip()
    user_id = str(message.from_user.id)
    await state.clear()

    logging.info(f"🔍 Поиск музыки для пользователя {user_id}: '{query}'")



    yt_url_pattern = r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+"
    if re.match(yt_url_pattern, query):
        # асинхронно скачиваем в background (не блокируем основной цикл)
        asyncio.create_task(download_track_from_url(message.from_user.id, query))
        return await message.answer("✅ Запущена загрузка трека. Он появится в «Моя музыка» когда будет готов.", reply_markup=main_menu)

    cached = get_cached_search(query)
    if cached:
        return await send_search_results(message.chat.id, cached)

    await message.answer("🔍 Ищу треки...")
    try:
        # Выполняем блокирующий yt-dlp search в executor — добавил cookiefile здесь тоже
        def search_block(q):
            ydl_opts = {
                'format': 'bestaudio/best',
                'noplaylist': True,
                'quiet': True,
                'cookiefile': COOKIES_FILE
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(f"ytsearch5:{q}", download=False)
        info = await asyncio.to_thread(search_block, query)
        results = info.get("entries", [])
        if not results:
            return await message.answer("❌ Ничего не нашёл.")
        set_cached_search(query, results)
        await send_search_results(message.chat.id, results)
    except Exception as e:
        logging.exception("Ошибка поиска: %s", e)
        await message.answer(f"❌ Ошибка: {e}")

@dp.message(SearchStates.waiting_for_artist, F.text)
async def search_by_artist(message: types.Message, state: FSMContext):
    """Ищет и загружает треки по исполнителю"""
    artist_name = message.text.strip()
    user_id = str(message.from_user.id)
    await state.clear()

    logging.info(f"👤 Поиск по исполнителю для пользователя {user_id}: '{artist_name}'")



    # Отправляем сообщение о начале поиска
    search_msg = await message.answer(
        f"🔍 **Поиск треков исполнителя {artist_name}...**\n\n"
        "🎵 Ищу лучшие треки на YouTube...\n"
        "⏳ Это может занять несколько минут.",
        parse_mode="Markdown"
    )

    try:
        # Ищем треки исполнителя
        results = await asyncio.to_thread(search_artist_tracks, artist_name, 12)
        
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
                    [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_main")]
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
                        await message.answer_audio(
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
                            await message.answer_document(
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
            await search_msg.edit_text(
                message_text,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        except Exception as edit_error:
            logging.error(f"❌ Ошибка редактирования итогового сообщения: {edit_error}")
            # Пытаемся отправить новое сообщение
            try:
                await message.answer(
                    message_text,
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
    keyboard = [
        [InlineKeyboardButton(text=(video.get("title") or "Без названия")[:60], callback_data=f"dl:{video['id']}")]
        for video in results[:5]
    ]
    # Добавляем кнопку "назад" для возврата в главное меню
    keyboard.append([InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_main")])
    await bot.send_message(chat_id, "🎶 Выбери трек:", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

# === Callback: скачивание выбранного из поиска ===
@dp.callback_query(F.data.startswith("dl:"))
async def download_track(callback: types.CallbackQuery):
    video_id = callback.data.split(":")[1]
    url = f"https://www.youtube.com/watch?v={video_id}"
    await callback.message.edit_text("⏳ Скачиваю...")
    # запускаем асинхронную задачу и не блокируем
    task = asyncio.create_task(download_track_from_url(callback.from_user.id, url))
    # можно await task если нужно дождаться, но мы хотим фоновую загрузку
    
    # Создаем клавиатуру с кнопкой "назад"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_main")]
    ])
    
    await callback.message.edit_text(
        "✅ **Загрузка запущена**\n\n"
        "🎵 Трек скачивается в фоновом режиме.\n"
        "💾 Он появится в разделе «Моя музыка», когда загрузка завершится.",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

# === Вспомог: строим клавиатуру для страницы треков пользователя ===
def build_tracks_keyboard(tracks, page=0, owner_for_buttons=None):
    kb = []
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    for i, path in enumerate(tracks[start:end], start=start):
        title = os.path.basename(path)
        row = []
        if owner_for_buttons:
            row.append(InlineKeyboardButton(text=(title[:35] + '...') if len(title) > 38 else title,
                                            callback_data=f"play_shared:{owner_for_buttons}:{i}"))
        else:
            row.append(InlineKeyboardButton(text=(title[:35] + '...') if len(title) > 38 else title,
                                            callback_data=f"play:{i}"))
            row.append(InlineKeyboardButton(text="🗑", callback_data=f"del:{i}"))
        kb.append(row)
    nav = []
    if page > 0:
        if owner_for_buttons:
            nav.append(InlineKeyboardButton(text="◀ Пред", callback_data=f"shared_page:{owner_for_buttons}:{page-1}"))
        else:
            nav.append(InlineKeyboardButton(text="◀ Пред", callback_data=f"music_page:{page-1}"))
    if len(tracks) > end:
        if owner_for_buttons:
            nav.append(InlineKeyboardButton(text="След ▶", callback_data=f"shared_page:{owner_for_buttons}:{page+1}"))
        else:
            nav.append(InlineKeyboardButton(text="След ▶", callback_data=f"music_page:{page+1}"))
    if nav:
        kb.append(nav)
    if owner_for_buttons:
        kb.append([InlineKeyboardButton(text="📥 Скачать все", callback_data=f"download_all_shared:{owner_for_buttons}")])
    else:
        kb.append([InlineKeyboardButton(text="📥 Скачать все", callback_data="download_all")])
    
    # Добавляем кнопку "назад" для возврата в главное меню
    kb.append([InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_main")])
    
    return InlineKeyboardMarkup(inline_keyboard=kb)

# === Моя музыка (показ первой страницы) ===
@dp.message(F.text == "🎼 Моя музыка")
async def my_music(message: types.Message):
    user_id = str(message.from_user.id)
    tracks = user_tracks.get(user_id, [])
    if not tracks:
        return await message.answer("📂 У тебя нет треков.")
    kb = build_tracks_keyboard(tracks, page=0, owner_for_buttons=None)
    await message.answer("🎧 Твои треки (страница 1):", reply_markup=kb)

# === Callback: перелистывание страницы своей музыки ===
@dp.callback_query(F.data.startswith("music_page:"))
async def music_page_cb(callback: types.CallbackQuery):
    page = int(callback.data.split(":")[1])
    user_id = str(callback.from_user.id)
    tracks = user_tracks.get(user_id, [])
    if not tracks:
        return await callback.message.edit_text("📂 У тебя нет треков.")
    kb = build_tracks_keyboard(tracks, page=page, owner_for_buttons=None)
    await callback.message.edit_text(f"🎧 Твои треки (страница {page+1}):", reply_markup=kb)

# === Callback: play / play_shared ===
@dp.callback_query(F.data.startswith("play:"))
async def play_track(callback: types.CallbackQuery):
    idx = int(callback.data.split(":")[1])
    tracks = user_tracks.get(str(callback.from_user.id), [])
    if 0 <= idx < len(tracks) and os.path.exists(tracks[idx]):
        await callback.message.answer_audio(types.FSInputFile(tracks[idx]), title=os.path.basename(tracks[idx]))
    else:
        await callback.answer("Файл не найден.", show_alert=True)

@dp.callback_query(F.data.startswith("play_shared:"))
async def play_shared(callback: types.CallbackQuery):
    parts = callback.data.split(":")
    owner = parts[1]
    idx = int(parts[2])
    
    # Ищем активный плейлист для этого пользователя
    tracks = []
    for code, playlist_data in shared_playlists.items():
        if playlist_data.get("owner") == owner and time.time() - playlist_data.get("created_at", 0) <= SHARE_TTL:
            tracks = playlist_data.get("tracks", [])
            break
    
    if 0 <= idx < len(tracks) and os.path.exists(tracks[idx]):
        await callback.message.answer_audio(types.FSInputFile(tracks[idx]), title=os.path.basename(tracks[idx]))
    else:
        await callback.answer("Файл не найден.", show_alert=True)

# === Callback: перелистывание чужого плейлиста ===
@dp.callback_query(F.data.startswith("shared_page:"))
async def shared_page_cb(callback: types.CallbackQuery):
    _, owner, page = callback.data.split(":")
    page = int(page)
    
    # Ищем активный плейлист для этого пользователя
    tracks = []
    for code, playlist_data in shared_playlists.items():
        if playlist_data.get("owner") == owner and time.time() - playlist_data.get("created_at", 0) <= SHARE_TTL:
            tracks = playlist_data.get("tracks", [])
            break
    
    if not tracks:
        return await callback.message.edit_text("📂 Плейлист пуст или недоступен.")
    kb = build_tracks_keyboard(tracks, page=page, owner_for_buttons=owner)
    await callback.message.edit_text(f"🎧 Плейлист (страница {page+1}):", reply_markup=kb)

# === Callback: download all (self) ===
@dp.callback_query(F.data == "download_all")
async def download_all_tracks(callback: types.CallbackQuery):
    tracks = user_tracks.get(str(callback.from_user.id), [])
    if not tracks:
        return await callback.message.answer("📂 У тебя нет треков.")
    await callback.message.answer("📥 Отправляю все треки...")
    for path in tracks:
        if os.path.exists(path):
            try:
                await callback.message.answer_audio(types.FSInputFile(path), title=os.path.basename(path))
                await asyncio.sleep(0.4)
            except Exception as e:
                logging.exception("Ошибка отправки %s: %s", path, e)
    await callback.message.answer("✅ Все треки отправлены.")

# === Callback: download all shared ===
@dp.callback_query(F.data.startswith("download_all_shared:"))
async def download_all_shared(callback: types.CallbackQuery):
    owner = callback.data.split(":")[1]
    
    # Ищем активный плейлист для этого пользователя
    tracks = []
    for code, playlist_data in shared_playlists.items():
        if playlist_data.get("owner") == owner and time.time() - playlist_data.get("created_at", 0) <= SHARE_TTL:
            tracks = playlist_data.get("tracks", [])
            break
    
    if not tracks:
        return await callback.message.answer("📂 Плейлист пуст или недоступен.")
    await callback.message.answer("📥 Отправляю все треки из чужого плейлиста...")
    for path in tracks:
        if os.path.exists(path):
            try:
                await callback.message.answer_audio(types.FSInputFile(path), title=os.path.basename(path))
                await asyncio.sleep(0.4)
            except Exception as e:
                logging.exception("Ошибка отправки %s: %s", path, e)
    await callback.message.answer("✅ Все треки отправлены.")

# === Удаление трека ===
@dp.callback_query(F.data.startswith("del:"))
async def delete_track(callback: types.CallbackQuery):
    idx = int(callback.data.split(":")[1])
    user_id = str(callback.from_user.id)
    tracks = user_tracks.get(user_id, [])
    if not (0 <= idx < len(tracks)):
        return await callback.answer("Трек не найден.", show_alert=True)
    
    path = tracks[idx]
    if os.path.exists(path):
        try:
            os.remove(path)
            logging.info(f"Удален файл: {path}")
        except Exception as e:
            logging.error(f"Ошибка удаления файла {path}: {e}")
            return await callback.answer("❌ Ошибка удаления файла.", show_alert=True)
    
    tracks.pop(idx)
    # 🔧 ИСПРАВЛЕНИЕ: Сохраняем в фоне без блокировки
    asyncio.create_task(save_tracks_async())
    
    # Обновляем интерфейс
    if not tracks:
        await callback.message.edit_text("📂 У тебя нет треков.", reply_markup=main_menu)
    else:
        # Пересчитываем страницу
        current_page = 0
        for i in range(len(tracks) // PAGE_SIZE + 1):
            if i * PAGE_SIZE <= idx < (i + 1) * PAGE_SIZE:
                current_page = i
                break
        
        kb = build_tracks_keyboard(tracks, page=current_page, owner_for_buttons=None)
        await callback.message.edit_text(f"🎧 Твои треки (страница {current_page+1}):", reply_markup=kb)
    
    await callback.answer("✅ Трек удален.")

# === Поделиться плейлистом ===
@dp.message(F.text == "📤 Поделиться плейлистом")
async def share_playlist(message: types.Message):
    user_id = str(message.from_user.id)
    username = message.from_user.username
    
    if not is_premium_user(user_id, username):
        await message.answer("🔒 Доступ ограничен!\n\n💎 Функция «Поделиться плейлистом» доступна только для премиум пользователей.", reply_markup=main_menu)
        return
    
    user_tracks_list = user_tracks.get(user_id, [])
    
    if not user_tracks_list:
        await message.answer("📂 У тебя нет треков для создания плейлиста.", reply_markup=premium_menu)
        return
    
    # Проверяем, что треки существуют
    existing_tracks = [track for track in user_tracks_list if os.path.exists(track)]
    if len(existing_tracks) != len(user_tracks_list):
        logging.warning(f"⚠️ Некоторые треки пользователя {user_id} не найдены: {len(user_tracks_list) - len(existing_tracks)} из {len(user_tracks_list)}")
        user_tracks_list = existing_tracks
    
    if not user_tracks_list:
        await message.answer("📂 Все твои треки недоступны для создания плейлиста.", reply_markup=premium_menu)
        return
    
    # Генерируем уникальный код для плейлиста
    share_code = secrets.token_urlsafe(8)
    
    # Сохраняем плейлист
    shared_playlists[share_code] = {
        "owner": user_id,
        "tracks": user_tracks_list,
        "created_at": time.time()
    }
    # 🔧 ИСПРАВЛЕНИЕ: Сохраняем в фоне без блокировки
    asyncio.create_task(save_shared_async())
    
    logging.info(f"📤 Пользователь {user_id} создал плейлист с кодом {share_code}, треков: {len(user_tracks_list)}")
    
    await message.answer(
        f"📤 Твой плейлист готов!\n\n"
        f"🔑 Код для доступа: `{share_code}`\n"
        f"📊 Количество треков: {len(user_tracks_list)}\n"
        f"⏰ Действует 24 часа\n\n"
        f"💡 Отправь этот код друзьям, чтобы они могли открыть твой плейлист!",
        parse_mode="Markdown",
        reply_markup=premium_menu
    )

# === Открыть плейлист ===
@dp.message(F.text == "📥 Открыть плейлист")
async def open_playlist_start(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    username = message.from_user.username
    
    if not is_premium_user(user_id, username):
        await message.answer("🔒 Доступ ограничен!\n\n💎 Функция «Открыть плейлист» доступна только для премиум пользователей.", reply_markup=main_menu)
        return
    
    await state.set_state(ShareStates.waiting_for_code)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_premium")]
    ])
    await message.answer("🔑 Введите код плейлиста:", reply_markup=keyboard)

@dp.message(ShareStates.waiting_for_code, F.text == "⬅ Назад")
async def back_from_playlist_open(message: types.Message, state: FSMContext):
    """Возврат из открытия плейлиста в премиум меню"""
    await state.clear()
    await message.answer("🔙 Возврат в премиум меню", reply_markup=premium_menu)

@dp.message(ShareStates.waiting_for_code, F.text)
async def open_playlist_code(message: types.Message, state: FSMContext):
    code = message.text.strip()
    await state.clear()

    logging.info(f"🔍 Попытка открыть плейлист с кодом: {code}")
    
    playlist_data = shared_playlists.get(code)
    if not playlist_data:
        await message.answer("❌ Код недействителен.", reply_markup=premium_menu)
        return
        
    if time.time() - playlist_data.get("created_at", 0) > SHARE_TTL:
        await message.answer("❌ Код устарел (действует только 24 часа).", reply_markup=premium_menu)
        return

    owner_id = playlist_data.get("owner")
    tracks_list = playlist_data.get("tracks", [])
    
    logging.info(f"📂 Открываем плейлист пользователя {owner_id}, треков: {len(tracks_list)}")
    
    if not tracks_list:
        await message.answer("📂 Плейлист пуст.", reply_markup=premium_menu)
        return

    # Проверяем, что треки существуют
    existing_tracks = [track for track in tracks_list if os.path.exists(track)]
    if len(existing_tracks) != len(tracks_list):
        logging.warning(f"⚠️ Некоторые треки не найдены: {len(tracks_list) - len(existing_tracks)} из {len(tracks_list)}")
        tracks_list = existing_tracks
    
    if not tracks_list:
        await message.answer("📂 Все треки в плейлисте недоступны.", reply_markup=premium_menu)
        return

    kb = build_tracks_keyboard(tracks_list, page=0, owner_for_buttons=owner_id)
    await message.answer(f"🎧 Плейлист пользователя ({len(tracks_list)} треков):", reply_markup=kb)

# === Отменить доступ ===
@dp.message(F.text == "🚫 Отменить доступ")
async def cancel_access(message: types.Message):
    user_id = str(message.from_user.id)
    username = message.from_user.username
    
    if not is_premium_user(user_id, username):
        await message.answer("🔒 Доступ ограничен!\n\n💎 Функция «Отменить доступ» доступна только для премиум пользователей.", reply_markup=main_menu)
        return
    
    # Находим и удаляем все плейлисты пользователя
    codes_to_remove = []
    for code, playlist_data in shared_playlists.items():
        if playlist_data.get("owner") == user_id:
            codes_to_remove.append(code)
    
    if codes_to_remove:
        for code in codes_to_remove:
            del shared_playlists[code]
        # 🔧 ИСПРАВЛЕНИЕ: Сохраняем в фоне без блокировки
        asyncio.create_task(save_shared_async())
        
        await message.answer(
            f"✅ Доступ отменен!\n\n"
            f"🚫 Удалено плейлистов: {len(codes_to_remove)}\n"
            f"🔒 Твои плейлисты больше недоступны для других пользователей.",
            reply_markup=premium_menu
        )
    else:
        await message.answer(
            "📭 У тебя нет активных плейлистов для отмены доступа.",
            reply_markup=premium_menu
        )

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
    """Возвращает список доступных жанров с поисковыми запросами конкретных исполнителей"""
    return {
        "🎵 Поп": [
            "Ed Sheeran - Shape of You",
            "Taylor Swift - Shake It Off",
            "Bruno Mars - Uptown Funk",
            "Adele - Hello",
            "Justin Bieber - Sorry",
            "Katy Perry - Roar",
            "Maroon 5 - Sugar",
            "OneRepublic - Counting Stars",
            "Imagine Dragons - Radioactive",
            "Sam Smith - Stay With Me",
            "Ariana Grande - Thank U Next",
            "Post Malone - Circles",
            "Dua Lipa - Don't Start Now",
            "The Weeknd - Blinding Lights",
            "Lady Gaga - Shallow",
            "Billie Eilish - Bad Guy",
            "Shawn Mendes - Señorita",
            "Camila Cabello - Havana",
            "Halsey - Without Me",
            "Lorde - Royals",
            "Sia - Chandelier",
            "P!nk - Just Give Me A Reason",
            "Kesha - Tik Tok",
            "Rihanna - Diamonds",
            "Beyoncé - Halo",
            "Christina Aguilera - Beautiful",
            "Britney Spears - Toxic",
            "Madonna - Like A Prayer",
            "Cyndi Lauper - Girls Just Want To Have Fun",
            "Whitney Houston - I Will Always Love You",
            "Celine Dion - My Heart Will Go On"
        ],
        "🎸 Рок": [
            "Queen - Bohemian Rhapsody",
            "Led Zeppelin - Stairway to Heaven",
            "Pink Floyd - Another Brick in the Wall",
            "The Beatles - Hey Jude",
            "Guns N Roses - Sweet Child O Mine",
            "AC/DC - Back In Black",
            "Metallica - Nothing Else Matters",
            "Nirvana - Smells Like Teen Spirit",
            "The Rolling Stones - Paint It Black",
            "Eagles - Hotel California",
            "U2 - With Or Without You",
            "Coldplay - Yellow",
            "Radiohead - Creep",
            "Oasis - Wonderwall",
            "The Killers - Mr. Brightside",
            "Arctic Monkeys - Do I Wanna Know",
            "Foo Fighters - Everlong",
            "Red Hot Chili Peppers - Californication",
            "Green Day - American Idiot",
            "Linkin Park - In The End",
            "System of a Down - Chop Suey",
            "Slipknot - Duality",
            "Tool - Schism",
            "Rage Against The Machine - Killing In The Name",
            "Pearl Jam - Alive",
            "Soundgarden - Black Hole Sun",
            "Alice In Chains - Man In The Box",
            "Stone Temple Pilots - Plush",
            "Smashing Pumpkins - Today",
            "The Cranberries - Zombie"
        ],
        "🎤 Хип-хоп": [
            "Eminem - Lose Yourself",
            "50 Cent - In Da Club",
            "Drake - God's Plan",
            "Kendrick Lamar - HUMBLE",
            "J. Cole - No Role Modelz",
            "Travis Scott - SICKO MODE",
            "Post Malone - Rockstar",
            "Cardi B - Bodak Yellow",
            "Nicki Minaj - Super Bass",
            "Lil Wayne - Lollipop",
            "Kanye West - Stronger",
            "Jay-Z - Empire State of Mind",
            "Nas - N.Y. State of Mind",
            "Tupac - Changes",
            "Notorious B.I.G. - Juicy",
            "Snoop Dogg - Gin and Juice",
            "Dr. Dre - Still D.R.E.",
            "Ice Cube - It Was A Good Day",
            "Public Enemy - Fight The Power",
            "Run DMC - Walk This Way",
            "Beastie Boys - Sabotage",
            "OutKast - Hey Ya",
            "A Tribe Called Quest - Can I Kick It",
            "De La Soul - Me Myself and I",
            "Wu-Tang Clan - C.R.E.A.M.",
            "Mobb Deep - Shook Ones",
            "Gang Starr - Moment of Truth",
            "Black Star - Definition",
            "Mos Def - Mathematics",
            "Talib Kweli - Get By"
        ],
        "🎹 Электроника": [
            "The Weeknd - Blinding Lights",
            "Calvin Harris - This Is What You Came For",
            "David Guetta - Titanium",
            "Skrillex - Bangarang",
            "Avicii - Wake Me Up",
            "Marshmello - Alone",
            "Zedd - Clarity",
            "Martin Garrix - Animals",
            "Kygo - Firestone",
            "Disclosure - Latch",
            "Daft Punk - Get Lucky",
            "The Chainsmokers - Closer",
            "Major Lazer - Lean On",
            "DJ Snake - Turn Down For What",
            "Flume - Never Be Like You",
            "Odesza - Say My Name",
            "Porter Robinson - Language",
            "Madeon - Pop Culture",
            "Kaskade - Eyes",
            "Tiesto - Red Lights",
            "Armin van Buuren - This Is What It Feels Like",
            "Above & Beyond - Sun & Moon",
            "Eric Prydz - Call On Me",
            "Swedish House Mafia - Don't You Worry Child",
            "Alesso - Heroes",
            "Sebastian Ingrosso - Reload",
            "Axwell - Center of the Universe",
            "Steve Angello - Payback",
            "Laidback Luke - Turbulence",
            "Hardwell - Spaceman"
        ],
        "🎷 Джаз": [
            "Louis Armstrong - What A Wonderful World",
            "Ella Fitzgerald - Summertime",
            "Miles Davis - So What",
            "John Coltrane - Giant Steps",
            "Duke Ellington - Take The A Train",
            "Billie Holiday - Strange Fruit",
            "Thelonious Monk - Round Midnight",
            "Chet Baker - My Funny Valentine",
            "Wes Montgomery - Four On Six",
            "Cannonball Adderley - Mercy Mercy Mercy",
            "Dave Brubeck - Take Five",
            "Herbie Hancock - Watermelon Man",
            "Wayne Shorter - Footprints",
            "Art Blakey - Moanin",
            "Horace Silver - Song for My Father",
            "Hank Mobley - Soul Station",
            "Lee Morgan - The Sidewinder",
            "Freddie Hubbard - Red Clay",
            "Woody Shaw - Rosewood",
            "Joe Henderson - Recorda Me",
            "Stan Getz - The Girl from Ipanema",
            "Gerry Mulligan - My Funny Valentine",
            "Paul Desmond - Take Five",
            "Cannonball Adderley - Work Song",
            "Nat King Cole - Nature Boy",
            "Frank Sinatra - Fly Me To The Moon",
            "Tony Bennett - I Left My Heart In San Francisco",
            "Sarah Vaughan - Misty",
            "Nina Simone - Feeling Good",
            "Diana Krall - The Look of Love"
        ],
        "🎻 Классика": [
            "Beethoven - Symphony No. 5",
            "Mozart - Symphony No. 40",
            "Bach - Brandenburg Concerto No. 3",
            "Tchaikovsky - Swan Lake",
            "Vivaldi - Four Seasons",
            "Chopin - Nocturne Op. 9 No. 2",
            "Debussy - Clair de Lune",
            "Rachmaninoff - Piano Concerto No. 2",
            "Liszt - Hungarian Rhapsody No. 2",
            "Schubert - Ave Maria",
            "Handel - Messiah Hallelujah",
            "Haydn - Symphony No. 94 Surprise",
            "Brahms - Symphony No. 1",
            "Mahler - Symphony No. 5",
            "Shostakovich - Symphony No. 5",
            "Prokofiev - Romeo and Juliet",
            "Stravinsky - The Rite of Spring",
            "Ravel - Bolero",
            "Grieg - Peer Gynt Suite",
            "Dvorak - Symphony No. 9 From the New World",
            "Sibelius - Finlandia",
            "Elgar - Pomp and Circumstance",
            "Holst - The Planets",
            "Vaughan Williams - The Lark Ascending",
            "Delius - On Hearing the First Cuckoo in Spring",
            "Butterworth - The Banks of Green Willow",
            "Britten - The Young Person's Guide to the Orchestra",
            "Walton - Crown Imperial",
            "Tippett - Fantasia Concertante",
            "Maxwell Davies - An Orkney Wedding"
        ],
        "🎺 Блюз": [
            "B.B. King - The Thrill Is Gone",
            "Eric Clapton - Layla",
            "Jimi Hendrix - Red House",
            "Stevie Ray Vaughan - Pride and Joy",
            "Muddy Waters - Hoochie Coochie Man",
            "Howlin Wolf - Smokestack Lightning",
            "John Lee Hooker - Boom Boom",
            "Albert King - Born Under A Bad Sign",
            "Freddie King - Hide Away",
            "Buddy Guy - Damn Right I Got The Blues",
            "Robert Johnson - Cross Road Blues",
            "Son House - Death Letter",
            "Skip James - Devil Got My Woman",
            "Charley Patton - Pony Blues",
            "Blind Lemon Jefferson - Black Snake Moan",
            "Lead Belly - Goodnight Irene",
            "Big Bill Broonzy - Key to the Highway",
            "Tampa Red - It's Tight Like That",
            "Leroy Carr - How Long Blues",
            "Lonnie Johnson - Tomorrow Night",
            "Blind Blake - Diddie Wa Diddie",
            "Blind Boy Fuller - Step It Up and Go",
            "Josh White - One Meat Ball",
            "Brownie McGhee - Key to the Highway",
            "Sonny Terry - Harmonica Blues",
            "Lightnin Hopkins - Mojo Hand",
            "Johnny Shines - Dynaflow Blues",
            "Homesick James - Set Down Gal",
            "Eddie Taylor - Bad Boy",
            "Jimmy Reed - Big Boss Man"
        ],
        "🎼 Кантри": [
            "Johnny Cash - Ring of Fire",
            "Dolly Parton - Jolene",
            "Willie Nelson - On The Road Again",
            "George Strait - Amarillo By Morning",
            "Garth Brooks - Friends In Low Places",
            "Shania Twain - Man! I Feel Like A Woman",
            "Kenny Rogers - The Gambler",
            "Loretta Lynn - Coal Miner's Daughter",
            "Merle Haggard - Mama Tried",
            "Hank Williams - I'm So Lonesome I Could Cry",
            "Patsy Cline - Crazy",
            "Tammy Wynette - Stand By Your Man",
            "Waylon Jennings - Luckenbach Texas",
            "Kris Kristofferson - Me and Bobby McGee",
            "Roger Miller - King of the Road",
            "Buck Owens - Act Naturally",
            "Don Williams - I Believe in You",
            "Alan Jackson - Chattahoochee",
            "Toby Keith - Should've Been a Cowboy",
            "Tim McGraw - Indian Outlaw",
            "Brooks & Dunn - Boot Scootin' Boogie",
            "Alabama - Mountain Music",
            "The Oak Ridge Boys - Elvira",
            "Statler Brothers - Flowers on the Wall",
            "Charlie Daniels Band - The Devil Went Down to Georgia",
            "Marshall Tucker Band - Can't You See",
            "Lynyrd Skynyrd - Sweet Home Alabama",
            "Allman Brothers Band - Ramblin' Man",
            "Eagles - Take It Easy",
            "Linda Ronstadt - Blue Bayou"
        ],
        "🎭 Рэгги": [
            "Bob Marley - No Woman No Cry",
            "Bob Marley - Three Little Birds",
            "Bob Marley - Redemption Song",
            "Peter Tosh - Legalize It",
            "Jimmy Cliff - The Harder They Come",
            "Toots and the Maytals - Pressure Drop",
            "Burning Spear - Marcus Garvey",
            "Culture - Two Sevens Clash",
            "Steel Pulse - Handsworth Revolution",
            "Black Uhuru - Shine Eye Gal",
            "Gregory Isaacs - Night Nurse",
            "Dennis Brown - Money in My Pocket",
            "John Holt - The Tide Is High",
            "Alton Ellis - I'm Still in Love With You",
            "Ken Boothe - Everything I Own",
            "Delroy Wilson - I'm Still in Love With You",
            "The Paragons - The Tide Is High",
            "The Melodians - Rivers of Babylon",
            "The Abyssinians - Satta Massagana",
            "The Congos - Fisherman",
            "The Heptones - Book of Rules",
            "The Mighty Diamonds - Pass the Kouchie",
            "The Wailers - Simmer Down",
            "The Skatalites - Guns of Navarone",
            "Desmond Dekker - Israelites",
            "Prince Buster - Al Capone",
            "Derrick Morgan - Forward March",
            "Laurel Aitken - Boogie in My Bones",
            "Owen Gray - Please Let Me Go",
            "The Pioneers - Long Shot Kick De Bucket"
        ],
        "🎪 Фолк": [
            "Bob Dylan - Like A Rolling Stone",
            "Joan Baez - Diamonds and Rust",
            "Simon and Garfunkel - The Sound of Silence",
            "Joni Mitchell - Big Yellow Taxi",
            "Woody Guthrie - This Land Is Your Land",
            "Pete Seeger - Turn Turn Turn",
            "The Byrds - Mr. Tambourine Man",
            "Crosby Stills Nash and Young - Suite: Judy Blue Eyes",
            "Donovan - Catch The Wind",
            "Fairport Convention - Matty Groves",
            "Pentangle - Light Flight",
            "Steeleye Span - All Around My Hat",
            "The Incredible String Band - Air",
            "Bert Jansch - Needle of Death",
            "John Renbourn - The Hermit",
            "Davey Graham - Anji",
            "Martin Carthy - Scarborough Fair",
            "Shirley Collins - A Bunch of Thyme",
            "Anne Briggs - Blackwater Side",
            "June Tabor - The Grey Funnel Line",
            "Richard Thompson - 1952 Vincent Black Lightning",
            "Sandy Denny - Who Knows Where the Time Goes",
            "Nick Drake - Pink Moon",
            "John Martyn - May You Never",
            "Roy Harper - When an Old Cricketer Leaves the Crease",
            "Ralph McTell - Streets of London",
            "Al Stewart - Year of the Cat",
            "Cat Stevens - Wild World",
            "James Taylor - Fire and Rain"
        ],
        "🎨 Альтернатива": [
            "Radiohead - Creep",
            "Arctic Monkeys - Do I Wanna Know",
            "The Strokes - Last Nite",
            "Vampire Weekend - A-Punk",
            "Tame Impala - The Less I Know The Better",
            "The Killers - Mr. Brightside",
            "Arcade Fire - Wake Up",
            "Modest Mouse - Float On",
            "Death Cab for Cutie - I Will Follow You Into The Dark",
            "The National - Bloodbuzz Ohio",
            "Interpol - Obstacle 1",
            "The White Stripes - Seven Nation Army",
            "The Black Keys - Lonely Boy",
            "Cage The Elephant - Ain't No Rest for the Wicked",
            "Portugal. The Man - Feel It Still",
            "Twenty One Pilots - Stressed Out",
            "Panic! At The Disco - I Write Sins Not Tragedies",
            "Fall Out Boy - Sugar We're Goin Down",
            "My Chemical Romance - Welcome to the Black Parade",
            "Paramore - Misery Business",
            "The 1975 - Chocolate",
            "Bastille - Pompeii",
            "Imagine Dragons - Radioactive",
            "Of Monsters and Men - Little Talks",
            "Mumford & Sons - I Will Wait",
            "The Lumineers - Ho Hey",
            "Edward Sharpe & The Magnetic Zeros - Home",
            "Fleet Foxes - White Winter Hymnal",
            "Bon Iver - Skinny Love",
            "The xx - Intro"
        ],
        "🎬 Саундтреки": [
            "Hans Zimmer - Time (Inception)",
            "John Williams - Star Wars Theme",
            "Ennio Morricone - The Good The Bad and The Ugly",
            "Danny Elfman - Batman Theme",
            "Howard Shore - The Lord of the Rings Theme",
            "James Horner - Titanic Theme",
            "Vangelis - Chariots of Fire",
            "Nino Rota - The Godfather Theme",
            "Bernard Herrmann - Psycho Theme",
            "Jerry Goldsmith - Star Trek Theme",
            "John Barry - James Bond Theme",
            "Maurice Jarre - Lawrence of Arabia Theme",
            "Alex North - 2001 A Space Odyssey Theme",
            "Elmer Bernstein - The Magnificent Seven",
            "Dimitri Tiomkin - High Noon Theme",
            "Max Steiner - Gone With The Wind Theme",
            "Erich Wolfgang Korngold - The Adventures of Robin Hood",
            "Franz Waxman - Sunset Boulevard",
            "Alfred Newman - How The West Was Won",
            "Miklós Rózsa - Ben-Hur Theme",
            "Bronisław Kaper - Mutiny on the Bounty",
            "Dimitri Shostakovich - The Gadfly Suite",
            "Sergei Prokofiev - Alexander Nevsky",
            "Igor Stravinsky - The Firebird Suite",
            "Claude Debussy - Clair de Lune",
            "Frédéric Chopin - Nocturne in C minor",
            "Ludwig van Beethoven - Moonlight Sonata",
            "Wolfgang Amadeus Mozart - Eine kleine Nachtmusik",
            "Johann Sebastian Bach - Air on the G String"
        ]
    }

def search_genre_tracks(genre_queries, limit=10):
    """Ищет треки по жанру используя случайные поисковые запросы для разнообразия"""
    all_results = []
    
    try:
        # Перемешиваем запросы для случайности
        shuffled_queries = list(genre_queries)
        random.shuffle(shuffled_queries)
        
        # Берем случайное подмножество запросов для разнообразия
        # Если запросов больше 15, берем случайные 15-20
        if len(shuffled_queries) > 15:
            num_queries = random.randint(15, min(20, len(shuffled_queries)))
            selected_queries = random.sample(shuffled_queries, num_queries)
        else:
            selected_queries = shuffled_queries
        
        logging.info(f"🎲 Выбрано {len(selected_queries)} случайных запросов из {len(genre_queries)} доступных")
        
        for query in selected_queries:
            try:
                # Выполняем поиск для каждого конкретного трека
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'noplaylist': True,
                    'quiet': True,
                    'cookiefile': COOKIES_FILE if os.path.exists(COOKIES_FILE) else None,
                    'extract_flat': True,  # Добавляем для более быстрого поиска
                    'no_warnings': True,
                    'ignoreerrors': True  # Игнорируем ошибки для отдельных запросов
                }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    try:
                        # Ищем конкретный трек (1 результат на запрос)
                        search_query = f"ytsearch1:{query}"
                        info = ydl.extract_info(search_query, download=False)
                        
                        if not info:
                            logging.warning(f"⚠️ Пустой результат поиска для '{query}'")
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
                                
                                # Проверяем, что это не сборник, не нарезка и не слишком короткий трек
                                if (duration and duration > 60 and  # Трек должен быть длиннее 1 минуты
                                    duration < 600 and  # И не слишком длинный (не более 10 минут)
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
                                    video_id):  # Убеждаемся, что есть ID видео
                                    
                                    valid_results.append(result)
                            
                            # Добавляем случайное количество результатов (1-3) для разнообразия
                            if valid_results:
                                num_to_add = random.randint(1, min(3, len(valid_results)))
                                selected_results = random.sample(valid_results, num_to_add)
                                all_results.extend(selected_results)
                                logging.info(f"✅ Добавлено {num_to_add} треков из запроса '{query}'")
                        else:
                            logging.warning(f"⚠️ Нет результатов для запроса '{query}'")
                            
                    except Exception as search_error:
                        logging.error(f"❌ Ошибка поиска для запроса '{query}': {search_error}")
                        continue
                        
            except Exception as e:
                logging.error(f"❌ Ошибка создания yt-dlp для запроса '{query}': {e}")
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

def search_artist_tracks(artist_name, limit=15):
    """Ищет треки конкретного исполнителя на YouTube"""
    try:
        logging.info(f"👤 Поиск треков исполнителя: {artist_name}")
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'quiet': True,
            'cookiefile': COOKIES_FILE if os.path.exists(COOKIES_FILE) else None,
            'extract_flat': True,
            'no_warnings': True,
            'ignoreerrors': True
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Ищем треки исполнителя (больше результатов для разнообразия)
            search_query = f"ytsearch{limit + 5}:{artist_name} music"
            info = ydl.extract_info(search_query, download=False)
            
            if not info:
                logging.warning(f"⚠️ Пустой результат поиска для исполнителя '{artist_name}'")
                return []
                
            results = info.get("entries", [])
            
            if not results:
                logging.warning(f"⚠️ Нет результатов для исполнителя '{artist_name}'")
                return []
            
            # Фильтруем результаты
            valid_results = []
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
                    
                    valid_results.append(result)
            
            # Убираем дубликаты по ID
            unique_results = []
            seen_ids = set()
            
            for result in valid_results:
                if result and result.get('id') and result['id'] not in seen_ids:
                    unique_results.append(result)
                    seen_ids.add(result['id'])
            
            logging.info(f"✅ Найдено {len(unique_results)} уникальных треков исполнителя {artist_name}")
            
            # Перемешиваем результаты для разнообразия
            random.shuffle(unique_results)
            
            # Возвращаем нужное количество треков
            return unique_results[:limit]
            
    except Exception as e:
        logging.error(f"❌ Ошибка поиска треков исполнителя {artist_name}: {e}")
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
        
        # Добавляем случайность в количество искомых треков (8-12 вместо фиксированных 10)
        random_limit = random.randint(8, 12)
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
                        f"⏳ **Загружаю трек {i}/{len(results)} по жанру {genre_name}...**\n\n"
                        f"🎵 **{track.get('title', 'Без названия')}**\n"
                        "💾 Скачиваю аудиофайл...",
                        parse_mode="Markdown"
                    )
                except Exception as edit_error:
                    logging.error(f"❌ Ошибка обновления прогресса: {edit_error}")
                
                # Скачиваем трек с таймаутом
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
            message_text += "• Недоступны на YouTube\n"
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
    
    # Создаем inline клавиатуру с жанрами
    keyboard = []
    for genre_name in genres.keys():
        keyboard.append([InlineKeyboardButton(text=genre_name, callback_data=f"genre:{genre_name}")])
    
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
        # Отправляем новое сообщение с главным меню
        await callback.message.answer(
            "🔙 Главное меню\n\n"
            "🎵 Выберите действие:",
            reply_markup=main_menu
        )
        
        # Удаляем предыдущее inline-сообщение
        await callback.message.delete()
    except Exception as e:
        logging.error(f"❌ Ошибка в back_to_main_menu: {e}")
        # Если что-то пошло не так, просто отправляем главное меню
        await callback.message.answer("🎵 Главное меню", reply_markup=main_menu)

@dp.callback_query(F.data == "search_artist_again")
async def search_artist_again_callback(callback: types.CallbackQuery, state: FSMContext):
    """Повторный поиск по исполнителю"""
    user_id = str(callback.from_user.id)
    username = callback.from_user.username
    
    # Проверяем премиум статус
    if not is_premium_user(user_id, username):
        await callback.answer("🔒 Доступ ограничен! Требуется премиум подписка.", show_alert=True)
        return
    
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
    
    # Проверяем премиум статус
    if not is_premium_user(user_id, username):
        await callback.answer("🔒 Доступ ограничен! Требуется премиум подписка.", show_alert=True)
        return
    
    logging.info(f"🔄 Повторная попытка поиска по исполнителю для пользователя {user_id}: '{artist_name}'")
    
    # Отправляем сообщение о начале повторного поиска
    search_msg = await callback.message.edit_text(
        f"🔄 **Повторный поиск треков исполнителя {artist_name}...**\n\n"
        "🎵 Ищу лучшие треки на YouTube...\n"
        "⏳ Это может занять несколько минут.",
        parse_mode="Markdown"
    )
    
    try:
        # Ищем треки исполнителя
        results = await asyncio.to_thread(search_artist_tracks, artist_name, 12)
        
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
    # 🔧 ИСПРАВЛЕНИЕ: Запускаем фоновую очистку MP3 файлов для устранения лагов
    asyncio.create_task(periodic_mp3_cleanup())
    logging.info("🧹 Запущена фоновая очистка MP3 файлов раз в 10 минут")
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())