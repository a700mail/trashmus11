import os
import logging
import requests
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
            "keep_alive_manual": "/keep_alive_manual (GET/POST)",
            "start_bot": "/start_bot (GET/POST)",
            "stop_bot": "/stop_bot (GET/POST)"
        }
    })

@app.route('/health')
def health():
    """Улучшенный health endpoint с детальной информацией"""
    try:
        # Проверяем статус бота
        bot_alive = bot_running and bot_thread and bot_thread.is_alive()
        
        # Проверяем доступность внешних сервисов
        external_status = {}
        external_services = [
            "https://httpbin.org/get",
            "https://api.github.com",
            "https://www.google.com"
        ]
        
        for service in external_services:
            try:
                response = requests.get(service, timeout=3)
                external_status[service] = {
                    "status": "healthy",
                    "response_time": response.elapsed.total_seconds(),
                    "status_code": response.status_code
                }
            except Exception as e:
                external_status[service] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
        
        return jsonify({
            "status": "healthy",
            "timestamp": time.time(),
            "bot_status": "running" if bot_alive else "stopped",
            "bot_thread_alive": bot_thread.is_alive() if bot_thread else False,
            "external_services": external_status,
            "uptime": time.time() - (getattr(app, '_start_time', time.time())),
            "memory_usage": "N/A"  # Можно добавить psutil для мониторинга памяти
        })
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": time.time()
        }), 500

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
        
        # Проверяем статус бота
        logger.info(f"Bot status: bot_thread={bot_thread}, bot_running={bot_running}")
        
        # Обрабатываем обновление через диспетчер бота
        if bot_thread and bot_running:
            try:
                # Импортируем функцию для обработки webhook обновлений
                from music_bot import process_webhook_update
                import asyncio
                
                # Используем существующий event loop из потока бота для ускорения
                # Передаем обновление в очередь бота без создания нового loop
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(process_webhook_update(update))
                loop.close()
                
                logger.info(f"Update {update.get('update_id', 'unknown')} queued for processing")
                
            except Exception as e:
                logger.error(f"Error processing update: {e}")
        else:
            logger.warning(f"Bot not ready: bot_thread={bot_thread}, bot_running={bot_running}")
            # Попробуем запустить бота автоматически
            if not bot_running:
                logger.info("Attempting to start bot automatically...")
                try:
                    start_bot()
                    logger.info("Bot started automatically from webhook")
                except Exception as e:
                    logger.error(f"Failed to start bot automatically: {e}")
        
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

def run_bot_in_thread():
    """Запускает бота в отдельном потоке с правильной обработкой асинхронности"""
    logger.info("🚀 Starting bot thread...")
    try:
        # Создаем новый event loop для этого потока
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        logger.info("✅ Event loop created for bot thread")
        
        # Импортируем и запускаем бота через main_worker (без polling)
        logger.info("📥 Importing main_worker from music_bot...")
        from music_bot import main_worker
        logger.info("✅ main_worker imported successfully")
        
        logger.info("🚀 Starting main_worker...")
        loop.run_until_complete(main_worker())
        logger.info("✅ main_worker completed")
    except Exception as e:
        logger.error(f"❌ Bot thread error: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
    finally:
        try:
            loop.close()
            logger.info("✅ Event loop closed")
        except Exception as e:
            logger.error(f"❌ Error closing event loop: {e}")

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
    """Детальный статус бота"""
    return jsonify({
        "bot_running": bot_running,
        "bot_thread_alive": bot_thread.is_alive() if bot_thread else False,
        "timestamp": time.time(),
        "uptime": time.time() - (getattr(app, '_start_time', time.time())),
        "keep_alive_active": True
    })

@app.route('/keep_alive_manual', methods=['GET', 'POST'])
def keep_alive_manual():
    """Принудительный keep alive для внешних мониторингов"""
    try:
        current_time = time.strftime("%H:%M:%S")
        logger.info(f"🔧 [{current_time}] Принудительный keep alive вызван")
        
        # Проверяем статус бота
        bot_alive = bot_running and bot_thread and bot_thread.is_alive()
        
        # Делаем внешний ping
        external_ping_success = False
        try:
            response = requests.get("https://httpbin.org/get", timeout=5)
            if response.status_code == 200:
                external_ping_success = True
                logger.info(f"🌐 [{current_time}] Внешний ping успешен")
        except Exception as e:
            logger.warning(f"⚠️ [{current_time}] Внешний ping не удался: {e}")
        
        return jsonify({
            "status": "keep_alive_triggered",
            "timestamp": time.time(),
            "bot_alive": bot_alive,
            "external_ping_success": external_ping_success,
            "message": f"Keep alive выполнен в {current_time}"
        })
    except Exception as e:
        logger.error(f"❌ Ошибка в принудительном keep alive: {e}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "timestamp": time.time()
        }), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "error": "Endpoint not found",
        "available_endpoints": {
            "home": "/",
            "health": "/health", 
            "status": "/status",
            "bot_status": "/bot_status",
            "keep_alive_manual": "/keep_alive_manual (GET/POST)",
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

def keep_alive():
    """Улучшенная Keep alive функция для предотвращения засыпания Render"""
    global bot_running, bot_thread
    
    logger.info("🚀 Keep alive запущен")
    
    # Счетчики для мониторинга
    ping_count = 0
    error_count = 0
    
    while True:
        try:
            ping_count += 1
            current_time = time.strftime("%H:%M:%S")
            
            # 1. Внутренний health check
            try:
                response = requests.get("http://localhost:10000/health", timeout=3)
                if response.status_code == 200:
                    logger.info(f"💓 [{current_time}] Keep alive #{ping_count} - бот активен")
                else:
                    logger.warning(f"⚠️ [{current_time}] Health check вернул статус: {response.status_code}")
            except Exception as e:
                logger.warning(f"⚠️ [{current_time}] Health check не удался: {e}")
            
            # 2. Внешний ping для предотвращения засыпания
            try:
                # Пингуем внешние сервисы для активности
                external_services = [
                    "https://httpbin.org/get",
                    "https://api.github.com",
                    "https://www.google.com"
                ]
                
                for service in external_services:
                    try:
                        response = requests.get(service, timeout=5)
                        if response.status_code in [200, 301, 302]:
                            logger.info(f"🌐 [{current_time}] Внешний ping успешен: {service}")
                            break
                    except Exception:
                        continue
                        
            except Exception as e:
                logger.warning(f"⚠️ [{current_time}] Внешний ping не удался: {e}")
            
            # 3. Проверяем статус бота
            if bot_running and bot_thread and bot_thread.is_alive():
                logger.info(f"🤖 [{current_time}] Бот активен и работает")
            else:
                logger.warning(f"⚠️ [{current_time}] Бот неактивен, попытка перезапуска")
                try:
                    # Попытка перезапуска бота
                    bot_running = False
                    time.sleep(2)
                    bot_thread_new = threading.Thread(target=run_bot_in_thread, daemon=True)
                    bot_thread_new.start()
                    bot_running = True
                    bot_thread = bot_thread_new  # Обновляем глобальную переменную
                    logger.info(f"🔄 [{current_time}] Бот перезапущен")
                except Exception as restart_error:
                    logger.error(f"❌ [{current_time}] Ошибка перезапуска бота: {restart_error}")
            
            # 4. Сброс счетчика ошибок при успешном выполнении
            if error_count > 0:
                logger.info(f"✅ [{current_time}] Сброс счетчика ошибок (было: {error_count})")
                error_count = 0
            
            # Ждем 25 секунд до следующего keep alive (более частые пинги)
            time.sleep(25)
            
        except Exception as e:
            error_count += 1
            current_time = time.strftime("%H:%M:%S")
            logger.error(f"❌ [{current_time}] Ошибка в keep alive #{error_count}: {e}")
            
            # При накоплении ошибок увеличиваем интервал
            if error_count > 5:
                logger.warning(f"⚠️ [{current_time}] Много ошибок, увеличиваю интервал до 60 сек")
                time.sleep(60)
            else:
                time.sleep(10)

if __name__ == '__main__':
    # Записываем время старта приложения
    app._start_time = time.time()
    logger.info(f"🚀 Приложение запущено в {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Автоматически запускаем бота при старте приложения
    try:
        bot_thread = threading.Thread(target=run_bot_in_thread, daemon=True)
        bot_thread.start()
        bot_running = True
        logger.info("🤖 Бот запущен автоматически")
    except Exception as e:
        logger.error(f"❌ Не удалось запустить бота автоматически: {e}")
    
    # Запускаем keep alive в отдельном потоке
    try:
        keep_alive_thread = threading.Thread(target=keep_alive, daemon=True)
        keep_alive_thread.start()
        logger.info("💓 Keep alive запущен автоматически")
    except Exception as e:
        logger.error(f"❌ Не удалось запустить keep alive автоматически: {e}")
    
    # Запускаем Flask приложение
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"🌐 Flask приложение запускается на порту {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
