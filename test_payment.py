#!/usr/bin/env python3
"""
Тестовый скрипт для проверки создания платежа YooMoney
"""

import os
import sys
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_yoomoney_payment():
    """Тестирует создание платежа YooMoney"""
    try:
        # Импортируем функцию
        from yoomoney_payment import create_simple_payment_url
        
        # Загрузка переменных окружения
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass
        
        # Тестовые данные из переменных окружения
        account = os.getenv("YOOMONEY_ACCOUNT")
        if not account:
            print("❌ Переменная окружения YOOMONEY_ACCOUNT не установлена")
            return False
            
        amount = 100.0
        comment = "Тестовая оплата"
        label = "test_payment"
        
        print(f"🔍 Тестируем создание платежа:")
        print(f"   Account: {account}")
        print(f"   Amount: {amount}")
        print(f"   Comment: {comment}")
        print(f"   Label: {label}")
        
        # Создаем URL
        payment_url = create_simple_payment_url(account, amount, comment, label)
        
        if payment_url:
            print(f"✅ Платежный URL создан успешно!")
            print(f"   URL: {payment_url[:100]}...")
            return True
        else:
            print("❌ Не удалось создать платежный URL")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

def test_bot_integration():
    """Тестирует интеграцию с ботом"""
    try:
        # Импортируем настройки из бота
        import music_bot
        
        print(f"🔍 Проверяем настройки YooMoney в боте:")
        print(f"   YOOMONEY_AVAILABLE: {music_bot.YOOMONEY_AVAILABLE}")
        print(f"   YOOMONEY_ENABLED: {music_bot.YOOMONEY_ENABLED}")
        print(f"   YOOMONEY_ACCOUNT: {music_bot.YOOMONEY_ACCOUNT}")
        print(f"   YOOMONEY_PAYMENT_AMOUNT: {music_bot.YOOMONEY_PAYMENT_AMOUNT}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка импорта бота: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Тестирование платежа YooMoney")
    print("=" * 50)
    
    # Тест 1: Создание платежа
    print("\n🔍 Тест 1: Создание платежа")
    payment_ok = test_yoomoney_payment()
    
    # Тест 2: Интеграция с ботом
    print("\n🔍 Тест 2: Интеграция с ботом")
    bot_ok = test_bot_integration()
    
    print("\n" + "=" * 50)
    print(f"📊 Результаты:")
    print(f"   Платеж: {'✅ OK' if payment_ok else '❌ ОШИБКА'}")
    print(f"   Бот: {'✅ OK' if bot_ok else '❌ ОШИБКА'}")
    
    if payment_ok and bot_ok:
        print("\n🎉 Все тесты пройдены! Платежи должны работать.")
    else:
        print("\n⚠️ Есть проблемы. Проверьте настройки.")

