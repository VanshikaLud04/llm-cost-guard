# 🛡️ LLM-Cost-Guard

> Cost-control middleware for LLM APIs that prevents runaway API spend using real-time burn rate monitoring and kill-switch enforcement.

LLM APIs can cause uncontrolled cost spikes in production. LLM-Cost-Guard is a middleware layer that monitors spend in real time, enforces budgets, and blocks runaway requests before tokens are consumed — across OpenAI, Anthropic, and Groq through a single unified interface.

> Designed to simulate production constraints like cost ceilings, failure handling, and provider fallback under load.

Unlike traditional rate limiting, LLM cost control must account for token-based pricing and dynamic output sizes — making pre-call enforcement critical.

---

## 🔥 Features

- **Multi-provider** — OpenAI, Anthropic Claude, Groq — one unified interface
- **Token tracking** — every call logged with model, tokens, cost, and timestamp
- **Burn rate monitor** — sliding-window cost velocity (true $/min calculation)
- **Killswitch** — blocks requests *before* they're made if limits are exceeded
- **Daily budgets** — per-user 24-hour spending caps
- **Cross-provider fallback** — `gpt-4o` → `claude-sonnet-4-5` → `gpt-4o-mini` → `claude-haiku-4-5` → `llama3`
- **REST API** — FastAPI with `/chat`, `/stats`, and `/health` endpoints
- **Slack alerts** — webhook notifications when killswitch or daily budget triggers
- **Stress tested** — concurrent load testing with `stress_test.py`
- **Pluggable storage** — SQLite active, Redis-ready interface for production scale


## 🏗️ Architecture

Every `call_llm()` request flows through a strict pipeline before any LLM provider is touched:

<img width="1440" height="1228" alt="image" src="https://github.com/user-attachments/assets/24bc9212-ec67-4f66-8797-5ae8fcf47440" />


**Key design decisions:**
- Killswitch runs *before* the API call — no tokens are spent on denied requests
- Storage is abstracted behind `base.py` — swap SQLite for Redis with zero middleware changes
- Fallback chain is deterministic: `gpt-4o → claude-sonnet → gpt-4o-mini → claude-haiku → llama3`
- All cost calculations are deterministic and offline — no external pricing API calls

---
## 📸 Screenshots

### ✅ Unit Tests Passing
<img width="1096" height="146" alt="image" src="https://github.com/user-attachments/assets/34280dff-d7ea-4403-bde2-a749652ff734" />


### ✅ Groq Live Response
<img width="1370" height="232" alt="image" src="https://github.com/user-attachments/assets/a4cd863a-0870-4b03-8903-36a24b05402e" />


### ✅ FastAPI Swagger UI
<img width="1265" height="579" alt="image" src="https://github.com/user-attachments/assets/31319f08-833e-4f7a-8cdd-fc5f7c27f55f" />

---

## ⚙️ Setup

```bash
git clone https://github.com/VanshikaLud04/llm-cost-guard
cd llm-cost-guard
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # add your API keys
```

### Environment Variables

```env
OPENAI_API_KEY=sk-your-openai-key
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key
GROQ_API_KEY=gsk_your-groq-key
SLACK_WEBHOOK_URL=               # optional, for alerts
```

---

## 🚀 Running

```bash
# Initialize DB and verify setup
python setup.py

# Run unit tests
python test_cost.py

# Run multi-provider demo
python demo.py

# Start API server
uvicorn main:app --reload
# → Open http://127.0.0.1:8000/docs for Swagger UI

# Stress test with mock provider (no API keys needed)
python stress_test.py
```

---

## 📁 Project Structure

```
llmguard/
├── llmguard/
│   ├── storage/
│   │   ├── __init__.py       # Backend switcher (SQLite ↔ Redis)
│   │   ├── base.py           # Abstract storage interface
│   │   ├── sqlite.py         # Active implementation
│   │   └── redis.py          # Roadmap — for distributed deployments
│   ├── __init__.py
│   ├── alerts.py             # Slack webhook notifications
│   ├── burn.py               # Cost velocity ($/min) calculation
│   ├── config.py             # System constants & per-user budgets
│   ├── cost.py               # Deterministic token cost calculator
│   ├── exceptions.py         # Custom exception hierarchy
│   ├── killswitch.py         # Budget enforcement logic
│   ├── pricing.py            # Provider map, pricing table & fallback chain
│   ├── providers.py          # OpenAI / Anthropic / Groq SDK routers
│   └── wrapper.py            # Core middleware (limits, retries, fallbacks)
├── .env                      # Your keys (git-ignored)
├── .env.example              # Safe template to commit
├── demo.py                   # Live multi-provider demo
├── main.py                   # FastAPI app
├── requirements.txt
├── setup.py                  # DB initializer
├── stress_test.py            # Concurrent load test (20 users)
└── test_cost.py              # Unit tests
```

---

## 🔌 API Endpoints

### `POST /chat`
Send a message through LLMGuard middleware.

```json
{
  "user_id": "user_123",
  "message": "What is 2+2?",
  "model": "gpt-4o-mini",
  "use_fallback": false
}
```

Response:
```json
{
  "user_id": "user_123",
  "model_used": "gpt-4o-mini",
  "response": "2 + 2 equals 4."
}
```

### `GET /stats/{user_id}`
Get real-time cost and usage stats for a user.

```json
{
  "user_id": "user_123",
  "requests_last_hour": 5,
  "cost_last_hour": 0.00045,
  "avg_cost_per_request": 0.00009,
  "total_cost_today": 0.00045,
  "burn_rate_per_min": 0.000075
}
```

### `GET /health`
```json
{ "status": "ok" }
```

---

## ⚡ Why This Matters

Traditional rate limiting reacts **after** usage has already occurred. LLM-Cost-Guard enforces limits **before** any tokens are spent:

- Most systems detect overspending after the API call returns
- LLM-Cost-Guard checks burn rate and budgets **before** routing to any provider
- If limits are exceeded, the request is blocked and zero tokens are consumed
- This prevents cost leaks instead of just reacting to them

---

## 💥 Example Scenario

> A user sends 30 requests in 1 minute.
>
> → Burn rate spikes above `MAX_BURN_RATE_PER_MIN`  
> → LLM-Cost-Guard detects abnormal cost velocity  
> → Killswitch triggers **before** the next request is made  
> → Slack alert fires  
> → No additional tokens are spent  

Run `python stress_test.py` to see this happen live with the mock provider — no API keys needed.

---

## ⚙️ Request Lifecycle (Critical Path)

Every call to `call_llm()` runs through this pipeline **before** hitting any LLM:

1. Fetch recent usage from SQLite for the user
2. Calculate burn rate (true $/min over last 60s)
3. If burn rate > `MAX_BURN_RATE_PER_MIN` → raise `BudgetExceededException` + Slack alert
4. Check total spend today vs per-user daily limit
5. If over daily limit → raise `DailyBudgetExceededException` + Slack alert
6. Only if both checks pass → route call to provider

---

## 💰 Supported Models & Pricing

| Model | Provider | Input ($/token) | Output ($/token) |
|---|---|---|---|
| gpt-4o | OpenAI | $0.000005 | $0.000015 |
| gpt-4o-mini | OpenAI | $0.00000015 | $0.00000060 |
| claude-sonnet-4-5 | Anthropic | $0.000003 | $0.000015 |
| claude-haiku-4-5 | Anthropic | $0.00000025 | $0.00000125 |
| llama-3.1-8b-instant | Groq | $0.00000005 | $0.00000008 |

---

## 🧪 Design Decisions

| Decision | Why |
|---|---|
| Sliding window burn rate | Detects cost spikes early, not just total spend |
| Pre-call enforcement | Prevents cost instead of reacting to it |
| Storage abstraction | Swap SQLite → Redis with zero middleware changes |
| Deterministic cost calculation | No external pricing API — works fully offline |
| Mock provider | Anyone can demo the killswitch without spending money |

---

## 🗺️ Roadmap

- [ ] Redis storage backend for distributed deployments
- [ ] Per-model budget caps (not just per-user)
- [ ] Streaming response support

---

## 🛠️ Built With

- [FastAPI](https://fastapi.tiangolo.com/) — REST API framework
- [OpenAI Python SDK](https://github.com/openai/openai-python)
- [Anthropic Python SDK](https://github.com/anthropic/anthropic-sdk-python)
- [Groq Python SDK](https://github.com/groq/groq-python)
- SQLite — lightweight persistent storage
- Python 3.13

---

## 👩‍💻 Author

**Vanshika Ludhani**  
Built as a production-style backend project demonstrating real-world LLM cost management patterns.
