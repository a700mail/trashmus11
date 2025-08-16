import logging
import os
import asyncio
import json
import time
from typing import Optional, Dict, Any, List
from aiogram import Bot, Dispatcher, types
from aiogram import F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
import httpx
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Настройки логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# Конфигурация
API_TOKEN = os.getenv("BOT_TOKEN")
MUSIC_SERVICE_URL = os.getenv("MUSIC_SERVICE_URL", "http://localhost:8001")
MUSIC_SERVICE_API_KEY = os.getenv("MUSIC_SERVICE_API_KEY", "default_key")
STORAGE_SERVICE_URL = os.getenv("STORAGE_SERVICE_URL", "http://localhost:8002")
STORAGE_SERVICE_API_KEY = os.getenv("STORAGE_SERVICE_API_KEY", "default_key")
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))

if not API_TOKEN:
    raise RuntimeError("Переменная окружения BOT_TOKEN не установлена")

# Инициализация бота
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# HTTP клиент для API
http_client = httpx.AsyncClient(timeout=30.0)

# Глобальное хранилище результатов поиска (в продакшене лучше использовать Redis)
search_results_cache = {}

# Состояния FSM
class SearchStates(StatesGroup):
    waiting_for_search = State()
    waiting_for_artist = State()

# Класс для работы с Music Processing Service
class MusicServiceClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key
        self.headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    async def search_music(self, query: str) -> Optional[List[Dict[str, Any]]]:
        """Поиск музыки через API"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/search",
                    json={"query": query, "limit": 10},
                    headers=self.headers,
                    timeout=15.0
                )
                if response.status_code == 200:
                    return response.json().get("results", [])
                else:
                    logging.error(f"Ошибка поиска: {response.status_code}")
                    return None
        except Exception as e:
            logging.error(f"Ошибка запроса к Music Service: {e}")
            return None
    
    async def download_track(self, url: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Загрузка трека через API"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/download",
                    json={"url": url, "user_id": user_id},
                    headers=self.headers,
                    timeout=120.0
                )
                if response.status_code == 200:
                    return response.json()
                else:
                    logging.error(f"Ошибка загрузки: {response.status_code}")
                    return None
        except Exception as e:
            logging.error(f"Ошибка запроса загрузки: {e}")
            return None
    
    async def search_by_artist(self, artist: str, limit: int = 10) -> Optional[List[Dict[str, Any]]]:
        """Поиск по исполнителю через API"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/search/artist",
                    json={"artist": artist, "limit": limit},
                    headers=self.headers,
                    timeout=30.0
                )
                if response.status_code == 200:
                    return response.json().get("results", [])
                else:
                    logging.error(f"Ошибка поиска по исполнителю: {response.status_code}")
                    return None
        except Exception as e:
            logging.error(f"Ошибка запроса поиска по исполнителю: {e}")
            return None

# Класс для работы с Data Storage Service
class StorageServiceClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key
        self.headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    async def get_user_tracks(self, user_id: str) -> Optional[List[Dict[str, Any]]]:
        """Получение треков пользователя"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/tracks/{user_id}",
                    headers=self.headers,
                    timeout=10.0
                )
                if response.status_code == 200:
                    return response.json().get("tracks", [])
                else:
                    logging.error(f"Ошибка получения треков: {response.status_code}")
                    return None
        except Exception as e:
            logging.error(f"Ошибка запроса треков: {e}")
            return None
    
    async def save_track(self, user_id: str, track_data: Dict[str, Any]) -> bool:
        """Сохранение трека пользователя"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/tracks/{user_id}",
                    json=track_data,
                    headers=self.headers,
                    timeout=10.0
                )
                return response.status_code == 200
        except Exception as e:
            logging.error(f"Ошибка сохранения трека: {e}")
            return False
    
    async def get_search_cache(self, query: str) -> Optional[List[Dict[str, Any]]]:
        """Получение кеша поиска"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/cache/search",
                    params={"query": query},
                    headers=self.headers,
                    timeout=5.0
                )
                if response.status_code == 200:
                    return response.json().get("results", [])
                return None
        except Exception as e:
            logging.error(f"Ошибка получения кеша: {e}")
            return None
    
    async def set_search_cache(self, query: str, results: List[Dict[str, Any]]) -> bool:
        """Сохранение кеша поиска"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/cache/search",
                    json={"query": query, "results": results},
                    headers=self.headers,
                    timeout=5.0
                )
                return response.status_code == 200
        except Exception as e:
            logging.error(f"Ошибка сохранения кеша: {e}")
            return False

# Инициализация клиентов
music_client = MusicServiceClient(MUSIC_SERVICE_URL, MUSIC_SERVICE_API_KEY)
storage_client = StorageServiceClient(STORAGE_SERVICE_URL, STORAGE_SERVICE_API_KEY)

# Главное меню
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

back_button = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_main")]]
)

# Команды
@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    """Приветственное сообщение"""
    try:
        await message.answer_video(
            video=types.FSInputFile("../beer.mp4"),
            reply_markup=main_menu
        )
    except Exception as e:
        logging.error(f"Ошибка отправки видео: {e}")
        await message.answer("🐻 Привет! Я бот для поиска и скачивания музыки.", reply_markup=main_menu)

@dp.message(Command("play"))
async def play_command(message: types.Message):
    """Команда /play <название> - пример взаимодействия с микросервисами"""
    try:
        # Парсим команду
        parts = message.text.split(' ', 1)
        if len(parts) < 2:
            await message.answer("❌ Использование: /play <название песни>")
            return
        
        query = parts[1].strip()
        user_id = str(message.from_user.id)
        
        # Отправляем сообщение о начале поиска
        search_msg = await message.answer("🔍 Поиск...")
        
        # Проверяем кеш
        cached_results = await storage_client.get_search_cache(query)
        if cached_results:
            await search_msg.delete()
            await send_search_results(message.chat.id, cached_results)
            return
        
        # Ищем музыку через Music Service
        results = await music_client.search_music(query)
        if not results:
            await search_msg.delete()
            await message.answer("❌ Ничего не найдено. Попробуйте изменить запрос.", reply_markup=main_menu)
            return
        
        # Сохраняем в кеш
        await storage_client.set_search_cache(query, results)
        
        # Отправляем результаты
        await search_msg.delete()
        await send_search_results(message.chat.id, results)
        
    except Exception as e:
        logging.error(f"Ошибка команды /play: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте еще раз.", reply_markup=main_menu)

# Callback обработчики
@dp.callback_query(F.data == "back_to_main")
async def back_to_main_menu(callback: types.CallbackQuery):
    """Возврат в главное меню"""
    await callback.answer("⏳ Обрабатываю...")
    try:
        await callback.message.edit_media(
            media=types.InputMediaVideo(media=types.FSInputFile("../beer.mp4")),
            reply_markup=main_menu
        )
    except Exception as e:
        logging.error(f"Ошибка возврата в главное меню: {e}")
        await callback.message.answer("🐻‍❄️ Главное меню", reply_markup=main_menu)

@dp.callback_query(F.data == "find_track")
async def ask_track_name(callback: types.CallbackQuery, state: FSMContext):
    """Запрос названия трека для поиска"""
    await callback.answer("⏳ Обрабатываю...")
    try:
        await callback.message.delete()
        await callback.message.answer_video(
            video=types.FSInputFile("../beer.mp4"),
            caption="🎵Введите название",
            reply_markup=back_button
        )
        await state.set_state(SearchStates.waiting_for_search)
    except Exception as e:
        logging.error(f"Ошибка запроса названия: {e}")
        await callback.answer("❌ Ошибка. Попробуйте еще раз.", show_alert=True)

@dp.callback_query(F.data == "my_music")
async def show_my_music(callback: types.CallbackQuery):
    """Показать музыку пользователя"""
    await callback.answer("⏳ Загружаю...")
    try:
        user_id = str(callback.from_user.id)
        tracks = await storage_client.get_user_tracks(user_id)
        
        if not tracks:
            await callback.message.answer("🎵 У вас пока нет сохраненных треков.", reply_markup=back_button)
            return
        
        # Формируем список треков
        tracks_text = "🎵 **Ваша музыка:**\n\n"
        for i, track in enumerate(tracks[:20], 1):  # Показываем первые 20
            title = track.get('title', 'Без названия')
            duration = track.get('duration', 0)
            if duration:
                duration_str = f"{duration//60}:{duration%60:02d}"
            else:
                duration_str = "??:??"
            tracks_text += f"{i}. {title} ({duration_str})\n"
        
        if len(tracks) > 20:
            tracks_text += f"\n... и еще {len(tracks) - 20} треков"
        
        # Создаем клавиатуру с треками для повторного скачивания
        keyboard = []
        for i, track in enumerate(tracks[:20], 1):  # Показываем первые 20
            title = track.get('title', 'Без названия')[:25]  # Ограничиваем длину
            keyboard.append([InlineKeyboardButton(
                text=f"{i}. {title}",
                callback_data=f"redownload_{track.get('id', i)}"
            )])
        
        keyboard.append([InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_main")])
        markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        
        await callback.message.answer(tracks_text, reply_markup=markup, parse_mode="Markdown")
        
    except Exception as e:
        logging.error(f"Ошибка показа музыки: {e}")
        await callback.answer("❌ Ошибка загрузки. Попробуйте еще раз.", show_alert=True)

@dp.callback_query(F.data == "by_artist")
async def by_artist_section(callback: types.CallbackQuery, state: FSMContext):
    """Поиск по исполнителю"""
    await callback.answer("⏳ Обрабатываю...")
    try:
        await callback.message.delete()
        msg = await callback.message.answer("🌨️ Введите исполнителя")
        await state.set_state(SearchStates.waiting_for_artist)
        await state.update_data(prompt_message_id=msg.message_id)
    except Exception as e:
        logging.error(f"Ошибка поиска по исполнителю: {e}")
        await callback.answer("❌ Ошибка. Попробуйте еще раз.", show_alert=True)

# Обработчики состояний
@dp.message(SearchStates.waiting_for_search, F.text)
async def search_music(message: types.Message, state: FSMContext):
    """Поиск музыки по тексту"""
    query = message.text.strip()
    user_id = str(message.from_user.id)
    await state.clear()
    
    if not query:
        await message.answer("❌ Пожалуйста, введите название песни.", reply_markup=main_menu)
        return
    
    # Проверяем, является ли это URL
    if query.startswith(('http://', 'https://')):
        await message.answer("⏳ Загружаю трек по ссылке...")
        
        # Загружаем трек через Music Service
        result = await music_client.download_track(query, user_id)
        if result:
            # Сохраняем в хранилище
            track_data = {
                "title": result.get("title", "Неизвестный трек"),
                "url": result.get("file_url", ""),
                "original_url": query,
                "duration": result.get("duration", 0),
                "uploader": result.get("uploader", "Неизвестный исполнитель"),
                "size_mb": result.get("size_mb", 0)
            }
            
            if await storage_client.save_track(user_id, track_data):
                await message.answer("✅ Трек успешно добавлен в вашу коллекцию!", reply_markup=main_menu)
            else:
                await message.answer("⚠️ Трек загружен, но не удалось сохранить в коллекцию.", reply_markup=main_menu)
        else:
            await message.answer("❌ Не удалось загрузить трек по ссылке.", reply_markup=main_menu)
        return
    
    # Поиск по названию
    search_msg = await message.answer("🔍 Поиск...")
    
    # Проверяем кеш
    cached_results = await storage_client.get_search_cache(query)
    if cached_results:
        await search_msg.delete()
        await send_search_results(message.chat.id, cached_results)
        return
    
    # Ищем через Music Service
    results = await music_client.search_music(query)
    if not results:
        await search_msg.delete()
        await message.answer("❌ Ничего не найдено. Попробуйте изменить запрос.", reply_markup=main_menu)
        return
    
    # Сохраняем в кеш
    await storage_client.set_search_cache(query, results)
    
    # Отправляем результаты
    await search_msg.delete()
    await send_search_results(message.chat.id, results)

@dp.message(SearchStates.waiting_for_artist, F.text)
async def search_by_artist(message: types.Message, state: FSMContext):
    """Поиск по исполнителю"""
    artist = message.text.strip()
    user_id = str(message.from_user.id)
    
    # Удаляем сообщение с запросом
    try:
        state_data = await state.get_data()
        prompt_message_id = state_data.get('prompt_message_id')
        if prompt_message_id:
            await message.bot.delete_message(message.chat.id, prompt_message_id)
    except:
        pass
    
    await state.clear()
    
    if not artist:
        await message.answer("❌ Пожалуйста, введите имя исполнителя.", reply_markup=main_menu)
        return
    
    search_msg = await message.answer(f"🔍 Поиск треков исполнителя '{artist}'...")
    
    # Ищем через Music Service
    results = await music_client.search_by_artist(artist, 10)
    if not results:
        await search_msg.delete()
        await message.answer(f"❌ Не найдено треков исполнителя '{artist}'.", reply_markup=main_menu)
        return
    
    await search_msg.delete()
    await message.answer(f"❄️ Найдено {len(results)} треков исполнителя '{artist}'. Скачиваю...")
    
    # Загружаем треки
    downloaded_count = 0
    for track in results:
        try:
            # Загружаем трек
            result = await music_client.download_track(track.get('url', ''), user_id)
            if result:
                # Сохраняем в хранилище
                track_data = {
                    "title": track.get("title", "Без названия"),
                    "url": result.get("file_url", ""),
                    "original_url": track.get("url", ""),
                    "duration": track.get("duration", 0),
                    "uploader": artist,
                    "size_mb": result.get("size_mb", 0)
                }
                
                if await storage_client.save_track(user_id, track_data):
                    downloaded_count += 1
                    
                    # Отправляем файл пользователю
                    try:
                        await message.answer_audio(
                            types.FSInputFile(result.get("file_path", "")),
                            title=track.get("title", "Без названия"),
                            performer=artist,
                            duration=track.get("duration", 0)
                        )
                    except Exception as audio_error:
                        logging.error(f"Ошибка отправки аудио: {audio_error}")
                        # Отправляем как документ
                        await message.answer_document(
                            types.FSInputFile(result.get("file_path", "")),
                            caption=f"🎵 {track.get('title', 'Без названия')} - {artist}"
                        )
                    
                    # Небольшая задержка между отправками
                    await asyncio.sleep(0.5)
                    
        except Exception as e:
            logging.error(f"Ошибка загрузки трека {track.get('title', '')}: {e}")
            continue
    
    await message.answer(f"✅ Загружено {downloaded_count} треков исполнителя '{artist}'!", reply_markup=main_menu)

async def send_search_results(chat_id: int, results: List[Dict[str, Any]]):
    """Отправка результатов поиска"""
    try:
        if not results:
            return
        
        # Сохраняем результаты в кеш для этого чата
        search_results_cache[chat_id] = results
        
        # Создаем клавиатуру с результатами
        keyboard = []
        for i, result in enumerate(results[:10]):  # Максимум 10 результатов
            title = result.get('title', 'Без названия')[:30]  # Ограничиваем длину
            keyboard.append([InlineKeyboardButton(
                text=f"{i+1}. {title}",
                callback_data=f"download_{i}"  # Используем индекс вместо id
            )])
        
        keyboard.append([InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_main")])
        
        markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        
        await bot.send_message(
            chat_id,
            f"🔍 Найдено {len(results)} результатов:\nВыберите трек для загрузки:",
            reply_markup=markup
        )
        
    except Exception as e:
        logging.error(f"Ошибка отправки результатов поиска: {e}")

# Обработчик загрузки выбранного трека
@dp.callback_query(F.data.startswith("download_"))
async def download_selected_track(callback: types.CallbackQuery):
    """Загрузка выбранного трека"""
    await callback.answer("⏳ Загружаю...")
    
    try:
        # Получаем индекс трека из callback_data
        track_index = int(callback.data.split("_")[1])
        user_id = str(callback.from_user.id)
        chat_id = callback.message.chat.id
        
        # Получаем результаты поиска из кеша
        if chat_id not in search_results_cache:
            await callback.answer("❌ Результаты поиска устарели. Выполните поиск заново.", show_alert=True)
            return
        
        results = search_results_cache[chat_id]
        if track_index >= len(results):
            await callback.answer("❌ Трек не найден.", show_alert=True)
            return
        
        # Получаем информацию о выбранном треке
        selected_track = results[track_index]
        track_url = selected_track.get('url', '')
        
        if not track_url:
            await callback.answer("❌ URL трека не найден.", show_alert=True)
            return
        
        # Отправляем сообщение о начале загрузки
        loading_msg = await callback.message.answer("⏳ Загружаю трек...")
        
        # Загружаем трек через Music Service
        download_result = await music_client.download_track(track_url, user_id)
        
        if not download_result:
            await loading_msg.delete()
            await callback.answer("❌ Ошибка загрузки трека.", show_alert=True)
            return
        
        # Сохраняем метаданные трека в Data Storage Service
        track_data = {
            "title": selected_track.get("title", "Без названия"),
            "url": download_result.get("file_url", ""),
            "original_url": track_url,
            "duration": selected_track.get("duration", 0),
            "uploader": selected_track.get("uploader", "Неизвестно"),
            "size_mb": download_result.get("size_mb", 0)
        }
        
        # Сохраняем в хранилище
        if await storage_client.save_track(user_id, track_data):
            await loading_msg.delete()
            await callback.message.answer(
                f"✅ Трек '{selected_track.get('title', 'Без названия')}' загружен, отправлен и добавлен в вашу коллекцию!",
                reply_markup=main_menu
            )
        else:
            await loading_msg.delete()
            await callback.message.answer(
                f"✅ Трек '{selected_track.get('title', 'Без названия')}' загружен и отправлен!",
                reply_markup=main_menu
            )
        
        # Отправляем файл пользователю
        try:
            file_path = download_result.get("file_path", "")
            if file_path and os.path.exists(file_path):
                await callback.message.answer_audio(
                    types.FSInputFile(file_path),
                    title=selected_track.get("title", "Без названия"),
                    performer=selected_track.get("uploader", "Неизвестно"),
                    duration=selected_track.get("duration", 0)
                )
            else:
                # Если файл недоступен, отправляем ссылку
                await callback.message.answer(
                    f"📁 Файл: {download_result.get('file_url', 'Ссылка недоступна')}"
                )
        except Exception as audio_error:
            logging.error(f"Ошибка отправки аудио: {audio_error}")
            # Отправляем как документ или ссылку
            await callback.message.answer(
                f"📁 Файл загружен: {download_result.get('file_url', 'Ссылка недоступна')}"
            )
        
    except Exception as e:
        logging.error(f"Ошибка загрузки выбранного трека: {e}")
        await callback.answer("❌ Ошибка загрузки. Попробуйте еще раз.", show_alert=True)

# Обработчик повторного скачивания трека из "Моей музыки"
@dp.callback_query(F.data.startswith("redownload_"))
async def redownload_track_from_my_music(callback: types.CallbackQuery):
    """Повторное скачивание трека из коллекции пользователя"""
    await callback.answer("⏳ Загружаю...")
    
    try:
        # Получаем ID трека из callback_data
        track_id = callback.data.split("_")[1]
        user_id = str(callback.from_user.id)
        
        # Получаем информацию о треке из Data Storage Service
        tracks = await storage_client.get_user_tracks(user_id)
        if not tracks:
            await callback.answer("❌ Треки не найдены.", show_alert=True)
            return
        
        # Ищем трек по ID (пока используем индекс, в реальности нужен ID)
        try:
            track_index = int(track_id) - 1
            if track_index < 0 or track_index >= len(tracks):
                await callback.answer("❌ Трек не найден.", show_alert=True)
                return
            selected_track = tracks[track_index]
        except ValueError:
            await callback.answer("❌ Неверный ID трека.", show_alert=True)
            return
        
        # Получаем оригинальную ссылку для повторного скачивания
        original_url = selected_track.get('original_url', '')
        if not original_url:
            await callback.answer("❌ Оригинальная ссылка не найдена.", show_alert=True)
            return
        
        # Отправляем сообщение о начале загрузки
        loading_msg = await callback.message.answer("⏳ Загружаю трек...")
        
        # Загружаем трек через Music Service
        download_result = await music_client.download_track(original_url, user_id)
        
        if not download_result:
            await loading_msg.delete()
            await callback.answer("❌ Ошибка загрузки трека.", show_alert=True)
            return
        
        # Отправляем файл пользователю
        try:
            file_path = download_result.get("file_path", "")
            if file_path and os.path.exists(file_path):
                await callback.message.answer_audio(
                    types.FSInputFile(file_path),
                    title=selected_track.get("title", "Без названия"),
                    performer=selected_track.get("uploader", "Неизвестно"),
                    duration=selected_track.get("duration", 0)
                )
            else:
                # Если файл недоступен, отправляем ссылку
                await callback.message.answer(
                    f"📁 Файл: {download_result.get('file_url', 'Ссылка недоступна')}"
                )
        except Exception as audio_error:
            logging.error(f"Ошибка отправки аудио: {audio_error}")
            # Отправляем как документ или ссылку
            await callback.message.answer(
                f"📁 Файл загружен: {download_result.get('file_url', 'Ссылка недоступна')}"
            )
        
        await loading_msg.delete()
        await callback.message.answer(
            f"✅ Трек '{selected_track.get('title', 'Без названия')}' загружен и отправлен!",
            reply_markup=main_menu
        )
        
    except Exception as e:
        logging.error(f"Ошибка повторного скачивания трека: {e}")
        await callback.answer("❌ Ошибка загрузки. Попробуйте еще раз.", show_alert=True)

async def main():
    """Главная функция"""
    try:
        logging.info("🚀 Запуск Core Bot Service...")
        
        # Проверяем доступность сервисов
        try:
            # Проверяем Music Service
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{MUSIC_SERVICE_URL}/health", timeout=5.0)
                if response.status_code == 200:
                    logging.info("✅ Music Processing Service доступен")
                else:
                    logging.warning("⚠️ Music Processing Service недоступен")
        except Exception as e:
            logging.warning(f"⚠️ Не удается подключиться к Music Processing Service: {e}")
        
        try:
            # Проверяем Storage Service
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{STORAGE_SERVICE_URL}/health", timeout=5.0)
                if response.status_code == 200:
                    logging.info("✅ Data Storage Service доступен")
                else:
                    logging.warning("⚠️ Data Storage Service недоступен")
        except Exception as e:
            logging.warning(f"⚠️ Не удается подключиться к Data Storage Service: {e}")
        
        # Запускаем бота
        await dp.start_polling(bot)
        
    except Exception as e:
        logging.error(f"❌ Критическая ошибка: {e}")
    finally:
        await http_client.aclose()

if __name__ == "__main__":
    asyncio.run(main())
