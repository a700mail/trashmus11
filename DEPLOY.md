# Деплой Telegram Music Bot на Render

## Подготовка к деплою

1. **Создайте аккаунт на Render.com**
2. **Подключите ваш Git репозиторий**

## Настройка переменных окружения

В Render Dashboard добавьте следующие переменные окружения:

- `TELEGRAM_BOT_TOKEN` - токен вашего Telegram бота
- `GOOGLE_DRIVE_CREDENTIALS` - JSON с учетными данными Google Drive API
- `GOOGLE_DRIVE_TOKEN` - токен доступа к Google Drive
- `STRIPE_SECRET_KEY` - секретный ключ Stripe
- `STRIPE_PUBLISHABLE_KEY` - публичный ключ Stripe
- `WEBHOOK_URL` - URL вашего сервиса на Render (например: https://your-app.onrender.com)

## Особенности бесплатного плана

- **Keep-alive**: Сервис автоматически пингует себя каждые 20 секунд
- **Автостарт**: При первом запросе сервис автоматически запускается
- **Webhook**: Настройте webhook в Telegram Bot API на ваш URL + `/webhook`

## Команды управления

- `GET /` - статус сервиса
- `GET /ping` - keep-alive endpoint
- `GET /status` - детальный статус
- `POST /start_bot` - запуск бота
- `POST /stop_bot` - остановка бота
- `POST /webhook` - webhook для Telegram

## Настройка webhook в Telegram

После деплоя настройте webhook:

```
https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook?url=https://your-app.onrender.com/webhook
```

## Мониторинг

- Логи доступны в Render Dashboard
- Keep-alive автоматически поддерживает сервис активным
- Статус можно проверить через `/status` endpoint
