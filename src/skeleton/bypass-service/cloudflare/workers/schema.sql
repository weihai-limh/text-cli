-- Cloudflare 专供版 D1 建表（策划 §5）
-- 运行时逻辑层走 kv 表（StorageKV 契约，供 tc-js-skeleton 组件复用）；
-- 业务表用于查询面（tasks 状态 / usage 聚合 / mesh_routes 路由 / tokens 校验）。

-- 通用键值（StorageKV 契约的 D1 落地：storage.namespace("tokens") 等 → kv 键带前缀）
CREATE TABLE IF NOT EXISTS kv (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at INTEGER NOT NULL
);

-- 指令包（可执行包：schema + handler 源码字符串）
CREATE TABLE IF NOT EXISTS packages (
  package_id TEXT PRIMARY KEY,
  schema_json TEXT NOT NULL,
  handler_js TEXT NOT NULL,
  domains TEXT NOT NULL,
  actions TEXT NOT NULL,
  installed_at INTEGER NOT NULL
);

-- Service-token（存 hash；可撤销）
CREATE TABLE IF NOT EXISTS tokens (
  token_hash TEXT PRIMARY KEY,
  requester_id TEXT NOT NULL,
  tier TEXT,
  created_at INTEGER NOT NULL,
  revoked_at INTEGER
);

-- key 指令化凭据（values 加密存储，密钥 Worker Secrets）
CREATE TABLE IF NOT EXISTS keys (
  service TEXT PRIMARY KEY,
  key_type TEXT,
  values_cipher TEXT NOT NULL,
  registered_at INTEGER NOT NULL,
  quota_track TEXT
);

-- 请求方计次（挂 Service-token requester_id）
CREATE TABLE IF NOT EXISTS usage (
  requester_id TEXT NOT NULL,
  target TEXT NOT NULL,
  cycle TEXT NOT NULL,
  limit INTEGER NOT NULL,
  used INTEGER NOT NULL,
  usage_date TEXT NOT NULL,
  PRIMARY KEY (requester_id, target, usage_date)
);

-- 异步任务五态
CREATE TABLE IF NOT EXISTS tasks (
  task_id TEXT PRIMARY KEY,
  domain TEXT NOT NULL,
  action TEXT NOT NULL,
  params TEXT,
  status TEXT NOT NULL,
  result_json TEXT,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);

-- 审计
CREATE TABLE IF NOT EXISTS audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts INTEGER NOT NULL,
  requester_id TEXT,
  prompt TEXT,
  rst_type TEXT,
  rst_err TEXT,
  sandbox_reject INTEGER
);

-- mesh：其他运行时双 token（加密存明文以便转发，hash 供校验）
CREATE TABLE IF NOT EXISTS mesh_peers (
  peer_id TEXT PRIMARY KEY,
  endpoint_url TEXT NOT NULL,
  access_token_cipher TEXT,
  service_token_cipher TEXT,
  created_at INTEGER NOT NULL
);

-- mesh 路由：domain;action → peer
CREATE TABLE IF NOT EXISTS mesh_routes (
  domain TEXT NOT NULL,
  action TEXT NOT NULL,
  peer_id TEXT NOT NULL,
  PRIMARY KEY (domain, action)
);

-- 技能白名单（暂定 {} 全开）
CREATE TABLE IF NOT EXISTS service_manifest (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  public_directives TEXT NOT NULL
);
