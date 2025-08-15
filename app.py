import os
import logging
from flask import Flask, request, jsonify
import threading
import time
import asyncio

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Глобальная переменная для хранения потока бота
bot_thread = None
bot_running = False

@app.route('/')
def home():
    return jsonify({
        "status": "running",
        "bot_status": "running" if bot_running else "stopped",
        "message": "Telegram Music Bot is running on Render",
        "endpoints": {
            "home": "/",
            "health": "/health",
            "status": "/status",
            "bot_status": "/bot_status",
            "start_bot": "/start_bot (GET/POST)",
            "stop_bot": "/stop_bot (GET/POST)"
        }
    })

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "timestamp": time.time(),
        "bot_status": "running" if bot_running else "stopped"
    })

@app.route('/status')
def status():
    """Алиас для /health для совместимости"""
    return health()

@app.route('/webhook', methods=['POST'])
def webhook():
    """Webhook endpoint для Telegram Bot API"""
    try:
        # Получаем обновление от Telegram
        update = request.get_json()
        
        # Логируем полученное обновление
        logger.info(f"Received webhook update: {update.get('update_id', 'unknown')}")
        
        # Обрабатываем обновление через диспетчер бота
        if bot_thread and bot_running:
            try:
                # Импортируем диспетчер и обрабатываем обновление
                from music_bot import dp
                import asyncio
                
                # Создаем новый event loop для обработки
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # Обрабатываем обновление
                loop.run_until_complete(dp.feed_webhook_update(bot, update))
                loop.close()
                
                logger.info(f"Update {update.get('update_id', 'unknown')} processed successfully")
            except Exception as e:
                logger.error(f"Error processing update: {e}")
        
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

def run_bot_in_thread():
    """Запускает бота в отдельном потоке с правильной обработкой асинхронности"""
    try:
        # Создаем новый event loop для этого потока
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Импортируем и запускаем бота через main_worker (без polling)
        from music_bot import main_worker
        loop.run_until_complete(main_worker())
    except Exception as e:
        logger.error(f"Bot thread error: {e}")
    finally:
        try:
            loop.close()
        except:
            pass

@app.route('/start_bot', methods=['GET', 'POST'])
def start_bot():
    global bot_thread, bot_running
    
    if bot_running:
        return jsonify({"status": "already_running", "message": "Bot is already running"})
    
    try:
        # Запускаем бота в отдельном потоке с правильной обработкой асинхронности
        bot_thread = threading.Thread(target=run_bot_in_thread, daemon=True)
        bot_thread.start()
        bot_running = True
        
        logger.info("Bot started successfully")
        return jsonify({"status": "started", "message": "Bot started successfully"})
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/stop_bot', methods=['GET', 'POST'])
def stop_bot():
    global bot_running
    
    if not bot_running:
        return jsonify({"status": "not_running", "message": "Bot is not running"})
    
    # Останавливаем бота (устанавливаем флаг)
    bot_running = False
    logger.info("Bot stop requested")
    return jsonify({"status": "stopped", "message": "Bot stop requested"})

@app.route('/bot_status')
def bot_status():
    return jsonify({
        "bot_running": bot_running,
        "bot_thread_alive": bot_thread.is_alive() if bot_thread else False,
        "timestamp": time.time()
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "error": "Endpoint not found",
        "available_endpoints": {
            "home": "/",
            "health": "/health", 
            "status": "/status",
            "bot_status": "/bot_status",
            "start_bot": "/start_bot (GET/POST)",
            "stop_bot": "/stop_bot (GET/POST)"
        }
    }), 404

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({
        "error": "Method not allowed",
        "message": "This endpoint supports both GET and POST methods",
        "endpoint": request.endpoint
    }), 405

if __name__ == '__main__':
    # Автоматически запускаем бота при старте приложения
    try:
        bot_thread = threading.Thread(target=run_bot_in_thread, daemon=True)
        bot_thread.start()
        bot_running = True
        logger.info("Bot started automatically")
    except Exception as e:
        logger.error(f"Failed to start bot automatically: {e}")
    
    # Запускаем Flask приложение
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
