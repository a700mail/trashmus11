# Деплой Telegram Music Bot на Render

## Подготовка к деплою

1. **Создайте аккаунт на Render.com**
2. **Подключите ваш Git репозиторий**

## Настройка переменных окружения

В Render Dashboard добавьте следующие переменные окружения:

### Основные настройки бота:
- `TELEGRAM_BOT_TOKEN` - токен вашего Telegram бота от @BotFather (рекомендуется)
- `BOT_TOKEN` - альтернативное название для токена бота
- `WEBHOOK_URL` - URL вашего сервиса на Render (например: https://your-app.onrender.com)
- `RENDER` - автоматически устанавливается в `true` (помогает боту определить среду)

**Примечание:** Бот поддерживает оба варианта названия токена. Если установить обе переменные, приоритет у `TELEGRAM_BOT_TOKEN`.

### Настройки платежей:
- `PAYMENT_PROVIDER_TOKEN` - токен платежного провайдера
- `YOOMONEY_CLIENT_ID` - ID клиента YooMoney
- `YOOMONEY_CLIENT_SECRET` - секрет клиента YooMoney  
- `YOOMONEY_ACCOUNT` - номер счета YooMoney
- `YOOMONEY_REDIRECT_URI` - URI для перенаправления YooMoney

### Дополнительные настройки:
- `CARD_NUMBER` - номер карты для автоматических платежей
- `TON_WALLET` - адрес TON кошелька
- `TON_API_KEY` - API ключ для TON
- `PAYMENT_AMOUNT_USD` - сумма платежа в USD
- `PAYMENT_AMOUNT_USDT` - сумма платежа в USDT

## Особенности бесплатного плана

- **Keep-alive**: Сервис автоматически пингует себя каждые 20 секунд
- **Автостарт**: При первом запросе сервис автоматически запускается
- **Webhook**: Настройте webhook в Telegram Bot API на ваш URL + `/webhook`

## Команды управления

- `GET /` - статус сервиса и список функций
- `GET /ping` - keep-alive endpoint
- `GET /status` - детальный статус и конфигурация
- `GET/POST /start_bot` - запуск бота (можно через браузер)
- `GET/POST /stop_bot` - остановка бота (можно через браузер)
- `POST /webhook` - webhook для Telegram

## Настройка webhook в Telegram

После деплоя настройте webhook:

```
https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook?url=https://your-app.onrender.com/webhook
```

## Функции бота

- 🎵 Скачивание музыки с YouTube
- 🎧 Поддержка SoundCloud
- 💳 Обработка платежей (YooMoney, TON)
- ⭐ Премиум функции
- 🔄 Автоматическое управление очередями

## Мониторинг

- Логи доступны в Render Dashboard
- Keep-alive автоматически поддерживает сервис активным
- Статус можно проверить через `/status` endpoint
- Проверка конфигурации через веб-интерфейс
- Отображение типа используемой переменной токена
