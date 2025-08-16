@echo off
chcp 65001 >nul
echo ⚡ Запуск МАКСИМАЛЬНО АГРЕССИВНОГО Keep Alive для Render
echo ================================================================
echo.
echo ⚠️  ВНИМАНИЕ: Этот keep alive пингует каждые 30 секунд!
echo ⚠️  Это предотвратит засыпание Render, но увеличит потребление ресурсов
echo ⚠️  Рекомендуется только для критически важных сервисов
echo.

REM Проверяем наличие Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python не найден. Установите Python 3.8+
    pause
    exit /b 1
)

echo ✅ Python найден
echo.

REM Устанавливаем зависимости если нужно
echo 🔍 Проверка зависимостей...
pip install requests >nul 2>&1
if errorlevel 1 (
    echo ⚠️ Не удалось установить requests автоматически
    echo Попробуйте вручную: pip install requests
    echo.
)

echo 🚀 Запуск агрессивного keep alive...
echo.
echo 💓 Keep alive будет пинговать каждые 30 секунд
echo 🌐 Внешние сервисы будут проверяться постоянно
echo 🔄 Render НЕ сможет заснуть
echo.
echo Нажмите Ctrl+C для остановки
echo.

REM Запускаем агрессивный keep alive
python aggressive_keep_alive.py

echo.
echo 📴 Агрессивный keep alive остановлен
pause
