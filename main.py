from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from dotenv import load_dotenv
load_dotenv()

from llmguard.wrapper import call_llm, call_llm_with_fallback
from llmguard.storage import storage
from llmguard.burn import calculate_burn_rate
from llmguard.config import BURN_RATE_WINDOW_SECONDS
from llmguard.exceptions import (
    BudgetExceededException,
    DailyBudgetExceededException,
    AllModelsExhaustedException,
)
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(                         
    title="LLM Cost Guard",
    description="Cost-aware middleware for LLM APIs with real-time killswitch and budget enforcement.",
    version="1.0.0",
    contact={"name": "Vanshika Ludhani"},
    swagger_ui_parameters={"syntaxHighlight.theme": "monokai"},
)

app.state.limiter = limiter             

@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request, exc):
    return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded. Try again later."})

class ChatRequest(BaseModel):
    user_id: str
    message: str
    model: str = "gpt-4o-mini"
    use_fallback: bool = False
    temperature: float = 0.7
    max_tokens: int = 1024

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
def chat(request: Request, req: ChatRequest):   
    messages = [{"role": "user", "content": req.message}]
    try:
        if req.use_fallback:
            llm_response = call_llm_with_fallback(
                req.user_id, messages, preferred_model=req.model,
                temperature=req.temperature, max_tokens=req.max_tokens
            )
        else:
            llm_response = call_llm(
                req.user_id, req.model, messages,
                temperature=req.temperature, max_tokens=req.max_tokens
            )
    except (BudgetExceededException, DailyBudgetExceededException, AllModelsExhaustedException) as e:
        raise HTTPException(status_code=429, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM call failed: {e}")

    return ChatResponse(
        user_id=req.user_id,
        model_used=llm_response.model,
        response=llm_response.content,
    )

@app.get("/stats/{user_id}", response_model=StatsResponse)
def stats(user_id: str):
    records_1h = storage.get_recent(user_id, window_seconds=3600)
    records_1m = storage.get_recent(user_id, window_seconds=BURN_RATE_WINDOW_SECONDS)
    total_today = storage.get_total_today(user_id)
    cost_1h = sum(r[0] for r in records_1h)
    burn_rate = calculate_burn_rate(records_1m)
    n = len(records_1h)
    return StatsResponse(
        user_id=user_id,
        requests_last_hour=n,
        cost_last_hour=round(cost_1h, 8),
        avg_cost_per_request=round(cost_1h / n, 8) if n else 0.0,
        total_cost_today=round(total_today, 8),
        burn_rate_per_min=round(burn_rate, 8),
    )

@app.get("/health")
def health():
    return {"status": "ok", "providers": ["openai", "anthropic", "groq"], "db": "sqlite"}