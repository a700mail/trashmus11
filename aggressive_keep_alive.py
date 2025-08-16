#!/usr/bin/env python3
"""
МАКСИМАЛЬНО АГРЕССИВНЫЙ Keep Alive для Render
Пингует каждые 30 секунд для предотвращения засыпания
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

class AggressiveRenderKeepAlive:
    def __init__(self):
        self.ping_count = 0
        self.error_count = 0
        self.start_time = time.time()
        
        # Получаем URL сервиса из переменных Render
        self.service_url = os.environ.get('RENDER_EXTERNAL_URL')
        if not self.service_url:
            # Fallback для локального тестирования
            self.service_url = "http://localhost:10000"
        
        logger.info(f"🚀 АГРЕССИВНЫЙ Render Keep Alive инициализирован для: {self.service_url}")
        logger.info(f"⚡ Пинги каждые 30 секунд для максимальной активности!")
    
    def ping_external_services(self):
        """Пингует внешние сервисы для активности"""
        external_services = [
            "https://httpbin.org/get",
            "https://api.github.com",
            "https://www.google.com",
            "https://www.cloudflare.com",
            "https://httpstat.us/200",
            "https://jsonplaceholder.typicode.com/posts/1"
        ]
        
        success_count = 0
        for service in external_services:
            try:
                response = requests.get(service, timeout=5)
                if response.status_code in [200, 301, 302]:
                    logger.info(f"🌐 Внешний ping успешен: {service}")
                    success_count += 1
                    if success_count >= 2:  # Достаточно 2 успешных пинга
                        return True
            except Exception as e:
                logger.debug(f"⚠️ Ping {service} не удался: {e}")
                continue
        
        return success_count >= 2
    
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
        """Основной цикл keep alive - МАКСИМАЛЬНО АГРЕССИВНО каждые 30 секунд"""
        logger.info("💓 МАКСИМАЛЬНО АГРЕССИВНЫЙ Render Keep Alive запущен")
        logger.info("⚡ Пинги каждые 30 секунд для предотвращения засыпания Render!")
        
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
                
                # 6. Ждем до следующего ping - МАКСИМАЛЬНО АГРЕССИВНО каждые 30 секунд!
                # Это гарантированно предотвратит засыпание Render
                sleep_time = 30  # 30 секунд для максимальной активности
                logger.info(f"⏳ Следующий ping через {sleep_time} секунд")
                
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
                
                # При накоплении ошибок увеличиваем интервал, но не слишком сильно
                if self.error_count > 5:
                    logger.warning(f"⚠️ [{current_time}] Много ошибок, увеличиваю интервал до 2 минут")
                    time.sleep(120)  # 2 минуты
                else:
                    time.sleep(60)  # 1 минута
        
        logger.info("✅ МАКСИМАЛЬНО АГРЕССИВНЫЙ Render Keep Alive завершен")

def main():
    """Главная функция"""
    logger.info("🚀 Запуск МАКСИМАЛЬНО АГРЕССИВНОГО Render Keep Alive")
    logger.info("=" * 70)
    
    # Проверяем, что мы в Render
    if os.environ.get('RENDER'):
        logger.info("🌐 Обнаружен Render - используем специальные настройки")
        logger.info(f"🔗 Service URL: {os.environ.get('RENDER_EXTERNAL_URL', 'не установлен')}")
        logger.info(f"🔗 Service ID: {os.environ.get('RENDER_SERVICE_ID', 'не установлен')}")
    else:
        logger.info("💻 Локальный запуск - используем тестовые настройки")
    
    logger.info("⚡ ВНИМАНИЕ: Этот keep alive пингует каждые 30 секунд!")
    logger.info("⚡ Это предотвратит засыпание Render, но увеличит потребление ресурсов")
    logger.info("⚡ Рекомендуется только для критически важных сервисов")
    
    # Создаем и запускаем keep alive
    keep_alive = AggressiveRenderKeepAlive()
    
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
