# Music Processing Service

Сервис для обработки и загрузки музыки с YouTube.

## Описание

Этот сервис отвечает за поиск музыки на YouTube, загрузку треков и их обработку. Он использует yt-dlp для работы с YouTube и Celery для асинхронной обработки задач.

## Функции

- Поиск музыки на YouTube
- Поиск по исполнителям
- Загрузка треков в формате MP3
- Асинхронная обработка через Celery
- Кеширование результатов
- Управление файлами

## Установка

1. Установите зависимости:
```bash
pip install -r requirements.txt
```

2. Установите Redis (для Celery):
```bash
# Ubuntu/Debian
sudo apt-get install redis-server

# macOS
brew install redis

# Windows
# Скачайте Redis с официального сайта
```

3. Создайте файл `.env` с переменными окружения:
```env
API_KEY=your_music_service_api_key_here
REDIS_URL=redis://localhost:6379
CELERY_BROKER_URL=redis://localhost:6379
CELERY_RESULT_BACKEND=redis://localhost:6379
CACHE_DIR=cache
MAX_FILE_SIZE_MB=50
COOKIES_FILE=cookies.txt
HOST=0.0.0.0
PORT=8001
WORKERS=4
```

4. Запустите Redis:
```bash
redis-server
```

5. Запустите Celery worker:
```bash
celery -A main.celery_app worker --loglevel=info
```

6. Запустите сервис:
```bash
python main.py
```

## Деплой на Render

1. Создайте новый Web Service на Render
2. Подключите ваш GitHub репозиторий
3. Установите переменные окружения в настройках сервиса
4. Деплой произойдет автоматически

## API Endpoints

### Поиск
- `POST /search` - Поиск музыки
- `POST /search/artist` - Поиск по исполнителю

### Загрузка
- `POST /download` - Загрузка трека
- `GET /download/status/{task_id}` - Статус загрузки

### Файлы
- `GET /files/{filename}` - Получение файла
- `DELETE /files/{filename}` - Удаление файла

### Кеш
- `GET /cache/info` - Информация о кеше
- `POST /cache/cleanup` - Очистка кеша

### Здоровье
- `GET /health` - Проверка здоровья сервиса

## Примеры использования

### Поиск музыки
```bash
curl -X POST "http://localhost:8001/search" \
  -H "Authorization: Bearer your_api_key" \
  -H "Content-Type: application/json" \
  -d '{"query": "Imagine Dragons", "limit": 5}'
```

### Загрузка трека
```bash
curl -X POST "http://localhost:8001/download" \
  -H "Authorization: Bearer your_api_key" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "user_id": "123"}'
```

## Структура проекта

```
music_processing_service/
├── main.py              # Основной файл сервиса
├── requirements.txt     # Зависимости Python
├── env_config.txt      # Пример конфигурации
├── render.yaml         # Конфигурация Render
├── Procfile           # Конфигурация для Heroku/Render
├── runtime.txt        # Версия Python
└── README.md          # Этот файл
```
