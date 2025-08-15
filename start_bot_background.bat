@echo off
chcp 65001 >nul
title Telegram Music Bot (Background)

echo.
echo ========================================
echo    🐻 TELEGRAM MUSIC BOT
echo    📱 ФОНОВЫЙ РЕЖИМ
echo ========================================
echo.

echo 🔍 Проверяем Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python не найден! Установите Python 3.8+
    echo 📥 Скачать: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo ✅ Python найден
echo.

echo 🔍 Проверяем файл music_bot.py...
if not exist "music_bot.py" (
    echo ❌ Файл music_bot.py не найден!
    pause
    exit /b 1
)

echo ✅ Файл music_bot.py найден
echo.

echo 🔍 Проверяем файл tracks.json...
if not exist "tracks.json" (
    echo ⚠️ Файл tracks.json не найден, создаем пустой...
    echo {} > tracks.json
)

echo ✅ Файл tracks.json готов
echo.

echo 🔍 Проверяем папку cache...
if not exist "cache" (
    echo 📁 Создаем папку cache...
    mkdir cache
)

echo ✅ Папка cache готова
echo.

echo 🚀 Запускаем бота в фоновом режиме...
echo.
echo 💡 Бот будет работать в фоне
echo 💡 Для остановки используйте stop_bot.bat
echo 💡 Или закройте это окно
echo.

start /min pythonw music_bot.py

echo.
echo ✅ Бот запущен в фоне!
echo 💡 Проверьте Telegram
echo.
pause



