import asyncio
import logging
import os
import signal
import sys
import threading
import time
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import yt_dlp
from datetime import datetime
from flask import Flask, request, jsonify

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Получаем токен бота
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN') or os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    logger.error("❌ Токен бота не установлен!")
    sys.exit(1)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Инициализация Flask
app = Flask(__name__)

# Глобальные переменные
user_tracks = {}
user_last_request = {}

# === FLASK ROUTES ===

@app.route('/')
def home():
    """Главная страница"""
    return jsonify({
        "status": "Telegram Music Bot Service",
        "bot_status": "running",
        "message": "Bot is active and responding",
        "features": [
            "YouTube music download",
            "SoundCloud support",
            "Music search",
            "User collections"
        ]
    })

@app.route('/ping')
def ping():
    """Эндпоинт для keep-alive"""
    return jsonify({"status": "pong", "timestamp": time.time()})

@app.route('/webhook', methods=['POST'])
def webhook():
    """Webhook для Telegram Bot API"""
    try:
        data = request.get_json()
        logger.info(f"Webhook received: {data}")
        
        # Обрабатываем webhook через aiogram
        asyncio.create_task(handle_webhook(data))
        
        return jsonify({"status": "ok", "message": "Webhook received successfully"})
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/status')
def status():
    """Статус сервиса"""
    return jsonify({
        "service": "running",
        "bot": "running",
        "timestamp": time.time(),
        "environment": {
            "bot_token_set": bool(BOT_TOKEN),
            "bot_token_type": "TELEGRAM_BOT_TOKEN" if os.getenv('TELEGRAM_BOT_TOKEN') else "BOT_TOKEN" if os.getenv('BOT_TOKEN') else "none"
        }
    })

async def handle_webhook(data):
    """Обработка webhook данных"""
    try:
        # Создаем объект Update из данных webhook
        from aiogram.types import Update
        update = Update(**data)
        
        # Обрабатываем через диспетчер
        await dp.feed_update(bot, update)
        
    except Exception as e:
        logger.error(f"Error handling webhook: {e}")

# === KEEP ALIVE ===

def keep_alive():
    """Функция для поддержания активности веб-сервиса на Render"""
    while True:
        try:
            webhook_url = os.getenv('WEBHOOK_URL')
            if webhook_url:
                base_url = webhook_url.replace('/webhook', '')
                ping_url = f"{base_url}/ping"
                import requests
                response = requests.get(ping_url, timeout=10)
                logger.info(f"Keep-alive ping sent: {response.status_code}")
            else:
                logger.info("WEBHOOK_URL not set, skipping keep-alive")
        except Exception as e:
            logger.error(f"Keep-alive error: {e}")
        time.sleep(20)

def start_keep_alive():
    """Запускает keep-alive в отдельном потоке"""
    keep_alive_thread = threading.Thread(target=keep_alive, daemon=True)
    keep_alive_thread.start()
    logger.info("Keep-alive thread started")

# === TELEGRAM BOT COMMANDS ===

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
    logger.info(f"✅ Пользователь {user_id} ({user_name}) запустил бота")

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
    logger.info(f"✅ Пользователь {message.from_user.id} запросил помощь")

@dp.message(Command("search"))
async def cmd_search(message: types.Message):
    """Команда /search для поиска музыки"""
    await message.answer("🔍 Введите название трека или исполнителя для поиска:")
    logger.info(f"✅ Пользователь {message.from_user.id} запустил поиск")

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
    logger.info(f"✅ Пользователь {user_id} просмотрел свою музыку")

@dp.message()
async def handle_message(message: types.Message):
    """Обработка всех сообщений"""
    user_id = str(message.from_user.id)
    text = message.text
    
    # Проверка антиспама
    current_time = time.time()
    if user_id in user_last_request:
        time_diff = current_time - user_last_request[user_id]
        if time_diff < 1.0:  # 1 секунда между запросами
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
        logger.error(f"❌ Ошибка обработки URL {url}: {e}")
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
        
        logger.info(f"✅ Пользователь {user_id} добавил YouTube трек")
        
    except Exception as e:
        logger.error(f"❌ Ошибка YouTube: {e}")
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
        
        logger.info(f"✅ Пользователь {user_id} добавил SoundCloud трек")
        
    except Exception as e:
        logger.error(f"❌ Ошибка SoundCloud: {e}")
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
        logger.info(f"✅ Пользователь {user_id} искал: {query}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка поиска: {e}")
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
    
    logger.info(f"✅ Пользователь {user_id} добавил аудио файл")

async def main():
    """Главная функция бота"""
    logger.info("🚀 Запуск Music Bot...")
    
    try:
        # Запускаем keep-alive
        start_keep_alive()
        
        # Получаем порт из переменной окружения (для Render)
        port = int(os.environ.get('PORT', 5000))
        
        logger.info(f"Starting Flask app on port {port}")
        logger.info("Keep-alive service started")
        
        # Запускаем Flask в отдельном потоке
        def run_flask():
            app.run(host='0.0.0.0', port=port, debug=False)
        
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        
        # Запускаем бота
        logger.info("✅ Бот запущен успешно!")
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        raise

def signal_handler(signum, frame):
    """Обработчик сигналов для корректного завершения"""
    logger.info("🛑 Получен сигнал завершения, останавливаю бота...")
    sys.exit(0)

if __name__ == "__main__":
    # Регистрируем обработчики сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Запускаем бота
    asyncio.run(main())
