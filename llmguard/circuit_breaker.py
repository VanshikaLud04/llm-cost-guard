import time

class CircuitBreakerState:
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

class CircuitBreaker:
    def __init__(self, redis_client, threshold=5, cooldown=60):
        self.redis = redis_client
        self.threshold = threshold
        self.cooldown = cooldown
        
    async def get_state(self, provider_id: str) -> str:
        state_key = f"cb:{provider_id}:state"
        state = await self.redis.get(state_key)
        
        # In redis-py with decode_responses=True (which we assume or handle), state is str
        if isinstance(state, bytes):
            state = state.decode('utf-8')
            
        if not state:
            return CircuitBreakerState.CLOSED
            
        if state == CircuitBreakerState.OPEN:
            opened_at_key = f"cb:{provider_id}:opened_at"
            opened_at = await self.redis.get(opened_at_key)
            if opened_at and time.time() - float(opened_at) > self.cooldown:
                await self.redis.set(state_key, CircuitBreakerState.HALF_OPEN)
                return CircuitBreakerState.HALF_OPEN
        return state
        
    async def record_failure(self, provider_id: str):
        fail_key = f"cb:{provider_id}:fails"
        fails = await self.redis.incr(fail_key)
        if fails == 1:
            await self.redis.expire(fail_key, 30) # Window for failures
            
        if fails >= self.threshold:
            state_key = f"cb:{provider_id}:state"
            await self.redis.set(state_key, CircuitBreakerState.OPEN)
            await self.redis.set(f"cb:{provider_id}:opened_at", time.time())
            
    async def record_success(self, provider_id: str):
        state_key = f"cb:{provider_id}:state"
        await self.redis.set(state_key, CircuitBreakerState.CLOSED)
        await self.redis.delete(f"cb:{provider_id}:fails")
        await self.redis.delete(f"cb:{provider_id}:opened_at")
