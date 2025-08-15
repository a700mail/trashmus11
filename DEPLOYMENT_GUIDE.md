# 🚀 Руководство по Деплою на Render

Пошаговое руководство по развертыванию микросервисной архитектуры Telegram Music Bot на Render.

## 📋 Предварительные требования

1. **GitHub репозиторий** с кодом
2. **Аккаунт на Render** (бесплатный)
3. **Telegram Bot Token** от @BotFather
4. **API ключи** для каждого сервиса

## 🔑 Подготовка API ключей

### Генерация API ключей

Создайте уникальные API ключи для каждого сервиса:

```bash
# Генерируем случайные ключи
openssl rand -hex 32
# Результат: 1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef

# Или используйте онлайн генератор
# https://generate-secret.vercel.app/32
```

**Сохраните эти ключи:**
- `MUSIC_SERVICE_API_KEY`: для Music Processing Service
- `STORAGE_SERVICE_API_KEY`: для Data Storage Service

## 🌐 Деплой сервисов

### Шаг 1: Data Storage Service

1. **Перейдите на [Render Dashboard](https://dashboard.render.com/)**
2. **Нажмите "New +" → "Web Service"**
3. **Подключите GitHub репозиторий**
4. **Настройте сервис:**

```
Name: data-storage-service
Root Directory: data_storage_service
Environment: Python 3
Build Command: pip install -r requirements.txt
Start Command: uvicorn main:app --host 0.0.0.0 --port $PORT
```

5. **Добавьте переменные окружения:**

```env
API_KEY=your_storage_service_api_key_here
DATABASE_URL=sqlite:///./music_storage.db
DATA_DIR=data
HOST=0.0.0.0
PORT=8002
SEARCH_CACHE_TTL=1800
TRACK_CACHE_TTL=3600
```

6. **Нажмите "Create Web Service"**
7. **Дождитесь успешного деплоя**
8. **Скопируйте URL сервиса** (например: `https://data-storage-service.onrender.com`)

### Шаг 2: Music Processing Service

1. **Создайте новый Web Service**
2. **Настройте сервис:**

```
Name: music-processing-service
Root Directory: music_processing_service
Environment: Python 3
Build Command: pip install -r requirements.txt
Start Command: uvicorn main:app --host 0.0.0.0 --port $PORT
```

3. **Добавьте переменные окружения:**

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
```

4. **Создайте сервис**
5. **Скопируйте URL** (например: `https://music-processing-service.onrender.com`)

### Шаг 3: Core Bot Service

1. **Создайте новый Web Service**
2. **Настройте сервис:**

```
Name: core-bot-service
Root Directory: core_bot_service
Environment: Python 3
Build Command: pip install -r requirements.txt
Start Command: python main.py
```

3. **Добавьте переменные окружения:**

```env
BOT_TOKEN=your_telegram_bot_token_here
MUSIC_SERVICE_URL=https://music-processing-service.onrender.com
MUSIC_SERVICE_API_KEY=your_music_service_api_key_here
STORAGE_SERVICE_URL=https://data-storage-service.onrender.com
STORAGE_SERVICE_API_KEY=your_storage_service_api_key_here
MAX_FILE_SIZE_MB=50
CACHE_DIR=cache
```

4. **Создайте сервис**

## 🔧 Настройка после деплоя

### Проверка работоспособности

1. **Проверьте Data Storage Service:**
```bash
curl https://data-storage-service.onrender.com/health
```

2. **Проверьте Music Processing Service:**
```bash
curl https://music-processing-service.onrender.com/health
```

3. **Проверьте Core Bot Service:**
```bash
# Отправьте команду /start боту в Telegram
```

### Настройка webhook (опционально)

Если хотите использовать webhook вместо polling:

1. **Получите webhook URL от Render**
2. **Настройте webhook в Telegram:**
```bash
curl -X POST "https://api.telegram.org/bot<BOT_TOKEN>/setWebhook" \
  -d "url=https://core-bot-service.onrender.com/webhook"
```

## 🧪 Тестирование

### Тест поиска музыки

1. **Отправьте боту команду:**
```
/play Imagine Dragons
```

2. **Проверьте логи в Render Dashboard**
3. **Убедитесь, что все сервисы работают**

### Тест загрузки трека

1. **Выберите трек из результатов поиска**
2. **Проверьте, что файл загружается**
3. **Проверьте логи загрузки**

## 📊 Мониторинг

### Логи сервисов

- **Render Dashboard** → выберите сервис → **Logs**
- **Real-time logs** для отладки
- **Build logs** для проверки деплоя

### Health Checks

- **Data Storage Service:** `/health`
- **Music Processing Service:** `/health`
- **Автоматические проверки Render**

### Статистика

- **Data Storage Service:** `/stats`
- **Music Processing Service:** `/cache/info`

## 🚨 Troubleshooting

### Проблема: Сервис не запускается

**Решение:**
1. Проверьте логи в Render Dashboard
2. Убедитесь, что все зависимости установлены
3. Проверьте переменные окружения

### Проблема: Ошибки подключения между сервисами

**Решение:**
1. Проверьте URL сервисов
2. Убедитесь, что API ключи совпадают
3. Проверьте CORS настройки

### Проблема: Бот не отвечает

**Решение:**
1. Проверьте BOT_TOKEN
2. Убедитесь, что Core Bot Service запущен
3. Проверьте логи бота

### Проблема: Музыка не загружается

**Решение:**
1. Проверьте Music Processing Service
2. Убедитесь, что yt-dlp работает
3. Проверьте права доступа к файлам

## 🔄 Обновление сервисов

### Автоматический деплой

1. **Внесите изменения в код**
2. **Закоммитьте и запушьте в GitHub**
3. **Render автоматически обновит сервисы**

### Ручной деплой

1. **Render Dashboard** → выберите сервис
2. **Manual Deploy** → **Deploy latest commit**

## 📈 Масштабирование

### Увеличение ресурсов

1. **Измените план сервиса** в Render Dashboard
2. **Добавьте больше CPU/RAM**
3. **Перезапустите сервис**

### Горизонтальное масштабирование

1. **Создайте несколько экземпляров сервиса**
2. **Используйте Load Balancer**
3. **Настройте shared storage**

## 💰 Оптимизация затрат

### Бесплатный план Render

- **512 MB RAM** на сервис
- **0.1 CPU** на сервис
- **750 часов** в месяц
- **Автоматическое засыпание** после 15 минут неактивности

### Платные планы

- **Starter:** $7/месяц за сервис
- **Standard:** $25/месяц за сервис
- **Pro:** $50/месяц за сервис

## 🔒 Безопасность

### API ключи

- **Никогда не коммитьте ключи в код**
- **Используйте переменные окружения Render**
- **Регулярно обновляйте ключи**

### CORS настройки

- **Ограничьте доступ по доменам**
- **Используйте HTTPS**
- **Проверяйте заголовки запросов**

## 📚 Полезные ссылки

- [Render Documentation](https://render.com/docs)
- [Render Python Guide](https://render.com/docs/deploy-python)
- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)
- [aiogram Webhook](https://docs.aiogram.dev/en/dev-3.x/dispatcher/webhook.html)

## 🆘 Получение помощи

### Render Support

- **Help Center:** https://render.com/docs/help
- **Community:** https://community.render.com/
- **Email:** support@render.com

### GitHub Issues

- **Создайте issue** в репозитории проекта
- **Опишите проблему** подробно
- **Приложите логи** и скриншоты

---

**Успешного деплоя! 🎉**
