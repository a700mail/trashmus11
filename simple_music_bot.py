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
API_TOKEN = os.getenv("BOT_TOKEN")
if not API_TOKEN:
    raise RuntimeError("Переменная окружения BOT_TOKEN не установлена")

MAX_FILE_SIZE_MB = 50
CACHE_DIR = "cache"
COOKIES_FILE = os.path.join(os.path.dirname(__file__), "cookies.txt")
TRACKS_FILE = os.path.join(os.path.dirname(__file__), "tracks.json")
SEARCH_CACHE_FILE = os.path.join(os.path.dirname(__file__), "search_cache.json")

# === НАСТРОЙКИ АВТОМАТИЧЕСКОЙ ОЧИСТКИ ===
AUTO_CLEANUP_ENABLED = True
AUTO_CLEANUP_DELAY = 1.0
CLEANUP_LOGGING = True

# === НАСТРОЙКИ ПОИСКА ===
SEARCH_CACHE_TTL = 600
PAGE_SIZE = 10

# === НАСТРОЙКИ ПАРАЛЛЕЛЬНЫХ ЗАГРУЗОК ===
MAX_CONCURRENT_DOWNLOADS = 5
MAX_CONCURRENT_DOWNLOADS_PER_USER = 2
ACTIVE_DOWNLOADS = 0
user_download_semaphores = {}

# === ГЛОБАЛЬНЫЕ ОБЪЕКТЫ ДЛЯ ЗАГРУЗОК ===
yt_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="yt_downloader")
download_semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)

# === ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ===
user_tracks = {}
user_recommendation_history = {}

# === НАСТРОЙКИ АНТИСПАМА ===
ANTISPAM_DELAY = 1.0
user_last_request = {}

# === НАСТРОЙКИ RENDER ===
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
WEBHOOK_PATH = f"/bot/{API_TOKEN}"
WEBAPP_HOST = "0.0.0.0"
WEBAPP_PORT = int(os.getenv("PORT", 8000))

# Настройка логирования
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

# === СОСТОЯНИЯ FSM ===
class SearchStates(StatesGroup):
    waiting_for_search = State()
    waiting_for_artist = State()
    waiting_for_artist_search = State()

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

def save_json(path, data):
    """Сохраняет данные в JSON файл"""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logging.error(f"❌ Ошибка сохранения {path}: {e}")
        return False

def format_duration(seconds):
    """Форматирует длительность в секундах в читаемый вид (MM:SS или HH:MM:SS)"""
    try:
        if not seconds or not isinstance(seconds, (int, float)) or seconds <= 0:
            return ""
        
        seconds = int(float(seconds))
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes}:{secs:02d}"
            
    except (ValueError, TypeError, OverflowError):
        return ""

def check_antispam(user_id: str) -> tuple[bool, float]:
    """Проверяет антиспам для пользователя"""
    try:
        current_time = time.time()
        last_request_time = user_last_request.get(str(user_id), 0)
        
        if current_time - last_request_time >= ANTISPAM_DELAY:
            user_last_request[str(user_id)] = current_time
            return True, 0.0
        
        time_until_next = ANTISPAM_DELAY - (current_time - last_request_time)
        return False, time_until_next
        
    except Exception as e:
        logging.error(f"❌ Ошибка проверки антиспама для пользователя {user_id}: {e}")
        return True, 0.0

def get_user_download_semaphore(user_id: str) -> asyncio.Semaphore:
    """Получает или создает семафор для конкретного пользователя"""
    if user_id not in user_download_semaphores:
        user_download_semaphores[user_id] = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS_PER_USER)
    return user_download_semaphores[user_id]

# === ФУНКЦИИ ДЛЯ РАБОТЫ С ТРЕКАМИ ===
async def download_track_to_temp(user_id: str, url: str, title: str) -> str:
    """Скачивает трек во временную папку"""
    try:
        # Создаем уникальное имя файла
        safe_title = re.sub(r'[^\w\s-]', '', title).strip()
        safe_title = re.sub(r'[-\s]+', '-', safe_title)
        timestamp = int(time.time())
        random_suffix = secrets.token_hex(4)
        filename = f"{safe_title}_{timestamp}_{random_suffix}.mp3"
        file_path = os.path.join(CACHE_DIR, filename)
        
        # Настройки yt-dlp
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': file_path.replace('.mp3', ''),
            'quiet': True,
            'no_warnings': True,
            'extractaudio': True,
            'audioformat': 'mp3',
            'audioquality': '192K',
        }
        
        # Скачиваем трек
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        # Проверяем, что файл создался
        if os.path.exists(file_path):
            logging.info(f"✅ Трек скачан: {file_path}")
            return file_path
        else:
            # Ищем файл с другим расширением
            for ext in ['.mp3', '.m4a', '.webm']:
                alt_path = file_path.replace('.mp3', ext)
                if os.path.exists(alt_path):
                    # Переименовываем в .mp3
                    os.rename(alt_path, file_path)
                    logging.info(f"✅ Трек переименован и готов: {file_path}")
                    return file_path
            
            logging.error(f"❌ Файл не найден после скачивания: {url}")
            return None
            
    except Exception as e:
        logging.error(f"❌ Ошибка скачивания трека {url}: {e}")
        return None

async def delete_temp_file(file_path: str):
    """Удаляет временный файл с задержкой"""
    try:
        if file_path and os.path.exists(file_path):
            await asyncio.sleep(AUTO_CLEANUP_DELAY)
            os.remove(file_path)
            if CLEANUP_LOGGING:
                logging.info(f"🧹 Удален временный файл: {file_path}")
    except Exception as e:
        logging.error(f"❌ Ошибка удаления файла {file_path}: {e}")

# === ФУНКЦИИ ПОИСКА ===
async def search_youtube_tracks(query: str, limit: int = 5) -> list:
    """Поиск треков на YouTube"""
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'default_search': 'ytsearch',
            'playlist_items': f'1-{limit}'
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            results = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
            
        tracks = []
        if 'entries' in results:
            for entry in results['entries']:
                if entry:
                    track_info = {
                        'title': entry.get('title', 'Неизвестный трек'),
                        'duration': entry.get('duration', 0),
                        'url': f"https://www.youtube.com/watch?v={entry.get('id', '')}",
                        'webpage_url': entry.get('webpage_url', ''),
                        'thumbnail': entry.get('thumbnail', ''),
                        'uploader': entry.get('uploader', 'Неизвестный исполнитель')
                    }
                    tracks.append(track_info)
        
        return tracks
    except Exception as e:
        logging.error(f"❌ Ошибка поиска YouTube: {e}")
        return []

async def search_youtube_artist_improved(artist: str, limit: int = 10) -> list:
    """Поиск треков по исполнителю на YouTube"""
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'default_search': 'ytsearch',
            'playlist_items': f'1-{limit}'
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            results = ydl.extract_info(f"ytsearch{limit}:{artist} music", download=False)
            
        tracks = []
        if 'entries' in results:
            for entry in results['entries']:
                if entry:
                    track_info = {
                        'title': entry.get('title', 'Неизвестный трек'),
                        'duration': entry.get('duration', 0),
                        'url': f"https://www.youtube.com/watch?v={entry.get('id', '')}",
                        'webpage_url': entry.get('webpage_url', ''),
                        'thumbnail': entry.get('thumbnail', ''),
                        'uploader': entry.get('uploader', 'Неизвестный исполнитель')
                    }
                    tracks.append(track_info)
        
        return tracks
    except Exception as e:
        logging.error(f"❌ Ошибка поиска по исполнителю: {e}")
        return []

# === КЛАВИАТУРЫ ===
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

# === ОБРАБОТЧИКИ ===
@dp.callback_query(F.data == "back_to_main")
async def back_to_main_menu(callback: types.CallbackQuery):
    """Возвращает пользователя в главное меню"""
    await callback.answer("⏳ Обрабатываю...")
    
    user_id = str(callback.from_user.id)
    
    is_allowed, time_until = check_antispam(user_id)
    if not is_allowed:
        await callback.answer(f"⏳ Подождите {time_until:.1f} сек. перед следующим запросом", show_alert=True)
        return
    
    try:
        await callback.message.delete()
        
        await callback.message.answer_photo(
            photo=types.FSInputFile("bear.png"),
            reply_markup=main_menu
        )
    except Exception as e:
        try:
            await callback.message.answer_photo(
                photo=types.FSInputFile("bear.png"),
                reply_markup=main_menu
            )
        except Exception as photo_error:
            await callback.message.answer("🐻 Главное меню", reply_markup=main_menu)

@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    try:
        await message.answer_photo(
            photo=types.FSInputFile("bear.png"),
            reply_markup=main_menu
        )
    except Exception as e:
        logging.error(f"❌ Ошибка отправки фото: {e}")
        await message.answer("🐻 Привет! Я бот для поиска и скачивания музыки с YouTube.", reply_markup=main_menu)

# === ПОИСК МУЗЫКИ ===
@dp.callback_query(F.data == "find_track")
async def ask_track_name(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer("⏳ Обрабатываю...")
    
    user_id = str(callback.from_user.id)
    
    is_allowed, time_until = check_antispam(user_id)
    if not is_allowed:
        await callback.answer(f"⏳ Подождите {time_until:.1f} сек. перед следующим запросом", show_alert=True)
        return
    
    try:
        await callback.message.delete()
    except:
        pass
    
    try:
        await callback.message.answer_photo(
            photo=types.FSInputFile("bear.png"),
            caption="🎵Введите название",
            reply_markup=back_button
        )
    except Exception as e:
        await callback.message.edit_text("🎵Введите название", reply_markup=back_button)
    
    await state.set_state(SearchStates.waiting_for_search)

@dp.message(SearchStates.waiting_for_search, F.text)
async def search_tracks(message: types.Message, state: FSMContext):
    """Поиск треков по названию"""
    query = message.text.strip()
    user_id = str(message.from_user.id)
    
    if not query:
        await message.answer("❌ Пожалуйста, введите название трека.", reply_markup=main_menu)
        await state.clear()
        return
    
    try:
        await message.delete()
    except:
        pass
    
    await state.clear()
    
    # Показываем сообщение о поиске
    search_msg = await message.answer("🔍 Ищу треки...")
    
    try:
        tracks = await search_youtube_tracks(query, 5)
        
        if not tracks:
            await search_msg.edit_text("❌ Ничего не найдено. Попробуйте другой запрос.", reply_markup=back_button)
            return
        
        # Создаем клавиатуру с результатами
        keyboard = []
        for i, track in enumerate(tracks):
            duration_text = format_duration(track['duration'])
            button_text = f"🎵 {track['title'][:40]}{'...' if len(track['title']) > 40 else ''}"
            if duration_text:
                button_text += f" ⏱{duration_text}"
            
            row = [
                InlineKeyboardButton(text=button_text, callback_data=f"download:{i}"),
                InlineKeyboardButton(text="💾", callback_data=f"save:{i}")
            ]
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_main")])
        
        # Формируем текст с результатами
        result_text = f"🔍 **Результаты поиска:** `{query}`\n\n"
        for i, track in enumerate(tracks):
            duration_text = format_duration(track['duration'])
            result_text += f"{i+1}. **{track['title']}**\n"
            if duration_text:
                result_text += f"   ⏱ {duration_text}\n"
            result_text += f"   👤 {track['uploader']}\n\n"
        
        await search_msg.edit_text(result_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
        
        # Сохраняем результаты в состоянии для callback
        await state.update_data(search_results=tracks)
        
    except Exception as e:
        logging.error(f"❌ Ошибка поиска: {e}")
        await search_msg.edit_text("❌ Произошла ошибка при поиске. Попробуйте еще раз.", reply_markup=back_button)

# === СКАЧИВАНИЕ ТРЕКОВ ===
@dp.callback_query(F.data.startswith("download:"))
async def download_track(callback: types.CallbackQuery, state: FSMContext):
    """Скачивает выбранный трек"""
    await callback.answer("⏳ Скачиваю...")
    
    user_id = str(callback.from_user.id)
    
    is_allowed, time_until = check_antispam(user_id)
    if not is_allowed:
        await callback.answer(f"⏳ Подождите {time_until:.1f} сек. перед следующим запросом", show_alert=True)
        return
    
    try:
        idx = int(callback.data.split(":")[1])
        state_data = await state.get_data()
        tracks = state_data.get('search_results', [])
        
        if not tracks or idx >= len(tracks):
            await callback.answer("❌ Трек не найден.", show_alert=True)
            return
        
        track = tracks[idx]
        title = track['title']
        url = track['url']
        
        # Показываем сообщение о скачивании
        loading_msg = await callback.message.edit_text(f"⏳ Скачиваю трек: {title}")
        
        try:
            temp_file_path = await download_track_to_temp(user_id, url, title)
            
            if temp_file_path and os.path.exists(temp_file_path):
                await callback.message.answer_audio(types.FSInputFile(temp_file_path), title=title)
                await delete_temp_file(temp_file_path)
                await callback.answer("✅ Трек отправлен!")
                
                # Восстанавливаем результаты поиска
                await loading_msg.delete()
                await callback.message.answer(f"🔍 **Результаты поиска:** `{title}`\n\nТрек скачан и отправлен!", reply_markup=back_button)
            else:
                await loading_msg.edit_text("❌ Не удалось скачать трек.", reply_markup=back_button)
                
        except Exception as e:
            logging.error(f"❌ Ошибка скачивания: {e}")
            await loading_msg.edit_text("❌ Ошибка при скачивании трека.", reply_markup=back_button)
            
    except Exception as e:
        logging.error(f"❌ Ошибка в download_track: {e}")
        await callback.answer("❌ Произошла ошибка.", show_alert=True)

# === СОХРАНЕНИЕ ТРЕКОВ ===
@dp.callback_query(F.data.startswith("save:"))
async def save_track(callback: types.CallbackQuery, state: FSMContext):
    """Сохраняет трек в коллекцию пользователя"""
    await callback.answer("💾 Сохраняю...")
    
    user_id = str(callback.from_user.id)
    
    is_allowed, time_until = check_antispam(user_id)
    if not is_allowed:
        await callback.answer(f"⏳ Подождите {time_until:.1f} сек. перед следующим запросом", show_alert=True)
        return
    
    try:
        idx = int(callback.data.split(":")[1])
        state_data = await state.get_data()
        tracks = state_data.get('search_results', [])
        
        if not tracks or idx >= len(tracks):
            await callback.answer("❌ Трек не найден.", show_alert=True)
            return
        
        track = tracks[idx]
        
        # Загружаем существующие треки
        global user_tracks
        if user_tracks is None:
            user_tracks = load_json(TRACKS_FILE, {})
        
        if user_id not in user_tracks:
            user_tracks[user_id] = []
        
        # Проверяем, не добавлен ли уже трек
        track_exists = any(t.get('title') == track['title'] for t in user_tracks[user_id])
        
        if track_exists:
            await callback.answer("⚠️ Трек уже в вашей коллекции!", show_alert=True)
            return
        
        # Добавляем трек
        track_to_save = {
            'title': track['title'],
            'original_url': track['url'],
            'duration': track['duration'],
            'uploader': track['uploader'],
            'added_at': datetime.now().isoformat()
        }
        
        user_tracks[user_id].append(track_to_save)
        save_json(TRACKS_FILE, user_tracks)
        
        await callback.answer("✅ Трек добавлен в коллекцию!")
        
    except Exception as e:
        logging.error(f"❌ Ошибка сохранения: {e}")
        await callback.answer("❌ Ошибка при сохранении трека.", show_alert=True)

# === МОЯ МУЗЫКА ===
@dp.callback_query(F.data == "my_music")
async def my_music(callback: types.CallbackQuery):
    """Показывает треки пользователя"""
    await callback.answer("⏳ Обрабатываю...")
    
    user_id = str(callback.from_user.id)
    
    is_allowed, time_until = check_antispam(user_id)
    if not is_allowed:
        await callback.answer(f"⏳ Подождите {time_until:.1f} сек. перед следующим запросом", show_alert=True)
        return
    
    global user_tracks
    user_tracks = load_json(TRACKS_FILE, {})
    
    tracks = user_tracks.get(user_id, [])
    
    if not tracks:
        try:
            await callback.message.answer("📂 У вас нет треков.")
        except Exception as answer_error:
            pass
        return
    
    try:
        keyboard = []
        
        for i, track in enumerate(tracks):
            if isinstance(track, dict):
                title = track.get('title', 'Неизвестный трек')
                original_url = track.get('original_url', '')
                duration = track.get('duration', 0)
                
                if original_url and original_url.startswith('http'):
                    duration_text = format_duration(duration)
                    
                    if duration_text:
                        max_title_length = 40
                        button_text = f"🎵 {title[:max_title_length]}{'...' if len(title) > max_title_length else ''} ⏱{duration_text}"
                    else:
                        max_title_length = 50
                        button_text = f"🎵 {title[:max_title_length]}{'...' if len(title) > max_title_length else ''}"
                    
                    row = [
                        InlineKeyboardButton(text=button_text, callback_data=f"play:{i}"),
                        InlineKeyboardButton(text="🗑", callback_data=f"del:{i}")
                    ]
                    keyboard.append(row)
                else:
                    max_title_length = 50
                    button_text = f"⚠️ {title[:max_title_length]}{'...' if len(title) > max_title_length else ''}"
                    row = [
                        InlineKeyboardButton(text=button_text, callback_data="no_url"),
                        InlineKeyboardButton(text="🗑", callback_data=f"del:{i}")
                    ]
                    keyboard.append(row)
            else:
                title = os.path.basename(track)
                max_title_length = 50
                button_text = f"⚠️ {title[:max_title_length]}{'...' if len(title) > max_title_length else ''}"
                row = [
                    InlineKeyboardButton(text=button_text, callback_data="old_format"),
                    InlineKeyboardButton(text="🗑", callback_data=f"del:{i}")
                ]
                keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_main")])
        
        try:
            await callback.message.answer_photo(
                photo=types.FSInputFile("bear.png"),
                caption="🌨️ **Моя музыка**\n\nВыберите трек для скачивания:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
            )
        except Exception as e:
            await callback.message.answer("🌨️ **Моя музыка**\n\nВыберите трек для скачивания:", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
            
    except Exception as e:
        logging.error(f"❌ Ошибка показа моей музыки: {e}")
        await callback.answer("❌ Произошла ошибка.", show_alert=True)

# === СКАЧИВАНИЕ ИЗ МОЕЙ МУЗЫКИ ===
@dp.callback_query(F.data.startswith("play:"))
async def play_track(callback: types.CallbackQuery):
    """Скачивает и отправляет один трек из коллекции"""
    global user_tracks
    try:
        user_id = str(callback.from_user.id)
        
        is_allowed, time_until = check_antispam(user_id)
        if not is_allowed:
            await callback.answer(f"⏳ Подождите {time_until:.1f} сек. перед следующим запросом", show_alert=True)
            return
        
        idx = int(callback.data.split(":")[1])
        
        if user_tracks is None:
            user_tracks = {}
        
        tracks = user_tracks.get(user_id, [])
        if not tracks:
            await callback.answer("📂 У вас нет треков.", show_alert=True)
            return
        
        if not (0 <= idx < len(tracks)):
            await callback.answer("❌ Трек не найден.", show_alert=True)
            return
        
        track = tracks[idx]
        
        if isinstance(track, dict):
            title = track.get('title', 'Неизвестный трек')
            original_url = track.get('original_url', '')
            
            if not original_url or not original_url.startswith('http'):
                await callback.answer("❌ Ссылка для скачивания не найдена.", show_alert=True)
                return
            
            # Показываем уведомление о скачивании без изменения сообщения с плейлистом
            await callback.answer("⏳ Скачиваю трек...", show_alert=False)
            
            try:
                temp_file_path = await download_track_to_temp(user_id, original_url, title)
                
                if temp_file_path and os.path.exists(temp_file_path):
                    await callback.message.answer_audio(types.FSInputFile(temp_file_path), title=title)
                    await delete_temp_file(temp_file_path)
                    await callback.answer("✅ Трек отправлен!")
                else:
                    await callback.answer("❌ Не удалось скачать трек.")
                    
            except Exception as e:
                logging.error(f"❌ Ошибка при скачивании/отправке трека {title}: {e}")
                await callback.answer("❌ Ошибка при скачивании трека.")

        else:
            title = os.path.basename(track)
            await callback.answer("❌ Трек в старом формате. Добавьте его заново.", show_alert=True)
                
    except ValueError as e:
        logging.error(f"❌ Ошибка парсинга индекса трека: {e}")
        await callback.answer("❌ Ошибка индекса трека.", show_alert=True)
    except Exception as e:
        logging.error(f"❌ Критическая ошибка в play_track: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте еще раз.", show_alert=True)

# === УДАЛЕНИЕ ТРЕКОВ ===
@dp.callback_query(F.data.startswith("del:"))
async def delete_track(callback: types.CallbackQuery):
    """Удаляет трек из коллекции"""
    await callback.answer("🗑 Удаляю...")
    
    user_id = str(callback.from_user.id)
    
    is_allowed, time_until = check_antispam(user_id)
    if not is_allowed:
        await callback.answer(f"⏳ Подождите {time_until:.1f} сек. перед следующим запросом", show_alert=True)
        return
    
    try:
        idx = int(callback.data.split(":")[1])
        
        global user_tracks
        if user_tracks is None:
            user_tracks = {}
        
        tracks = user_tracks.get(user_id, [])
        if not tracks or idx >= len(tracks):
            await callback.answer("❌ Трек не найден.", show_alert=True)
            return
        
        deleted_track = tracks.pop(idx)
        save_json(TRACKS_FILE, user_tracks)
        
        title = deleted_track.get('title', 'Неизвестный трек') if isinstance(deleted_track, dict) else os.path.basename(deleted_track)
        await callback.answer(f"✅ Трек '{title}' удален из коллекции!")
        
    except Exception as e:
        logging.error(f"❌ Ошибка удаления трека: {e}")
        await callback.answer("❌ Ошибка при удалении трека.", show_alert=True)

# === ПОИСК ПО ИСПОЛНИТЕЛЯМ ===
@dp.callback_query(F.data == "by_artist")
async def by_artist_section(callback: types.CallbackQuery, state: FSMContext):
    """Открывает поиск по исполнителю"""
    await callback.answer("⏳ Обрабатываю...")
    
    user_id = str(callback.from_user.id)
    
    is_allowed, time_until = check_antispam(user_id)
    if not is_allowed:
        await callback.answer(f"⏳ Подождите {time_until:.1f} сек. перед следующим запросом", show_alert=True)
        return
    
    try:
        await callback.message.delete()
    except:
        pass
    
    try:
        await callback.message.answer_photo(
            photo=types.FSInputFile("bear.png"),
            caption="🌨️ **Поиск по исполнителям**\n\nВведите имя исполнителя для поиска треков:",
            reply_markup=artist_search_menu
        )
    except Exception as e:
        await callback.message.answer("🌨️ **Поиск по исполнителям**\n\nВведите имя исполнителя для поиска треков:", reply_markup=artist_search_menu)
    
    await state.set_state(SearchStates.waiting_for_artist_search)

@dp.callback_query(F.data == "search_by_artist")
async def search_by_artist_handler(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик кнопки поиска по исполнителю"""
    await callback.answer("⏳ Обрабатываю...")
    
    user_id = str(callback.from_user.id)
    
    is_allowed, time_until = check_antispam(user_id)
    if not is_allowed:
        await callback.answer(f"⏳ Подождите {time_until:.1f} сек. перед следующим запросом", show_alert=True)
        return
    
    try:
        await callback.message.delete()
    except:
        pass
    
    try:
        await callback.message.answer_photo(
            photo=types.FSInputFile("bear.png"),
            caption="🌨️ Введите исполнителя",
            reply_markup=back_button
        )
    except Exception as e:
        await callback.message.answer("🌨️ Введите исполнителя", reply_markup=back_button)
    
    await state.set_state(SearchStates.waiting_for_artist_search)

@dp.message(SearchStates.waiting_for_artist_search, F.text)
async def search_by_artist(message: types.Message, state: FSMContext):
    """Поиск треков по исполнителю"""
    artist = message.text.strip()
    user_id = str(message.from_user.id)
    
    await state.clear()

    if not artist:
        await message.answer("❌ Пожалуйста, введите имя исполнителя.", reply_markup=main_menu)
        return

    try:
        await message.delete()
    except:
        pass

    # Показываем сообщение о поиске
    search_msg = await message.answer(f"🔍 Ищу треки исполнителя: {artist}")

    try:
        tracks = await search_youtube_artist_improved(artist, 10)
        
        if not tracks:
            await search_msg.edit_text(f"❌ Для исполнителя '{artist}' ничего не найдено.", reply_markup=back_button)
            return
        
        # Создаем клавиатуру с результатами
        keyboard = []
        for i, track in enumerate(tracks):
            duration_text = format_duration(track['duration'])
            button_text = f"🎵 {track['title'][:40]}{'...' if len(track['title']) > 40 else ''}"
            if duration_text:
                button_text += f" ⏱{duration_text}"
            
            row = [
                InlineKeyboardButton(text=button_text, callback_data=f"download_artist:{i}"),
                InlineKeyboardButton(text="💾", callback_data=f"save_artist:{i}")
            ]
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_main")])
        
        # Формируем текст с результатами
        result_text = f"🌨️ **Треки исполнителя:** `{artist}`\n\n"
        for i, track in enumerate(tracks):
            duration_text = format_duration(track['duration'])
            result_text += f"{i+1}. **{track['title']}**\n"
            if duration_text:
                result_text += f"   ⏱ {duration_text}\n"
            result_text += f"   👤 {track['uploader']}\n\n"
        
        await search_msg.edit_text(result_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
        
        # Сохраняем результаты в состоянии для callback
        await state.update_data(artist_search_results=tracks, artist_name=artist)
        
    except Exception as e:
        logging.error(f"❌ Ошибка поиска по исполнителю: {e}")
        await search_msg.edit_text("❌ Произошла ошибка при поиске. Попробуйте еще раз.", reply_markup=back_button)

# === СКАЧИВАНИЕ И СОХРАНЕНИЕ ТРЕКОВ ПО ИСПОЛНИТЕЛЮ ===
@dp.callback_query(F.data.startswith("download_artist:"))
async def download_artist_track(callback: types.CallbackQuery, state: FSMContext):
    """Скачивает трек по исполнителю"""
    await callback.answer("⏳ Скачиваю...")
    
    user_id = str(callback.from_user.id)
    
    is_allowed, time_until = check_antispam(user_id)
    if not is_allowed:
        await callback.answer(f"⏳ Подождите {time_until:.1f} сек. перед следующим запросом", show_alert=True)
        return
    
    try:
        idx = int(callback.data.split(":")[1])
        state_data = await state.get_data()
        tracks = state_data.get('artist_search_results', [])
        artist_name = state_data.get('artist_name', '')
        
        if not tracks or idx >= len(tracks):
            await callback.answer("❌ Трек не найден.", show_alert=True)
            return
        
        track = tracks[idx]
        title = track['title']
        url = track['url']
        
        loading_msg = await callback.message.edit_text(f"⏳ Скачиваю трек: {title}")
        
        try:
            temp_file_path = await download_track_to_temp(user_id, url, title)
            
            if temp_file_path and os.path.exists(temp_file_path):
                await callback.message.answer_audio(types.FSInputFile(temp_file_path), title=title)
                await delete_temp_file(temp_file_path)
                await callback.answer("✅ Трек отправлен!")
                
                await loading_msg.delete()
                await callback.message.answer(f"🌨️ **Треки исполнителя:** `{artist_name}`\n\nТрек скачан и отправлен!", reply_markup=back_button)
            else:
                await loading_msg.edit_text("❌ Не удалось скачать трек.", reply_markup=back_button)
                
        except Exception as e:
            logging.error(f"❌ Ошибка скачивания: {e}")
            await loading_msg.edit_text("❌ Ошибка при скачивании трека.", reply_markup=back_button)
            
    except Exception as e:
        logging.error(f"❌ Ошибка в download_artist_track: {e}")
        await callback.answer("❌ Произошла ошибка.", show_alert=True)

@dp.callback_query(F.data.startswith("save_artist:"))
async def save_artist_track(callback: types.CallbackQuery, state: FSMContext):
    """Сохраняет трек по исполнителю в коллекцию"""
    await callback.answer("💾 Сохраняю...")
    
    user_id = str(callback.from_user.id)
    
    is_allowed, time_until = check_antispam(user_id)
    if not is_allowed:
        await callback.answer(f"⏳ Подождите {time_until:.1f} сек. перед следующим запросом", show_alert=True)
        return
    
    try:
        idx = int(callback.data.split(":")[1])
        state_data = await state.get_data()
        tracks = state_data.get('artist_search_results', [])
        
        if not tracks or idx >= len(tracks):
            await callback.answer("❌ Трек не найден.", show_alert=True)
            return
        
        track = tracks[idx]
        
        global user_tracks
        if user_tracks is None:
            user_tracks = load_json(TRACKS_FILE, {})
        
        if user_id not in user_tracks:
            user_tracks[user_id] = []
        
        track_exists = any(t.get('title') == track['title'] for t in user_tracks[user_id])
        
        if track_exists:
            await callback.answer("⚠️ Трек уже в вашей коллекции!", show_alert=True)
            return
        
        track_to_save = {
            'title': track['title'],
            'original_url': track['url'],
            'duration': track['duration'],
            'uploader': track['uploader'],
            'added_at': datetime.now().isoformat()
        }
        
        user_tracks[user_id].append(track_to_save)
        save_json(TRACKS_FILE, user_tracks)
        
        await callback.answer("✅ Трек добавлен в коллекцию!")
        
    except Exception as e:
        logging.error(f"❌ Ошибка сохранения: {e}")
        await callback.answer("❌ Ошибка при сохранении трека.", show_alert=True)

# === ОБРАБОТКА ОШИБОК ===
@dp.callback_query(F.data == "no_url")
async def no_url_handler(callback: types.CallbackQuery):
    await callback.answer("⚠️ Этот трек не имеет ссылки для скачивания", show_alert=True)

@dp.callback_query(F.data == "old_format")
async def old_format_handler(callback: types.CallbackQuery):
    await callback.answer("⚠️ Трек в старом формате. Добавьте его заново.", show_alert=True)

# === ЗАПУСК БОТА ===
async def main():
    """Основная функция запуска бота"""
    try:
        logging.info("🚀 Запуск упрощенного музыкального бота...")
        
        # Проверяем наличие изображения
        if not os.path.exists("bear.png"):
            logging.warning("⚠️ Файл bear.png не найден. Бот будет работать без изображения.")
        
        # Проверяем наличие cookies
        if not os.path.exists(COOKIES_FILE):
            logging.warning("⚠️ Файл cookies.txt не найден. Некоторые функции могут работать некорректно.")
        
        # Создаем необходимые директории
        os.makedirs(CACHE_DIR, exist_ok=True)
        
        # Загружаем существующие треки
        global user_tracks
        user_tracks = load_json(TRACKS_FILE, {})
        
        logging.info("✅ Бот готов к работе!")
        
        # Запускаем бота
        await dp.start_polling(bot)
        
    except Exception as e:
        logging.error(f"❌ Критическая ошибка запуска: {e}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("🛑 Бот остановлен пользователем")
    except Exception as e:
        logging.error(f"❌ Критическая ошибка: {e}")
        raise
