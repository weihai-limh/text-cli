/**
 * answerer.ts——审批回调 answerer（功能设计 §8.4 / §8.4.1 安全面）
 *
 * 设计要点：
 * 1. 归属过滤（红线⑥）：req.agent 存在 → 立即委托（delegate），绝不替 dsh agent 决策。
 * 2. 未配置 webhook → 恒 deny（ask 无通道退化为 deny）。
 * 3. 请求双向 HMAC 签名；响应回显 callId + 响应签名校验（防伪造/串线）。
 * 4. 重放防护：已应答 callId（TTL 内）直接返回缓存决策，不再触发 webhook。
 * 5. 超时/不可达/非预期 → fail-closed（deny + unavailable）。
 * 6. 每个请求/决策写审计事件（approval asked/decided pair，独立 JSONL）。
 */
import type {
  ApprovalConfig,
  ApprovalDecision,
  ApprovalDeps,
  ApprovalRequest,
} from "./types.js";

interface ReplayEntry {
  decision: ApprovalDecision;
  expireAt: number;
}

const DEFAULT_TIMEOUT = 5000;
const DEFAULT_TTL = 300_000;

export class ApprovalAnswerer {
  private readonly replay = new Map<string, ReplayEntry>();
  private readonly now: () => number;

  constructor(
    private readonly config: ApprovalConfig,
    private readonly deps: ApprovalDeps,
  ) {
    this.now = deps.now ?? Date.now;
  }

  /** 处理一个审批请求 */
  async answer(req: ApprovalRequest): Promise<ApprovalDecision> {
    // ① 归属过滤（红线⑥）——dsh agent 审批永不被 tc webhook 劫持
    if (req.agent) {
      this.auditEvent("delegate", {
        callId: req.callId,
        toolName: req.toolName,
        reason: "agent-attribution",
      });
      return { decided: false }; // 委托给 waterfall 下一个处理器
    }

    // ② 重放防护——已应答 callId 直接返回缓存
    const cached = this.replay.get(req.callId);
    if (cached && cached.expireAt > this.now()) {
      this.auditEvent("replay-served", { callId: req.callId, allowed: cached.decision.allowed });
      return cached.decision;
    }

    // ③ 未配置 webhook → 恒 deny（fail-closed）
    if (!this.config.webhookUrl || !this.config.secret) {
      const d: ApprovalDecision = { decided: true, allowed: false, decidedBy: "unconfigured" };
      this.recordAndAudit(d, req, "denied-unconfigured");
      return d;
    }

    // ④ 构造请求体 + 双向 HMAC 签名
    const body = JSON.stringify({
      agent: req.agent ?? null,
      toolName: req.toolName,
      callId: req.callId,
      reason: req.reason ?? "",
    });
    const sig = this.deps.hmacSign(this.config.secret, body);
    const headers = {
      "Content-Type": "application/json",
      "X-Tc-CallId": req.callId,
      "X-Tc-Signature": sig,
    };

    this.auditEvent("asked", { callId: req.callId, toolName: req.toolName, webhook: this.config.webhookUrl });

    let res: { status: number; body: string; headers?: Record<string, string> };
    const timeoutMs = this.config.timeoutMs ?? DEFAULT_TIMEOUT;
    try {
      res = await withTimeout(this.deps.httpPost(this.config.webhookUrl, body, headers), timeoutMs, this.now);
    } catch (e) {
      // 超时 / 不可达 → fail-closed
      const decidedBy = isTimeoutError(e) ? "timeout" : "unavailable";
      const d: ApprovalDecision = { decided: true, allowed: false, decidedBy };
      this.recordAndAudit(d, req, decidedBy);
      return d;
    }

    // ⑤ 解析 + 回显校验 + 响应签名校验
    let parsed: { allowed?: unknown; callId?: unknown };
    try {
      parsed = JSON.parse(res.body);
    } catch {
      const d: ApprovalDecision = { decided: true, allowed: false, decidedBy: "unavailable" };
      this.recordAndAudit(d, req, "malformed-response");
      return d;
    }

    // 非 2xx → fail-closed
    if (res.status < 200 || res.status >= 300) {
      const d: ApprovalDecision = { decided: true, allowed: false, decidedBy: "unavailable" };
      this.recordAndAudit(d, req, `http-${res.status}`);
      return d;
    }

    // 回显校验（防串线：响应必须对应同一 callId）
    if (parsed.callId !== req.callId) {
      const d: ApprovalDecision = { decided: true, allowed: false, decidedBy: "forged" };
      this.recordAndAudit(d, req, "callid-mismatch");
      return d;
    }

    // 响应签名校验（防伪造：webhook 用同一 secret 对响应体签名置于响应头）
    const respSig = res.headers?.["x-tc-response-signature"];
    const expectedSig = this.deps.hmacSign(this.config.secret, res.body);
    if (!respSig || respSig !== expectedSig) {
      const d: ApprovalDecision = { decided: true, allowed: false, decidedBy: "forged" };
      this.recordAndAudit(d, req, "bad-response-signature");
      return d;
    }

    const allowed = parsed.allowed === true;
    const d: ApprovalDecision = { decided: true, allowed, decidedBy: "webhook" };
    this.recordAndAudit(d, req, allowed ? "allowed" : "denied");
    return d;
  }

  private recordAndAudit(d: ApprovalDecision, req: ApprovalRequest, detail: string): void {
    // 重放防护写入
    const ttl = this.config.callIdTtlMs ?? DEFAULT_TTL;
    this.replay.set(req.callId, { decision: d, expireAt: this.now() + ttl });
    this.auditEvent("decided", {
      callId: req.callId,
      toolName: req.toolName,
      allowed: d.allowed,
      decidedBy: d.decidedBy,
      detail,
    });
  }

  private auditEvent(sub: string, payload: Record<string, unknown>): void {
    this.deps.audit?.({ sub, ...payload });
  }
}

/** Promise 超时包装（注入 now 便于测试；超时抛 TimeoutError） */
function withTimeout<T>(
  p: Promise<T>,
  ms: number,
  now: () => number,
): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const start = now();
    const timer = setTimeout(() => reject(new TimeoutError()), ms);
    p.then(
      (v) => {
        clearTimeout(timer);
        void start;
        resolve(v);
      },
      (e) => {
        clearTimeout(timer);
        reject(e);
      },
    );
  });
}

class TimeoutError extends Error {
  constructor() {
    super("timeout");
    this.name = "TimeoutError";
  }
}

function isTimeoutError(e: unknown): boolean {
  return e instanceof TimeoutError;
}
