from flask import Flask, request, jsonify
import os
import logging
import asyncio
import threading
from simple_music_bot import bot, dp, main_worker

app = Flask(__name__)

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Глобальная переменная для хранения потока бота
bot_thread = None

@app.route('/')
def home():
    """Главная страница"""
    return """
    <html>
        <head>
            <title>🎵 Простой Музыкальный Бот</title>
            <meta charset="utf-8">
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
                .container { max-width: 800px; margin: 0 auto; background: rgba(255,255,255,0.1); padding: 30px; border-radius: 15px; backdrop-filter: blur(10px); }
                h1 { text-align: center; color: #fff; margin-bottom: 30px; }
                .status { background: rgba(0,0,0,0.2); padding: 20px; border-radius: 10px; margin: 20px 0; }
                .feature { background: rgba(255,255,255,0.1); padding: 15px; border-radius: 8px; margin: 10px 0; }
                .emoji { font-size: 24px; margin-right: 10px; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🎵 Простой Музыкальный Бот</h1>
                
                <div class="status">
                    <h2>📊 Статус сервиса</h2>
                    <p><strong>Статус:</strong> ✅ Работает</p>
                    <p><strong>Версия:</strong> 1.0 (Упрощенная)</p>
                    <p><strong>Платформа:</strong> Render</p>
                </div>
                
                <div class="feature">
                    <h3><span class="emoji">🔍</span>Поиск музыки</h3>
                    <p>Ищите треки по названию на YouTube</p>
                </div>
                
                <div class="feature">
                    <h3><span class="emoji">🌨️</span>Моя музыка</h3>
                    <p>Сохраняйте и управляйте своей коллекцией треков</p>
                </div>
                
                <div class="feature">
                    <h3><span class="emoji">🎤</span>По исполнителям</h3>
                    <p>Находите треки конкретных исполнителей</p>
                </div>
                
                <div class="status">
                    <h2>🔧 Техническая информация</h2>
                    <p><strong>Фреймворк:</strong> aiogram 3.x</p>
                    <p><strong>Загрузка:</strong> yt-dlp + FFmpeg</p>
                    <p><strong>Формат:</strong> MP3 (192 kbps)</p>
                    <p><strong>Автоочистка:</strong> ✅ Включена</p>
                </div>
            </div>
        </body>
    </html>
    """

@app.route('/health')
def health():
    """Проверка здоровья сервиса"""
    try:
        return jsonify({
            "status": "healthy",
            "service": "Simple Music Bot",
            "version": "1.0",
            "platform": "Render"
        }), 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e)
        }), 500

@app.route('/bot_status')
def bot_status():
    """Статус бота"""
    try:
        bot_info = {
            "bot_id": bot.id if bot else None,
            "bot_username": bot.username if bot else None,
            "dispatcher_ready": dp is not None,
            "thread_running": bot_thread and bot_thread.is_alive() if bot_thread else False
        }
        return jsonify(bot_info), 200
    except Exception as e:
        logger.error(f"Bot status check failed: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/webhook', methods=['POST'])
def webhook():
    """Webhook для Telegram"""
    try:
        # Получаем данные от Telegram
        update_data = request.get_json()
        
        if not update_data:
            logger.warning("Empty webhook data received")
            return "OK", 200
        
        # Логируем входящие обновления
        logger.info(f"Webhook received: {update_data.get('update_id', 'unknown')}")
        
        # Обрабатываем обновление асинхронно
        asyncio.run(process_webhook_update(update_data))
        
        return "OK", 200
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return "Error", 500

async def process_webhook_update(update_data):
    """Обрабатывает webhook обновление"""
    try:
        # Передаем обновление в диспетчер бота
        await dp.feed_webhook_update(bot, update_data)
        logger.info(f"Webhook update processed: {update_data.get('update_id', 'unknown')}")
    except Exception as e:
        logger.error(f"Error processing webhook update: {e}")

def start_bot_in_thread():
    """Запускает бота в отдельном потоке"""
    global bot_thread
    
    def run_bot():
        try:
            logger.info("Starting bot in worker thread...")
            asyncio.run(main_worker())
        except Exception as e:
            logger.error(f"Bot thread error: {e}")
    
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    logger.info("Bot thread started")

@app.before_first_request
def initialize_bot():
    """Инициализирует бота при первом запросе"""
    try:
        logger.info("Initializing bot...")
        start_bot_in_thread()
        logger.info("Bot initialization completed")
    except Exception as e:
        logger.error(f"Bot initialization failed: {e}")

if __name__ == '__main__':
    # Проверяем переменные окружения
    bot_token = os.getenv('BOT_TOKEN')
    if not bot_token:
        logger.error("BOT_TOKEN not set!")
        exit(1)
    
    logger.info("Starting Simple Music Bot web server...")
    
    # Запускаем бота в отдельном потоке
    start_bot_in_thread()
    
    # Запускаем Flask сервер
    port = int(os.getenv('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False)
