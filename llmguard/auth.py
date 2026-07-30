import os
import time
from fastapi import HTTPException, Security, Depends
from fastapi.security import APIKeyHeader
from passlib.context import CryptContext
import jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from .storage.postgres import async_session
from .models import User, ApiKey, Organization

from .config import settings

SECRET_KEY = settings.JWT_SECRET
ALGORITHM = settings.JWT_ALGORITHM

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=False)
jwt_header = APIKeyHeader(name="Authorization", auto_error=False)

async def get_db():
    async with async_session() as session:
        yield session

def create_access_token(data: dict, expires_delta: int = 3600):
    to_encode = data.copy()
    to_encode.update({"exp": time.time() + expires_delta})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(
    api_key: str = Security(api_key_header),
    token: str = Security(jwt_header),
    db: AsyncSession = Depends(get_db)
):
    user = None
    if api_key:
        stmt = select(User).options(joinedload(User.organization)).join(ApiKey).where(ApiKey.key_hash == api_key)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
    elif token:
        try:
            if token.startswith("Bearer "):
                token = token.split(" ")[1]
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id: str = payload.get("sub")
            if user_id:
                stmt = select(User).options(joinedload(User.organization)).where(User.id == user_id)
                result = await db.execute(stmt)
                user = result.scalar_one_or_none()
        except jwt.PyJWTError:
            pass

    if not user:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    return user
