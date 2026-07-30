# 🛡️ LLM-Cost-Guard: Enterprise AI Gateway

> Transformed a single-purpose LLM cost middleware into a production-oriented AI Gateway by introducing multi-tenant policy enforcement, provider abstraction, intelligent routing, reserve-and-reconcile token budgeting, semantic caching, circuit breaking, streaming observability, and enterprise-grade telemetry. The architecture emphasizes vendor independence, fault tolerance, extensibility, and low-latency request processing while maintaining compatibility with existing workloads.

## 🏗️ System Architecture

### System Context Diagram

```mermaid
graph TD
    Client[Client Applications] --> Gateway[LLM-Cost-Guard Gateway]
    
    subgraph Gateway Core
    Gateway
    end
    
    Gateway <--> Redis[(Redis: Cache, Ratelimit, Circuit Breaker)]
    Gateway <--> Postgres[(PostgreSQL: Policies, Usage, Auth)]
    
    Gateway --> Worker[Celery Async Workers]
    Worker --> Postgres
    
    Gateway --> OpenAI[OpenAI API]
    Gateway --> Anthropic[Anthropic API]
    Gateway --> Groq[Groq API]
```

### High-Level Component Diagram

```mermaid
flowchart LR
    Request --> Auth[Authentication & Multi-Tenancy]
    Auth --> Policy[Policy Engine]
    Policy --> Limiter[Reserve & Reconcile Rate Limiter]
    Limiter --> Cache[Semantic Cache]
    Cache --> Router[Intelligent Router]
    Router --> Provider[LLMProvider Abstraction]
    Provider --> Response
```

## 🔥 Core Engineering Achievements

### 1. Multi-Tenant Authorization & Policy Engine
Implemented strict multi-tenancy separating API keys, organizations, and hierarchical role-based policies. The gateway intelligently restricts token usage and model allowances per organization/role, ensuring organizational quotas are never breached.

### 2. Provider Abstraction & Dependency Injection
Refactored provider integrations behind a common `LLMProvider` interface, enabling vendor-independent routing, streaming, health checks, and future provider integrations without modifying gateway logic. Coupled with strict **Dependency Injection** (e.g. storage layers injected via FastAPI `Depends`), the architecture achieves true decoupling.

### 3. Reserve-and-Reconcile Token Limiting
Replaced naive sliding-window cost calculations with a highly resilient `TokenRateLimiter` utilizing a custom Redis Lua script.
Requests securely reserve their estimated maximum token capacity across multiple time boundaries (minute, hour, day). Upon completion, actual tokens consumed are efficiently reconciled to eliminate TOCTOU (Time-Of-Check, Time-Of-Use) race conditions.

### 4. Semantic Cache Architecture
Engineered a vector-search semantic cache that drastically reduces latency and LLM costs by returning highly similar previous responses.

```text
PGVector (Source of Truth)
↓
Redis (Fast, Hot Cache via RediSearch)
↓
Gateway
```
* **Redis** = Fast, hot vector cache for sub-millisecond similarity scoring.
* **PGVector** = Durable storage and async persistence for long-term historical context.

### 5. Intelligent Rule Router
Deprecated static fallback sequences in favor of a dynamic `RuleRouter` evaluating a strict pipeline of constraints before hitting any provider:

```text
Routing Decision
↓
Policy Restrictions
↓
Capability Filter
↓
Health Filter
↓
Cost Filter
↓
Latency Filter
↓
Selected Provider
```

### 6. Resilient Circuit Breaking
Engineered a Redis-backed Circuit Breaker protecting against catastrophic cascading failures when upstream providers experience significant downtime. Features include:
* Rolling failure windows
* Configurable failure thresholds
* Half-open probing
* Exponential cooldown

### 7. Non-Blocking Streaming & Observability
Introduced **non-blocking streaming telemetry** to ensure precise token accounting during Server-Sent Events (SSE) proxying, streaming without increasing user-visible latency.

The system features robust OpenTelemetry middleware capturing granular traces, including:
* Spans & Correlation IDs
* Request lifecycle tracking
* Provider vs. Cache timings
* Router decision logs

### 8. Configuration Layer
Implemented a typed, hierarchical configuration layer ensuring clear precedence and validation across the enterprise stack:

```text
GatewayConfig
↓
RedisConfig
↓
ProviderConfig
↓
RateLimitConfig
↓
TelemetryConfig
```

---

## ⚙️ Request Sequence

```mermaid
sequenceDiagram
    participant Client
    participant Auth
    participant Policy
    participant RateLimiter
    participant Cache
    participant Router
    participant Provider
    participant Worker
    
    Client->>Auth: POST /chat (API Key)
    Auth->>Policy: Validate Organization & Role
    Policy-->>Auth: Policy Allowed
    Auth->>RateLimiter: Reserve Estimated Tokens (Lua Script)
    RateLimiter-->>Auth: Reservation ID
    Auth->>Cache: Check Semantic Cache (KNN)
    alt Cache Hit
        Cache-->>Client: Cached Response
    else Cache Miss
        Auth->>Router: Execute Routing Pipeline
        Router->>Provider: Call Provider (Stream/Block)
        Provider-->>Auth: Generated Response
        Auth->>RateLimiter: Reconcile Actual Tokens
        Auth->>Cache: Async Set Cache
        Auth->>Worker: Dispatch Async Save Usage
        Auth-->>Client: Response
    end
```

## 🗄️ Database ER Diagram

```mermaid
erDiagram
    ORGANIZATION ||--o{ USER : contains
    ORGANIZATION ||--o{ POLICY : defines
    USER ||--o{ API_KEY : owns
    USER ||--o{ USAGE_RECORD : generates
    
    ORGANIZATION {
        string id PK
        string name
        string plan_tier
    }
    USER {
        string id PK
        string org_id FK
        string role
        string email
    }
    API_KEY {
        string id PK
        string user_id FK
        string key_hash
    }
    POLICY {
        string id PK
        string org_id FK
        string role
        jsonb token_limits
        string[] allowed_models
    }
    USAGE_RECORD {
        integer id PK
        string user_id FK
        string org_id FK
        float cost
        integer input_tokens
        integer output_tokens
    }
    CACHE_ENTRY {
        string id PK
        string org_id FK
        string prompt
        vector prompt_embedding
        string response
    }
```

## 🚀 Deployment & Resilience

To guarantee production-grade stability, deployment follows a strict pipeline:

```text
Architecture Complete
↓
Integration Tests
↓
Load Testing
↓
Chaos Tests
↓
Benchmark
↓
Docker Deployment
```

### Deployment Diagram

```mermaid
graph TD
    User((Users)) --> NGINX[NGINX Reverse Proxy]
    NGINX --> FastAPI1[FastAPI Node 1]
    NGINX --> FastAPI2[FastAPI Node 2]
    
    FastAPI1 <--> Redis[(Redis Cluster)]
    FastAPI2 <--> Redis
    
    FastAPI1 --> RMQ[RabbitMQ]
    FastAPI2 --> RMQ
    
    RMQ --> Celery[Celery Workers]
    
    FastAPI1 <--> Postgres[(PostgreSQL)]
    FastAPI2 <--> Postgres
    Celery --> Postgres
    
    FastAPI1 --> Prom[Prometheus]
    FastAPI2 --> Prom
    Prom --> Grafana[Grafana Dashboards]
```

---

## 📊 Performance & Scale

- **High-Throughput Concurrency:** Load tested across 7,100+ concurrent requests with a 0.00% failure rate. Maintained a highly responsive p95 latency of 110ms.
- **Sub-Millisecond Overhead:** Redis Semantic Cache and Lua-based Reserve-Reconcile adds negligible `<2ms` latency overhead per request.

### 🎯 Load Testing Results (Locust)
Benchmarked via Locust simulating continuous concurrent traffic:

| Metric | Result |
|---|---|
| Total Requests | 7,129 |
| Failure Rate | 0.00% |
| Median Latency (p50) | 100 ms |
| Tail Latency (p95) | 110 ms |

![alt text](image.png)

*(Historical architecture reference)*
<img width="1440" height="1228" alt="image" src="https://github.com/user-attachments/assets/24bc9212-ec67-4f66-8797-5ae8fcf47440" />

---

## 🧪 Testing Coverage
Robust testing has been expanded across the codebase focusing on areas where bugs usually hide:
* Circuit Breaker state transitions
* Redis Lua script atomic correctness
* Router selection determinism
* Cache threshold tuning
* Policy precedence resolution
* Streaming token accounting
* Concurrent token reservations

---

## ⚙️ Setup & Running

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
REDIS_URL=redis://localhost:6379/0
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/llmguard
```

### Running via Docker Compose

The recommended way to run the full enterprise stack:

```bash
docker-compose up --build
# → Open http://127.0.0.1:8000/docs for Swagger UI
# → Open http://127.0.0.1:8000/metrics for Prometheus Metrics
```
