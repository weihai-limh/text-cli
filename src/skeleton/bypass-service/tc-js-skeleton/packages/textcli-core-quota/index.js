// textcli-core-quota — 配额 store（Phase 2，路径 A 纯搬运）
//
// 从母本 runtime-quota 忠实搬运，仅做风格统一：构造注入 (storage, now) 保持。
// 协议红线（已实证）：配额耗尽 → {status:"stop"} 走降级链，绝不出 SERVICE_DENIED；
// 超限不扣减；同步 stop = 降级信号（非终态）。

const KEY_PREFIX = "quota:";
const DAY = 86400000;
const keyOf = (id) => `${KEY_PREFIX}${id}`;

// ─── 周期窗口 ──────────────────────────────────────────────────────
export function windowFor(period, now, createdAt) {
  const d = new Date(now);
  const y = d.getUTCFullYear();
  const m = d.getUTCMonth();
  const day = d.getUTCDate();
  switch (period) {
    case "day":
      return { start: Date.UTC(y, m, day), end: Date.UTC(y, m, day) + DAY };
    case "week": {
      const dow = d.getUTCDay(); // 0=Sun..6=Sat
      const diffToMonday = (dow + 6) % 7;
      const monday = Date.UTC(y, m, day - diffToMonday);
      return { start: monday, end: monday + 7 * DAY };
    }
    case "month":
      return { start: Date.UTC(y, m, 1), end: Date.UTC(y, m + 1, 1) };
    case "year":
      return { start: Date.UTC(y, 0, 1), end: Date.UTC(y + 1, 0, 1) };
    case "forever":
      return { start: createdAt, end: Infinity };
    default:
      throw new Error(`invalid period: ${period}`);
  }
}

export function needsFlip(recWindowStart, period, now, createdAt) {
  const w = windowFor(period, now, createdAt);
  return now >= w.end || recWindowStart !== w.start;
}

// ─── 内存 KV（测试 / 裸环境默认实现）──────────────────────────────
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

// ─── QuotaStore ────────────────────────────────────────────────────
export class QuotaStore {
  constructor(storage, now = Date.now) {
    this.storage = storage;
    this.now = now;
  }

  async load(id) {
    const raw = await this.storage.get(keyOf(id));
    return raw ? JSON.parse(raw) : null;
  }
  async save(rec) {
    await this.storage.set(keyOf(rec.id), JSON.stringify(rec));
  }
  async flipIfNeeded(rec) {
    if (needsFlip(rec.windowStart, rec.period, this.now(), rec.createdAt)) {
      const w = windowFor(rec.period, this.now(), rec.createdAt);
      rec.used = 0;
      rec.windowStart = w.start;
      return true;
    }
    return false;
  }

  async register(id, opts) {
    if (!id) return { ok: false, error: "id required" };
    if (!opts || !opts.period || !opts.limit || typeof opts.limit !== "number" || opts.limit < 0 || !Number.isFinite(opts.limit)) {
      return { ok: false, error: "limit must be a non-negative finite number" };
    }
    if (await this.load(id)) return { ok: false, error: `already registered: ${id}` };
    const rec = {
      id,
      period: opts.period,
      limit: opts.limit,
      used: 0,
      createdAt: this.now(),
      windowStart: windowFor(opts.period, this.now(), this.now()).start,
    };
    await this.save(rec);
    return { ok: true, record: rec };
  }

  async unregister(id) {
    if (!(await this.load(id))) return { ok: false, error: `not found: ${id}` };
    await this.storage.delete(keyOf(id));
    return { ok: true };
  }

  async reset(id) {
    const rec = await this.load(id);
    if (!rec) return { ok: false, error: `not found: ${id}` };
    rec.used = 0;
    rec.windowStart = windowFor(rec.period, this.now(), rec.createdAt).start;
    await this.save(rec);
    return { ok: true, record: rec };
  }

  async check(id) {
    const rec = await this.load(id);
    if (!rec) return { ok: false, error: `not found: ${id}` };
    if (await this.flipIfNeeded(rec)) await this.save(rec);
    const status = rec.used >= rec.limit ? "stop" : "ok";
    return {
      ok: true,
      id,
      status,
      used: rec.used,
      limit: rec.limit,
      remaining: Math.max(0, rec.limit - rec.used),
      period: rec.period,
      windowStart: rec.windowStart,
    };
  }

  /** 原子 check+consume：超限直接 stop（不扣减），否则扣减并返回 ok */
  async consume(id, n = 1) {
    if (!Number.isInteger(n) || n < 1) return { ok: false, error: "n must be a positive integer" };
    const rec = await this.load(id);
    if (!rec) return { ok: false, error: `not found: ${id}` };
    if (await this.flipIfNeeded(rec)) await this.save(rec);
    if (rec.used >= rec.limit) {
      await this.save(rec);
      return { ok: true, id, status: "stop", used: rec.used, limit: rec.limit, remaining: 0 };
    }
    rec.used += n;
    await this.save(rec);
    return { ok: true, id, status: "ok", used: rec.used, limit: rec.limit, remaining: Math.max(0, rec.limit - rec.used) };
  }

  async list() {
    const keys = this.storage.keys ? await this.storage.keys(KEY_PREFIX) : [];
    const ids = keys.filter((k) => k.startsWith(KEY_PREFIX)).map((k) => k.slice(KEY_PREFIX.length));
    const recs = (await Promise.all(ids.map((id) => this.load(id)))).filter(Boolean);
    return {
      ok: true,
      records: recs.map((r) => ({
        id: r.id,
        period: r.period,
        limit: r.limit,
        used: r.used,
        status: r.used >= r.limit ? "stop" : "ok",
        windowStart: r.windowStart,
      })),
    };
  }
}

// ─── withQuota 中间件（dispatch 前守卫钩子）────────────────────────
/**
 * 配额守卫：keyFor 决定桶 id（默认 domain;action）。
 * 桶未注册 → 放行；已注册且 stop → 短路返回 stop 信封（降级信号，非错误）。
 */
export function withQuota(store, opts = {}) {
  const keyFor = opts.keyFor || ((domain, action) => `${domain};${action}`);
  return (next) => async (domain, action, params, context) => {
    const id = keyFor(domain, action);
    const q = await store.consume(id);
    if (q.status === "stop") {
      return { rst_types: "text", rst_err: "", rst_data: { status: "stop", reason: "quota_exhausted", quotaId: id } };
    }
    return next(domain, action, params, context);
  };
}
