import os
import logging
import asyncio
import json
import time
import hashlib
from typing import Optional, Dict, Any, List
from pathlib import Path
import yt_dlp
import aiofiles
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Header
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import httpx
from celery import Celery
import redis

# Загружаем переменные окружения
load_dotenv()

# Настройки логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('music_service.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# Конфигурация
API_KEY = os.getenv("API_KEY", "default_key")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379")
CACHE_DIR = os.getenv("CACHE_DIR", "cache")
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
COOKIES_FILE = os.getenv("COOKIES_FILE", "cookies.txt")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8001"))

# Создаем директории
os.makedirs(CACHE_DIR, exist_ok=True)

# Инициализация FastAPI
app = FastAPI(
    title="Music Processing Service",
    description="Сервис для обработки и загрузки музыки",
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

# Инициализация Celery
celery_app = Celery(
    "music_processing",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 минут
    task_soft_time_limit=240,  # 4 минуты
)

# Инициализация Redis
redis_client = redis.from_url(REDIS_URL)

# Модели данных
class SearchRequest(BaseModel):
    query: str
    limit: int = 10

class DownloadRequest(BaseModel):
    url: str
    user_id: str

class ArtistSearchRequest(BaseModel):
    artist: str
    limit: int = 10

class SearchResult(BaseModel):
    id: str
    title: str
    duration: Optional[int]
    uploader: Optional[str]
    url: str
    source: str = "yt"

class DownloadResult(BaseModel):
    title: str
    file_path: str
    file_url: str
    duration: Optional[int]
    uploader: Optional[str]
    size_mb: float
    status: str

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

# Класс для работы с YouTube
class YouTubeProcessor:
    def __init__(self):
        self.cookies_file = COOKIES_FILE if os.path.exists(COOKIES_FILE) else None
        self.cache_dir = CACHE_DIR
    
    def get_ydl_opts(self, is_premium: bool = False) -> Dict[str, Any]:
        """Получение настроек yt-dlp"""
        opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'extract_flat': False,
            'timeout': 300,
            'retries': 3,
            'outtmpl': os.path.join(self.cache_dir, '%(id)s.%(ext)s'),
        }
        
        if self.cookies_file:
            opts['cookiefile'] = self.cookies_file
        
        if is_premium:
            opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320'
            }]
        else:
            opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192'
            }]
        
        return opts
    
    async def search_music(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Поиск музыки на YouTube"""
        try:
            def search_blocking():
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'noplaylist': True,
                    'quiet': True,
                    'no_warnings': True,
                    'ignoreerrors': True,
                    'extract_flat': True
                }
                
                if self.cookies_file:
                    ydl_opts['cookiefile'] = self.cookies_file
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    search_query = f"ytsearch{limit}:{query}"
                    result = ydl.extract_info(search_query, download=False)
                    return result
            
            # Выполняем блокирующую операцию в отдельном потоке
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, search_blocking)
            
            if not result or not result.get('entries'):
                return []
            
            # Обрабатываем результаты
            processed_results = []
            for entry in result['entries']:
                if entry and entry.get('id') and entry.get('title'):
                    # Фильтруем по длительности (минимум 1 минута, максимум 15 минут)
                    duration = entry.get('duration', 0)
                    if 60 <= duration <= 900:
                        processed_results.append({
                            'id': entry['id'],
                            'title': entry['title'],
                            'duration': duration,
                            'uploader': entry.get('uploader', 'Неизвестный исполнитель'),
                            'url': f"https://www.youtube.com/watch?v={entry['id']}",
                            'source': 'yt'
                        })
            
            return processed_results[:limit]
            
        except Exception as e:
            logging.error(f"Ошибка поиска музыки: {e}")
            return []
    
    async def search_by_artist(self, artist: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Поиск треков по исполнителю"""
        try:
            def search_blocking():
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'noplaylist': True,
                    'quiet': True,
                    'no_warnings': True,
                    'ignoreerrors': True,
                    'extract_flat': True
                }
                
                if self.cookies_file:
                    ydl_opts['cookiefile'] = self.cookies_file
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    search_query = f"ytsearch{limit}:{artist}"
                    result = ydl.extract_info(search_query, download=False)
                    return result
            
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, search_blocking)
            
            if not result or not result.get('entries'):
                return []
            
            processed_results = []
            for entry in result['entries']:
                if entry and entry.get('id') and entry.get('title'):
                    duration = entry.get('duration', 0)
                    if 60 <= duration <= 900:
                        processed_results.append({
                            'id': entry['id'],
                            'title': entry['title'],
                            'duration': duration,
                            'uploader': entry.get('uploader', artist),
                            'url': f"https://www.youtube.com/watch?v={entry['id']}",
                            'source': 'yt'
                        })
            
            return processed_results[:limit]
            
        except Exception as e:
            logging.error(f"Ошибка поиска по исполнителю: {e}")
            return []
    
    async def download_track(self, url: str, user_id: str, is_premium: bool = False) -> Optional[Dict[str, Any]]:
        """Загрузка трека"""
        try:
            def download_blocking():
                ydl_opts = self.get_ydl_opts(is_premium)
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    # Получаем информацию о видео
                    info = ydl.extract_info(url, download=True)
                    
                    if not info:
                        return None
                    
                    # Получаем имя файла
                    filename = ydl.prepare_filename(info)
                    if not filename:
                        return None
                    
                    # Преобразуем в .mp3
                    mp3_filename = os.path.splitext(filename)[0] + ".mp3"
                    
                    # Проверяем, что файл создался
                    if not os.path.exists(mp3_filename):
                        return None
                    
                    # Проверяем размер файла
                    file_size = os.path.getsize(mp3_filename)
                    if file_size == 0:
                        return None
                    
                    return {
                        'title': info.get('title', 'Неизвестный трек'),
                        'file_path': mp3_filename,
                        'duration': info.get('duration', 0),
                        'uploader': info.get('uploader', 'Неизвестный исполнитель'),
                        'size_mb': file_size / (1024 * 1024)
                    }
            
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, download_blocking)
            
            if result:
                # Создаем URL для доступа к файлу
                file_url = f"/files/{os.path.basename(result['file_path'])}"
                result['file_url'] = file_url
                result['status'] = 'completed'
                
                # Сохраняем информацию в Redis для отслеживания
                track_info = {
                    'user_id': user_id,
                    'url': url,
                    'file_path': result['file_path'],
                    'timestamp': time.time()
                }
                redis_client.setex(
                    f"track:{user_id}:{hashlib.md5(url.encode()).hexdigest()}",
                    3600,  # TTL 1 час
                    json.dumps(track_info)
                )
                
                return result
            
            return None
            
        except Exception as e:
            logging.error(f"Ошибка загрузки трека: {e}")
            return None

# Инициализация процессора
youtube_processor = YouTubeProcessor()

# Celery задачи
@celery_app.task
def download_track_async(url: str, user_id: str, is_premium: bool = False):
    """Асинхронная загрузка трека через Celery"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(
            youtube_processor.download_track(url, user_id, is_premium)
        )
        
        loop.close()
        return result
    except Exception as e:
        logging.error(f"Ошибка асинхронной загрузки: {e}")
        return None

# API endpoints
@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    return {
        "status": "healthy",
        "service": "Music Processing Service",
        "timestamp": time.time(),
        "redis_connected": redis_client.ping()
    }

@app.post("/search", response_model=List[SearchResult])
async def search_music(
    request: SearchRequest,
    api_key: str = Depends(verify_api_key)
):
    """Поиск музыки"""
    try:
        results = await youtube_processor.search_music(request.query, request.limit)
        return results
    except Exception as e:
        logging.error(f"Ошибка поиска: {e}")
        raise HTTPException(status_code=500, detail="Ошибка поиска")

@app.post("/search/artist", response_model=List[SearchResult])
async def search_by_artist(
    request: ArtistSearchRequest,
    api_key: str = Depends(verify_api_key)
):
    """Поиск по исполнителю"""
    try:
        results = await youtube_processor.search_by_artist(request.artist, request.limit)
        return results
    except Exception as e:
        logging.error(f"Ошибка поиска по исполнителю: {e}")
        raise HTTPException(status_code=500, detail="Ошибка поиска по исполнителю")

@app.post("/download", response_model=DownloadResult)
async def download_track(
    request: DownloadRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_api_key)
):
    """Загрузка трека"""
    try:
        # Проверяем, не загружен ли уже этот трек
        cache_key = f"track:{request.user_id}:{hashlib.md5(request.url.encode()).hexdigest()}"
        cached_track = redis_client.get(cache_key)
        
        if cached_track:
            track_info = json.loads(cached_track)
            if os.path.exists(track_info['file_path']):
                # Возвращаем информацию о существующем файле
                file_size = os.path.getsize(track_info['file_path'])
                return DownloadResult(
                    title="Кешированный трек",
                    file_path=track_info['file_path'],
                    file_url=f"/files/{os.path.basename(track_info['file_path'])}",
                    duration=0,
                    uploader="Неизвестный исполнитель",
                    size_mb=file_size / (1024 * 1024),
                    status="cached"
                )
        
        # Запускаем загрузку в фоне
        task = download_track_async.delay(request.url, request.user_id, False)
        
        # Возвращаем информацию о задаче
        return DownloadResult(
            title="Загрузка начата",
            file_path="",
            file_url="",
            duration=0,
            uploader="",
            size_mb=0,
            status=f"task_id:{task.id}"
        )
        
    except Exception as e:
        logging.error(f"Ошибка загрузки: {e}")
        raise HTTPException(status_code=500, detail="Ошибка загрузки")

@app.get("/download/status/{task_id}")
async def download_status(
    task_id: str,
    api_key: str = Depends(verify_api_key)
):
    """Проверка статуса загрузки"""
    try:
        task_result = celery_app.AsyncResult(task_id)
        
        if task_result.ready():
            if task_result.successful():
                result = task_result.result
                if result:
                    return {
                        "status": "completed",
                        "result": result
                    }
                else:
                    return {"status": "failed", "error": "Загрузка не удалась"}
            else:
                return {"status": "failed", "error": str(task_result.info)}
        else:
            return {"status": "pending"}
            
    except Exception as e:
        logging.error(f"Ошибка проверки статуса: {e}")
        raise HTTPException(status_code=500, detail="Ошибка проверки статуса")

@app.get("/files/{filename}")
async def get_file(filename: str):
    """Получение файла"""
    try:
        file_path = os.path.join(CACHE_DIR, filename)
        if os.path.exists(file_path):
            return FileResponse(file_path, media_type="audio/mpeg")
        else:
            raise HTTPException(status_code=404, detail="Файл не найден")
    except Exception as e:
        logging.error(f"Ошибка получения файла: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения файла")

@app.delete("/files/{filename}")
async def delete_file(
    filename: str,
    api_key: str = Depends(verify_api_key)
):
    """Удаление файла"""
    try:
        file_path = os.path.join(CACHE_DIR, filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            return {"message": "Файл удален"}
        else:
            raise HTTPException(status_code=404, detail="Файл не найден")
    except Exception as e:
        logging.error(f"Ошибка удаления файла: {e}")
        raise HTTPException(status_code=500, detail="Ошибка удаления файла")

@app.get("/cache/info")
async def cache_info(api_key: str = Depends(verify_api_key)):
    """Информация о кеше"""
    try:
        cache_files = []
        total_size = 0
        
        for filename in os.listdir(CACHE_DIR):
            if filename.endswith('.mp3'):
                file_path = os.path.join(CACHE_DIR, filename)
                file_size = os.path.getsize(file_path)
                total_size += file_size
                
                cache_files.append({
                    'filename': filename,
                    'size_mb': file_size / (1024 * 1024),
                    'modified': os.path.getmtime(file_path)
                })
        
        return {
            "total_files": len(cache_files),
            "total_size_mb": total_size / (1024 * 1024),
            "files": cache_files
        }
        
    except Exception as e:
        logging.error(f"Ошибка получения информации о кеше: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения информации о кеше")

@app.post("/cache/cleanup")
async def cleanup_cache(api_key: str = Depends(verify_api_key)):
    """Очистка кеша"""
    try:
        cleaned_files = 0
        freed_space = 0
        
        for filename in os.listdir(CACHE_DIR):
            if filename.endswith('.mp3'):
                file_path = os.path.join(CACHE_DIR, filename)
                file_size = os.path.getsize(file_path)
                
                # Удаляем файлы старше 1 часа
                if time.time() - os.path.getmtime(file_path) > 3600:
                    os.remove(file_path)
                    cleaned_files += 1
                    freed_space += file_size
        
        return {
            "cleaned_files": cleaned_files,
            "freed_space_mb": freed_space / (1024 * 1024)
        }
        
    except Exception as e:
        logging.error(f"Ошибка очистки кеша: {e}")
        raise HTTPException(status_code=500, detail="Ошибка очистки кеша")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=True,
        workers=1  # Для разработки
    )
