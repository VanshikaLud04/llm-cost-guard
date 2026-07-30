import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # LLM Settings
    MAX_BURN_RATE_PER_MIN: float = float(os.getenv("MAX_BURN_RATE_PER_MIN", 0.01))
    BURN_RATE_WINDOW_SECONDS: int = int(os.getenv("BURN_RATE_WINDOW_SECONDS", 60))
    DEFAULT_DAILY_BUDGET: float = float(os.getenv("DEFAULT_DAILY_BUDGET", 0.05))
    USER_BUDGETS: dict[str, float] = {"user_123": 0.05, "user_456": 0.10, "user_admin": 1.00}
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", 3))
    
    # System Settings
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/llmguard")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    JWT_SECRET: str = os.getenv("JWT_SECRET", "super-secret-key-change-me")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    
    # Provider Keys
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

settings = Settings()