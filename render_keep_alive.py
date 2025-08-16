#!/usr/bin/env python3
"""
Keep Alive для Render - предотвращает засыпание сервиса
"""

import os
import time
import requests
import logging
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RenderKeepAlive:
    def __init__(self):
        self.ping_count = 0
        self.error_count = 0
        self.start_time = time.time()
        
        # Получаем URL сервиса из переменных Render
        self.service_url = os.environ.get('RENDER_EXTERNAL_URL')
        if not self.service_url:
            # Fallback для локального тестирования
            self.service_url = "http://localhost:10000"
        
        logger.info(f"🚀 Render Keep Alive инициализирован для: {self.service_url}")
    
    def ping_external_services(self):
        """Пингует внешние сервисы для активности"""
        external_services = [
            "https://httpbin.org/get",
            "https://api.github.com",
            "https://www.google.com",
            "https://www.cloudflare.com"
        ]
        
        for service in external_services:
            try:
                response = requests.get(service, timeout=5)
                if response.status_code in [200, 301, 302]:
                    logger.info(f"🌐 Внешний ping успешен: {service}")
                    return True
            except Exception as e:
                logger.debug(f"⚠️ Ping {service} не удался: {e}")
                continue
        
        return False
    
    def ping_own_service(self):
        """Пингует собственный сервис"""
        try:
            # Пингуем health endpoint
            health_url = f"{self.service_url}/health"
            response = requests.get(health_url, timeout=3)
            
            if response.status_code == 200:
                data = response.json()
                status = data.get('status', 'unknown')
                logger.info(f"💓 Health check успешен: {status}")
                return True
            else:
                logger.warning(f"⚠️ Health check вернул статус: {response.status_code}")
                return False
                
        except Exception as e:
            logger.warning(f"⚠️ Health check не удался: {e}")
            return False
    
    def ping_home_endpoint(self):
        """Пингует главный endpoint"""
        try:
            response = requests.get(self.service_url, timeout=3)
            if response.status_code == 200:
                logger.info(f"🏠 Главный endpoint доступен")
                return True
            else:
                logger.warning(f"⚠️ Главный endpoint вернул статус: {response.status_code}")
                return False
        except Exception as e:
            logger.warning(f"⚠️ Главный endpoint недоступен: {e}")
            return False
    
    def run_keep_alive(self):
        """Основной цикл keep alive"""
        logger.info("💓 Render Keep Alive запущен")
        
        while True:
            try:
                self.ping_count += 1
                current_time = datetime.now().strftime("%H:%M:%S")
                
                logger.info(f"💓 [{current_time}] Keep Alive #{self.ping_count}")
                
                # 1. Пингуем собственный сервис
                own_service_ok = self.ping_own_service()
                
                # 2. Пингуем внешние сервисы
                external_ok = self.ping_external_services()
                
                # 3. Пингуем главный endpoint
                home_ok = self.ping_home_endpoint()
                
                # 4. Логируем результаты
                if own_service_ok and external_ok and home_ok:
                    logger.info(f"✅ [{current_time}] Все проверки успешны")
                    if self.error_count > 0:
                        logger.info(f"✅ Сброс счетчика ошибок (было: {self.error_count})")
                        self.error_count = 0
                else:
                    self.error_count += 1
                    logger.warning(f"⚠️ [{current_time}] Некоторые проверки не прошли (ошибок: {self.error_count})")
                
                # 5. Показываем статистику
                uptime = time.time() - self.start_time
                hours = int(uptime // 3600)
                minutes = int((uptime % 3600) // 60)
                logger.info(f"📊 Uptime: {hours}ч {minutes}м | Ping: {self.ping_count} | Ошибок: {self.error_count}")
                
                # 6. Ждем до следующего ping
                # Для Render оптимально каждые 14 минут (840 секунд)
                # Это предотвращает засыпание, но не перегружает сервис
                sleep_time = 840  # 14 минут
                logger.info(f"⏳ Следующий ping через {sleep_time//60} минут")
                
                # Разбиваем ожидание на части для возможности быстрого завершения
                for _ in range(sleep_time):
                    time.sleep(1)
                
            except KeyboardInterrupt:
                logger.info("📴 Получен сигнал прерывания, завершаю keep alive")
                break
            except Exception as e:
                self.error_count += 1
                current_time = datetime.now().strftime("%H:%M:%S")
                logger.error(f"❌ [{current_time}] Ошибка в keep alive #{self.error_count}: {e}")
                
                # При накоплении ошибок увеличиваем интервал
                if self.error_count > 5:
                    logger.warning(f"⚠️ [{current_time}] Много ошибок, увеличиваю интервал до 30 минут")
                    time.sleep(1800)  # 30 минут
                else:
                    time.sleep(300)  # 5 минут
        
        logger.info("✅ Render Keep Alive завершен")

def main():
    """Главная функция"""
    logger.info("🚀 Запуск Render Keep Alive")
    logger.info("=" * 50)
    
    # Проверяем, что мы в Render
    if os.environ.get('RENDER'):
        logger.info("🌐 Обнаружен Render - используем специальные настройки")
        logger.info(f"🔗 Service URL: {os.environ.get('RENDER_EXTERNAL_URL', 'не установлен')}")
        logger.info(f"🔗 Service ID: {os.environ.get('RENDER_SERVICE_ID', 'не установлен')}")
    else:
        logger.info("💻 Локальный запуск - используем тестовые настройки")
    
    # Создаем и запускаем keep alive
    keep_alive = RenderKeepAlive()
    
    try:
        keep_alive.run_keep_alive()
    except KeyboardInterrupt:
        logger.info("📴 Keep alive остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
