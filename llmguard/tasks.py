import asyncio
import logging
from .celery_app import celery_app
from .storage import storage

logger = logging.getLogger(__name__)

@celery_app.task(name="tasks.save_usage_record")
def save_usage_record(record: dict):
    """
    Saves the usage record asynchronously.
    """
    try:
        # Run the async save function in a synchronous Celery task
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # In case the event loop is already running (rare in Celery worker)
            asyncio.ensure_future(storage.postgres.save(record))
        else:
            loop.run_until_complete(storage.postgres.save(record))
    except Exception as e:
        logger.error(f"Failed to save usage record: {e}", extra={"record": record})
        raise

@celery_app.task(name="tasks.save_cache_entry")
def save_cache_entry(cache_id: str, org_id: str, prompt: str, embedding: list, response: str):
    try:
        from .storage.postgres import async_session
        from .models import CacheEntry
        import time

        async def _save():
            async with async_session() as session:
                entry = CacheEntry(
                    id=cache_id,
                    org_id=org_id,
                    prompt=prompt,
                    prompt_embedding=embedding,
                    response=response,
                    ttl_expires_at=time.time() + 604800,
                    hit_count=1
                )
                session.add(entry)
                await session.commit()
                
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(_save())
        else:
            loop.run_until_complete(_save())
    except Exception as e:
        logger.error(f"Failed to save cache entry: {e}", extra={"cache_id": cache_id})
        raise
