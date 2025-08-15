import os
import logging
import json
import time
import sqlite3
import hashlib
from typing import Optional, Dict, Any, List
from pathlib import Path
import aiofiles
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Настройки логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('storage_service.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# Конфигурация
API_KEY = os.getenv("API_KEY", "default_key")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./music_storage.db")
DATA_DIR = os.getenv("DATA_DIR", "data")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8002"))
SEARCH_CACHE_TTL = int(os.getenv("SEARCH_CACHE_TTL", "1800"))
TRACK_CACHE_TTL = int(os.getenv("TRACK_CACHE_TTL", "3600"))

# Создаем директории
os.makedirs(DATA_DIR, exist_ok=True)

# Инициализация FastAPI
app = FastAPI(
    title="Data Storage Service",
    description="Сервис для хранения данных о треках и кеше поиска",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Модели данных
class TrackData(BaseModel):
    title: str
    url: str
    original_url: str
    duration: Optional[int]
    uploader: Optional[str]
    size_mb: float

class SearchCacheData(BaseModel):
    query: str
    results: List[Dict[str, Any]]

class UserTracksResponse(BaseModel):
    user_id: str
    tracks: List[Dict[str, Any]]
    total_count: int

# Класс для работы с базой данных
class DatabaseManager:
    def __init__(self, db_path: str = "music_storage.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Инициализация базы данных"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Таблица пользователей и их треков
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_tracks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    original_url TEXT NOT NULL,
                    duration INTEGER,
                    uploader TEXT,
                    size_mb REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица кеша поиска
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS search_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query_hash TEXT UNIQUE NOT NULL,
                    query TEXT NOT NULL,
                    results TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL
                )
            ''')
            
            # Таблица cookies
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cookies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    domain TEXT NOT NULL,
                    cookie_data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Создаем индексы для ускорения поиска
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_tracks_user_id ON user_tracks(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_search_cache_query_hash ON search_cache(query_hash)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_search_cache_expires_at ON search_cache(expires_at)')
            
            conn.commit()
            conn.close()
            
            logging.info("✅ База данных инициализирована")
            
        except Exception as e:
            logging.error(f"❌ Ошибка инициализации базы данных: {e}")
    
    def get_connection(self):
        """Получение соединения с базой данных"""
        return sqlite3.connect(self.db_path)
    
    def save_user_track(self, user_id: str, track_data: TrackData) -> bool:
        """Сохранение трека пользователя"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO user_tracks (user_id, title, url, original_url, duration, uploader, size_mb)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                track_data.title,
                track_data.url,
                track_data.original_url,
                track_data.duration,
                track_data.uploader,
                track_data.size_mb
            ))
            
            conn.commit()
            conn.close()
            
            logging.info(f"✅ Трек сохранен для пользователя {user_id}: {track_data.title}")
            return True
            
        except Exception as e:
            logging.error(f"❌ Ошибка сохранения трека: {e}")
            return False
    
    def get_user_tracks(self, user_id: str) -> List[Dict[str, Any]]:
        """Получение треков пользователя"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT title, url, original_url, duration, uploader, size_mb, created_at
                FROM user_tracks
                WHERE user_id = ?
                ORDER BY created_at DESC
            ''', (user_id,))
            
            rows = cursor.fetchall()
            conn.close()
            
            tracks = []
            for row in rows:
                tracks.append({
                    'title': row[0],
                    'url': row[1],
                    'original_url': row[2],
                    'duration': row[3],
                    'uploader': row[4],
                    'size_mb': row[5],
                    'created_at': row[6]
                })
            
            return tracks
            
        except Exception as e:
            logging.error(f"❌ Ошибка получения треков: {e}")
            return []
    
    def delete_user_track(self, user_id: str, track_url: str) -> bool:
        """Удаление трека пользователя"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                DELETE FROM user_tracks
                WHERE user_id = ? AND url = ?
            ''', (user_id, track_url))
            
            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            if deleted_count > 0:
                logging.info(f"✅ Трек удален для пользователя {user_id}")
                return True
            else:
                logging.warning(f"⚠️ Трек не найден для удаления: {user_id} - {track_url}")
                return False
                
        except Exception as e:
            logging.error(f"❌ Ошибка удаления трека: {e}")
            return False
    
    def save_search_cache(self, query: str, results: List[Dict[str, Any]]) -> bool:
        """Сохранение кеша поиска"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Создаем хеш запроса
            query_hash = hashlib.md5(query.lower().encode()).hexdigest()
            
            # Вычисляем время истечения
            expires_at = time.time() + SEARCH_CACHE_TTL
            
            # Сохраняем или обновляем кеш
            cursor.execute('''
                INSERT OR REPLACE INTO search_cache (query_hash, query, results, expires_at)
                VALUES (?, ?, ?, ?)
            ''', (
                query_hash,
                query,
                json.dumps(results, ensure_ascii=False),
                expires_at
            ))
            
            conn.commit()
            conn.close()
            
            logging.info(f"✅ Кеш поиска сохранен для запроса: {query}")
            return True
            
        except Exception as e:
            logging.error(f"❌ Ошибка сохранения кеша поиска: {e}")
            return False
    
    def get_search_cache(self, query: str) -> Optional[List[Dict[str, Any]]]:
        """Получение кеша поиска"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            query_hash = hashlib.md5(query.lower().encode()).hexdigest()
            current_time = time.time()
            
            cursor.execute('''
                SELECT results, expires_at
                FROM search_cache
                WHERE query_hash = ? AND expires_at > ?
            ''', (query_hash, current_time))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                results = json.loads(row[0])
                logging.info(f"✅ Кеш поиска найден для запроса: {query}")
                return results
            else:
                return None
                
        except Exception as e:
            logging.error(f"❌ Ошибка получения кеша поиска: {e}")
            return None
    
    def cleanup_expired_cache(self) -> Dict[str, int]:
        """Очистка истекшего кеша"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            current_time = time.time()
            
            # Удаляем истекший кеш поиска
            cursor.execute('''
                DELETE FROM search_cache
                WHERE expires_at <= ?
            ''', (current_time,))
            
            expired_searches = cursor.rowcount
            
            # Удаляем старые треки (старше 30 дней)
            thirty_days_ago = current_time - (30 * 24 * 3600)
            cursor.execute('''
                DELETE FROM user_tracks
                WHERE created_at < ?
            ''', (thirty_days_ago,))
            
            expired_tracks = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            if expired_searches > 0 or expired_tracks > 0:
                logging.info(f"🧹 Очищен истекший кеш: {expired_searches} поисков, {expired_tracks} треков")
            
            return {
                "expired_searches": expired_searches,
                "expired_tracks": expired_tracks
            }
            
        except Exception as e:
            logging.error(f"❌ Ошибка очистки кеша: {e}")
            return {"expired_searches": 0, "expired_tracks": 0}
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Получение статистики базы данных"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Количество треков
            cursor.execute('SELECT COUNT(*) FROM user_tracks')
            total_tracks = cursor.fetchone()[0]
            
            # Количество уникальных пользователей
            cursor.execute('SELECT COUNT(DISTINCT user_id) FROM user_tracks')
            unique_users = cursor.fetchone()[0]
            
            # Количество кешированных поисков
            cursor.execute('SELECT COUNT(*) FROM search_cache')
            cached_searches = cursor.fetchone()[0]
            
            # Размер базы данных
            db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
            
            conn.close()
            
            return {
                "total_tracks": total_tracks,
                "unique_users": unique_users,
                "cached_searches": cached_searches,
                "database_size_mb": db_size / (1024 * 1024)
            }
            
        except Exception as e:
            logging.error(f"❌ Ошибка получения статистики: {e}")
            return {}

# Класс для работы с файлами cookies
class CookiesManager:
    def __init__(self, cookies_file: str = "cookies.txt"):
        self.cookies_file = cookies_file
        self.cookies_dir = DATA_DIR
    
    def get_cookies_path(self) -> str:
        """Получение пути к файлу cookies"""
        return os.path.join(self.cookies_dir, self.cookies_file)
    
    def save_cookies(self, cookies_data: str) -> bool:
        """Сохранение cookies"""
        try:
            cookies_path = self.get_cookies_path()
            
            async def save_async():
                async with aiofiles.open(cookies_path, 'w', encoding='utf-8') as f:
                    await f.write(cookies_data)
            
            # Запускаем асинхронное сохранение
            import asyncio
            asyncio.run(save_async())
            
            logging.info(f"✅ Cookies сохранены в {cookies_path}")
            return True
            
        except Exception as e:
            logging.error(f"❌ Ошибка сохранения cookies: {e}")
            return False
    
    def get_cookies(self) -> Optional[str]:
        """Получение cookies"""
        try:
            cookies_path = self.get_cookies_path()
            
            if not os.path.exists(cookies_path):
                return None
            
            async def read_async():
                async with aiofiles.open(cookies_path, 'r', encoding='utf-8') as f:
                    return await f.read()
            
            # Запускаем асинхронное чтение
            import asyncio
            cookies_data = asyncio.run(read_async())
            
            return cookies_data
            
        except Exception as e:
            logging.error(f"❌ Ошибка чтения cookies: {e}")
            return None
    
    def delete_cookies(self) -> bool:
        """Удаление cookies"""
        try:
            cookies_path = self.get_cookies_path()
            
            if os.path.exists(cookies_path):
                os.remove(cookies_path)
                logging.info(f"✅ Cookies удалены: {cookies_path}")
                return True
            else:
                logging.warning(f"⚠️ Файл cookies не найден: {cookies_path}")
                return False
                
        except Exception as e:
            logging.error(f"❌ Ошибка удаления cookies: {e}")
            return False

# Инициализация менеджеров
db_manager = DatabaseManager()
cookies_manager = CookiesManager()

# Функция проверки API ключа
async def verify_api_key(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="API ключ не предоставлен")
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Неверный формат авторизации")
    
    api_key = authorization.replace("Bearer ", "")
    if api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Неверный API ключ")
    
    return api_key

# API endpoints
@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    try:
        # Проверяем подключение к базе данных
        conn = db_manager.get_connection()
        conn.close()
        
        return {
            "status": "healthy",
            "service": "Data Storage Service",
            "timestamp": time.time(),
            "database_connected": True
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "service": "Data Storage Service",
            "timestamp": time.time(),
            "database_connected": False,
            "error": str(e)
        }

@app.post("/tracks/{user_id}")
async def save_track(
    user_id: str,
    track_data: TrackData,
    api_key: str = Depends(verify_api_key)
):
    """Сохранение трека пользователя"""
    try:
        if await db_manager.save_user_track(user_id, track_data):
            return {"message": "Трек успешно сохранен", "user_id": user_id}
        else:
            raise HTTPException(status_code=500, detail="Ошибка сохранения трека")
    except Exception as e:
        logging.error(f"Ошибка сохранения трека: {e}")
        raise HTTPException(status_code=500, detail="Ошибка сохранения трека")

@app.get("/tracks/{user_id}", response_model=UserTracksResponse)
async def get_user_tracks(
    user_id: str,
    api_key: str = Depends(verify_api_key)
):
    """Получение треков пользователя"""
    try:
        tracks = db_manager.get_user_tracks(user_id)
        return UserTracksResponse(
            user_id=user_id,
            tracks=tracks,
            total_count=len(tracks)
        )
    except Exception as e:
        logging.error(f"Ошибка получения треков: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения треков")

@app.delete("/tracks/{user_id}")
async def delete_user_track(
    user_id: str,
    track_url: str,
    api_key: str = Depends(verify_api_key)
):
    """Удаление трека пользователя"""
    try:
        if db_manager.delete_user_track(user_id, track_url):
            return {"message": "Трек успешно удален", "user_id": user_id}
        else:
            raise HTTPException(status_code=404, detail="Трек не найден")
    except Exception as e:
        logging.error(f"Ошибка удаления трека: {e}")
        raise HTTPException(status_code=500, detail="Ошибка удаления трека")

@app.post("/cache/search")
async def save_search_cache(
    cache_data: SearchCacheData,
    api_key: str = Depends(verify_api_key)
):
    """Сохранение кеша поиска"""
    try:
        if db_manager.save_search_cache(cache_data.query, cache_data.results):
            return {"message": "Кеш поиска сохранен", "query": cache_data.query}
        else:
            raise HTTPException(status_code=500, detail="Ошибка сохранения кеша")
    except Exception as e:
        logging.error(f"Ошибка сохранения кеша: {e}")
        raise HTTPException(status_code=500, detail="Ошибка сохранения кеша")

@app.get("/cache/search")
async def get_search_cache(
    query: str,
    api_key: str = Depends(verify_api_key)
):
    """Получение кеша поиска"""
    try:
        results = db_manager.get_search_cache(query)
        if results:
            return {"query": query, "results": results, "cached": True}
        else:
            return {"query": query, "results": [], "cached": False}
    except Exception as e:
        logging.error(f"Ошибка получения кеша: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения кеша")

@app.post("/cookies")
async def save_cookies(
    cookies_data: str,
    api_key: str = Depends(verify_api_key)
):
    """Сохранение cookies"""
    try:
        if cookies_manager.save_cookies(cookies_data):
            return {"message": "Cookies успешно сохранены"}
        else:
            raise HTTPException(status_code=500, detail="Ошибка сохранения cookies")
    except Exception as e:
        logging.error(f"Ошибка сохранения cookies: {e}")
        raise HTTPException(status_code=500, detail="Ошибка сохранения cookies")

@app.get("/cookies")
async def get_cookies(api_key: str = Depends(verify_api_key)):
    """Получение cookies"""
    try:
        cookies = cookies_manager.get_cookies()
        if cookies:
            return {"cookies": cookies, "exists": True}
        else:
            return {"cookies": "", "exists": False}
    except Exception as e:
        logging.error(f"Ошибка получения cookies: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения cookies")

@app.delete("/cookies")
async def delete_cookies(api_key: str = Depends(verify_api_key)):
    """Удаление cookies"""
    try:
        if cookies_manager.delete_cookies():
            return {"message": "Cookies успешно удалены"}
        else:
            raise HTTPException(status_code=404, detail="Файл cookies не найден")
    except Exception as e:
        logging.error(f"Ошибка удаления cookies: {e}")
        raise HTTPException(status_code=500, detail="Ошибка удаления cookies")

@app.post("/cache/cleanup")
async def cleanup_cache(api_key: str = Depends(verify_api_key)):
    """Очистка истекшего кеша"""
    try:
        cleanup_stats = db_manager.cleanup_expired_cache()
        return {
            "message": "Кеш очищен",
            "stats": cleanup_stats
        }
    except Exception as e:
        logging.error(f"Ошибка очистки кеша: {e}")
        raise HTTPException(status_code=500, detail="Ошибка очистки кеша")

@app.get("/stats")
async def get_stats(api_key: str = Depends(verify_api_key)):
    """Получение статистики сервиса"""
    try:
        db_stats = db_manager.get_database_stats()
        return {
            "service": "Data Storage Service",
            "timestamp": time.time(),
            "database_stats": db_stats
        }
    except Exception as e:
        logging.error(f"Ошибка получения статистики: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения статистики")

# Фоновая задача очистки кеша
@app.on_event("startup")
async def startup_event():
    """Событие запуска сервиса"""
    logging.info("🚀 Data Storage Service запущен")
    
    # Создаем периодическую задачу очистки кеша
    import asyncio
    
    async def periodic_cleanup():
        while True:
            try:
                await asyncio.sleep(3600)  # Каждый час
                cleanup_stats = db_manager.cleanup_expired_cache()
                if cleanup_stats["expired_searches"] > 0 or cleanup_stats["expired_tracks"] > 0:
                    logging.info(f"🧹 Периодическая очистка: {cleanup_stats}")
            except Exception as e:
                logging.error(f"❌ Ошибка периодической очистки: {e}")
                await asyncio.sleep(300)  # Ждем 5 минут при ошибке
    
    # Запускаем фоновую задачу
    asyncio.create_task(periodic_cleanup())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=True,
        workers=1  # Для разработки
    )
