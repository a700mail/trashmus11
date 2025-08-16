# ⚡ Быстрый старт на Render

## 🚀 Развертывание за 5 минут

### 1. Подготовка репозитория
```bash
git clone https://github.com/a700mail/trashmus11.git
cd trashmus11
```

### 2. Создание Web Service на Render
1. Перейдите на [dashboard.render.com](https://dashboard.render.com)
2. Нажмите **"New +"** → **"Web Service"**
3. Подключите GitHub и выберите репозиторий **"trashmus11"**

### 3. Настройка сервиса
- **Name**: `telegram-music-bot`
- **Environment**: `Python 3`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python app.py`
- **Plan**: `Free`

### 4. Переменные окружения
Добавьте в раздел **"Environment"**:
```
BOT_TOKEN=your_bot_token_here
```

### 5. Создание сервиса
Нажмите **"Create Web Service"** и дождитесь развертывания.

## ✅ Проверка работы

### Веб-интерфейс
- **Главная страница**: `https://your-service.onrender.com/`
- **Статус здоровья**: `https://your-service.onrender.com/health`
- **Статус бота**: `https://your-service.onrender.com/bot_status`

### Telegram
1. Найдите вашего бота
2. Отправьте `/start`
3. Проверьте ответ

## 🔧 Управление

### Перезапуск
- **Автоматически**: при push в GitHub
- **Вручную**: кнопка "Manual Deploy" в Render

### Логи
- Вкладка **"Logs"** в Render Dashboard
- Логи в реальном времени

## 🚨 Решение проблем

### Бот не отвечает
1. Проверьте `BOT_TOKEN` в переменных окружения
2. Убедитесь, что сервис запущен
3. Проверьте логи на наличие ошибок

### Ошибки сборки
1. Проверьте `requirements.txt`
2. Убедитесь, что Python 3.11+ поддерживается
3. Проверьте логи сборки

## 📚 Подробная документация

Полная инструкция: [RENDER_DEPLOYMENT.md](./RENDER_DEPLOYMENT.md)

---

**Бот готов к работе! 🎵**
