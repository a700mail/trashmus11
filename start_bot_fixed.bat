@echo off
chcp 65001 >nul
echo 🔧 Запуск бота с исправленным keep alive
echo ================================================

REM Проверяем наличие Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python не найден. Установите Python 3.8+
    pause
    exit /b 1
)

REM Проверяем наличие pip
pip --version >nul 2>&1
if errorlevel 1 (
    echo ❌ pip не найден. Установите pip
    pause
    exit /b 1
)

echo ✅ Python найден
echo.

REM Устанавливаем зависимости если нужно
echo 🔍 Проверка зависимостей...
pip install -r requirements.txt >nul 2>&1
if errorlevel 1 (
    echo ⚠️ Не удалось установить зависимости автоматически
    echo Попробуйте вручную: pip install -r requirements.txt
    echo.
)

REM Проверяем наличие .env файла
if not exist ".env" (
    echo ⚠️ Файл .env не найден
    echo Создайте файл .env с переменной BOT_TOKEN
    echo.
)

echo 🚀 Запуск бота...
echo.
echo 📱 Бот будет доступен через webhook
echo 💓 Keep alive будет работать в фоне  
echo 🔍 Мониторинг: http://localhost:10000/health
echo.
echo Нажмите Ctrl+C для остановки
echo.

REM Запускаем бота
python start_bot_fixed.py

echo.
echo 📴 Бот остановлен
pause
