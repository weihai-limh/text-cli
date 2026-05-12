-- D1 数据库迁移脚本 — text-cli 指令服务
-- 仅在启用 D1 模式时使用

CREATE TABLE IF NOT EXISTS directives (
  id TEXT PRIMARY KEY,
  domain TEXT NOT NULL,
  action TEXT NOT NULL,
  name TEXT NOT NULL,
  category TEXT,
  description TEXT,
  parameters_json TEXT DEFAULT '[]',
  prompt_template TEXT,
  trigger_keywords_json TEXT DEFAULT '[]',
  response_type TEXT DEFAULT 'text',
  response_example_json TEXT,
  handler_type TEXT DEFAULT 'static',
  enabled INTEGER DEFAULT 1,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_directives_domain_action
  ON directives(domain, action);

CREATE TABLE IF NOT EXISTS tokens (
  token_hash TEXT PRIMARY KEY,
  client_name TEXT NOT NULL,
  quota INTEGER DEFAULT -1,
  used INTEGER DEFAULT 0,
  enabled INTEGER DEFAULT 1,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS usage_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  request_id TEXT,
  directive_key TEXT NOT NULL,
  token_hash TEXT,
  params_json TEXT,
  result_status TEXT,
  response_time_ms INTEGER,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_usage_logs_created
  ON usage_logs(created_at);

CREATE INDEX IF NOT EXISTS idx_usage_logs_directive
  ON usage_logs(directive_key, created_at);
