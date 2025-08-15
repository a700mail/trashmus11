import os
import logging
import requests
from flask import Flask, request, jsonify
import threading
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
import queue
import weakref

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# === ОПТИМИЗИРОВАННЫЕ НАСТРОЙКИ ===
MAX_WORKERS = 4  # Оптимизированное количество воркеров
REQUEST_TIMEOUT = 30  # Таймаут для HTTP запросов
HEALTH_CHECK_INTERVAL = 60  # Интервал проверки здоровья (секунды)
WEBHOOK_QUEUE_SIZE = 1000  # Размер очереди webhook обновлений

# === ГЛОБАЛЬНЫЕ ОБЪЕКТЫ ===
bot_thread = None
bot_running = False
webhook_queue = queue.Queue(maxsize=WEBHOOK_QUEUE_SIZE)
webhook_processor_thread = None
health_check_thread = None

# === ОПТИМИЗИРОВАННЫЕ ПУЛЫ ПОТОКОВ ===
webhook_executor = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="webhook_worker")
health_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="health_worker")

# === КЭШИРОВАНИЕ ===
response_cache = {}
cache_ttl = 300  # 5 минут TTL для кэша

def get_cached_response(key: str):
    """Получает кэшированный ответ"""
    if key in response_cache:
        timestamp, response = response_cache[key]
        if time.time() - timestamp < cache_ttl:
            return response
        else:
            del response_cache[key]
    return None

def set_cached_response(key: str, response):
    """Устанавливает кэшированный ответ"""
    response_cache[key] = (time.time(), response)
    
    # Очищаем старые записи кэша
    if len(response_cache) > 100:
        current_time = time.time()
        expired_keys = [
            k for k, (ts, _) in response_cache.items()
            if current_time - ts > cache_ttl
        ]
        for k in expired_keys:
            del response_cache[k]

@app.route('/')
def home():
    """Оптимизированный домашний endpoint с кэшированием"""
    cache_key = "home_response"
    cached = get_cached_response(cache_key)
    if cached:
        return cached
    
    response = jsonify({
        "status": "running",
        "bot_status": "running" if bot_running else "stopped",
        "message": "Telegram Music Bot is running on Render (Optimized)",
        "endpoints": {
            "home": "/",
            "health": "/health",
            "status": "/status",
            "bot_status": "/bot_status",
            "start_bot": "/start_bot (GET/POST)",
            "stop_bot": "/stop_bot (GET/POST)"
        },
        "optimizations": {
            "max_workers": MAX_WORKERS,
            "webhook_queue_size": WEBHOOK_QUEUE_SIZE,
            "cache_ttl": cache_ttl
        }
    })
    
    set_cached_response(cache_key, response)
    return response

@app.route('/health')
def health():
    """Оптимизированный health check"""
    cache_key = f"health_{int(time.time() // 10)}"  # Кэш на 10 секунд
    cached = get_cached_response(cache_key)
    if cached:
        return cached
    
    response = jsonify({
        "status": "healthy",
        "timestamp": time.time(),
        "bot_status": "running" if bot_running else "stopped",
        "system_info": {
            "webhook_queue_size": webhook_queue.qsize(),
            "active_workers": len(webhook_executor._threads) if hasattr(webhook_executor, '_threads') else 0,
            "cache_size": len(response_cache)
        }
    })
    
    set_cached_response(cache_key, response)
    return response

@app.route('/status')
def status():
    """Алиас для /health для совместимости"""
    return health()

@app.route('/webhook', methods=['POST'])
def webhook():
    """Оптимизированный webhook endpoint"""
    try:
        # Получаем обновление от Telegram
        update = request.get_json()
        
        if not update:
            return jsonify({"status": "error", "message": "Empty update"}), 400
        
        # Логируем полученное обновление
        update_id = update.get('update_id', 'unknown')
        logger.info(f"Received webhook update: {update_id}")
        
        # Проверяем статус бота
        if not bot_running:
            logger.warning(f"Bot not running, attempting auto-start for update {update_id}")
            try:
                start_bot()
                logger.info("Bot started automatically from webhook")
            except Exception as e:
                logger.error(f"Failed to start bot automatically: {e}")
                return jsonify({"status": "error", "message": "Bot not ready"}), 503
        
        # Добавляем в очередь для асинхронной обработки
        try:
            webhook_queue.put_nowait(update)
            logger.info(f"Update {update_id} queued for processing")
        except queue.Full:
            logger.warning(f"Webhook queue full, dropping update {update_id}")
            return jsonify({"status": "warning", "message": "Queue full"}), 429
        
        return jsonify({"status": "ok", "queued": True})
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

def process_webhook_update(update_data: dict):
    """Обрабатывает webhook обновление в отдельном потоке"""
    try:
        # Импортируем функцию для обработки webhook обновлений
        from music_bot_optimized import process_webhook_update as bot_process_webhook
        
        # Создаем новый event loop для этого потока
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Обрабатываем обновление
            result = loop.run_until_complete(bot_process_webhook(update_data))
            logger.info(f"Update {update_data.get('update_id', 'unknown')} processed: {result}")
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Error processing webhook update: {e}")

def webhook_processor():
    """Фоновый процессор webhook обновлений"""
    logger.info("🔄 Starting webhook processor...")
    
    while bot_running:
        try:
            # Получаем обновление из очереди с таймаутом
            try:
                update_data = webhook_queue.get(timeout=1.0)
            except queue.Empty:
                continue
            
            if update_data:
                # Обрабатываем обновление в отдельном потоке
                webhook_executor.submit(process_webhook_update, update_data)
                
        except Exception as e:
            logger.error(f"Error in webhook processor: {e}")
            time.sleep(1)  # Небольшая пауза при ошибке
    
    logger.info("🔄 Webhook processor stopped")

def run_bot_in_thread():
    """Запускает бота в отдельном потоке с оптимизацией"""
    logger.info("🚀 Starting optimized bot thread...")
    try:
        # Создаем новый event loop для этого потока
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        logger.info("✅ Event loop created for bot thread")
        
        # Импортируем и запускаем бота
        logger.info("📥 Importing main from music_bot_optimized...")
        from music_bot_optimized import main
        logger.info("✅ main imported successfully")
        
        logger.info("🚀 Starting main...")
        loop.run_until_complete(main())
        logger.info("✅ main completed")
        
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
    """Запуск бота с оптимизацией"""
    global bot_thread, bot_running, webhook_processor_thread
    
    if bot_running:
        return jsonify({"status": "already_running", "message": "Bot is already running"})
    
    try:
        # Запускаем бота в отдельном потоке
        bot_thread = threading.Thread(target=run_bot_in_thread, daemon=True)
        bot_thread.start()
        bot_running = True
        
        # Запускаем процессор webhook обновлений
        webhook_processor_thread = threading.Thread(target=webhook_processor, daemon=True)
        webhook_processor_thread.start()
        
        logger.info("Bot started successfully with webhook processor")
        return jsonify({"status": "started", "message": "Bot started successfully"})
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/stop_bot', methods=['GET', 'POST'])
def stop_bot():
    """Остановка бота"""
    global bot_running
    
    if not bot_running:
        return jsonify({"status": "not_running", "message": "Bot is not running"})
    
    # Останавливаем бота
    bot_running = False
    logger.info("Bot stop requested")
    return jsonify({"status": "stopped", "message": "Bot stop requested"})

@app.route('/bot_status')
def bot_status():
    """Статус бота с детальной информацией"""
    cache_key = f"bot_status_{int(time.time() // 30)}"  # Кэш на 30 секунд
    cached = get_cached_response(cache_key)
    if cached:
        return cached
    
    response = jsonify({
        "bot_running": bot_running,
        "bot_thread_alive": bot_thread.is_alive() if bot_thread else False,
        "webhook_processor_alive": webhook_processor_thread.is_alive() if webhook_processor_thread else False,
        "webhook_queue_size": webhook_queue.qsize(),
        "active_workers": len(webhook_executor._threads) if hasattr(webhook_executor, '_threads') else 0,
        "timestamp": time.time()
    })
    
    set_cached_response(cache_key, response)
    return response

def health_check_worker():
    """Фоновый воркер для проверки здоровья"""
    logger.info("💓 Starting health check worker...")
    
    while True:
        try:
            time.sleep(HEALTH_CHECK_INTERVAL)
            
            # Проверяем собственный health endpoint
            try:
                response = requests.get("http://localhost:10000/health", timeout=REQUEST_TIMEOUT)
                if response.status_code == 200:
                    logger.info("💓 Health check - бот активен")
                else:
                    logger.warning(f"⚠️ Health check вернул статус: {response.status_code}")
            except Exception as e:
                logger.warning(f"⚠️ Health check не удался: {e}")
                
        except Exception as e:
            logger.error(f"❌ Ошибка в health check worker: {e}")
            time.sleep(10)

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

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({
        "error": "Internal server error",
        "message": "Something went wrong on our end"
    }), 500

def cleanup_resources():
    """Очистка ресурсов при завершении"""
    try:
        logger.info("🧹 Cleaning up resources...")
        
        # Останавливаем исполнители
        webhook_executor.shutdown(wait=True)
        health_executor.shutdown(wait=True)
        
        # Очищаем кэш
        response_cache.clear()
        
        logger.info("✅ Resources cleaned up")
        
    except Exception as e:
        logger.error(f"❌ Error during cleanup: {e}")

if __name__ == '__main__':
    try:
        # Автоматически запускаем бота при старте приложения
        bot_thread = threading.Thread(target=run_bot_in_thread, daemon=True)
        bot_thread.start()
        bot_running = True
        logger.info("Bot started automatically")
        
        # Запускаем процессор webhook
        webhook_processor_thread = threading.Thread(target=webhook_processor, daemon=True)
        webhook_processor_thread.start()
        logger.info("Webhook processor started automatically")
        
        # Запускаем health check в отдельном потоке
        health_check_thread = threading.Thread(target=health_check_worker, daemon=True)
        health_check_thread.start()
        logger.info("Health check worker started automatically")
        
        # Регистрируем обработчик для очистки ресурсов
        import atexit
        atexit.register(cleanup_resources)
        
    except Exception as e:
        logger.error(f"Failed to start services automatically: {e}")
    
    # Запускаем Flask приложение
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
