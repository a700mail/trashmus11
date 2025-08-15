@echo off
chcp 65001 >nul
title Check Bot Status

echo.
echo ========================================
echo    🔍 СТАТУС TELEGRAM MUSIC BOT
echo ========================================
echo.

echo 🔍 Проверяем процессы Python...
tasklist /FI "IMAGENAME eq python.exe" 2>NUL | find /I "python.exe" >NUL
if errorlevel 1 (
    echo ❌ Бот НЕ запущен
    echo 💡 Запустите start_bot.bat
) else (
    echo ✅ Бот ЗАПУЩЕН
    echo.
    echo 📊 Активные процессы Python:
    tasklist /FI "IMAGENAME eq python.exe"
)

echo.
echo 🔍 Проверяем файлы...
if exist "music_bot.py" (
    echo ✅ music_bot.py найден
) else (
    echo ❌ music_bot.py НЕ найден
)

if exist "tracks.json" (
    echo ✅ tracks.json найден
) else (
    echo ❌ tracks.json НЕ найден
)

if exist "cache" (
    echo ✅ Папка cache найдена
) else (
    echo ❌ Папка cache НЕ найдена
)

echo.
echo 🔍 Проверяем логи...
if exist "bot.log" (
    echo ✅ bot.log найден
    echo 📊 Размер: 
    for %%A in ("bot.log") do echo    %%~zA байт
) else (
    echo ❌ bot.log НЕ найден
)

echo.
pause



