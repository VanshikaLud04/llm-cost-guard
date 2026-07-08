from fastapi import FastAPI, Depends, HTTPException, Header, Request
from pydantic import BaseModel
import time
import asyncio
import redis
import json
import uuid

app = FastAPI()
redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

# In-memory DB
dummy_db = []

def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != "test_api_key_123":
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return x_api_key

class ChatRequest(BaseModel):
    message: str
    idempotency_key: str | None = None

async def call_mock():
    # Simulate 100ms LLM latency
    await asyncio.sleep(0.1)
    return {"response": "Mock LLM Response", "tokens": 42}

@app.post("/chat_no_idempotency")
async def chat_no_idempotency(req: ChatRequest, api_key: str = Depends(verify_api_key)):
    # Dummy DB save
    dummy_db.append({"msg": req.message, "time": time.time()})
    
    # Mock LLM call
    llm_resp = await call_mock()
    return llm_resp

@app.post("/chat_with_idempotency")
async def chat_with_idempotency(req: ChatRequest, api_key: str = Depends(verify_api_key)):
    if not req.idempotency_key:
        raise HTTPException(status_code=400, detail="Idempotency key required")
        
    cache_key = f"idem:{req.idempotency_key}"
    
    # 1. Redis GET (Cache check)
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)
        
    # Dummy DB save
    dummy_db.append({"msg": req.message, "time": time.time()})
    
    # Mock LLM call
    llm_resp = await call_mock()
    
    # 2. Redis SET (Save result)
    redis_client.setex(cache_key, 3600, json.dumps(llm_resp))
    
    return llm_resp
