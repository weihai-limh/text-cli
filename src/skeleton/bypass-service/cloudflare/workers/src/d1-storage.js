// d1-storage — D1 → StorageKV 契约适配器（StorageKV 的 D1 落地）
//
// 复用 tc-js-skeleton 组件（quota/audit/auth/storage 等）的关键：
// StorageKV { get/set/delete/keys? } 在此用 D1 kv 表实现。
// 真实 Worker：env.DB.prepare(...).bind(...).first()/all()/run()；
// 本地测试：test/helpers.js 的 createD1Mock 提供同构接口。

export function createD1Storage(db) {
  return {
    async get(k) {
      const row = await db.prepare("SELECT value FROM kv WHERE key = ?").bind(k).first();
      return row ? row.value : null;
    },
    async set(k, v) {
      await db
        .prepare(
          "INSERT INTO kv (key, value, updated_at) VALUES (?, ?, ?) " +
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
        )
        .bind(k, v, Date.now())
        .run();
    },
    async delete(k) {
      await db.prepare("DELETE FROM kv WHERE key = ?").bind(k).run();
    },
    async keys(prefix) {
      const res = await db.prepare("SELECT key FROM kv WHERE key LIKE ?").bind(`${prefix || ""}%`).all();
      return (res.results || []).map((r) => r.key);
    },
  };
}
