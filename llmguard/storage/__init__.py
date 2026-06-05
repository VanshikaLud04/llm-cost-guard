import os
from .sqlite import SQLiteStorage
from .redis import RedisStorage

class CachedStorage:
    def __init__(self):
        self.sqlite = SQLiteStorage()
        redis_url = os.environ.get("REDIS_URL")
        self.redis = RedisStorage(redis_url) if redis_url else None

    def save(self, record: dict) -> None:
        self.sqlite.save(record)
        if self.redis:
            self.redis.save(record)

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

Storage = CachedStorage
__all__ = ["Storage"]