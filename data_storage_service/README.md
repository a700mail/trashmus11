# Data Storage Service

Сервис для хранения данных о треках пользователей и кеша поиска.

## Описание

Этот сервис отвечает за хранение и управление данными пользователей, включая их коллекции треков, кеш поиска и файлы cookies. Использует SQLite для хранения данных и предоставляет REST API для взаимодействия с другими сервисами.

## Функции

- Хранение треков пользователей
- Кеширование результатов поиска
- Управление файлами cookies
- Автоматическая очистка истекших данных
- REST API для взаимодействия
- Статистика использования

## Установка

1. Установите зависимости:
```bash
pip install -r requirements.txt
```

2. Создайте файл `.env` с переменными окружения:
```env
API_KEY=your_storage_service_api_key_here
DATABASE_URL=sqlite:///./music_storage.db
DATA_DIR=data
HOST=0.0.0.0
PORT=8002
SEARCH_CACHE_TTL=1800
TRACK_CACHE_TTL=3600
```

3. Запустите сервис:
```bash
python main.py
```

## Деплой на Render

1. Создайте новый Web Service на Render
2. Подключите ваш GitHub репозиторий
3. Установите переменные окружения в настройках сервиса
4. Деплой произойдет автоматически

## API Endpoints

### Треки пользователей
- `POST /tracks/{user_id}` - Сохранение трека
- `GET /tracks/{user_id}` - Получение треков пользователя
- `DELETE /tracks/{user_id}` - Удаление трека

### Кеш поиска
- `POST /cache/search` - Сохранение кеша поиска
- `GET /cache/search` - Получение кеша поиска
- `POST /cache/cleanup` - Очистка кеша

### Cookies
- `POST /cookies` - Сохранение cookies
- `GET /cookies` - Получение cookies
- `DELETE /cookies` - Удаление cookies

### Система
- `GET /health` - Проверка здоровья сервиса
- `GET /stats` - Статистика сервиса

## Примеры использования

### Сохранение трека
```bash
curl -X POST "http://localhost:8002/tracks/123" \
  -H "Authorization: Bearer your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Imagine Dragons - Believer",
    "url": "file:///path/to/file.mp3",
    "original_url": "https://www.youtube.com/watch?v=7wtfhFnSnhQ",
    "duration": 204,
    "uploader": "Imagine Dragons",
    "size_mb": 3.2
  }'
```

### Получение треков пользователя
```bash
curl -X GET "http://localhost:8002/tracks/123" \
  -H "Authorization: Bearer your_api_key"
```

### Сохранение кеша поиска
```bash
curl -X POST "http://localhost:8002/cache/search" \
  -H "Authorization: Bearer your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Imagine Dragons",
    "results": [
      {
        "id": "7wtfhFnSnhQ",
        "title": "Imagine Dragons - Believer",
        "duration": 204,
        "uploader": "Imagine Dragons",
        "url": "https://www.youtube.com/watch?v=7wtfhFnSnhQ"
      }
    ]
  }'
```

## Структура базы данных

### Таблица user_tracks
- `id` - Уникальный идентификатор
- `user_id` - ID пользователя
- `title` - Название трека
- `url` - Путь к файлу
- `original_url` - Оригинальная ссылка
- `duration` - Длительность в секундах
- `uploader` - Исполнитель
- `size_mb` - Размер файла в MB
- `created_at` - Время создания
- `updated_at` - Время обновления

### Таблица search_cache
- `id` - Уникальный идентификатор
- `query_hash` - Хеш запроса
- `query` - Текст запроса
- `results` - Результаты поиска (JSON)
- `created_at` - Время создания
- `expires_at` - Время истечения

### Таблица cookies
- `id` - Уникальный идентификатор
- `domain` - Домен
- `cookie_data` - Данные cookies
- `created_at` - Время создания
- `updated_at` - Время обновления

## Автоматическая очистка

Сервис автоматически очищает:
- Истекший кеш поиска (по умолчанию через 30 минут)
- Старые треки (старше 30 дней)
- Неиспользуемые данные

## Структура проекта

```
data_storage_service/
├── main.py              # Основной файл сервиса
├── requirements.txt     # Зависимости Python
├── env_config.txt      # Пример конфигурации
├── render.yaml         # Конфигурация Render
├── Procfile           # Конфигурация для Heroku/Render
├── runtime.txt        # Версия Python
└── README.md          # Этот файл
```
