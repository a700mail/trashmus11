# 🚀 Быстрый Старт - Микросервисная Архитектура

Быстрое развертывание трех микросервисов для Telegram Music Bot.

## ⚡ 5-минутный старт

### 1. Подготовка
```bash
# Клонируйте репозиторий
git clone <your-repo-url>
cd TelegramMusicBot

# Создайте виртуальное окружение
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate     # Windows
```

### 2. Установка зависимостей
```bash
# Установите зависимости для всех сервисов
pip install -r core_bot_service/requirements.txt
pip install -r music_processing_service/requirements.txt
pip install -r data_storage_service/requirements.txt
```

### 3. Настройка переменных окружения
```bash
# Скопируйте файлы конфигурации
cp core_bot_service/env_config.txt core_bot_service/.env
cp music_processing_service/env_config.txt music_processing_service/.env
cp data_storage_service/env_config.txt data_storage_service/.env

# Отредактируйте .env файлы с вашими ключами
```

### 4. Запуск сервисов
```bash
# Терминал 1: Data Storage Service
cd data_storage_service
python main.py

# Терминал 2: Music Processing Service
cd music_processing_service
python main.py

# Терминал 3: Core Bot Service
cd core_bot_service
python main.py
```

## 🔑 Минимальная конфигурация

### Core Bot Service (.env)
```env
BOT_TOKEN=your_telegram_bot_token
MUSIC_SERVICE_URL=http://localhost:8001
MUSIC_SERVICE_API_KEY=music_key_123
STORAGE_SERVICE_URL=http://localhost:8002
STORAGE_SERVICE_API_KEY=storage_key_456
```

### Music Processing Service (.env)
```env
API_KEY=music_key_123
REDIS_URL=redis://localhost:6379
CELERY_BROKER_URL=redis://localhost:6379
CELERY_RESULT_BACKEND=redis://localhost:6379
```

### Data Storage Service (.env)
```env
API_KEY=storage_key_456
DATABASE_URL=sqlite:///./music_storage.db
DATA_DIR=data
```

## 🧪 Тестирование

### 1. Проверьте сервисы
```bash
# Data Storage Service
curl http://localhost:8002/health

# Music Processing Service
curl http://localhost:8001/health

# Core Bot Service
# Отправьте /start боту в Telegram
```

### 2. Тест поиска
```
/play Imagine Dragons
```

### 3. Тест загрузки
```
Выберите трек из результатов поиска
```

## 🌐 Деплой на Render

### 1. Подготовка репозитория
```bash
# Убедитесь, что все файлы на месте
ls -la core_bot_service/
ls -la music_processing_service/
ls -la data_storage_service/
```

### 2. Push в GitHub
```bash
git add .
git commit -m "Add microservices architecture"
git push origin main
```

### 3. Создание сервисов на Render

#### Data Storage Service
- **Name:** `data-storage-service`
- **Root Directory:** `data_storage_service`
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`

#### Music Processing Service
- **Name:** `music-processing-service`
- **Root Directory:** `music_processing_service`
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`

#### Core Bot Service
- **Name:** `core-bot-service`
- **Root Directory:** `core_bot_service`
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `python main.py`

### 4. Переменные окружения на Render

После деплоя каждого сервиса получите их URL и обновите переменные в Core Bot Service:

```env
MUSIC_SERVICE_URL=https://music-processing-service.onrender.com
STORAGE_SERVICE_URL=https://data-storage-service.onrender.com
```

## 📊 Мониторинг

### Health Checks
- **Data Storage:** `https://data-storage-service.onrender.com/health`
- **Music Processing:** `https://music-processing-service.onrender.com/health`

### Логи
- **Render Dashboard** → выберите сервис → **Logs**

### Статистика
- **Data Storage:** `https://data-storage-service.onrender.com/stats`
- **Music Processing:** `https://music-processing-service.onrender.com/cache/info`

## 🚨 Частые проблемы

### Сервис не запускается
```bash
# Проверьте логи
cd core_bot_service
python main.py

# Проверьте переменные окружения
echo $BOT_TOKEN
```

### Ошибки подключения
```bash
# Проверьте URL сервисов
curl http://localhost:8001/health
curl http://localhost:8002/health

# Проверьте API ключи
```

### Бот не отвечает
```bash
# Проверьте BOT_TOKEN
# Убедитесь, что Core Bot Service запущен
# Проверьте логи бота
```

## 🔧 Отладка

### Включение подробных логов
```python
# В каждом main.py
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Тестирование API
```bash
# Тест поиска
curl -X POST "http://localhost:8001/search" \
  -H "Authorization: Bearer music_key_123" \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "limit": 5}'

# Тест сохранения
curl -X POST "http://localhost:8002/tracks/123" \
  -H "Authorization: Bearer storage_key_456" \
  -H "Content-Type: application/json" \
  -d '{"title": "Test", "url": "test.mp3", "original_url": "test.com", "duration": 120, "uploader": "Test", "size_mb": 1.0}'
```

## 📈 Следующие шаги

### 1. Добавьте Redis
```bash
# Ubuntu/Debian
sudo apt-get install redis-server

# macOS
brew install redis

# Windows
# Скачайте Redis с официального сайта
```

### 2. Настройте Celery
```bash
# В music_processing_service
celery -A main.celery_app worker --loglevel=info
```

### 3. Добавьте мониторинг
```bash
# Установите Prometheus и Grafana
# Настройте метрики для каждого сервиса
```

### 4. Настройте CI/CD
```bash
# GitHub Actions для автоматического деплоя
# Тесты перед деплоем
# Автоматическое обновление сервисов
```

## 🎯 Цели архитектуры

✅ **Разделение ответственности** - каждый сервис отвечает за свою область  
✅ **Масштабируемость** - можно развернуть несколько экземпляров каждого сервиса  
✅ **Отказоустойчивость** - сбой одного сервиса не влияет на другие  
✅ **Простота деплоя** - каждый сервис можно развернуть независимо  
✅ **Асинхронность** - бот всегда остается отзывчивым  

## 📚 Документация

- [Полное руководство по деплою](DEPLOYMENT_GUIDE.md)
- [Примеры взаимодействия](INTERACTION_EXAMPLE.md)
- [README микросервисов](README_MICROSERVICES.md)

---

**Готово! Ваш Telegram Music Bot теперь работает на микросервисной архитектуре! 🎉**
