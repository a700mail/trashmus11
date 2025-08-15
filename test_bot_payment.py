#!/usr/bin/env python3
"""
Тестирует создание платежа YooMoney в контексте бота
"""

import asyncio
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def test_payment_creation():
    """Тестирует создание платежа"""
    try:
        # Импортируем функцию из бота
        from music_bot import create_yoomoney_payment
        
        print("✅ Функция импортирована успешно")
        
        # Тестируем создание платежа
        user_id = "test_user_123"
        username = "test_user"
        
        print(f"🔍 Тестируем создание платежа для пользователя {user_id}")
        
        payment_url = await create_yoomoney_payment(user_id, username)
        
        if payment_url:
            print(f"✅ Платеж создан успешно!")
            print(f"   URL: {payment_url[:100]}...")
            return True
        else:
            print("❌ Платеж не создан")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Основная функция"""
    print("🚀 Тестирование создания платежа в контексте бота")
    print("=" * 50)
    
    success = await test_payment_creation()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 Тест пройден успешно!")
    else:
        print("❌ Тест не пройден")

if __name__ == "__main__":
    asyncio.run(main())

