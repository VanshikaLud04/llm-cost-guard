import time
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, func
from .base import BaseStorage
from ..models import Base, UsageRecord

from ..config import settings
DATABASE_URL = settings.DATABASE_URL

engine = create_async_engine(DATABASE_URL, echo=False, pool_size=20, max_overflow=10)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

class PostgresStorage(BaseStorage):
    def __init__(self):
        pass

    async def save(self, record: dict):
        async with async_session() as session:
            usage = UsageRecord(
                user_id=record["user_id"],
                org_id=record.get("org_id"),
                model=record["model"],
                input_tokens=record["input_tokens"],
                output_tokens=record["output_tokens"],
                cost=record["cost"],
                timestamp=record["timestamp"]
            )
            session.add(usage)
            await session.commit()

    async def get_recent(self, user_id: str, window_seconds: int = 60):
        async with async_session() as session:
            stmt = select(UsageRecord.cost, UsageRecord.timestamp).where(
                UsageRecord.user_id == user_id,
                UsageRecord.timestamp >= (time.time() - window_seconds)
            )
            result = await session.execute(stmt)
            return result.all()

    async def get_total_today(self, user_id: str):
        async with async_session() as session:
            stmt = select(func.sum(UsageRecord.cost)).where(
                UsageRecord.user_id == user_id,
                UsageRecord.timestamp >= (time.time() - 86400)
            )
            result = await session.execute(stmt)
            return result.scalar() or 0.0

    async def get_history(self, user_id: str, limit: int = 100):
        async with async_session() as session:
            stmt = select(UsageRecord).where(
                UsageRecord.user_id == user_id
            ).order_by(UsageRecord.timestamp.desc()).limit(limit)
            result = await session.execute(stmt)
            records = result.scalars().all()
            return [(r.user_id, r.model, r.input_tokens, r.output_tokens, r.cost, r.timestamp) for r in records]
