import os
import concurrent.futures
from .sqlite import SQLiteStorage
from .redis import RedisStorage

class CachedStorage:
    def __init__(self):
        self.sqlite = SQLiteStorage()
        redis_url = os.environ.get("REDIS_URL")
        self.redis = RedisStorage(redis_url) if redis_url else None
        # Single worker queue to serialize SQLite writes without blocking API
        self.writer_queue = concurrent.futures.ThreadPoolExecutor(max_workers=1)

    def save(self, record: dict) -> None:
        if self.redis:
            self.redis.save(record)
        # Offload SQLite write to background thread
        self.writer_queue.submit(self.sqlite.save, record)

    def get_recent(self, user_id: str, window_seconds: int = 60) -> list[tuple]:
        if self.redis:
            try:
                return self.redis.get_recent(user_id, window_seconds)
            except Exception as e:
                print(f"Redis get_recent error: {e}")
        return self.sqlite.get_recent(user_id, window_seconds)

    def get_total_today(self, user_id: str) -> float:
        if self.redis:
            try:
                return self.redis.get_total_today(user_id)
            except Exception as e:
                print(f"Redis get_total_today error: {e}")
        return self.sqlite.get_total_today(user_id)

    def get_history(self, user_id: str, limit: int = 100) -> list[tuple]:
        return self.sqlite.get_history(user_id, limit)

storage = CachedStorage()
Storage = CachedStorage  # keeping for backward compatibility in types
__all__ = ["Storage", "storage"]