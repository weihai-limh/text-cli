// textcli-core-approval — 审批 answerer（Phase 3，路径 C：接口重设计）
//
// 从母本 runtime-approval/answerer.ts 复用核心算法，dsh seam 全部改为注入 deps：
//   ApprovalDeps.httpPost / hmacSign 必填；audit / now 可选。
// 关键语义（红线）：
//   · req.agent 存在 → 直接委托（decided:false），绝不联网替宿主决策
//   · 未配置 webhook/secret → fail-closed deny（unconfigured）
//   · 超时/不可达/非2xx/回显callId不符/响应签名不符 → 一律 deny
//   · 同 callId 二次请求命中重放缓存（TTL 内不联网）

export class ApprovalAnswerer {
  constructor(config = {}, deps) {
    if (!deps || typeof deps.httpPost !== "function" || typeof deps.hmacSign !== "function") {
      throw new Error("ApprovalAnswerer requires deps.httpPost and deps.hmacSign");
    }
    this.config = { timeoutMs: 5000, callIdTtlMs: 300000, ...config };
    this.deps = deps;
    this.now = deps.now || Date.now;
    this.replay = new Map();
  }

  /**
   * 应答一次审批请求。
   * @param {{callId:string, toolName:string, reason?:string, agent?:string}} req
   * @returns {{decided:boolean, allowed?:boolean, decidedBy?:string, reason?:string}}
   */
  async answer(req) {
    // ① 归属过滤：agent 存在 → 委托（waterfall 下一个处理器）
    if (req.agent) {
      this.audit("delegate", { callId: req.callId, toolName: req.toolName, reason: "agent-attribution" });
      return { decided: false };
    }
    // ② 防重放
    const cached = this.replay.get(req.callId);
    if (cached && cached.expireAt > this.now()) {
      this.audit("replay-served", { callId: req.callId, allowed: cached.decision.allowed });
      return cached.decision;
    }
    // ③ 未配置 → fail-closed
    if (!this.config.webhookUrl || !this.config.secret) {
      const d = { decided: true, allowed: false, decidedBy: "unconfigured" };
      this.record(req.callId, d);
      return d;
    }
    // ④ HMAC 双向签名请求
    const body = JSON.stringify({ callId: req.callId, toolName: req.toolName, reason: req.reason, agent: req.agent });
    const sig = this.deps.hmacSign(this.config.secret, body);
    const headers = {
      "Content-Type": "application/json",
      "X-Tc-CallId": req.callId,
      "X-Tc-Signature": sig,
    };
    let res;
    try {
      res = await withTimeout(this.deps.httpPost(this.config.webhookUrl, body, headers), this.config.timeoutMs);
    } catch (e) {
      const decidedBy = isTimeoutError(e) ? "timeout" : "unavailable";
      const d = { decided: true, allowed: false, decidedBy };
      this.record(req.callId, d);
      return d;
    }
    // ⑤ 非 2xx → deny
    if (res.status < 200 || res.status >= 300) {
      const d = { decided: true, allowed: false, decidedBy: "unavailable" };
      this.record(req.callId, d);
      return d;
    }
    // ⑥ 回显 callId 校验
    let parsed;
    try {
      parsed = JSON.parse(res.body);
    } catch {
      const d = { decided: true, allowed: false, decidedBy: "unavailable" };
      this.record(req.callId, d);
      return d;
    }
    if (parsed.callId !== req.callId) {
      const d = { decided: true, allowed: false, decidedBy: "forged" };
      this.record(req.callId, d);
      return d;
    }
    // ⑦ 响应签名校验（fail-closed）
    const respSig = res.headers && (res.headers["x-tc-response-signature"] || res.headers["X-Tc-Response-Signature"]);
    const expected = this.deps.hmacSign(this.config.secret, res.body);
    if (!respSig || respSig !== expected) {
      const d = { decided: true, allowed: false, decidedBy: "forged" };
      this.record(req.callId, d);
      return d;
    }
    const d = { decided: true, allowed: parsed.allowed === true, decidedBy: "webhook", reason: parsed.reason };
    this.record(req.callId, d);
    return d;
  }

  record(callId, decision) {
    this.replay.set(callId, { decision, expireAt: this.now() + this.config.callIdTtlMs });
    this.audit("decided", { callId, decidedBy: decision.decidedBy, allowed: decision.allowed });
  }
  audit(type, payload) {
    if (this.deps.audit) this.deps.audit({ type, ...payload });
  }
}

function withTimeout(promise, ms) {
  return new Promise((resolve, reject) => {
    const t = setTimeout(() => reject(Object.assign(new Error("timeout"), { __timeout: true })), ms);
    promise.then(
      (v) => {
        clearTimeout(t);
        resolve(v);
      },
      (e) => {
        clearTimeout(t);
        reject(e);
      },
    );
  });
}
function isTimeoutError(e) {
  return !!(e && e.__timeout);
}

// ─── withApproval 中间件（dispatch 前审批闸）────────────────────────
/**
 * 审批守卫：每个 dispatch 先问 answerer；deny → ACCESS_DENIED 信封短路。
 * decided:false（委托/无 agent 体系）→ 放行 next。
 */
export function withApproval(answerer, opts = {}) {
  const toolNameFor = opts.toolNameFor || ((domain, action) => `tc__${domain}__${action}`);
  const callIdFor =
    opts.callIdFor ||
    ((domain, action, params, context) =>
      `${domain};${action}:${(context && context.callId) || Math.random().toString(36).slice(2)}`);
  return (next) => async (domain, action, params, context) => {
    const d = await answerer.answer({
      callId: callIdFor(domain, action, params, context),
      toolName: toolNameFor(domain, action),
      reason: opts.reason,
      agent: context && context.agent,
    });
    if (d.decided && !d.allowed) {
      return { rst_types: "text", rst_err: "ACCESS_DENIED", rst_data: { reason: `approval denied: ${d.decidedBy ?? "no-decision"}` } };
    }
    return next(domain, action, params, context);
  };
}
