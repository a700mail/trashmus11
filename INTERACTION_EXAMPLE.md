# 🔄 Примеры Взаимодействия между Микросервисами

Детальные примеры того, как три сервиса взаимодействуют друг с другом для выполнения задач пользователя.

## 🎵 Пример 1: Поиск музыки

### Пользователь отправляет: `/play Imagine Dragons`

#### 1. Core Bot Service получает команду
```python
@dp.message(Command("play"))
async def play_command(message: types.Message):
    # Парсим команду
    parts = message.text.split(' ', 1)
    query = parts[1].strip()  # "Imagine Dragons"
    user_id = str(message.from_user.id)
```

#### 2. Проверка кеша в Data Storage Service
```python
# Core Bot Service → Data Storage Service
cached_results = await storage_client.get_search_cache(query)

# HTTP запрос:
GET /cache/search?query=Imagine Dragons
Authorization: Bearer your_storage_service_api_key
```

**Ответ Data Storage Service:**
```json
{
  "query": "Imagine Dragons",
  "results": [],
  "cached": false
}
```

#### 3. Поиск в Music Processing Service
```python
# Core Bot Service → Music Processing Service
results = await music_client.search_music(query)

# HTTP запрос:
POST /search
Authorization: Bearer your_music_service_api_key
Content-Type: application/json

{
  "query": "Imagine Dragons",
  "limit": 10
}
```

**Ответ Music Processing Service:**
```json
[
  {
    "id": "7wtfhFnSnhQ",
    "title": "Imagine Dragons - Believer",
    "duration": 204,
    "uploader": "Imagine Dragons",
    "url": "https://www.youtube.com/watch?v=7wtfhFnSnhQ",
    "source": "yt"
  },
  {
    "id": "fJ9rUzIMcZQ",
    "title": "Imagine Dragons - Bohemian Rhapsody",
    "duration": 354,
    "uploader": "Imagine Dragons",
    "url": "https://www.youtube.com/watch?v=fJ9rUzIMcZQ",
    "source": "yt"
  }
]
```

#### 4. Сохранение в кеш Data Storage Service
```python
# Core Bot Service → Data Storage Service
await storage_client.set_search_cache(query, results)

# HTTP запрос:
POST /cache/search
Authorization: Bearer your_storage_service_api_key
Content-Type: application/json

{
  "query": "Imagine Dragons",
  "results": [
    {
      "id": "7wtfhFnSnhQ",
      "title": "Imagine Dragons - Believer",
      "duration": 204,
      "uploader": "Imagine Dragons",
      "url": "https://www.youtube.com/watch?v=7wtfhFnSnhQ",
      "source": "yt"
    }
  ]
}
```

**Ответ Data Storage Service:**
```json
{
  "message": "Кеш поиска сохранен",
  "query": "Imagine Dragons"
}
```

#### 5. Отправка результатов пользователю
```python
# Core Bot Service отправляет пользователю
await send_search_results(message.chat.id, results)

# Результат: клавиатура с найденными треками
```

## 🎧 Пример 2: Загрузка трека

### Пользователь выбирает трек из результатов поиска

#### 1. Core Bot Service получает callback
```python
@dp.callback_query(F.data.startswith("download_"))
async def download_selected_track(callback: types.CallbackQuery):
    track_id = callback.data.split("_")[1]  # "7wtfhFnSnhQ"
    user_id = str(callback.from_user.id)
```

#### 2. Запрос на загрузку в Music Processing Service
```python
# Core Bot Service → Music Processing Service
result = await music_client.download_track(track_url, user_id)

# HTTP запрос:
POST /download
Authorization: Bearer your_music_service_api_key
Content-Type: application/json

{
  "url": "https://www.youtube.com/watch?v=7wtfhFnSnhQ",
  "user_id": "123456789"
}
```

**Ответ Music Processing Service:**
```json
{
  "title": "Imagine Dragons - Believer",
  "file_path": "/app/cache/7wtfhFnSnhQ.mp3",
  "file_url": "/files/7wtfhFnSnhQ.mp3",
  "duration": 204,
  "uploader": "Imagine Dragons",
  "size_mb": 3.2,
  "status": "task_id:abc123def456"
}
```

#### 3. Проверка статуса загрузки
```python
# Core Bot Service → Music Processing Service
task_id = result["status"].split(":")[1]  # "abc123def456"

# HTTP запрос:
GET /download/status/abc123def456
Authorization: Bearer your_music_service_api_key
```

**Ответ Music Processing Service:**
```json
{
  "status": "completed",
  "result": {
    "title": "Imagine Dragons - Believer",
    "file_path": "/app/cache/7wtfhFnSnhQ.mp3",
    "file_url": "/files/7wtfhFnSnhQ.mp3",
    "duration": 204,
    "uploader": "Imagine Dragons",
    "size_mb": 3.2
  }
}
```

#### 4. Сохранение информации о треке в Data Storage Service
```python
# Core Bot Service → Data Storage Service
track_data = {
    "title": result["title"],
    "url": result["file_url"],
    "original_url": track_url,
    "duration": result["duration"],
    "uploader": result["uploader"],
    "size_mb": result["size_mb"]
}

await storage_client.save_track(user_id, track_data)

# HTTP запрос:
POST /tracks/123456789
Authorization: Bearer your_storage_service_api_key
Content-Type: application/json

{
  "title": "Imagine Dragons - Believer",
  "url": "/files/7wtfhFnSnhQ.mp3",
  "original_url": "https://www.youtube.com/watch?v=7wtfhFnSnhQ",
  "duration": 204,
  "uploader": "Imagine Dragons",
  "size_mb": 3.2
}
```

**Ответ Data Storage Service:**
```json
{
  "message": "Трек успешно сохранен",
  "user_id": "123456789"
}
```

#### 5. Отправка файла пользователю
```python
# Core Bot Service отправляет MP3 файл
await message.answer_audio(
    types.FSInputFile(result["file_path"]),
    title=result["title"],
    performer=result["uploader"],
    duration=result["duration"]
)
```

## 🎤 Пример 3: Поиск по исполнителю

### Пользователь отправляет: "🌨️ По исполнителям" → "Imagine Dragons"

#### 1. Core Bot Service получает имя исполнителя
```python
@dp.message(SearchStates.waiting_for_artist, F.text)
async def search_by_artist(message: types.Message, state: FSMContext):
    artist = message.text.strip()  # "Imagine Dragons"
    user_id = str(message.from_user.id)
```

#### 2. Поиск треков исполнителя в Music Processing Service
```python
# Core Bot Service → Music Processing Service
results = await music_client.search_by_artist(artist, 10)

# HTTP запрос:
POST /search/artist
Authorization: Bearer your_music_service_api_key
Content-Type: application/json

{
  "artist": "Imagine Dragons",
  "limit": 10
}
```

**Ответ Music Processing Service:**
```json
[
  {
    "id": "7wtfhFnSnhQ",
    "title": "Imagine Dragons - Believer",
    "duration": 204,
    "uploader": "Imagine Dragons",
    "url": "https://www.youtube.com/watch?v=7wtfhFnSnhQ",
    "source": "yt"
  },
  {
    "id": "fJ9rUzIMcZQ",
    "title": "Imagine Dragons - Bohemian Rhapsody",
    "duration": 354,
    "uploader": "Imagine Dragons",
    "url": "https://www.youtube.com/watch?v=fJ9rUzIMcZQ",
    "source": "yt"
  }
]
```

#### 3. Загрузка каждого трека
```python
# Для каждого трека:
for track in results:
    # Загружаем трек
    result = await music_client.download_track(track.get('url', ''), user_id)
    
    if result:
        # Сохраняем в Data Storage Service
        track_data = {
            "title": track.get("title", "Без названия"),
            "url": result.get("file_url", ""),
            "original_url": track.get("url", ""),
            "duration": track.get("duration", 0),
            "uploader": artist,
            "size_mb": result.get("size_mb", 0)
        }
        
        await storage_client.save_track(user_id, track_data)
        
        # Отправляем пользователю
        await message.answer_audio(
            types.FSInputFile(result.get("file_path", "")),
            title=track.get("title", "Без названия"),
            performer=artist,
            duration=track.get("duration", 0)
        )
```

## 📱 Пример 4: Просмотр коллекции пользователя

### Пользователь нажимает "🌨️ Моя музыка"

#### 1. Core Bot Service получает callback
```python
@dp.callback_query(F.data == "my_music")
async def show_my_music(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
```

#### 2. Запрос треков в Data Storage Service
```python
# Core Bot Service → Data Storage Service
tracks = await storage_client.get_user_tracks(user_id)

# HTTP запрос:
GET /tracks/123456789
Authorization: Bearer your_storage_service_api_key
```

**Ответ Data Storage Service:**
```json
{
  "user_id": "123456789",
  "tracks": [
    {
      "title": "Imagine Dragons - Believer",
      "url": "/files/7wtfhFnSnhQ.mp3",
      "original_url": "https://www.youtube.com/watch?v=7wtfhFnSnhQ",
      "duration": 204,
      "uploader": "Imagine Dragons",
      "size_mb": 3.2,
      "created_at": "2024-01-15T10:30:00"
    },
    {
      "title": "Imagine Dragons - Bohemian Rhapsody",
      "url": "/files/fJ9rUzIMcZQ.mp3",
      "original_url": "https://www.youtube.com/watch?v=fJ9rUzIMcZQ",
      "duration": 354,
      "uploader": "Imagine Dragons",
      "size_mb": 4.1,
      "created_at": "2024-01-15T11:15:00"
    }
  ],
  "total_count": 2
}
```

#### 3. Формирование и отправка списка
```python
# Core Bot Service формирует список
tracks_text = "🎵 **Ваша музыка:**\n\n"
for i, track in enumerate(tracks[:20], 1):
    duration_str = f"{track['duration']//60}:{track['duration']%60:02d}"
    tracks_text += f"{i}. {track['title']} ({duration_str})\n"

# Отправляем пользователю
await callback.message.answer(
    tracks_text,
    reply_markup=back_button,
    parse_mode="Markdown"
)
```

## 🔍 Пример 5: Проверка здоровья сервисов

### Автоматическая проверка при запуске Core Bot Service

#### 1. Проверка Music Processing Service
```python
# Core Bot Service → Music Processing Service
async with httpx.AsyncClient() as client:
    response = await client.get(f"{MUSIC_SERVICE_URL}/health", timeout=5.0)
    if response.status_code == 200:
        logging.info("✅ Music Processing Service доступен")
    else:
        logging.warning("⚠️ Music Processing Service недоступен")

# HTTP запрос:
GET /health
```

**Ответ Music Processing Service:**
```json
{
  "status": "healthy",
  "service": "Music Processing Service",
  "timestamp": 1705312200.123,
  "redis_connected": true
}
```

#### 2. Проверка Data Storage Service
```python
# Core Bot Service → Data Storage Service
async with httpx.AsyncClient() as client:
    response = await client.get(f"{STORAGE_SERVICE_URL}/health", timeout=5.0)
    if response.status_code == 200:
        logging.info("✅ Data Storage Service доступен")
    else:
        logging.warning("⚠️ Data Storage Service недоступен")

# HTTP запрос:
GET /health
```

**Ответ Data Storage Service:**
```json
{
  "status": "healthy",
  "service": "Data Storage Service",
  "timestamp": 1705312200.456,
  "database_connected": true
}
```

## 📊 Диаграмма взаимодействия

```
Пользователь → Core Bot Service
                ↓
        ┌─────────────────┐
        │   Проверка      │
        │     кеша        │
        └─────────────────┘
                ↓
        Data Storage Service
                ↓
        ┌─────────────────┐
        │   Поиск         │
        │   музыки        │
        └─────────────────┘
                ↓
        Music Processing Service
                ↓
        ┌─────────────────┐
        │   Сохранение    │
        │   в кеш         │
        └─────────────────┘
                ↓
        Data Storage Service
                ↓
        ┌─────────────────┐
        │   Отправка      │
        │   результатов   │
        └─────────────────┘
                ↓
        Пользователь
```

## 🚀 Оптимизация взаимодействия

### 1. Асинхронные запросы
```python
# Параллельные запросы к сервисам
async def check_services_health():
    tasks = [
        check_music_service(),
        check_storage_service()
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results
```

### 2. Кеширование результатов
```python
# Кеш на уровне Core Bot Service
@lru_cache(maxsize=100)
def get_cached_service_response(service_url: str, endpoint: str):
    # Кеширование ответов сервисов
    pass
```

### 3. Retry логика
```python
# Повторные попытки при ошибках
async def make_service_request_with_retry(client, url, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = await client.get(url, timeout=10.0)
            return response
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
```

### 4. Circuit Breaker
```python
# Защита от каскадных сбоев
class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    async def call(self, func, *args, **kwargs):
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF_OPEN"
            else:
                raise Exception("Circuit breaker is OPEN")
        
        try:
            result = await func(*args, **kwargs)
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
            
            raise e
```

## 🔒 Безопасность взаимодействия

### 1. API ключи
```python
# Проверка API ключей в каждом сервисе
async def verify_api_key(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="API ключ не предоставлен")
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Неверный формат авторизации")
    
    api_key = authorization.replace("Bearer ", "")
    if api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Неверный API ключ")
    
    return api_key
```

### 2. Rate Limiting
```python
# Ограничение частоты запросов
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/search")
@limiter.limit("10/minute")
async def search_music(request: Request, ...):
    # Максимум 10 запросов в минуту с одного IP
    pass
```

### 3. Валидация данных
```python
# Pydantic модели для валидации
class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=100)
    limit: int = Field(default=10, ge=1, le=50)

class DownloadRequest(BaseModel):
    url: str = Field(..., regex=r'^https?://.*')
    user_id: str = Field(..., min_length=1, max_length=50)
```

---

**Эти примеры демонстрируют, как три микросервиса работают вместе для обеспечения функциональности Telegram бота! 🎉**
