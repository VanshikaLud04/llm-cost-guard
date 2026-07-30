import time
import logging
from fastapi import FastAPI, HTTPException, Request, Depends, Header, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import uuid
import json
from prometheus_client import make_asgi_app, Counter, Histogram
import redis.asyncio as redis_async
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

load_dotenv()

from llmguard.wrapper import call_llm, call_llm_with_fallback, stream_llm
from llmguard.storage import CachedStorage, get_storage
from llmguard.burn import calculate_burn_rate
from llmguard.config import settings
from llmguard.exceptions import (
    BudgetExceededException,
    DailyBudgetExceededException,
    AllModelsExhaustedException,
    UnknownModelException
)
from llmguard.auth import get_current_user
from llmguard.models import User
from llmguard.logging_config import logger
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)

# Prometheus Metrics
REQUEST_COUNT = Counter("request_count", "Total HTTP Requests", ["method", "endpoint", "http_status"])
REQUEST_LATENCY = Histogram("request_latency_seconds", "HTTP Request Latency", ["endpoint"])
TOKEN_CONSUMPTION = Counter("token_consumption", "Total tokens consumed", ["model", "user_id"])

app = FastAPI(
    title="LLM Cost Guard",
    description="Cost-aware middleware for LLM APIs with real-time killswitch and budget enforcement.",
    version="2.0.0",
)
app.state.limiter = limiter

# Add Prometheus asgi app
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

FastAPIInstrumentor.instrument_app(app)

# Redis for Idempotency
redis_client = redis_async.from_url(settings.REDIS_URL)

@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    
    REQUEST_COUNT.labels(request.method, request.url.path, response.status_code).inc()
    REQUEST_LATENCY.labels(request.url.path).observe(process_time)
    
    logger.info("Request processed", extra={
        "request_id": request_id,
        "path": request.url.path,
        "method": request.method,
        "status_code": response.status_code,
        "process_time": process_time
    })
    
    response.headers["X-Request-ID"] = request_id
    return response

@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request, exc):
    return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded. Try again later."})

class ChatRequest(BaseModel):
    message: str
    model: str = "gpt-4o-mini"
    use_fallback: bool = False
    temperature: float = 0.7
    max_tokens: int = 1024
    stream: bool = False

class ChatResponse(BaseModel):
    user_id: str
    model_used: str
    response: str

class StatsResponse(BaseModel):
    user_id: str
    requests_last_hour: int
    cost_last_hour: float
    avg_cost_per_request: float
    total_cost_today: float
    burn_rate_per_min: float

@app.post("/chat", response_model=ChatResponse)
@limiter.limit("30/minute")
async def chat(
    request: Request,
    req: ChatRequest,
    current_user: User = Depends(get_current_user),
    storage: CachedStorage = Depends(get_storage),
    idempotency_key: str = Header(None, alias="Idempotency-Key")
):
    request_id = request.state.request_id
    logger.info("Chat request received", extra={"user_id": current_user.id, "request_id": request_id, "model": req.model})
    
    if idempotency_key:
        cache_key = f"idemp:{current_user.id}:{idempotency_key}"
        cached_response = await redis_client.get(cache_key)
        if cached_response:
            logger.info("Returning cached response for idempotent request", extra={"user_id": current_user.id, "request_id": request_id})
            return JSONResponse(content=json.loads(cached_response))

    messages = [{"role": "user", "content": req.message}]

    try:
        if req.stream:
            async def event_generator():
                async for chunk in stream_llm(
                    current_user, req.model, messages, storage, redis_client,
                    temperature=req.temperature, max_tokens=req.max_tokens
                ):
                    yield f"data: {chunk}\n\n"
                yield "data: [DONE]\n\n"
                
            return StreamingResponse(event_generator(), media_type="text/event-stream")

        if req.use_fallback:
            llm_response = await call_llm_with_fallback(
                current_user, messages, storage, redis_client, preferred_model=req.model,
                temperature=req.temperature, max_tokens=req.max_tokens
            )
        else:
            llm_response = await call_llm(
                current_user, req.model, messages, storage, redis_client,
                temperature=req.temperature, max_tokens=req.max_tokens
            )
            
        TOKEN_CONSUMPTION.labels(llm_response.model, current_user.id).inc(llm_response.input_tokens + llm_response.output_tokens)
        
    except (BudgetExceededException, DailyBudgetExceededException, AllModelsExhaustedException) as e:
        logger.warning(f"Limit exceeded: {e}", extra={"user_id": current_user.id, "request_id": request_id})
        raise HTTPException(status_code=429, detail=str(e))
    except UnknownModelException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"LLM call failed: {e}", extra={"user_id": current_user.id, "request_id": request_id})
        raise HTTPException(status_code=500, detail=f"LLM call failed: {e}")

    resp_data = {
        "user_id": current_user.id,
        "model_used": llm_response.model,
        "response": llm_response.content,
    }

    if idempotency_key:
        await redis_client.set(cache_key, json.dumps(resp_data), ex=86400) # cache for 24h

    return resp_data
    
@app.get("/stats", response_model=StatsResponse)
async def stats(current_user: User = Depends(get_current_user), storage: CachedStorage = Depends(get_storage)):
    records_1h = await storage.get_recent(current_user.id, window_seconds=3600)
    records_1m = await storage.get_recent(current_user.id, window_seconds=settings.BURN_RATE_WINDOW_SECONDS)
    total_today = await storage.get_total_today(current_user.id)
    
    # get_recent returns [(cost, timestamp)] or just tuples if we adjusted postgres to match
    # Wait, postgres.py returns Row objects, so r.cost if accessed as attribute or r[0]. 
    # In postgres.py: select(UsageRecord.cost, UsageRecord.timestamp) returns a tuple (cost, timestamp)
    cost_1h = sum(r[0] for r in records_1h)
    burn_rate = calculate_burn_rate(records_1m)
    n = len(records_1h)
    
    return StatsResponse(
        user_id=current_user.id,
        requests_last_hour=n,
        cost_last_hour=round(cost_1h, 8),
        avg_cost_per_request=round(cost_1h / n, 8) if n else 0.0,
        total_cost_today=round(total_today, 8),
        burn_rate_per_min=round(burn_rate, 8),
    )

@app.get("/health")
def health():
    return {"status": "ok", "providers": ["openai", "anthropic", "groq"], "db": "postgres"}
