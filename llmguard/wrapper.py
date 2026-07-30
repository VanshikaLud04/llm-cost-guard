import time, logging
import asyncio
from .cost import calculate_cost
from .providers import route_call, route_stream, NormalizedResponse
from .pricing import FALLBACK_CHAIN, MODEL_PROVIDER
from .exceptions import BudgetExceededException, DailyBudgetExceededException, AllModelsExhaustedException
from .config import settings
from ..retry_decorator import retry
from .tasks import save_usage_record
from .models import User
from .rate_limiter import TokenRateLimiter
from .policy import PolicyEngine
from .semantic_cache import SemanticCache
from .router import RuleRouter
from .circuit_breaker import CircuitBreaker, CircuitBreakerState

logger = logging.getLogger(__name__)

@retry(max_attempts=3)
def _route_call_with_retry(model, messages, temperature, max_tokens):
    # Retry on the synchronous provider call
    return route_call(model, messages, temperature, max_tokens)

async def call_llm(user: User, model: str, messages: list, storage, redis_client, temperature: float = 0.7, max_tokens: int = 1024) -> NormalizedResponse:
    policy_engine = PolicyEngine(redis_client)
    rate_limiter = TokenRateLimiter(redis_client)
    cache = SemanticCache(redis_client)
    cb = CircuitBreaker(redis_client)
    
    # 1. Resolve Policy
    policy = await policy_engine.get_policy(user.org_id, user.role)
    if model not in policy["allowed_models"]:
        raise ValueError(f"Model {model} not allowed by policy.")

    # 1.2 Check Circuit Breaker
    provider_name = MODEL_PROVIDER.get(model, "unknown")
    state = await cb.get_state(provider_name)
    if state == CircuitBreakerState.OPEN:
        raise ValueError(f"Circuit breaker OPEN for provider {provider_name}")

    # 1.5 Check Cache
    prompt = messages[-1]["content"] if messages else ""
    cached_response = await cache.get_cached_response(user.org_id, prompt)
    if cached_response:
        return NormalizedResponse(cached_response, 0, 0, model, {"cached": True})

    # 2. Reserve Tokens
    estimated_tokens = sum(len(m["content"]) // 4 for m in messages) + max_tokens
    reservation_id = await rate_limiter.reserve(user.org_id, user.role, estimated_tokens, policy["token_limits"])
    
    try:
        # 3. Call Provider
        resp = await asyncio.to_thread(_route_call_with_retry, model, messages, temperature, max_tokens)
        await cb.record_success(provider_name)
    except Exception as e:
        await cb.record_failure(provider_name)
        raise e
    
    # 4. Reconcile
    actual_tokens = resp.input_tokens + resp.output_tokens
    await rate_limiter.reconcile(reservation_id, actual_tokens)
    
    if resp.input_tokens > 0:
        await cache.set_cached_response(user.org_id, prompt, resp.content)
    
    cost = calculate_cost(model, resp.input_tokens, resp.output_tokens)
    
    record = {
        "user_id": user.id,
        "org_id": user.org_id,
        "model": model, 
        "input_tokens": resp.input_tokens, 
        "output_tokens": resp.output_tokens, 
        "cost": cost, 
        "timestamp": time.time()
    }
    save_usage_record.delay(record)
    
    return resp

async def call_llm_with_fallback(user: User, messages: list, storage, redis_client, preferred_model: str = "gpt-4o", temperature: float = 0.7, max_tokens: int = 1024) -> NormalizedResponse:
    policy_engine = PolicyEngine(redis_client)
    policy = await policy_engine.get_policy(user.org_id, user.role)
    allowed = policy["allowed_models"]
    
    cb = CircuitBreaker(redis_client)
    healthy_allowed = []
    for m in allowed:
        provider = MODEL_PROVIDER.get(m, "unknown")
        if await cb.get_state(provider) != CircuitBreakerState.OPEN:
            healthy_allowed.append(m)
            
    if not healthy_allowed:
        raise AllModelsExhaustedException("No healthy allowed models available")
        
    router = RuleRouter()
    prompt = messages[-1]["content"] if messages else ""
    
    candidates = []
    if preferred_model in healthy_allowed:
        candidates.append(preferred_model)
    
    routed_model = router.select_model(prompt, healthy_allowed)
    if routed_model not in candidates:
        candidates.append(routed_model)
        
    for m in healthy_allowed:
        if m not in candidates:
            candidates.append(m)
            
    for model in candidates:
        try:
            return await call_llm(user, model, messages, storage, redis_client, temperature, max_tokens)
        except (BudgetExceededException, DailyBudgetExceededException):
            raise
        except ValueError:
            continue
        except Exception:
            continue
            
            
    raise AllModelsExhaustedException("All models exhausted or not allowed")

async def stream_llm(user: User, model: str, messages: list, storage, redis_client, temperature: float = 0.7, max_tokens: int = 1024):
    policy_engine = PolicyEngine(redis_client)
    rate_limiter = TokenRateLimiter(redis_client)
    cb = CircuitBreaker(redis_client)
    
    policy = await policy_engine.get_policy(user.org_id, user.role)
    if model not in policy["allowed_models"]:
        raise ValueError(f"Model {model} not allowed by policy.")

    provider_name = MODEL_PROVIDER.get(model, "unknown")
    state = await cb.get_state(provider_name)
    if state == CircuitBreakerState.OPEN:
        raise ValueError(f"Circuit breaker OPEN for provider {provider_name}")

    estimated_tokens = sum(len(m["content"]) // 4 for m in messages) + max_tokens
    reservation_id = await rate_limiter.reserve(user.org_id, user.role, estimated_tokens, policy["token_limits"])
    
    stream_gen = route_stream(model, messages, temperature, max_tokens)
    
    actual_in = 0
    actual_out = 0
    
    try:
        async for text, inp, out in stream_gen:
            actual_in = inp
            actual_out = out
            yield text
        await cb.record_success(provider_name)
    except Exception as e:
        await cb.record_failure(provider_name)
        raise e
    finally:
        actual_tokens = actual_in + actual_out
        if actual_tokens > 0:
            # We can't await inside finally of an async generator in older Pythons without care, but Python 3.8+ supports it.
            await rate_limiter.reconcile(reservation_id, actual_tokens)
            cost = calculate_cost(model, actual_in, actual_out)
            record = {
                "user_id": user.id,
                "org_id": user.org_id,
                "model": model, 
                "input_tokens": actual_in, 
                "output_tokens": actual_out, 
                "cost": cost, 
                "timestamp": time.time()
            }
            save_usage_record.delay(record)