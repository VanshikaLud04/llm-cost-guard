import os
from .postgres import PostgresStorage
from .redis import RedisStorage
from .base import BaseStorage

class CachedStorage(BaseStorage):
    def __init__(self, postgres: BaseStorage, redis: BaseStorage = None):
        self.postgres = postgres
        self.redis = redis

    async def save(self, record: dict) -> None:
        if self.redis:
            self.redis.save(record)
        # Note: In the new architecture, saving to Postgres is typically offloaded to a Celery task.
        # This method can be used for direct async saves if needed.
        await self.postgres.save(record)

    async def get_recent(self, user_id: str, window_seconds: int = 60) -> list[tuple]:
        if self.redis:
            try:
                return self.redis.get_recent(user_id, window_seconds)
            except Exception as e:
                print(f"Redis get_recent error: {e}")
        return await self.postgres.get_recent(user_id, window_seconds)

    async def get_total_today(self, user_id: str) -> float:
        if self.redis:
            try:
                return self.redis.get_total_today(user_id)
            except Exception as e:
                print(f"Redis get_total_today error: {e}")
        return await self.postgres.get_total_today(user_id)

    async def get_history(self, user_id: str, limit: int = 100) -> list[tuple]:
        return await self.postgres.get_history(user_id, limit)

_storage_instance = None

def get_storage() -> CachedStorage:
    global _storage_instance
    if _storage_instance is None:
        from ..config import settings
        postgres = PostgresStorage()
        redis_url = settings.REDIS_URL
        redis = RedisStorage(redis_url) if redis_url else None
        _storage_instance = CachedStorage(postgres, redis)
    return _storage_instance

# For backwards compatibility with Celery tasks temporarily
storage = get_storage()
__all__ = ["CachedStorage", "get_storage", "storage"]