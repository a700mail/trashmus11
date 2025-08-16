# 🔐 Настройка переменных окружения

## 📋 Обзор изменений

Все чувствительные данные (API токены, ключи, номера кошельков) были вынесены из кода в файл `.env`.

## 🚀 Быстрый старт

1. **Скопируйте файл `.env`** и переименуйте его в `.env.local` для локальной разработки
2. **Отредактируйте значения** в `.env.local` под ваши реальные данные
3. **Установите зависимости**: `pip install -r requirements.txt`

## 🔑 Переменные окружения

### Telegram Bot
- `BOT_TOKEN` - токен вашего Telegram бота от @BotFather

### Payment Provider
- `PAYMENT_PROVIDER_TOKEN` - токен платежного провайдера

### YooMoney
- `YOOMONEY_CLIENT_ID` - ID клиента YooMoney
- `YOOMONEY_CLIENT_SECRET` - секретный ключ YooMoney
- `YOOMONEY_REDIRECT_URI` - URI для перенаправления после авторизации
- `YOOMONEY_ACCOUNT` - номер кошелька YooMoney

### TON Wallet
- `TON_WALLET` - адрес TON кошелька
- `TON_API_KEY` - API ключ для TON

### Payment Amounts
- `PAYMENT_AMOUNT_USD` - сумма в USD
- `PAYMENT_AMOUNT_USDT` - сумма в USDT

### Card Number
- `CARD_NUMBER` - номер карты (пример: XXXX XXXX XXXX XXXX)

## ⚠️ Важные замечания

1. **Файл `.env` добавлен в `.gitignore`** - он не будет загружен в репозиторий
2. **Все переменные обязательны** - если какая-то не установлена, код выбросит `RuntimeError`
3. **Загрузка происходит автоматически** через `python-dotenv` при импорте модулей

## 🧪 Тестирование

Для проверки настроек запустите:
```bash
python -c "import music_bot; print('✅ Настройки загружены')"
```

## 🔒 Безопасность

- Никогда не коммитьте файл `.env` в репозиторий
- Используйте разные значения для разработки и продакшена
- Регулярно обновляйте токены и ключи
- Ограничивайте доступ к файлу `.env` на сервере

## 📁 Структура файлов

```
TelegramMusicBot/
├── .env                    # Переменные окружения (НЕ в git)
├── .env.local             # Локальные переменные (НЕ в git)
├── .gitignore             # Исключает .env файлы
├── music_bot.py           # Основной бот (обновлен)
├── yoomoney_config.py     # Конфигурация YooMoney (обновлена)
├── yoomoney_payment.py    # Платежи YooMoney (обновлен)
└── test_*.py              # Тестовые файлы (обновлены)
```

