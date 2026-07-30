"""
Locust load testing file for LLM Cost Guard.

Two scenarios are tested:
1. ChatWithoutIdempotency — raw throughput, no Redis check
2. ChatWithIdempotency    — Redis idempotency overhead measurement

Run with:
    locust -f locustfile.py --host http://localhost:8001 --headless -u 50 -r 10 --run-time 60s

Or open the Locust Web UI:
    locust -f locustfile.py --host http://localhost:8001
    # → Navigate to http://localhost:8089
"""

from locust import HttpUser, task, between, events
import uuid
import time
import statistics

# Track raw Redis overhead samples
_without_idemp_latencies = []
_with_idemp_latencies = []

class ChatWithoutIdempotency(HttpUser):
    """Scenario 1: Raw /chat throughput — NO idempotency key."""
    wait_time = between(0.01, 0.05)
    weight = 1

    @task
    def post_chat(self):
        t0 = time.perf_counter()
        with self.client.post(
            "/chat",
            json={"message": "What is 2+2?", "model": "mock"},
            headers={"X-API-KEY": "test_api_key_123"},
            name="/chat (no-idempotency)",
            catch_response=True
        ) as resp:
            latency_ms = (time.perf_counter() - t0) * 1000
            if resp.status_code == 200:
                _without_idemp_latencies.append(latency_ms)
                resp.success()
            else:
                resp.failure(f"Got {resp.status_code}: {resp.text}")


class ChatWithIdempotency(HttpUser):
    """Scenario 2: /chat with unique Idempotency-Key — measures Redis overhead."""
    wait_time = between(0.01, 0.05)
    weight = 1

    @task
    def post_chat_with_idempotency(self):
        idempotency_key = str(uuid.uuid4())  # Always unique → always a miss (measures write overhead)
        t0 = time.perf_counter()
        with self.client.post(
            "/chat",
            json={"message": "Tell me a joke.", "model": "mock"},
            headers={
                "X-API-KEY": "test_api_key_123",
                "Idempotency-Key": idempotency_key,
            },
            name="/chat (with-idempotency)",
            catch_response=True
        ) as resp:
            latency_ms = (time.perf_counter() - t0) * 1000
            if resp.status_code == 200:
                _with_idemp_latencies.append(latency_ms)
                resp.success()
            else:
                resp.failure(f"Got {resp.status_code}: {resp.text}")


@events.quitting.add_listener
def on_quit(environment, **kwargs):
    """Print the latency overhead report when Locust exits."""
    print("\n" + "="*60)
    print("📊 LOAD TEST RESULTS SUMMARY")
    print("="*60)

    if _without_idemp_latencies and _with_idemp_latencies:
        avg_no_idemp = statistics.mean(_without_idemp_latencies)
        avg_with_idemp = statistics.mean(_with_idemp_latencies)
        p99_no_idemp = statistics.quantiles(_without_idemp_latencies, n=100)[98]
        p99_with_idemp = statistics.quantiles(_with_idemp_latencies, n=100)[98]
        overhead = avg_with_idemp - avg_no_idemp

        print(f"\n🔵 Without Idempotency Check:")
        print(f"   Avg Latency : {avg_no_idemp:.2f} ms")
        print(f"   P99 Latency : {p99_no_idemp:.2f} ms")
        print(f"   Samples     : {len(_without_idemp_latencies)}")

        print(f"\n🟣 With Redis Idempotency Check (unique key, cache miss):")
        print(f"   Avg Latency : {avg_with_idemp:.2f} ms")
        print(f"   P99 Latency : {p99_with_idemp:.2f} ms")
        print(f"   Samples     : {len(_with_idemp_latencies)}")

        print(f"\n⚡ Redis Idempotency Overhead (cache miss):")
        print(f"   Added ~{overhead:.2f} ms of latency per request")
    else:
        print("Not enough data collected for comparison.")
    print("="*60)
