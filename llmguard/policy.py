import json
from .storage.postgres import async_session
from sqlalchemy import select
from .models import Policy

class PolicyEngine:
    def __init__(self, redis_client):
        self.redis = redis_client

    async def get_policy(self, org_id: str, role: str) -> dict:
        # Check cache first
        cache_key = f"policy:{org_id}:{role}"
        cached = await self.redis.get(cache_key)
        if cached:
            return json.loads(cached)
            
        # Fallback to DB
        async with async_session() as session:
            # Order by priority descending (highest priority wins)
            stmt = select(Policy).where(
                (Policy.org_id == org_id) | (Policy.org_id == None),
                (Policy.role == role) | (Policy.role == None)
            ).order_by(Policy.priority.desc())
            
            result = await session.execute(stmt)
            policy = result.scalars().first()
            
            if not policy:
                # Default empty policy
                policy_data = {
                    "allowed_models": [],
                    "token_limits": {"minute": 100000, "hour": 500000, "day": 2000000}
                }
            else:
                policy_data = {
                    "allowed_models": policy.allowed_models,
                    "token_limits": policy.token_limits
                }
                
            # Cache it
            await self.redis.set(cache_key, json.dumps(policy_data), ex=60)
            return policy_data
