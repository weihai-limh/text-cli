/**
 * store.ts——dsh-quota 纯逻辑核心（功能设计 §8.5）
 *
 * - register/unregister/reset/list：生命周期
 * - check：只读探测（超限 → status:"stop"）
 * - consume：原子 check+consume（乐观锁语义——读改写在单函数内，无中间 await 穿插；
 *   多进程场景由 StorageKV 实现层保证原子，裸环境内存实现天然原子）
 *
 * 存储注入 StorageKV（ctx.storage）；`now` 可注入便于测试周期翻转。
 */
import type {
  CheckResult,
  ConsumeResult,
  ListResult,
  QuotaRecord,
  RegisterOptions,
  RegisterResult,
  StorageKV,
} from "./types.js";
import { needsFlip, windowFor } from "./period.js";

const KEY_PREFIX = "quota:";
const keyOf = (id: string) => `${KEY_PREFIX}${id}`;

export class QuotaStore {
  constructor(
    private readonly storage: StorageKV,
    private readonly now: () => number = Date.now,
  ) {}

  private async load(id: string): Promise<QuotaRecord | null> {
    const raw = await this.storage.get(keyOf(id));
    return raw ? (JSON.parse(raw) as QuotaRecord) : null;
  }

  private async save(rec: QuotaRecord): Promise<void> {
    await this.storage.set(keyOf(rec.id), JSON.stringify(rec));
  }

  /** 窗口翻转：超期则清零 used 并重设 windowStart */
  private async flipIfNeeded(rec: QuotaRecord): Promise<boolean> {
    if (needsFlip(rec.windowStart, rec.period, this.now(), rec.createdAt)) {
      const w = windowFor(rec.period, this.now(), rec.createdAt);
      rec.used = 0;
      rec.windowStart = w.start;
      return true;
    }
    return false;
  }

  async register(id: string, opts: RegisterOptions): Promise<RegisterResult> {
    if (!id) return { ok: false, error: "id required" };
    if (!Number.isFinite(opts.limit) || opts.limit < 0) {
      return { ok: false, error: "limit must be a non-negative number" };
    }
    const existing = await this.load(id);
    if (existing) return { ok: false, error: `already registered: ${id}` };

    const now = this.now();
    const rec: QuotaRecord = {
      id,
      period: opts.period,
      limit: opts.limit,
      used: 0,
      createdAt: now,
      windowStart: windowFor(opts.period, now, now).start,
    };
    await this.save(rec);
    return { ok: true, record: rec };
  }

  async unregister(id: string): Promise<{ ok: boolean; error?: string }> {
    const rec = await this.load(id);
    if (!rec) return { ok: false, error: `not found: ${id}` };
    await this.storage.delete(keyOf(id));
    return { ok: true };
  }

  async reset(id: string): Promise<RegisterResult> {
    const rec = await this.load(id);
    if (!rec) return { ok: false, error: `not found: ${id}` };
    const w = windowFor(rec.period, this.now(), rec.createdAt);
    rec.used = 0;
    rec.windowStart = w.start;
    await this.save(rec);
    return { ok: true, record: rec };
  }

  async check(id: string): Promise<CheckResult> {
    const rec = await this.load(id);
    if (!rec) return { ok: false, error: `not found: ${id}` };
    await this.flipIfNeeded(rec);
    await this.save(rec);
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

  /** 原子 check+consume：超限直接返回 stop（不扣减），否则扣减并返回 ok */
  async consume(id: string, n = 1): Promise<ConsumeResult> {
    if (!Number.isInteger(n) || n < 1) return { ok: false, error: "n must be a positive integer" };
    const rec = await this.load(id);
    if (!rec) return { ok: false, error: `not found: ${id}` };
    await this.flipIfNeeded(rec);
    if (rec.used >= rec.limit) {
      await this.save(rec);
      return { ok: true, id, status: "stop", used: rec.used, limit: rec.limit, remaining: 0 };
    }
    rec.used += n;
    await this.save(rec);
    return {
      ok: true,
      id,
      status: "ok",
      used: rec.used,
      limit: rec.limit,
      remaining: Math.max(0, rec.limit - rec.used),
    };
  }

  async list(): Promise<ListResult> {
    const keys = this.storage.keys ? await this.storage.keys(KEY_PREFIX) : [];
    const ids = keys.filter((k) => k.startsWith(KEY_PREFIX)).map((k) => k.slice(KEY_PREFIX.length));
    const recs = await Promise.all(ids.map((id) => this.load(id)));
    const records = recs
      .filter((r): r is QuotaRecord => r !== null)
      .map((r) => ({
        id: r.id,
        period: r.period,
        limit: r.limit,
        used: r.used,
        status: (r.used >= r.limit ? "stop" : "ok") as "stop" | "ok",
        windowStart: r.windowStart,
      }));
    return { ok: true, records };
  }
}

/** 内存 KV（测试 / 裸环境默认实现） */
export function createMemoryStorage(): StorageKV {
  const map = new Map<string, string>();
  return {
    async get(k) {
      return map.has(k) ? map.get(k)! : null;
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
