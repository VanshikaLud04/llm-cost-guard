import sqlite3
from llmguard.storage.sqlite import SQLiteStorage

if __name__ == "__main__":
    print("🛠️  Initializing LLM Cost Guard database...")
    SQLiteStorage()  # just triggers table creation
    print("✅ Database ready (llmguard.db)")