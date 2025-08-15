from flask import Flask, request, jsonify
import os
import threading
import time
from keep_alive import start_keep_alive

app = Flask(__name__)

# Глобальная переменная для хранения состояния бота
bot_running = False
bot_thread = None

@app.route('/')
def home():
    """Главная страница"""
    return jsonify({
        "status": "Telegram Music Bot Service",
        "bot_status": "running" if bot_running else "stopped",
        "message": "Service is active and responding"
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
        print(f"Webhook received: {data}")
        
        # Здесь будет логика обработки сообщений от Telegram
        # Пока просто возвращаем успешный ответ
        
        return jsonify({"status": "ok"})
    except Exception as e:
        print(f"Webhook error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/start_bot', methods=['POST'])
def start_bot():
    """Запуск бота"""
    global bot_running, bot_thread
    
    if bot_running:
        return jsonify({"status": "already_running"})
    
    try:
        # Импортируем и запускаем бота в отдельном потоке
        import music_bot
        bot_thread = threading.Thread(target=music_bot.main, daemon=True)
        bot_thread.start()
        bot_running = True
        
        return jsonify({"status": "started"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/stop_bot', methods=['POST'])
def stop_bot():
    """Остановка бота"""
    global bot_running, bot_thread
    
    if not bot_running:
        return jsonify({"status": "not_running"})
    
    try:
        # Останавливаем бота
        bot_running = False
        # Здесь можно добавить логику остановки бота
        
        return jsonify({"status": "stopped"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/status')
def status():
    """Статус сервиса"""
    return jsonify({
        "service": "running",
        "bot": "running" if bot_running else "stopped",
        "timestamp": time.time()
    })

if __name__ == '__main__':
    # Запускаем keep-alive
    start_keep_alive()
    
    # Получаем порт из переменной окружения (для Render)
    port = int(os.environ.get('PORT', 5000))
    
    print(f"Starting Flask app on port {port}")
    print("Keep-alive service started")
    
    # Запускаем Flask приложение
    app.run(host='0.0.0.0', port=port, debug=False)
