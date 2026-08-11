CREATE TABLE IF NOT EXISTS rate_limits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    is_get INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_rate_limits_created_at ON rate_limits(created_at);
