@echo off
chcp 65001 >nul
title Stop Telegram Music Bot

echo.
echo ========================================
echo    🛑 ОСТАНОВКА TELEGRAM MUSIC BOT
echo ========================================
echo.

echo 🔍 Ищем процессы Python...
tasklist /FI "IMAGENAME eq python.exe" 2>NUL | find /I "python.exe" >NUL
if errorlevel 1 (
    echo ✅ Процессы Python не найдены
    echo 💡 Бот уже остановлен
    pause
    exit /b 0
)

echo ⚠️ Найдены процессы Python:
tasklist /FI "IMAGENAME eq python.exe"

echo.
echo 🛑 Останавливаем все процессы Python...
taskkill /F /IM python.exe >NUL 2>&1
if errorlevel 1 (
    echo ❌ Не удалось остановить процессы
    echo 💡 Попробуйте закрыть окна вручную
) else (
    echo ✅ Все процессы Python остановлены
    echo 💡 Бот остановлен
)

echo.
pause


