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

CREATE TABLE IF NOT EXISTS directives (
    id TEXT PRIMARY KEY,
    name TEXT,
    category TEXT,
    description TEXT,
    domain TEXT,
    action TEXT,
    backend_url TEXT,
    parameters_json TEXT,
    prompt_template TEXT,
    trigger_keywords_json TEXT,
    response_type TEXT,
    response_example_json TEXT,
    directive_key TEXT,
    enabled BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_call_logs_created_at ON call_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_call_logs_domain_action ON call_logs(domain, action);
CREATE INDEX IF NOT EXISTS idx_daily_stats_date ON daily_stats(date);
CREATE INDEX IF NOT EXISTS idx_directives_directive_key ON directives(directive_key);
CREATE INDEX IF NOT EXISTS idx_access_tokens_token_hash ON access_tokens(token_hash);
