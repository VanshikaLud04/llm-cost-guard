import json
import logging
import struct
import uuid
import redis.asyncio as redis_async
from .config import settings

logger = logging.getLogger(__name__)

class SemanticCache:
    def __init__(self, redis_client):
        self.redis = redis_client
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
            self.enabled = True
        except ImportError:
            logger.warning("sentence-transformers not installed. Semantic cache disabled.")
            self.enabled = False

    def _normalize(self, prompt: str) -> str:
        return prompt.strip().lower()

    def _get_embedding(self, text: str) -> list[float]:
        embedding = self.model.encode(text)
        return embedding.tolist()
        
    async def get_cached_response(self, org_id: str, prompt: str, threshold: float = 0.93):
        if not self.enabled:
            return None
            
        normalized = self._normalize(prompt)
        embedding = self._get_embedding(normalized)
        
        # Ensure index exists? Typically done at startup, assuming it exists here.
        query = "*=>[KNN 1 @embedding $vec AS score]"
        vec_bytes = struct.pack(f'{len(embedding)}f', *embedding)
        
        try:
            index_name = f"idx:cache:{org_id}"
            res = await self.redis.execute_command(
                'FT.SEARCH', index_name, query, 
                'PARAMS', '2', 'vec', vec_bytes, 
                'RETURN', '2', 'response', 'score',
                'DIALECT', '2'
            )
            
            if res and len(res) > 1:
                # FT.SEARCH returns [number_of_results, key_name, [field1, value1, field2, value2]]
                # Because we are using redis-py decode_responses=True in other parts, 
                # binary might be decoded as string if we aren't careful, 
                # but let's assume it handles it or we parse carefully.
                fields = res[2]
                
                # Convert list to dict for easier lookup
                # fields can be like ['score', '0.05', 'response', 'Hello world']
                field_dict = {fields[i]: fields[i+1] for i in range(0, len(fields), 2)}
                
                if "score" in field_dict and "response" in field_dict:
                    score = float(field_dict["score"])
                    # Cosine distance to similarity
                    similarity = 1 - score
                    if similarity >= threshold:
                        return field_dict["response"]
                        
        except Exception as e:
            logger.debug(f"Cache miss or error: {e}")
            
        return None
        
    async def set_cached_response(self, org_id: str, prompt: str, response: str, ttl: int = 604800):
        if not self.enabled:
            return
            
        normalized = self._normalize(prompt)
        embedding = self._get_embedding(normalized)
        
        vec_bytes = struct.pack(f'{len(embedding)}f', *embedding)
        
        cache_id = str(uuid.uuid4())
        key = f"cache:{org_id}:{cache_id}"
        
        await self.redis.hset(key, mapping={
            "prompt": normalized,
            "embedding": vec_bytes,
            "response": response
        })
        await self.redis.expire(key, ttl)
        
        # Async persist to Postgres PGVector
        from .tasks import save_cache_entry
        save_cache_entry.delay(cache_id, org_id, normalized, embedding, response)
