import time
import uuid
import logging
from .storage.__init__ import get_storage
from .exceptions import BudgetExceededException

logger = logging.getLogger(__name__)

# Lua script for Reserve-Reconcile token bucket/window.
# It reserves tokens across multiple time windows (minute, hour, day).
# KEYS: [key_min, key_hour, key_day]
# ARGV: [tokens_to_reserve, limit_min, limit_hour, limit_day, ttl_min, ttl_hour, ttl_day]
RESERVE_LUA = """
local key_min = KEYS[1]
local key_hour = KEYS[2]
local key_day = KEYS[3]

local tokens = tonumber(ARGV[1])
local limit_min = tonumber(ARGV[2])
local limit_hour = tonumber(ARGV[3])
local limit_day = tonumber(ARGV[4])

local current_min = tonumber(redis.call('GET', key_min) or "0")
local current_hour = tonumber(redis.call('GET', key_hour) or "0")
local current_day = tonumber(redis.call('GET', key_day) or "0")

if current_min + tokens > limit_min then return -1 end
if current_hour + tokens > limit_hour then return -2 end
if current_day + tokens > limit_day then return -3 end

redis.call('INCRBY', key_min, tokens)
if current_min == 0 then redis.call('EXPIRE', key_min, tonumber(ARGV[5])) end

redis.call('INCRBY', key_hour, tokens)
if current_hour == 0 then redis.call('EXPIRE', key_hour, tonumber(ARGV[6])) end

redis.call('INCRBY', key_day, tokens)
if current_day == 0 then redis.call('EXPIRE', key_day, tonumber(ARGV[7])) end

return 1
"""

class TokenRateLimiter:
    def __init__(self, redis_client):
        self.redis = redis_client
        self.reserve_script = self.redis.register_script(RESERVE_LUA)

    async def reserve(self, org_id: str, role: str, estimated_tokens: int, policy_limits: dict) -> str:
        # Construct keys for current time windows
        now = int(time.time())
        min_ts = now // 60
        hour_ts = now // 3600
        day_ts = now // 86400
        
        base_key = f"ratelimit:{org_id}:{role}"
        keys = [
            f"{base_key}:min:{min_ts}",
            f"{base_key}:hour:{hour_ts}",
            f"{base_key}:day:{day_ts}"
        ]
        
        # Default limits if not specified
        limit_min = policy_limits.get("minute", 100000)
        limit_hour = policy_limits.get("hour", 500000)
        limit_day = policy_limits.get("day", 2000000)
        
        result = await self.reserve_script(keys=keys, args=[
            estimated_tokens, 
            limit_min, limit_hour, limit_day,
            60, 3600, 86400
        ])
        
        if result == -1:
            raise BudgetExceededException("Minute token budget exceeded")
        elif result == -2:
            raise BudgetExceededException("Hour token budget exceeded")
        elif result == -3:
            raise BudgetExceededException("Day token budget exceeded")
            
        reservation_id = str(uuid.uuid4())
        # Store reservation for reconciliation
        await self.redis.hset(f"reservation:{reservation_id}", mapping={
            "keys": ",".join(keys),
            "reserved": estimated_tokens
        })
        await self.redis.expire(f"reservation:{reservation_id}", 3600)
        
        return reservation_id

    async def reconcile(self, reservation_id: str, actual_tokens: int):
        res_key = f"reservation:{reservation_id}"
        reservation = await self.redis.hgetall(res_key)
        if not reservation:
            return # Already reconciled or expired
            
        reserved = int(reservation["reserved"])
        keys = reservation["keys"].split(",")
        
        diff = actual_tokens - reserved
        
        if diff != 0:
            # Reconcile all keys
            for k in keys:
                await self.redis.incrby(k, diff)
                
        await self.redis.delete(res_key)
