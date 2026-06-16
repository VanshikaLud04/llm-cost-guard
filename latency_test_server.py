from fastapi import FastAPI, HTTPException
from llmguard.wrapper import call_llm
from llmguard.exceptions import BudgetExceededException, DailyBudgetExceededException
import llmguard.config as config
import uvicorn
import logging

# Increase limits to infinity for the test so we don't get blocked
config.MAX_BURN_RATE_PER_MIN = 1e9
config.DEFAULT_DAILY_BUDGET = 1e9

app = FastAPI()

# Disable logging to avoid overhead during the stress test
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("uvicorn.error").setLevel(logging.ERROR)

@app.get("/baseline")
def baseline():
    return {"status": "ok"}

@app.get("/wrapped")
def wrapped():
    try:
        messages = [{"role": "user", "content": "hello"}]
        # using mock-instant avoids external network latency
        resp = call_llm(user_id="test_user", model="mock-instant", messages=messages)
        return {"status": "ok", "mock_tokens": resp.output_tokens}
    except (BudgetExceededException, DailyBudgetExceededException) as e:
        raise HTTPException(status_code=429, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
