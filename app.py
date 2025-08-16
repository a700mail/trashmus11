import os
import logging
import requests
from flask import Flask, request, jsonify
import threading
import time
import asyncio
import aiohttp
import signal
import sys

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Глобальные переменные для управления потоками
bot_thread = None
bot_running = False
keep_alive_thread = None
shutdown_event = threading.Event()

# Graceful shutdown handler
def signal_handler(signum, frame):
    """Обработчик сигналов для graceful shutdown"""
    logger.info(f"📴 Получен сигнал {signum}, начинаю graceful shutdown...")
    shutdown_event.set()
    
    # Останавливаем бота
    global bot_running
    bot_running = False
    
    # Ждем завершения потоков
    if bot_thread and bot_thread.is_alive():
        logger.info("⏳ Ожидаю завершения потока бота...")
        bot_thread.join(timeout=10)
    
    if keep_alive_thread and keep_alive_thread.is_alive():
        logger.info("⏳ Ожидаю завершения keep alive потока...")
        keep_alive_thread.join(timeout=5)
    
    logger.info("✅ Graceful shutdown завершен")
    sys.exit(0)

# Регистрируем обработчики сигналов
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

async def async_health_check():
    """Асинхронная проверка здоровья бота"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:10000/health", timeout=3) as response:
                if response.status == 200:
                    return True, response.status
                else:
                    return False, response.status
    except Exception as e:
        return False, str(e)

async def async_external_ping():
    """Асинхронный ping внешних сервисов"""
    external_services = [
        "https://httpbin.org/get",
        "https://api.github.com",
        "https://www.google.com"
    ]
    
    async with aiohttp.ClientSession() as session:
        for service in external_services:
            try:
                async with session.get(service, timeout=5) as response:
                    if response.status in [200, 301, 302]:
                        return True, service
            except Exception:
                continue
    
    return False, "no_services_available"

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
    """Улучшенный health endpoint для Render"""
    try:
        # Проверяем статус бота
        bot_alive = bot_running and bot_thread and bot_thread.is_alive()
        
        # Проверяем статус keep alive
        keep_alive_alive = keep_alive_thread and keep_alive_thread.is_alive()
        
        # Проверяем доступность внешних сервисов (синхронно для Render)
        external_status = {}
        external_services = [
            "https://httpbin.org/get",
            "https://api.github.com",
            "https://www.google.com"
        ]
        
        for service in external_services:
            try:
                start_time = time.time()
                response = requests.get(service, timeout=3)
                response_time = time.time() - start_time
                external_status[service] = {
                    "status": "healthy",
                    "response_time": response_time,
                    "status_code": response.status_code
                }
            except Exception as e:
                external_status[service] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
        
        # Общий статус системы
        overall_status = "healthy"
        if not bot_alive:
            overall_status = "degraded"
        if not keep_alive_alive:
            overall_status = "degraded"
        
        # Проверяем количество здоровых внешних сервисов
        healthy_services = sum(1 for s in external_status.values() if s.get("status") == "healthy")
        if healthy_services == 0:
            overall_status = "unhealthy"
        
        # Проверяем, что мы в Render
        is_render = os.environ.get('RENDER', False)
        render_info = {}
        if is_render:
            render_info = {
                "service_id": os.environ.get('RENDER_SERVICE_ID'),
                "service_url": os.environ.get('RENDER_EXTERNAL_URL'),
                "environment": os.environ.get('RENDER_ENVIRONMENT', 'production')
            }
        
        return jsonify({
            "status": overall_status,
            "timestamp": time.time(),
            "bot_status": "running" if bot_alive else "stopped",
            "bot_thread_alive": bot_thread.is_alive() if bot_thread else False,
            "keep_alive_status": "running" if keep_alive_alive else "stopped",
            "keep_alive_thread_alive": keep_alive_thread.is_alive() if keep_alive_thread else False,
            "external_services": external_status,
            "external_services_summary": {
                "total": len(external_services),
                "healthy": healthy_services,
                "unhealthy": len(external_services) - healthy_services
            },
            "uptime": time.time() - (getattr(app, '_start_time', time.time())),
            "shutdown_requested": shutdown_event.is_set(),
            "render": {
                "is_render": is_render,
                "info": render_info
            },
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
                # Если обработка не удалась, возвращаем ошибку
                return jsonify({"status": "error", "message": f"Failed to process update: {str(e)}"}), 500
        else:
            logger.warning(f"Bot not ready: bot_thread={bot_thread}, bot_running={bot_running}")
            # Попробуем запустить бота автоматически
            if not bot_running:
                logger.info("Attempting to start bot automatically...")
                try:
                    start_bot()
                    logger.info("Bot started automatically from webhook")
                    
                    # Теперь попробуем обработать обновление
                    try:
                        from music_bot import process_webhook_update
                        import asyncio
                        
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(process_webhook_update(update))
                        loop.close()
                        
                        logger.info(f"Update {update.get('update_id', 'unknown')} processed after auto-start")
                        
                    except Exception as process_error:
                        logger.error(f"Failed to process update after auto-start: {process_error}")
                        return jsonify({"status": "error", "message": f"Bot started but failed to process update: {str(process_error)}"}), 500
                        
                except Exception as e:
                    logger.error(f"Failed to start bot automatically: {e}")
                    return jsonify({"status": "error", "message": f"Failed to start bot: {str(e)}"}), 500
            else:
                return jsonify({"status": "error", "message": "Bot is starting up, please retry"}), 503
        
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

def run_bot_in_thread():
    """Запускает бота в отдельном потоке с правильной обработкой асинхронности"""
    global bot_running, shutdown_event
    
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
        
        # Запускаем main_worker с обработкой graceful shutdown
        try:
            loop.run_until_complete(main_worker())
        except KeyboardInterrupt:
            logger.info("📴 Получен сигнал прерывания в потоке бота")
        except Exception as e:
            logger.error(f"❌ Ошибка в main_worker: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
        finally:
            # Graceful shutdown для бота
            if not shutdown_event.is_set():
                logger.info("🔄 Перезапуск бота через 5 секунд...")
                time.sleep(5)
                if not shutdown_event.is_set():
                    # Рекурсивно перезапускаем бота
                    bot_thread_new = threading.Thread(target=run_bot_in_thread, daemon=True)
                    bot_thread_new.start()
                    bot_thread = bot_thread_new
                    return
        
        logger.info("✅ main_worker completed")
        
    except Exception as e:
        logger.error(f"❌ Bot thread error: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Попытка перезапуска при критических ошибках
        if not shutdown_event.is_set():
            logger.info("🔄 Попытка перезапуска бота через 10 секунд...")
            time.sleep(10)
            if not shutdown_event.is_set():
                try:
                    bot_thread_new = threading.Thread(target=run_bot_in_thread, daemon=True)
                    bot_thread_new.start()
                    bot_thread = bot_thread_new
                    logger.info("✅ Бот перезапущен после критической ошибки")
                except Exception as restart_error:
                    logger.error(f"❌ Не удалось перезапустить бота: {restart_error}")
                    bot_running = False
    finally:
        try:
            if 'loop' in locals() and loop and not loop.is_closed():
                loop.close()
                logger.info("✅ Event loop closed")
        except Exception as e:
            logger.error(f"❌ Error closing event loop: {e}")
        
        # Помечаем бота как неактивного
        bot_running = False
        logger.info("📴 Бот помечен как неактивный")

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

def render_keep_alive():
    """Агрессивный keep alive для Render - каждые 30 секунд для предотвращения засыпания"""
    global bot_running, bot_thread, shutdown_event
    
    logger.info("🚀 Агрессивный Render Keep Alive запущен (каждые 30 сек)")
    
    # Счетчики для мониторинга
    ping_count = 0
    error_count = 0
    
    while not shutdown_event.is_set():
        try:
            ping_count += 1
            current_time = time.strftime("%H:%M:%S")
            
            # 1. Простой health check
            try:
                response = requests.get("http://localhost:10000/health", timeout=3)
                if response.status_code == 200:
                    logger.info(f"💓 [{current_time}] Keep alive #{ping_count} - бот активен")
                else:
                    logger.warning(f"⚠️ [{current_time}] Health check вернул статус: {response.status_code}")
            except Exception as e:
                logger.warning(f"⚠️ [{current_time}] Health check не удался: {e}")
            
            # 2. Внешний ping для Render (предотвращает засыпание)
            try:
                external_services = [
                    "https://httpbin.org/get",
                    "https://api.github.com",
                    "https://www.google.com",
                    "https://www.cloudflare.com"
                ]
                
                external_success = False
                for service in external_services:
                    try:
                        response = requests.get(service, timeout=5)
                        if response.status_code in [200, 301, 302]:
                            logger.info(f"🌐 [{current_time}] Внешний ping успешен: {service}")
                            external_success = True
                            break
                    except Exception:
                        continue
                
                if not external_success:
                    logger.warning(f"⚠️ [{current_time}] Все внешние пинги не удались")
                        
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
                    
                    if not shutdown_event.is_set():
                        bot_thread_new = threading.Thread(target=run_bot_in_thread, daemon=True)
                        bot_thread_new.start()
                        bot_running = True
                        bot_thread = bot_thread_new
                        logger.info(f"🔄 [{current_time}] Бот перезапущен")
                    
                except Exception as restart_error:
                    logger.error(f"❌ [{current_time}] Ошибка перезапуска бота: {restart_error}")
            
            # 4. Сброс счетчика ошибок при успешном выполнении
            if error_count > 0:
                logger.info(f"✅ [{current_time}] Сброс счетчика ошибок (было: {error_count})")
                error_count = 0
            
            # 5. Проверяем сигнал shutdown
            if shutdown_event.is_set():
                logger.info("📴 Keep alive получил сигнал shutdown, завершаю работу")
                break
            
            # 6. Ждем до следующего keep alive - АГРЕССИВНО каждые 30 секунд!
            sleep_time = 30  # 30 секунд для предотвращения засыпания Render
            logger.info(f"⏳ [{current_time}] Следующий keep alive через {sleep_time} секунд")
            
            # Разбиваем ожидание на части для возможности быстрого завершения
            for _ in range(sleep_time):
                if shutdown_event.is_set():
                    break
                time.sleep(1)
            
        except Exception as e:
            error_count += 1
            current_time = time.strftime("%H:%M:%S")
            logger.error(f"❌ [{current_time}] Ошибка в keep alive #{error_count}: {e}")
            
            # При накоплении ошибок увеличиваем интервал, но не слишком сильно
            if error_count > 5:
                logger.warning(f"⚠️ [{current_time}] Много ошибок, увеличиваю интервал до 2 минут")
                for _ in range(120):  # 2 минуты
                    if shutdown_event.is_set():
                        break
                    time.sleep(1)
            else:
                for _ in range(60):  # 1 минута
                    if shutdown_event.is_set():
                        break
                    time.sleep(1)
    
    logger.info("✅ Агрессивный Render Keep Alive завершен")

if __name__ == '__main__':
    # Записываем время старта приложения
    app._start_time = time.time()
    logger.info(f"🚀 Приложение запущено в {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Автоматически запускаем бота при старте приложения
        bot_thread = threading.Thread(target=run_bot_in_thread, daemon=True)
        bot_thread.start()
        bot_running = True
        logger.info("🤖 Бот запущен автоматически")
    except Exception as e:
        logger.error(f"❌ Не удалось запустить бота автоматически: {e}")
    
    # Запускаем keep alive в отдельном потоке
    try:
        keep_alive_thread = threading.Thread(target=render_keep_alive, daemon=True)
        keep_alive_thread.start()
        logger.info("💓 Keep alive запущен автоматически")
    except Exception as e:
        logger.error(f"❌ Не удалось запустить keep alive автоматически: {e}")
    
    # Запускаем Flask приложение с улучшенными настройками
    try:
        logger.info("🌐 Запуск Flask приложения...")
        # Используем host='0.0.0.0' для доступности извне
        # Используем port из переменных окружения или 10000 по умолчанию
        port = int(os.environ.get('PORT', 10000))
        
        app.run(
            host='0.0.0.0',
            port=port,
            debug=False,  # Отключаем debug для production
            use_reloader=False,  # Отключаем reloader для предотвращения дублирования
            threaded=True  # Включаем многопоточность
        )
    except Exception as e:
        logger.error(f"❌ Ошибка запуска Flask приложения: {e}")
        # Если Flask не запустился, ждем завершения других потоков
        shutdown_event.set()
        if bot_thread and bot_thread.is_alive():
            bot_thread.join(timeout=10)
        if keep_alive_thread and keep_alive_thread.is_alive():
            keep_alive_thread.join(timeout=5)
        sys.exit(1)
