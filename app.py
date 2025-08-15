import os
import logging
from flask import Flask, request, jsonify
import threading
import time

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
        "message": "Telegram Music Bot is running on Render"
    })

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "timestamp": time.time(),
        "bot_status": "running" if bot_running else "stopped"
    })

@app.route('/start_bot', methods=['POST'])
def start_bot():
    global bot_thread, bot_running
    
    if bot_running:
        return jsonify({"status": "already_running", "message": "Bot is already running"})
    
    try:
        # Импортируем и запускаем бота в отдельном потоке
        from music_bot import main
        bot_thread = threading.Thread(target=main, daemon=True)
        bot_thread.start()
        bot_running = True
        
        logger.info("Bot started successfully")
        return jsonify({"status": "started", "message": "Bot started successfully"})
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/stop_bot', methods=['POST'])
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
        "bot_thread_alive": bot_thread.is_alive() if bot_thread else False
    })

if __name__ == '__main__':
    # Автоматически запускаем бота при старте приложения
    try:
        from music_bot import main
        bot_thread = threading.Thread(target=main, daemon=True)
        bot_thread.start()
        bot_running = True
        logger.info("Bot started automatically")
    except Exception as e:
        logger.error(f"Failed to start bot automatically: {e}")
    
    # Запускаем Flask приложение
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
