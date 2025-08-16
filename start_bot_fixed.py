#!/usr/bin/env python3
"""
Скрипт для запуска бота с исправленным keep alive
"""

import os
import sys
import logging
import time

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot_fixed.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def check_dependencies():
    """Проверяет наличие необходимых зависимостей"""
    required_modules = ['aiohttp', 'flask', 'aiogram', 'yt_dlp']
    missing_modules = []
    
    for module in required_modules:
        try:
            __import__(module)
            logger.info(f"✅ {module} доступен")
        except ImportError:
            missing_modules.append(module)
            logger.error(f"❌ {module} не найден")
    
    if missing_modules:
        logger.error(f"❌ Отсутствуют модули: {', '.join(missing_modules)}")
        logger.error("Установите их командой: pip install " + " ".join(missing_modules))
        return False
    
    return True

def check_environment():
    """Проверяет переменные окружения"""
    required_vars = ['BOT_TOKEN']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
            logger.error(f"❌ Переменная окружения {var} не установлена")
    
    if missing_vars:
        logger.error(f"❌ Отсутствуют переменные окружения: {', '.join(missing_vars)}")
        logger.error("Создайте файл .env или установите переменные в системе")
        return False
    
    logger.info("✅ Переменные окружения проверены")
    return True

def check_files():
    """Проверяет наличие необходимых файлов"""
    required_files = ['app.py', 'music_bot.py']
    missing_files = []
    
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)
            logger.error(f"❌ Файл {file} не найден")
    
    if missing_files:
        logger.error(f"❌ Отсутствуют файлы: {', '.join(missing_files)}")
        return False
    
    logger.info("✅ Необходимые файлы найдены")
    return True

def start_bot():
    """Запускает бота с исправленным keep alive"""
    try:
        logger.info("🚀 Запуск бота с исправленным keep alive...")
        
        # Импортируем и запускаем app.py
        from app import app, bot_running, bot_thread, keep_alive_thread
        
        logger.info("✅ Модули импортированы успешно")
        
        # Проверяем статус
        if bot_running:
            logger.info("🤖 Бот уже запущен")
        else:
            logger.info("🤖 Бот не запущен, запускаю...")
        
        if keep_alive_thread and keep_alive_thread.is_alive():
            logger.info("💓 Keep alive уже работает")
        else:
            logger.info("💓 Keep alive не работает")
        
        logger.info("🌐 Запуск Flask приложения...")
        logger.info("📱 Бот будет доступен через webhook")
        logger.info("💓 Keep alive будет работать в фоне")
        logger.info("🔍 Мониторинг доступен по адресу: http://localhost:10000/health")
        
        # Запускаем Flask (это запустит и бота, и keep alive)
        port = int(os.environ.get('PORT', 10000))
        app.run(
            host='0.0.0.0',
            port=port,
            debug=False,
            use_reloader=False,
            threaded=True
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка запуска бота: {e}")
        import traceback
        logger.error(f"📋 Traceback:\n{traceback.format_exc()}")
        return False
    
    return True

def main():
    """Главная функция"""
    logger.info("🔧 Запуск бота с исправленным keep alive")
    logger.info("=" * 50)
    
    # Проверяем зависимости
    logger.info("🔍 Проверка зависимостей...")
    if not check_dependencies():
        logger.error("❌ Проверка зависимостей не пройдена")
        sys.exit(1)
    
    # Проверяем переменные окружения
    logger.info("🔍 Проверка переменных окружения...")
    if not check_environment():
        logger.error("❌ Проверка переменных окружения не пройдена")
        sys.exit(1)
    
    # Проверяем файлы
    logger.info("🔍 Проверка файлов...")
    if not check_files():
        logger.error("❌ Проверка файлов не пройдена")
        sys.exit(1)
    
    logger.info("✅ Все проверки пройдены успешно")
    logger.info("=" * 50)
    
    # Запускаем бота
    try:
        start_bot()
    except KeyboardInterrupt:
        logger.info("📴 Получен сигнал прерывания, завершаю работу...")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
