import json
import time
import redis
from .base import BaseStorage

class RedisStorage(BaseStorage):
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis_url = redis_url
        self.client = redis.from_url(redis_url, decode_responses=True)
        print(f"Redis storage initialized at {redis_url}")

    def _get_key(self, user_id: str):
        return f"usage:{user_id}"

    def save(self, record: dict) -> None:
        key = self._get_key(record["user_id"])
        # Store the record as a JSON string in a sorted set, scored by timestamp
        self.client.zadd(key, {json.dumps(record): record["timestamp"]})
        # Keep only the last 24 hours of data to manage memory
        cutoff = time.time() - 86400
        self.client.zremrangebyscore(key, "-inf", cutoff)

    def get_recent(self, user_id: str, window_seconds: int = 60) -> list[tuple]:
        key = self._get_key(user_id)
        cutoff = time.time() - window_seconds
        records = self.client.zrangebyscore(key, cutoff, "+inf")
        # Return list of (cost, timestamp) as expected by the application
        result = []
        for r in records:
            data = json.loads(r)
            result.append((data["cost"], data["timestamp"]))
        return result

    def get_total_today(self, user_id: str) -> float:
        key = self._get_key(user_id)
        cutoff = time.time() - 86400
        records = self.client.zrangebyscore(key, cutoff, "+inf")
        total = 0.0
        for r in records:
            data = json.loads(r)
            total += data["cost"]
        return total

    def get_history(self, user_id: str, limit: int = 100) -> list[tuple]:
        key = self._get_key(user_id)
        # Get the latest records
        records = self.client.zrevrange(key, 0, limit - 1)
        result = []
        for r in records:
            data = json.loads(r)
            result.append((user_id, data["model"], data["input_tokens"], data["output_tokens"], data["cost"], data["timestamp"]))
        return result