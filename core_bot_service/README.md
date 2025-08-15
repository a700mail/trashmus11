# Core Bot Service

Основной сервис Telegram бота для поиска и скачивания музыки.

## Описание

Этот сервис является основным интерфейсом для пользователей Telegram. Он принимает команды от пользователей и взаимодействует с другими микросервисами для выполнения задач.

## Функции

- Обработка команд Telegram бота
- Поиск музыки через Music Processing Service
- Хранение данных через Data Storage Service
- Асинхронная обработка запросов
- Кеширование результатов

## Установка

1. Установите зависимости:
```bash
pip install -r requirements.txt
```

2. Создайте файл `.env` с переменными окружения:
```env
BOT_TOKEN=your_telegram_bot_token_here
MUSIC_SERVICE_URL=http://localhost:8001
MUSIC_SERVICE_API_KEY=your_music_service_api_key
STORAGE_SERVICE_URL=http://localhost:8002
STORAGE_SERVICE_API_KEY=your_storage_service_api_key
MAX_FILE_SIZE_MB=50
CACHE_DIR=cache
```

3. Запустите бота:
```bash
python main.py
```

## Деплой на Render

1. Создайте новый Web Service на Render
2. Подключите ваш GitHub репозиторий
3. Установите переменные окружения в настройках сервиса
4. Деплой произойдет автоматически

## API Endpoints

Бот не предоставляет HTTP API, но использует следующие сервисы:

- **Music Processing Service**: для поиска и загрузки музыки
- **Data Storage Service**: для хранения данных пользователей и кеша

## Структура проекта

```
core_bot_service/
├── main.py              # Основной файл бота
├── requirements.txt     # Зависимости Python
├── env_config.txt      # Пример конфигурации
├── render.yaml         # Конфигурация Render
├── Procfile           # Конфигурация для Heroku/Render
├── runtime.txt        # Версия Python
└── README.md          # Этот файл
```
