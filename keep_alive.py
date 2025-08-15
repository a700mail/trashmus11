import threading
import time
import requests
import os

def keep_alive():
    """
    Функция для поддержания активности веб-сервиса на Render
    Отправляет ping каждые 20 секунд
    """
    while True:
        try:
            # Получаем URL сервиса из переменной окружения
            webhook_url = os.getenv('WEBHOOK_URL')
            if webhook_url:
                # Убираем /webhook из URL если есть
                base_url = webhook_url.replace('/webhook', '')
                ping_url = f"{base_url}/ping"
                
                # Отправляем GET запрос для поддержания активности
                response = requests.get(ping_url, timeout=10)
                print(f"Keep-alive ping sent: {response.status_code}")
            else:
                print("WEBHOOK_URL not set, skipping keep-alive")
                
        except Exception as e:
            print(f"Keep-alive error: {e}")
        
        # Ждем 20 секунд перед следующим ping
        time.sleep(20)

def start_keep_alive():
    """
    Запускает keep-alive в отдельном потоке
    """
    keep_alive_thread = threading.Thread(target=keep_alive, daemon=True)
    keep_alive_thread.start()
    print("Keep-alive thread started")
