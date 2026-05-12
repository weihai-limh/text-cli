import sqlite3
import os
import logging

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "textcli.db"))

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS call_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT UNIQUE NOT NULL,
    directive TEXT NOT NULL,
    domain TEXT,
    action TEXT,
    backend_url TEXT,
    service_token_prefix TEXT,
    access_token_prefix TEXT,
    status_code INTEGER,
    response_time_ms INTEGER,
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS daily_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    domain TEXT,
    action TEXT,
    call_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    avg_response_ms INTEGER DEFAULT 0,
    UNIQUE(date, domain, action)
);

CREATE TABLE IF NOT EXISTS access_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_hash TEXT UNIQUE NOT NULL,
    token_prefix TEXT NOT NULL,
    client_name TEXT,
    quota INTEGER DEFAULT -1,
    used_count INTEGER DEFAULT 0,
    max_requests_per_minute INTEGER DEFAULT 60,
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_call_logs_created_at ON call_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_call_logs_domain_action ON call_logs(domain, action);
CREATE INDEX IF NOT EXISTS idx_daily_stats_date ON daily_stats(date);
"""


def get_db() -> sqlite3.Connection:
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        logger.info("Database initialized at %s", DB_PATH)
    finally:
        conn.close()


def query_db(sql: str, params: tuple = ()) -> list[dict]:
    conn = get_db()
    try:
        cursor = conn.execute(sql, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def execute_db(sql: str, params: tuple = ()) -> int:
    conn = get_db()
    try:
        cursor = conn.execute(sql, params)
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def execute_db_returning(sql: str, params: tuple = ()) -> int | None:
    conn = get_db()
    try:
        cursor = conn.execute(sql, params)
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()
