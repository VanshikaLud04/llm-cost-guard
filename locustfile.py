from locust import HttpUser, task, between, events
import uuid

class LLMUser(HttpUser):
    wait_time = between(0.1, 0.5)
    
    @task(1)
    def chat_no_idempotency(self):
        self.client.post(
            "/chat_no_idempotency",
            json={"message": "hello"},
            headers={"X-API-KEY": "test_api_key_123"},
            name="ChatWithoutIdempotency"
        )

    @task(1)
    def chat_with_idempotency(self):
        self.client.post(
            "/chat_with_idempotency",
            json={
                "message": "hello", 
                "idempotency_key": str(uuid.uuid4())
            },
            headers={"X-API-KEY": "test_api_key_123"},
            name="ChatWithIdempotency"
        )

@events.quitting.add_listener
def _(environment, **kw):
    if environment.stats.total.num_requests == 0:
        return
        
    no_idem_stats = environment.stats.get("ChatWithoutIdempotency", "POST")
    with_idem_stats = environment.stats.get("ChatWithIdempotency", "POST")
    
    no_idem_avg = no_idem_stats.avg_response_time
    with_idem_avg = with_idem_stats.avg_response_time
    
    if no_idem_avg > 0 and with_idem_avg > 0:
        overhead = with_idem_avg - no_idem_avg
        print("\n" + "="*50)
        print("🎯 IDEMPOTENCY OVERHEAD RESULTS")
        print("="*50)
        print(f"🔵 Without Idempotency: avg {no_idem_avg:.2f}ms")
        print(f"🟣 With Idempotency:    avg {with_idem_avg:.2f}ms")
        print(f"⚡ Redis overhead:      ~{overhead:.2f}ms per request")
        print("="*50 + "\n")
