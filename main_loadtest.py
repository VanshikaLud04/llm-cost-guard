"""
Self-contained FastAPI app for load testing.
- Uses in-memory storage (no PostgreSQL needed)
- Uses real Redis for idempotency (if available, else skips check)
- Uses mock LLM provider (no real API keys needed)
- Hardcoded test API Key: "test_api_key_123"

Run with:
    uvicorn main_loadtest:app --reload --port 8001
"""
import time
import uuid
import json
import logging
import os
from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from prometheus_client import make_asgi_app, Counter, Histogram

# --- In-Memory Storage ---
_usage_store: list[dict] = []

def save_record(record: dict):
    _usage_store.append(record)

def get_recent(user_id: str, window_seconds: int = 60):
    cutoff = time.time() - window_seconds
    return [(r["cost"], r["timestamp"]) for r in _usage_store
            if r["user_id"] == user_id and r["timestamp"] >= cutoff]

def get_total_today(user_id: str):
    cutoff = time.time() - 86400
    return sum(r["cost"] for r in _usage_store
               if r["user_id"] == user_id and r["timestamp"] >= cutoff)

# --- Redis Idempotency (optional) ---
redis_client = None
try:
    import redis
    rc = redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)
    rc.ping()
    redis_client = rc
    print("[load-test] Redis connected — idempotency checks ENABLED")
except Exception as e:
    print(f"[load-test] Redis not available ({e}) — idempotency checks DISABLED")

# --- Mock LLM ---
from llmguard.mock_provider import call_mock
from llmguard.cost import calculate_cost

TEST_API_KEY = "test_api_key_123"

# --- Prometheus Metrics ---
REQUEST_COUNT = Counter("lt_request_count", "Total Requests", ["endpoint"])
REQUEST_LATENCY = Histogram("lt_request_latency_seconds", "Request Latency", ["endpoint"])
REDIS_LATENCY = Histogram("lt_redis_latency_seconds", "Redis Idempotency Check Latency")

app = FastAPI(title="LLM Cost Guard — Load Test Mode", version="2.0.0-loadtest")
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

class ChatRequest(BaseModel):
    message: str
    model: str = "mock"
    use_fallback: bool = False
    temperature: float = 0.7
    max_tokens: int = 1024

@app.middleware("http")
async def request_middleware(request: Request, call_next):
    request.state.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    response = await call_next(request)
    return response

@app.post("/chat")
async def chat(
    request: Request,
    req: ChatRequest,
    x_api_key: str = Header(None, alias="X-API-KEY"),
    idempotency_key: str = Header(None, alias="Idempotency-Key")
):
    # Auth
    if x_api_key != TEST_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    user_id = "load_test_user"

    # Idempotency check — time it
    if idempotency_key and redis_client:
        t0 = time.perf_counter()
        cache_key = f"idemp:{user_id}:{idempotency_key}"
        cached = redis_client.get(cache_key)
        redis_latency = (time.perf_counter() - t0) * 1000  # ms
        REDIS_LATENCY.observe(redis_latency / 1000)
        if cached:
            return JSONResponse(content=json.loads(cached))

    # Call mock LLM
    messages = [{"role": "user", "content": req.message}]
    resp = call_mock(req.model, messages, req.temperature, req.max_tokens)
    cost = calculate_cost("gpt-4o-mini", resp.input_tokens, resp.output_tokens)

    # Save record in memory (async-safe via simple list append)
    save_record({
        "user_id": user_id,
        "model": req.model,
        "input_tokens": resp.input_tokens,
        "output_tokens": resp.output_tokens,
        "cost": cost,
        "timestamp": time.time()
    })

    resp_data = {
        "user_id": user_id,
        "model_used": resp.model,
        "response": resp.content,
    }

    if idempotency_key and redis_client:
        redis_client.set(cache_key, json.dumps(resp_data), ex=3600)

    return resp_data

@app.get("/stats")
async def stats(x_api_key: str = Header(None, alias="X-API-KEY")):
    if x_api_key != TEST_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    user_id = "load_test_user"
    records_1h = get_recent(user_id, window_seconds=3600)
    total_today = get_total_today(user_id)
    n = len(records_1h)
    cost_1h = sum(r[0] for r in records_1h)
    return {
        "user_id": user_id,
        "requests_last_hour": n,
        "cost_last_hour": round(cost_1h, 8),
        "avg_cost_per_request": round(cost_1h / n, 8) if n else 0.0,
        "total_cost_today": round(total_today, 8),
    }

@app.get("/health")
def health():
    return {"status": "ok", "mode": "load-test", "redis": redis_client is not None}
