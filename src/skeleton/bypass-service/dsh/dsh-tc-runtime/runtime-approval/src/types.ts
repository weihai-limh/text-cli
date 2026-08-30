/**
 * types.ts——审批 answerer 类型模型（功能设计 §8.4 / §8.4.1）
 */

/** 入站审批请求（来自 dsh approval waterfall） */
export interface ApprovalRequest {
  /** 工具调用 id（回显校验 + 重放防护 key） */
  callId: string;
  /** 工具名（如 tc__math__eval） */
  toolName: string;
  /** 审批原因 */
  reason?: string;
  /**
   * dsh agent 归属（红线⑥）。存在 → answerer 委托（delegate），
   * 绝不替 dsh agent 的审批做决策，防止被 tc webhook 劫持。
   */
  agent?: string;
}

export type ApprovalDecidedBy =
  | "webhook" // 由 tc webhook 决策
  | "unconfigured" // 未配置 webhook → 恒 deny
  | "unavailable" // 不可达/超时/非预期/伪造 → fail-closed deny
  | "forged" // 响应签名/回显校验失败
  | "timeout"; // HTTP 超时

/**
 * answerer 决策结果：
 * - decided=false 且 decidedBy 缺失 → 委托（delegate），由 waterfall 下一个处理器决策
 * - decided=true → 本 answerer 已决策（allow/deny）
 */
export interface ApprovalDecision {
  decided: boolean;
  allowed?: boolean;
  decidedBy?: ApprovalDecidedBy;
  reason?: string;
}

export interface ApprovalConfig {
  /** tcRuntime.approval.webhook_url；缺省 → 恒 deny */
  webhookUrl?: string;
  /** 共享 HMAC 密钥（请求+响应双向签名） */
  secret?: string;
  /** HTTP 超时（ms），缺省 5000 */
  timeoutMs?: number;
  /** 已应答 callId 重放防护 TTL（ms），缺省 300000 */
  callIdTtlMs?: number;
}

export interface ApprovalDeps {
  /** 注入式 HTTP POST（裸环境用 mock；真实环境用 fetch/node-http） */
  httpPost: (
    url: string,
    body: string,
    headers: Record<string, string>,
  ) => Promise<{ status: number; body: string; headers?: Record<string, string> }>;
  /** 注入式 HMAC 签名（sha256 hex） */
  hmacSign: (secret: string, payload: string) => string;
  /** 审计回调（写入独立 JSONL）；缺省不审计 */
  audit?: (payload: Record<string, unknown>) => void;
  /** 时钟（可注入，便于测试 TTL） */
  now?: () => number;
}
