# 🚀 Развертывание на Render с Keep Alive

## Описание
Этот проект настроен для автоматического развертывания на Render с встроенным keep alive механизмом, который предотвращает "засыпание" бесплатного сервиса.

## 🎯 Особенности для Render

### Keep Alive система
- **Автоматические пинги** каждые 14 минут
- **Внешние проверки** для поддержания активности
- **Health check endpoint** для мониторинга
- **Автоматический перезапуск** бота при сбоях

### Оптимизация для бесплатного плана
- Минимальное потребление ресурсов
- Эффективные интервалы проверок
- Graceful shutdown при остановке

## 📋 Требования

### Переменные окружения
```bash
BOT_TOKEN=your_telegram_bot_token_here
RENDER=true
```

### Зависимости
Все зависимости указаны в `requirements.txt`:
- `aiogram` - Telegram Bot API
- `flask` - Web framework
- `requests` - HTTP клиент
- `aiohttp` - Асинхронный HTTP клиент
- `yt-dlp` - YouTube загрузчик

## 🚀 Развертывание

### 1. Подготовка репозитория
```bash
# Клонируйте репозиторий
git clone <your-repo-url>
cd TelegramMusicBot

# Убедитесь, что все файлы на месте
ls -la
```

### 2. Настройка Render
1. Зайдите на [render.com](https://render.com)
2. Создайте новый **Web Service**
3. Подключите ваш GitHub репозиторий
4. Настройте переменные окружения

### 3. Конфигурация сервиса
- **Name**: `telegram-music-bot`
- **Environment**: `Python 3`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python app.py`
- **Health Check Path**: `/health`

### 4. Переменные окружения
```bash
BOT_TOKEN=your_bot_token_here
RENDER=true
```

## 🔧 Конфигурация

### render.yaml
Файл `render.yaml` содержит готовую конфигурацию:
```yaml
services:
  - type: web
    name: telegram-music-bot
    env: python
    plan: free
    buildCommand: pip install -r requirements.txt
    startCommand: python app.py
    healthCheckPath: /health
    autoDeploy: true
```

### Автоматическое развертывание
- При push в main ветку
- Автоматическая проверка здоровья
- Перезапуск при сбоях

## 📊 Мониторинг

### Health Check Endpoint
```
https://your-service-name.onrender.com/health
```

### Ответ health check
```json
{
  "status": "healthy",
  "bot_status": "running",
  "keep_alive_status": "running",
  "external_services_summary": {
    "total": 3,
    "healthy": 3,
    "unhealthy": 0
  },
  "render": {
    "is_render": true,
    "info": {
      "service_id": "your-service-id",
      "service_url": "https://your-service-name.onrender.com"
    }
  }
}
```

### Логи
- 💓 Keep alive активен
- 🤖 Бот работает
- 🌐 Внешние сервисы доступны
- 🔄 Автоматический перезапуск

## 🛠️ Устранение неполадок

### Бот не отвечает
1. Проверьте health endpoint
2. Убедитесь, что BOT_TOKEN установлен
3. Проверьте логи в Render Dashboard

### Keep alive не работает
1. Проверьте переменную RENDER=true
2. Убедитесь, что порт доступен
3. Проверьте логи keep alive потока

### Высокое потребление ресурсов
1. Увеличьте интервал keep alive (измените `sleep_time` в `render_keep_alive()`)
2. Уменьшите количество внешних сервисов
3. Мониторьте использование в Render Dashboard

## 📈 Производительность

### Оптимизация для бесплатного плана
- **Keep alive**: каждые 14 минут
- **Health check**: при каждом запросе
- **Внешние пинги**: только при keep alive
- **Автоперезапуск**: при сбоях

### Мониторинг ресурсов
- CPU: минимальное использование
- RAM: ~100-200 MB
- Диск: ~50-100 MB
- Сеть: только keep alive пинги

## 🔄 Обновления

### Автоматическое обновление
```bash
# В вашем локальном репозитории
git add .
git commit -m "Update keep alive for Render"
git push origin main
```

### Ручное обновление
1. В Render Dashboard
2. Нажмите "Manual Deploy"
3. Выберите ветку и коммит

## 📞 Поддержка

### Логи
- Render Dashboard → Logs
- Локальные логи в `bot.log`

### Отладка
- Health endpoint для проверки состояния
- Логи keep alive для диагностики
- Мониторинг внешних сервисов

## ✅ Готово!

После развертывания ваш бот будет:
- 🚀 Автоматически запускаться на Render
- 💓 Поддерживать активность через keep alive
- 🔄 Автоматически перезапускаться при сбоях
- 📊 Предоставлять детальную информацию о состоянии
- 🌐 Работать стабильно на бесплатном плане

**Ваш бот больше не будет засыпать на Render!** 🎉
