-- key_registry: 密钥存储
CREATE TABLE IF NOT EXISTS key_registry (
    service TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    key_type TEXT NOT NULL,
    registered_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- call_log: 操作审计
CREATE TABLE IF NOT EXISTS call_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL DEFAULT (datetime('now')),
    action TEXT NOT NULL,
    service TEXT,
    detail TEXT
);
