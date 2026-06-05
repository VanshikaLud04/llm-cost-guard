import asyncio
import aiohttp
import time
from collections import Counter
import json
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

API_URL = "http://127.0.0.1:8000/chat"

PAYLOAD = {
    "user_id": "load_test_user",         
    "message": "Say exactly 'test'",
    "model": "gpt-4o-mini",
    "use_fallback": False,
    "temperature": 0.7,
    "max_tokens": 1024
}

NUM_REQUESTS = 500
CONCURRENCY = 100

async def fetch(session, request_id):
    start = time.time()
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with session.post(API_URL, json=PAYLOAD, timeout=timeout) as response:
            status = response.status
            if status == 200:
                data = await response.json()
                actual_response = data.get("response", "").strip()
                success = actual_response.lower() == "test"
                duration = time.time() - start
                return {
                    "id": request_id,
                    "status": status,
                    "duration": duration,
                    "success": success
                }
            else:
                error_text = await response.text()
                duration = time.time() - start
                return {
                    "id": request_id,
                    "status": status,
                    "duration": duration,
                    "success": False,
                    "error": error_text[:100]
                }
    except Exception as e:
        return {
            "id": request_id,
            "status": "ERROR",
            "duration": time.time() - start,
            "success": False,
            "error": str(e)
        }

async def bound_fetch(sem, session, request_id):
    async with sem:
        return await fetch(session, request_id)

async def main():
    print(f"🚀 Starting load test: {NUM_REQUESTS} requests with concurrency {CONCURRENCY}...")
    start_time = time.time()
    
    sem = asyncio.Semaphore(CONCURRENCY)
    connector = aiohttp.TCPConnector(limit=CONCURRENCY)
    
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [bound_fetch(sem, session, i) for i in range(NUM_REQUESTS)]
        results = await asyncio.gather(*tasks)
        
    total_time = time.time() - start_time
    
    successes = sum(1 for r in results if r["success"])
    status_counts = Counter(str(r["status"]) for r in results)
    avg_duration = sum(r["duration"] for r in results) / len(results)
    rps = NUM_REQUESTS / total_time
    
    print(f"\n✅ Finished in {total_time:.2f} seconds\n")
    print(f"Requests per second (RPS): {rps:.2f}")
    print(f"Success rate             : {successes}/{NUM_REQUESTS} ({successes/NUM_REQUESTS*100:.1f}%)")
    print(f"Average latency          : {avg_duration:.3f}s")
    print(f"Status codes             : {dict(status_counts)}")
    
    failures = [r for r in results if not r["success"]]
    if failures:
        print("\nSample failures:")
        for r in failures[:5]:
            print(f"  ❌ Request {r['id']:03d} (Status {r['status']}) → {r.get('error', 'Unknown')}")

if __name__ == "__main__":
    asyncio.run(main())
