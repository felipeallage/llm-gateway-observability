"""SQLite storage for logged LLM gateway calls."""
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path(__file__).parent / "data" / "calls.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    model TEXT NOT NULL,
    provider TEXT,
    endpoint TEXT NOT NULL,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    latency_ms REAL,
    cost_usd REAL,
    cost_status TEXT NOT NULL,  -- 'known' | 'unknown_price' | 'error'
    status TEXT NOT NULL,       -- 'ok' | 'error'
    error_message TEXT,
    run_tag TEXT
);
"""


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(SCHEMA)
    return conn


def log_call(
    model: str,
    provider: str | None,
    endpoint: str,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    total_tokens: int | None,
    latency_ms: float,
    cost_usd: float | None,
    cost_status: str,
    status: str,
    error_message: str | None = None,
    run_tag: str | None = None,
) -> None:
    conn = get_connection()
    with conn:
        conn.execute(
            """INSERT INTO calls
            (ts, model, provider, endpoint, prompt_tokens, completion_tokens,
             total_tokens, latency_ms, cost_usd, cost_status, status, error_message, run_tag)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                datetime.now(timezone.utc).isoformat(),
                model,
                provider,
                endpoint,
                prompt_tokens,
                completion_tokens,
                total_tokens,
                latency_ms,
                cost_usd,
                cost_status,
                status,
                error_message,
                run_tag,
            ),
        )
    conn.close()


def fetch_all() -> list[sqlite3.Row]:
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM calls ORDER BY ts DESC").fetchall()
    conn.close()
    return rows
