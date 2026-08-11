-- key_registry: 密钥存储
CREATE TABLE IF NOT EXISTS key_registry (
    service TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    value2 TEXT,
    cred_count INTEGER DEFAULT 1,
    key_type TEXT NOT NULL,
    quota_track TEXT,
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

-- token_registry: Service Token 准入控制
CREATE TABLE IF NOT EXISTS token_registry (
    token TEXT PRIMARY KEY,
    enabled INTEGER DEFAULT 1,
    quota_limit INTEGER,
    used_count INTEGER DEFAULT 0,
    expires_at TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- token_call_logs: Token 调用审计
CREATE TABLE IF NOT EXISTS token_call_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token TEXT,
    domain TEXT,
    action TEXT,
    status TEXT,
    error_msg TEXT,
    duration_ms INTEGER,
    created_at TEXT DEFAULT (datetime('now'))
);

-- peer_credentials: 联邦 Mesh 对等节点凭证
CREATE TABLE IF NOT EXISTS peer_credentials (
    peer TEXT PRIMARY KEY,
    service_token TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
