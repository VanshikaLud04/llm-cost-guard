import asyncio
from llmguard.storage.postgres import init_db
from llmguard.models import Organization, User, ApiKey, Policy
from llmguard.storage.postgres import async_session
import time

async def setup():
    # Create tables
    await init_db()
    
    # Insert a test user and org
    async with async_session() as session:
        org = Organization(id="org_default", name="Default Organization", plan_tier="pro")
        user = User(id="test_user", org_id="org_default", role="admin", email="test@example.com")
        api_key = ApiKey(id="key_1", user_id="test_user", key_hash="test_api_key_123") # In prod, this should be bcrypt hashed
        policy = Policy(id="pol_1", org_id="org_default", allowed_models=["gpt-4o", "gpt-4o-mini", "claude-3-5-sonnet-20240620"], token_limits={"minute": 100000, "hour": 500000, "day": 2000000})

        session.add(org)
        session.add(user)
        session.add(api_key)
        session.add(policy)
        try:
            await session.commit()
            print("Test user, organization, api key, and policy created successfully.")
        except Exception as e:
            print(f"Data might already exist or error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(setup())
