#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Загрузка переменных окружения
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Тестовый токен из переменных окружения
API_TOKEN = os.getenv("BOT_TOKEN")
if not API_TOKEN:
    raise RuntimeError("Переменная окружения BOT_TOKEN не установлена")

# Создаем бота и диспетчер
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Тестовое меню
test_menu = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="🧪 Тест кнопка", callback_data="test_button"),
            InlineKeyboardButton(text="💎 Купить премиум", callback_data="buy_premium")
        ]
    ]
)

@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    """Обработчик команды /start"""
    try:
        await message.answer("🧪 Тестовый бот запущен!", reply_markup=test_menu)
        logging.info("✅ Команда /start обработана успешно")
    except Exception as e:
        logging.error(f"❌ Ошибка в команде /start: {e}")

@dp.callback_query(lambda c: c.data == "test_button")
async def test_button_callback(callback: types.CallbackQuery):
    """Обработчик тестовой кнопки"""
    try:
        await callback.answer("🧪 Тестовая кнопка работает!")
        logging.info("✅ Тестовая кнопка обработана успешно")
    except Exception as e:
        logging.error(f"❌ Ошибка в тестовой кнопке: {e}")

@dp.callback_query(lambda c: c.data == "buy_premium")
async def buy_premium_callback(callback: types.CallbackQuery):
    """Обработчик кнопки 'Купить премиум'"""
    try:
        user_id = str(callback.from_user.id)
        username = callback.from_user.username
        
        logging.info(f"🔍 Нажата кнопка 'Купить премиум' пользователем {user_id} ({username})")
        
        # Простой ответ для теста
        await callback.answer("💎 Кнопка 'Купить премиум' работает!")
        
        # Отправляем тестовое сообщение
        await callback.message.edit_text(
            "💎 **ТЕСТ ПРЕМИУМА**\n\n"
            "✅ Кнопка работает корректно!\n\n"
            "Это тестовое сообщение для проверки функциональности.",
            reply_markup=test_menu
        )
        
        logging.info(f"✅ Кнопка 'Купить премиум' обработана успешно для пользователя {user_id}")
        
    except Exception as e:
        logging.error(f"❌ Ошибка в кнопке 'Купить премиум': {e}")
        await callback.answer("❌ Произошла ошибка")

async def main():
    """Главная функция"""
    try:
        logging.info("🚀 Запуск тестового бота...")
        
        # Запускаем бота
        await dp.start_polling(bot)
        
    except Exception as e:
        logging.error(f"❌ Критическая ошибка: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
