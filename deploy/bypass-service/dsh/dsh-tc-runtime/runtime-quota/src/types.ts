/**
 * types.ts——dsh-quota 类型模型（功能设计 §8.5）
 */

/** 配额周期（对齐 tc quota 周期语义） */
export type QuotaPeriod = "day" | "week" | "month" | "year" | "forever";

/** 配额超限后的状态——`stop` 即降级信号源（Phase 10.2 消费） */
export type QuotaStatus = "ok" | "stop";

/** 持久化记录（JSON 存入 StorageKV，key = `quota:<id>`） */
export interface QuotaRecord {
  id: string;
  period: QuotaPeriod;
  limit: number;
  used: number;
  createdAt: number;
  /** 当前周期窗口起点（epochMs） */
  windowStart: number;
}

/** 可注入的 KV 存储（对齐 ctx.storage；裸环境用内存实现） */
export interface StorageKV {
  get(key: string): Promise<string | null>;
  set(key: string, value: string): Promise<void>;
  delete(key: string): Promise<void>;
  /** 可选：列出带前缀的 key（list 指令依赖） */
  keys?(prefix?: string): Promise<string[]>;
}

export interface RegisterOptions {
  period: QuotaPeriod;
  limit: number;
}

export interface RegisterResult {
  ok: boolean;
  error?: string;
  record?: QuotaRecord;
}

export interface CheckResult {
  ok: boolean;
  error?: string;
  id?: string;
  status?: QuotaStatus;
  used?: number;
  limit?: number;
  remaining?: number;
  period?: QuotaPeriod;
  windowStart?: number;
}

export interface ConsumeResult {
  ok: boolean;
  error?: string;
  id?: string;
  status?: QuotaStatus;
  used?: number;
  limit?: number;
  remaining?: number;
}

export interface ListResult {
  ok: boolean;
  records?: Array<{
    id: string;
    period: QuotaPeriod;
    limit: number;
    used: number;
    status: QuotaStatus;
    windowStart: number;
  }>;
}
