#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт для экспорта cookies из Chrome для YouTube
"""

import os
import logging
import browser_cookie3
from http.cookiejar import MozillaCookieJar

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def export_cookies():
    """Экспортирует cookies из Chrome для YouTube"""
    try:
        cookies_file = "cookies.txt"
        
        # Проверяем, доступен ли Chrome
        try:
            cj = browser_cookie3.chrome(domain_name=".youtube.com")
            if not cj:
                logging.warning("⚠️ Cookies Chrome не найдены")
                return False
        except Exception as chrome_error:
            logging.warning(f"⚠️ Ошибка доступа к Chrome: {chrome_error}")
            return False
        
        cj_mozilla = MozillaCookieJar()
        cookie_count = 0
        
        for cookie in cj:
            try:
                cj_mozilla.set_cookie(cookie)
                cookie_count += 1
            except Exception as cookie_error:
                logging.warning(f"⚠️ Ошибка обработки cookie: {cookie_error}")
                continue
        
        if cookie_count == 0:
            logging.warning("⚠️ Не удалось обработать ни одного cookie")
            return False
        
        # Создаем директорию, если она не существует
        os.makedirs(os.path.dirname(cookies_file), exist_ok=True)
        
        # Сохраняем cookies в файл
        cj_mozilla.save(cookies_file, ignore_discard=True, ignore_expires=True)
        
        logging.info(f"✅ Cookies успешно экспортированы: {cookie_count} cookies сохранено в {cookies_file}")
        return True
        
    except Exception as e:
        logging.error(f"❌ Ошибка экспорта cookies: {e}")
        return False

if __name__ == "__main__":
    print("🍪 Экспорт cookies из Chrome для YouTube...")
    if export_cookies():
        print("✅ Cookies успешно экспортированы!")
    else:
        print("❌ Ошибка экспорта cookies")
