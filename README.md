# 🛡️ LLM-Cost-Guard

> Cost-control middleware for LLM APIs that prevents runaway API spend using real-time burn rate monitoring and kill-switch enforcement.

LLM APIs can cause uncontrolled cost spikes in production. LLM-Cost-Guard is a scalable, cloud-native enterprise gateway that monitors spend in real time, enforces budgets, and blocks runaway requests before tokens are consumed — across OpenAI, Anthropic, and Groq through a single unified interface.

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
- **Authentication** — Secure JWT and API Key endpoints to authenticate users
- **Idempotency** — Prevents double-charging during network blips with Redis-backed idempotency keys
- **Observability** — Built-in Prometheus `/metrics` and Structured JSON Logging
- **Async Processing** — RabbitMQ + Celery for offloading database writes
- **Production Storage** — PostgreSQL backed via async SQLAlchemy

---

## 📊 Performance & Scale

- **High-Throughput Concurrency:** Load tested across 7,100+ concurrent requests with a 0.00% failure rate. Maintained a highly responsive p95 latency of 110ms by offloading database I/O to background workers.
- **Background Worker Queues:** Implemented asynchronous Celery workers (backed by RabbitMQ) to decouple database writes from the main API thread.
- **Enterprise Database:** Configured PostgreSQL with async SQLAlchemy and connection pooling for scalable, high-throughput operations.
- **Sub-Millisecond Caching & Idempotency:** Leverages Redis to cache idempotent requests, adding only ~0.63ms of latency overhead while strictly preventing double charges during network retries.
- **Automated CI/CD:** Deployed a **GitHub Actions pipeline** for automated linting, test execution, and continuous integration.
- **Resilient Fallback Routing:** Achieved **100% uptime** simulation by designing a deterministic fallback chain across 3 separate AI providers, combined with exponential backoff for API errors.
---
### 🎯 Load Testing Results (Locust)
Benchmarked via Locust simulating continuous concurrent traffic:

| Metric | Result |
|---|---|
| Total Requests | 7,129 |
| Failure Rate | 0.00% |
| Median Latency (p50) | 100 ms |
| Tail Latency (p95) | 110 ms |
| Idempotency Overhead | ~0.63 ms |
<img width="1600" height="610" alt="image" src="https://github.com/user-attachments/assets/071ed876-0800-4f01-8c98-8fde5dfac309" />

---
## 🏗️ Architecture

Every `call_llm()` request flows through a strict pipeline before any LLM provider is touched:

<img width="1440" height="1228" alt="image" src="https://github.com/user-attachments/assets/24bc9212-ec67-4f66-8797-5ae8fcf47440" />


**Key Design Decisions:**
- **Pre-Call Killswitch:** Budget checks run *before* the API call, ensuring zero tokens are spent on denied requests.
- **Asynchronous Storage & Events:** API calls dispatch Celery tasks to write usage logs to PostgreSQL, preserving the event loop's responsiveness.
- **Deterministic Routing:** Provides guaranteed fallback chains: `gpt-4o → claude-sonnet → gpt-4o-mini → claude-haiku → llama3`.
- **Offline Cost Calculation:** All cost metrics are evaluated deterministically offline, eliminating latency from external pricing APIs.

---

## ⚙️ Setup

```bash
git clone https://github.com/VanshikaLud04/llm-cost-guard
cd llm-cost-guard
cp .env.example .env            # add your API keys
```

### Environment Variables

```env
OPENAI_API_KEY=sk-your-openai-key
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key
GROQ_API_KEY=gsk_your-groq-key
JWT_SECRET=super-secret-key-change-me
SLACK_WEBHOOK_URL=               # optional, for alerts
```

---

## 🚀 Running

The recommended way to run the full enterprise stack is using Docker Compose:

```bash
# Run with Docker and Redis, PostgreSQL, RabbitMQ, and Celery (Production-ready)
docker-compose up --build
# → Open http://127.0.0.1:8000/docs for Swagger UI
# → Open http://127.0.0.1:8000/metrics for Prometheus Metrics
```

---

## 📁 Project Structure

```
llmguard/
├── llmguard/
│   ├── storage/
│   │   ├── __init__.py       # Backend switcher 
│   │   ├── base.py           # Abstract storage interface
│   │   ├── postgres.py       # Async SQLAlchemy implementation
│   │   └── redis.py          # Redis caching implementation
│   ├── __init__.py
│   ├── alerts.py             # Slack webhook notifications
│   ├── auth.py               # JWT and API Key handling
│   ├── burn.py               # Cost velocity ($/min) calculation
│   ├── celery_app.py         # Celery broker configuration
│   ├── config.py             # System constants & per-user budgets
│   ├── cost.py               # Deterministic token cost calculator
│   ├── exceptions.py         # Custom exception hierarchy
│   ├── killswitch.py         # Budget enforcement logic
│   ├── logging_config.py     # Structured JSON Logging
│   ├── models.py             # SQLAlchemy schemas
│   ├── pricing.py            # Provider map, pricing table & fallback chain
│   ├── providers.py          # OpenAI / Anthropic / Groq SDK routers
│   ├── tasks.py              # Celery background tasks
│   └── wrapper.py            # Core middleware (limits, retries, fallbacks)
├── .github/workflows         # GitHub Actions CI/CD pipelines
├── .env                      # Your keys (git-ignored)
├── demo.py                   # Live multi-provider demo
├── main.py                   # FastAPI app with metrics and idempotency
├── requirements.txt
├── stress_test.py            # Concurrent load test (20 users)
└── test_cost.py              # Unit tests
```

---

## 🔌 API Endpoints

### `POST /chat`
Send a message through LLM Cost Guard middleware.

**Headers:**
```
Authorization: Bearer <JWT_TOKEN>
# OR
X-API-KEY: <YOUR_API_KEY>

Idempotency-Key: <UNIQUE_UUID> # Optional, prevents double charge on retry
```

**Body:**
```json
{
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

### `GET /stats`
Get real-time cost and usage stats for the authenticated user.

Response:
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
{ "status": "ok", "providers": ["openai", "anthropic", "groq"], "db": "postgres" }
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

---

## ⚙️ Request Lifecycle (Critical Path)

Every call to `call_llm()` runs through this pipeline **before** hitting any LLM:

1. Fetch recent usage from PostgreSQL (via Async SQLAlchemy)
2. Calculate burn rate (true $/min over last 60s)
3. If burn rate > `MAX_BURN_RATE_PER_MIN` → raise `BudgetExceededException` + Slack alert
4. Check total spend today vs per-user daily limit
5. If over daily limit → raise `DailyBudgetExceededException` + Slack alert
6. Only if both checks pass → route call to provider (with exponential backoff)
7. Dispatch background Celery task to record usage asynchronously

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
| Async PostgreSQL | Handles high-throughput database reads efficiently via connection pooling |
| Celery Background Queue | Offloads latency-heavy writes, preventing API blocking |
| Mock provider | Anyone can demo the killswitch without spending money |

---

## 🗺️ Roadmap

- [x] Redis storage backend for distributed deployments
- [x] Background worker queue for high-scale logging
- [x] Containerized multi-service deployment
- [ ] Per-model budget caps (not just per-user)
- [ ] Streaming response support

---

## 🛠️ Built With

- [FastAPI](https://fastapi.tiangolo.com/) — REST API framework
- [PostgreSQL](https://www.postgresql.org/) & [SQLAlchemy](https://www.sqlalchemy.org/) — Relational data & ORM
- [RabbitMQ](https://www.rabbitmq.org/) & [Celery](https://docs.celeryq.dev/) — Message Broker & Task Queue
- [Redis](https://redis.io/) — Key-Value Store (Caching & Idempotency)
- [Prometheus](https://prometheus.io/) — Metrics & Observability
- Docker & Docker Compose — Containerization
- GitHub Actions — CI/CD pipeline
- Python 3.11

---

## 👩‍💻 Author

**Vanshika Ludhani**  
Built as a production-style backend project demonstrating real-world LLM cost management patterns.
