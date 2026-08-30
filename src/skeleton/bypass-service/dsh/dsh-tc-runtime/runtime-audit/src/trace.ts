/**
 * trace.ts——审计 trace 模型（功能设计 §1.1.1 审计事件模型）
 *
 * traceId = `tc-<epochMs>-<rand6>`；每入站请求一个 TraceSession，
 * 管道各段事件携带 traceId + 递增 seq——按 traceId 归组 + seq 排序可重建全链路。
 */

export type AuditType =
  | "inbound" // 入站接收
  | "parse" // 解析
  | "route" // 路由决策
  | "tool-exec" // 工具执行（信封结果）
  | "credential" // 凭据取用
  | "sandbox-deny" // 沙箱拒绝
  | "approval" // 审批应答（asked/decided pair）
  | "envelope"; // 信封返回

export interface AuditEvent {
  ts: string; // ISO 8601
  traceId: string;
  seq: number;
  type: AuditType;
  payload: Record<string, unknown>;
}

/** 生成 traceId：tc-<epochMs>-<rand6> */
export function newTraceId(): string {
  return `tc-${Date.now()}-${Math.floor(Math.random() * 1_000_000)}`;
}

/** 单次请求的审计会话（traceId + seq 递增） */
export class TraceSession {
  readonly traceId: string;
  private _seq = 0;

  constructor(traceId?: string) {
    this.traceId = traceId ?? newTraceId();
  }

  /** 产出一条事件（seq 递增） */
  next(type: AuditType, payload: Record<string, unknown> = {}): AuditEvent {
    return {
      ts: new Date().toISOString(),
      traceId: this.traceId,
      seq: this._seq++,
      type,
      payload,
    };
  }
}
