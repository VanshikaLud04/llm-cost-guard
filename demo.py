import time
from dotenv import load_dotenv
load_dotenv()
from llmguard.wrapper import call_llm, call_llm_with_fallback
from llmguard.exceptions import BudgetExceededException, DailyBudgetExceededException

MSG = [{"role": "user", "content": "What is 2+2? One sentence only."}]

def section(title: str):
    print(f"\n{'─'*55}\n  {title}\n{'─'*55}")

def demo_mock():
    section("Demo 0: Mock Provider (no API key needed)")
    for i in range(3):
        resp = call_llm("user_demo", "mock-instant", MSG)
        print(f"  Call {i+1}: ✅ {resp.content}")
        print(f"  📊 Tokens: {resp.input_tokens} in / {resp.output_tokens} out")

def demo_openai():
    section("Demo 1: OpenAI (gpt-4o-mini)")
    resp = call_llm("user_123", "gpt-4o-mini", MSG)
    print(f"  ✅ Response : {resp.content}\n  📊 Tokens  : {resp.input_tokens} in / {resp.output_tokens} out")


def demo_anthropic():
    section("Demo 2: Anthropic Claude (claude-haiku-4-5)")
    try:
        resp = call_llm("user_123", "claude-haiku-4-5", MSG)
        print(f"  ✅ Response : {resp.content}")
    except Exception as e:
        print(f"  ⚠️ Anthropic call failed: {type(e).__name__}: {e}")
        import traceback; traceback.print_exc()

def demo_groq():
    section("Demo 3: Groq (llama-3.1-8b-instant)")
    try:
        resp = call_llm("user_123", "llama-3.1-8b-instant", MSG)
        print(f"  ✅ Response : {resp.content}\n  📊 Tokens  : {resp.input_tokens} in / {resp.output_tokens} out")
    except Exception as e:
        print(f"  ⚠️ Groq call failed: {e}")

def demo_killswitch():
    section("Demo 4: Killswitch — rapid-fire calls")
    for i in range(15):
        try:
            resp = call_llm("user_123", "gpt-4o-mini", MSG)
            print(f"  Call {i+1:02d}: ✅  {resp.content.strip()[:40]}")
        except (BudgetExceededException, DailyBudgetExceededException) as e:
            print(f"  Call {i+1:02d}: 🛑 BLOCKED — {e}")
            break

def demo_fallback():
    section("Demo 5: Cross-provider fallback chain")
    print("  Trying gpt-4o first → degrades across providers if over budget")
    try:
        resp = call_llm_with_fallback("user_456", MSG, preferred_model="gpt-4o")
        print(f"  ✅ Served by : {resp.model}\n  ✅ Response  : {resp.content}")
    except Exception as e:
        print(f"  All models exhausted: {e}")

def inspect_db():
    section("Demo 6: DB — last 10 calls")
    import sqlite3
    conn = sqlite3.connect("llmguard.db")
    rows = conn.execute("SELECT user_id, model, input_tokens, output_tokens, cost FROM usage ORDER BY timestamp DESC LIMIT 10").fetchall()
    if not rows: print("  (no records yet)")
    for r in rows: print(f"  user={r[0]:<10} model={r[1]:<25} tokens={r[2]}+{r[3]}  cost=${r[4]:.8f}")

if __name__ == "__main__":
    demo_mock()
    demo_openai()
    demo_anthropic()
    demo_groq()
    demo_killswitch()
    demo_fallback()
    inspect_db()
    print()