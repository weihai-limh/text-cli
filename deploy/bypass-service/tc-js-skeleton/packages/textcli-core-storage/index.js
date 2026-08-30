// textcli-core-storage — 统一持久化地基（外挂，storage.on）
//
// 职责：包存储/索引、token 存储、配额计数、审计日志、请求方计次 —— 对外提供一致
// StorageKV 接口（get/set/delete/keys?）。quota/audit/usage 硬依赖它。
//
// 适配器双模态：
//   · createMemoryStorage()   内存（测试 / 裸环境）
//   · createFileStorage(dir)  Node 文件（每 key 一个 JSON 文件，原子写：tmp+rename）
// Cloudflare 版用 D1 适配器实现同一 StorageKV 契约即可（设计稿：node=文件，cloudflare=D1）。
//
// createStorage(adapter) 追加 namespace(prefix) 分区能力：
//   const store = createStorage(adapter);
//   const tokens = store.namespace("tokens");  // 键自动带 tokens: 前缀

import fs from "node:fs";
import path from "node:path";

// ─── 适配器契约：StorageKV ─────────────────────────────────────────
// interface StorageKV {
//   get(key): Promise<string|null>
//   set(key, value): Promise<void>
//   delete(key): Promise<void>
//   keys?(prefix?): Promise<string[]>
// }

// ─── 内存适配器 ────────────────────────────────────────────────────
export function createMemoryStorage() {
  const map = new Map();
  return {
    async get(k) {
      return map.has(k) ? map.get(k) : null;
    },
    async set(k, v) {
      map.set(k, v);
    },
    async delete(k) {
      map.delete(k);
    },
    async keys(prefix) {
      const all = [...map.keys()];
      return prefix ? all.filter((k) => k.startsWith(prefix)) : all;
    },
  };
}

// ─── 文件适配器（Node）─────────────────────────────────────────────
// key → base64url 文件名（含 ":"、"/" 等特殊字符安全落盘）；写入走 tmp+rename 原子替换。
function encodeKey(k) {
  return Buffer.from(k, "utf8").toString("base64url") + ".json";
}
function decodeKey(fileName) {
  return Buffer.from(fileName.slice(0, -".json".length), "base64url").toString("utf8");
}

export function createFileStorage(dir) {
  fs.mkdirSync(dir, { recursive: true });
  const fileOf = (k) => path.join(dir, encodeKey(k));
  return {
    async get(k) {
      try {
        return fs.readFileSync(fileOf(k), "utf8");
      } catch {
        return null;
      }
    },
    async set(k, v) {
      const f = fileOf(k);
      const tmp = `${f}.tmp`;
      fs.mkdirSync(path.dirname(f), { recursive: true });
      fs.writeFileSync(tmp, v, "utf8");
      fs.renameSync(tmp, f);
    },
    async delete(k) {
      try {
        fs.unlinkSync(fileOf(k));
      } catch {
        /* 不存在即幂等成功 */
      }
    },
    async keys(prefix) {
      let names;
      try {
        names = fs.readdirSync(dir);
      } catch {
        return [];
      }
      return names
        .filter((n) => n.endsWith(".json"))
        .map(decodeKey)
        .filter((k) => !prefix || k.startsWith(prefix));
    },
  };
}

// ─── createStorage：统一 store + namespace 分区 ────────────────────
function makePrefixed(adapter, prefix) {
  const p = prefix.endsWith(":") ? prefix : `${prefix}:`;
  return {
    get: (k) => adapter.get(p + k),
    set: (k, v) => adapter.set(p + k, v),
    delete: (k) => adapter.delete(p + k),
    keys: (sub) =>
      adapter.keys
        ? adapter.keys(p + (sub || "")).then((ks) =>
            ks.filter((k) => k.startsWith(p)).map((k) => k.slice(p.length)),
          )
        : Promise.resolve([]),
  };
}

export function createStorage(adapter) {
  const store = {
    get: (k) => adapter.get(k),
    set: (k, v) => adapter.set(k, v),
    delete: (k) => adapter.delete(k),
    keys: (prefix) => (adapter.keys ? adapter.keys(prefix) : Promise.resolve([])),
    /** 返回带前缀隔离的子 store（tokens: / quota: / usage: / audit: ...） */
    namespace(prefix) {
      return createStorage(makePrefixed(adapter, prefix));
    },
  };
  return store;
}
