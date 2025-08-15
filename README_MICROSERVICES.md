# Telegram Music Bot - Микросервисная Архитектура

Микросервисная архитектура для Telegram бота поиска и скачивания музыки, оптимизированная для деплоя на Render.

## 🏗️ Архитектура

Проект разделен на три независимых сервиса:

### 1. Core Bot Service (`core_bot_service/`)
- **Назначение**: Основной Telegram бот на aiogram
- **Функции**: Прием команд, взаимодействие с пользователями
- **Технологии**: aiogram, aiohttp, httpx
- **Порт**: 8000 (по умолчанию)

### 2. Music Processing Service (`music_processing_service/`)
- **Назначение**: Обработка и загрузка музыки
- **Функции**: Поиск на YouTube, скачивание треков, конвертация в MP3
- **Технологии**: FastAPI, yt-dlp, Celery, Redis
- **Порт**: 8001

### 3. Data Storage Service (`data_storage_service/`)
- **Назначение**: Хранение данных и кеш
- **Функции**: База данных пользователей, кеш поиска, cookies
- **Технологии**: FastAPI, SQLite, aiofiles
- **Порт**: 8002

## 🚀 Быстрый старт

### Локальная разработка

1. **Клонируйте репозиторий**:
```bash
git clone <your-repo-url>
cd TelegramMusicBot
```

2. **Настройте Core Bot Service**:
```bash
cd core_bot_service
cp env_config.txt .env
# Отредактируйте .env файл
pip install -r requirements.txt
python main.py
```

3. **Настройте Music Processing Service**:
```bash
cd ../music_processing_service
cp env_config.txt .env
# Отредактируйте .env файл
pip install -r requirements.txt
# Установите Redis
python main.py
```

4. **Настройте Data Storage Service**:
```bash
cd ../data_storage_service
cp env_config.txt .env
# Отредактируйте .env файл
pip install -r requirements.txt
python main.py
```

### Переменные окружения

#### Core Bot Service
```env
BOT_TOKEN=your_telegram_bot_token
MUSIC_SERVICE_URL=http://localhost:8001
MUSIC_SERVICE_API_KEY=your_music_service_api_key
STORAGE_SERVICE_URL=http://localhost:8002
STORAGE_SERVICE_API_KEY=your_storage_service_api_key
MAX_FILE_SIZE_MB=50
CACHE_DIR=cache
```

#### Music Processing Service
```env
API_KEY=your_music_service_api_key
REDIS_URL=redis://localhost:6379
CELERY_BROKER_URL=redis://localhost:6379
CELERY_RESULT_BACKEND=redis://localhost:6379
CACHE_DIR=cache
MAX_FILE_SIZE_MB=50
COOKIES_FILE=cookies.txt
HOST=0.0.0.0
PORT=8001
```

#### Data Storage Service
```env
API_KEY=your_storage_service_api_key
DATABASE_URL=sqlite:///./music_storage.db
DATA_DIR=data
HOST=0.0.0.0
PORT=8002
SEARCH_CACHE_TTL=1800
TRACK_CACHE_TTL=3600
```

## 🌐 Деплой на Render

### 1. Подготовка репозитория

Каждый сервис должен быть в отдельной папке с собственными файлами:
- `requirements.txt`
- `render.yaml`
- `Procfile`
- `runtime.txt`

### 2. Создание сервисов на Render

#### Core Bot Service
1. Создайте новый **Web Service**
2. Подключите репозиторий
3. Укажите папку: `core_bot_service`
4. Установите переменные окружения

#### Music Processing Service
1. Создайте новый **Web Service**
2. Подключите репозиторий
3. Укажите папку: `music_processing_service`
4. Установите переменные окружения

#### Data Storage Service
1. Создайте новый **Web Service**
2. Подключите репозиторий
3. Укажите папку: `data_storage_service`
4. Установите переменные окружения

### 3. Настройка переменных окружения на Render

После деплоя каждого сервиса получите их URL и обновите переменные окружения в Core Bot Service:

```env
MUSIC_SERVICE_URL=https://your-music-service.onrender.com
STORAGE_SERVICE_URL=https://your-storage-service.onrender.com
```

## 🔄 Пример взаимодействия

### Команда `/play Imagine Dragons`

1. **Core Bot Service** получает команду
2. Отправляет запрос в **Data Storage Service** для проверки кеша
3. Если кеш пуст, отправляет запрос в **Music Processing Service**
4. **Music Processing Service** ищет на YouTube и возвращает результаты
5. **Core Bot Service** сохраняет результаты в кеш через **Data Storage Service**
6. Отправляет пользователю список найденных треков

### Загрузка трека

1. Пользователь выбирает трек
2. **Core Bot Service** отправляет запрос на загрузку в **Music Processing Service**
3. **Music Processing Service** скачивает трек и возвращает статус
4. **Core Bot Service** сохраняет информацию о треке через **Data Storage Service**
5. Пользователь получает готовый MP3 файл

## 📊 Мониторинг и логи

### Health Checks
- `GET /health` - проверка здоровья каждого сервиса
- Автоматические проверки Render

### Логи
- Каждый сервис ведет собственные логи
- Логи доступны в панели управления Render

### Статистика
- `GET /stats` - статистика использования Data Storage Service
- `GET /cache/info` - информация о кеше Music Processing Service

## 🔧 Разработка и тестирование

### Локальное тестирование
```bash
# Тест Core Bot Service
cd core_bot_service
python -m pytest tests/

# Тест Music Processing Service
cd ../music_processing_service
python -m pytest tests/

# Тест Data Storage Service
cd ../data_storage_service
python -m pytest tests/
```

### API тестирование
```bash
# Тест Music Processing Service
curl -X GET "http://localhost:8001/health"

# Тест Data Storage Service
curl -X GET "http://localhost:8002/health"
```

## 🚨 Troubleshooting

### Проблемы с подключением между сервисами
1. Проверьте URL сервисов в переменных окружения
2. Убедитесь, что API ключи совпадают
3. Проверьте логи каждого сервиса

### Проблемы с Redis (Music Processing Service)
1. Убедитесь, что Redis запущен
2. Проверьте подключение к Redis
3. Рассмотрите использование внешнего Redis сервиса

### Проблемы с базой данных (Data Storage Service)
1. Проверьте права доступа к файлу базы данных
2. Убедитесь, что директория `data` существует
3. Проверьте логи SQLite

## 📈 Масштабирование

### Горизонтальное масштабирование
- Каждый сервис может быть развернут в нескольких экземплярах
- Используйте Load Balancer для распределения нагрузки

### Вертикальное масштабирование
- Увеличьте план Render для каждого сервиса
- Добавьте больше ресурсов CPU/RAM

### Кеширование
- Redis для Music Processing Service
- SQLite + in-memory кеш для Data Storage Service
- Кеш поиска с TTL

## 🔒 Безопасность

### API ключи
- Уникальные API ключи для каждого сервиса
- Хранение ключей в переменных окружения Render
- Никогда не коммитьте ключи в репозиторий

### CORS
- Настроены CORS политики для каждого сервиса
- Ограничение доступа по доменам при необходимости

### Валидация данных
- Pydantic модели для валидации входных данных
- Проверка типов и форматов

## 📚 Дополнительные ресурсы

- [Render Documentation](https://render.com/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [aiogram Documentation](https://docs.aiogram.dev/)
- [Celery Documentation](https://docs.celeryproject.org/)
- [yt-dlp Documentation](https://github.com/yt-dlp/yt-dlp)

## 🤝 Вклад в проект

1. Fork репозитория
2. Создайте feature branch
3. Внесите изменения
4. Добавьте тесты
5. Создайте Pull Request

## 📄 Лицензия

Этот проект распространяется под лицензией MIT. См. файл `LICENSE` для деталей.
