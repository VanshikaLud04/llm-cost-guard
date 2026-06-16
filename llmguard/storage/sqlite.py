import time, sqlite3
import threading
from .base import BaseStorage

class SQLiteStorage(BaseStorage):
    def __init__(self, db_path: str = "llmguard.db"):
        self.db_path = db_path
        self._local = threading.local()
        # Initialize schema once
        with sqlite3.connect(db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("""CREATE TABLE IF NOT EXISTS usage (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, model TEXT, input_tokens INTEGER, output_tokens INTEGER, cost REAL, timestamp REAL)""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_user_ts ON usage (user_id, timestamp)")

    @property
    def conn(self):
        if not hasattr(self._local, "conn"):
            self._local.conn = sqlite3.connect(self.db_path)
            self._local.conn.execute("PRAGMA journal_mode=WAL;")
        return self._local.conn

    def save(self, record: dict):
        self.conn.execute("INSERT INTO usage (user_id, model, input_tokens, output_tokens, cost, timestamp) VALUES (?, ?, ?, ?, ?, ?)", 
                          (record["user_id"], record["model"], record["input_tokens"], record["output_tokens"], record["cost"], record["timestamp"]))
        self.conn.commit()

    def get_recent(self, user_id: str, window_seconds: int = 60):
        return self.conn.execute("SELECT cost, timestamp FROM usage WHERE user_id=? AND timestamp>=?", (user_id, time.time() - window_seconds)).fetchall()

    def get_total_today(self, user_id: str):
        return self.conn.execute("SELECT SUM(cost) FROM usage WHERE user_id=? AND timestamp>=?", (user_id, time.time() - 86400)).fetchone()[0] or 0.0

    def get_history(self, user_id: str, limit: int = 100):
        return self.conn.execute("SELECT user_id, model, input_tokens, output_tokens, cost, timestamp FROM usage WHERE user_id=? ORDER BY timestamp DESC LIMIT ?", (user_id, limit)).fetchall()