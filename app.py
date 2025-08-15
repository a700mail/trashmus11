from flask import Flask, request, jsonify
import os
import threading
import time
from keep_alive import start_keep_alive

app = Flask(__name__)

# Глобальная переменная для хранения состояния бота
bot_running = False
bot_thread = None

# Функция для получения токена бота
def get_bot_token():
    """Получает токен бота из переменных окружения"""
    return os.getenv('TELEGRAM_BOT_TOKEN') or os.getenv('BOT_TOKEN')

@app.route('/')
def home():
    """Главная страница"""
    return jsonify({
        "status": "Telegram Music Bot Service",
        "bot_status": "running" if bot_running else "stopped",
        "message": "Service is active and responding",
        "features": [
            "YouTube music download",
            "SoundCloud support", 
            "Payment processing",
            "Premium features"
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
        print(f"Webhook received: {data}")
        
        # Проверяем, что бот запущен
        if not bot_running:
            return jsonify({"status": "error", "message": "Bot is not running"}), 500
        
        # Здесь будет логика обработки сообщений от Telegram
        # Пока просто возвращаем успешный ответ
        
        # TODO: Добавить обработку сообщений от Telegram
        # Это потребует интеграции с aiogram в синхронном режиме
        
        return jsonify({"status": "ok", "message": "Webhook received successfully"})
    except Exception as e:
        print(f"Webhook error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/start_bot', methods=['POST', 'GET'])
def start_bot():
    """Запуск бота"""
    global bot_running, bot_thread
    
    if bot_running:
        return jsonify({"status": "already_running"})
    
    try:
        print("🔄 Попытка запуска бота...")
        
        # Проверяем переменные окружения
        bot_token = get_bot_token()
        print(f"🔑 Токен бота: {'установлен' if bot_token else 'НЕ установлен'}")
        
        # Запускаем web_service.py в отдельном процессе
        print("🚀 Запускаем web_service.py...")
        import subprocess
        import sys
        
        # Запускаем web_service.py в фоновом режиме
        process = subprocess.Popen([
            sys.executable, 'web_service.py'
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Сохраняем процесс для возможности остановки
        bot_thread = process
        bot_running = True
        
        print("🎉 Бот успешно запущен в отдельном процессе!")
        
        return jsonify({
            "status": "started", 
            "message": "Bot started successfully in separate process",
            "process_id": process.pid
        })
        
    except Exception as e:
        print(f"❌ Критическая ошибка при запуске бота: {e}")
        import traceback
        print(f"📋 Traceback: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e), "traceback": traceback.format_exc()}), 500

@app.route('/stop_bot', methods=['POST', 'GET'])
def stop_bot():
    """Остановка бота"""
    global bot_running, bot_thread
    
    if not bot_running:
        return jsonify({"status": "not_running"})
    
    try:
        # Останавливаем процесс бота
        if bot_thread and hasattr(bot_thread, 'terminate'):
            bot_thread.terminate()
            bot_thread.wait(timeout=5)  # Ждем завершения процесса
            print("✅ Процесс бота остановлен")
        
        bot_running = False
        return jsonify({"status": "stopped", "message": "Bot process terminated"})
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/status')
def status():
    """Статус сервиса"""
    bot_token = get_bot_token()
    return jsonify({
        "service": "running",
        "bot": "running" if bot_running else "stopped",
        "timestamp": time.time(),
        "environment": {
            "bot_token_set": bool(bot_token),
            "bot_token_type": "TELEGRAM_BOT_TOKEN" if os.getenv('TELEGRAM_BOT_TOKEN') else "BOT_TOKEN" if os.getenv('BOT_TOKEN') else "none",
            "payment_token_set": bool(os.getenv('PAYMENT_PROVIDER_TOKEN')),
            "yoomoney_configured": all([
                os.getenv('YOOMONEY_CLIENT_ID'),
                os.getenv('YOOMONEY_CLIENT_SECRET'),
                os.getenv('YOOMONEY_ACCOUNT')
            ])
        }
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
