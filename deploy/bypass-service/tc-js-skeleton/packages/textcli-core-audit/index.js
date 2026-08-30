// textcli-core-audit — 审计 trace（Phase 2，路径 A 纯搬运）
//
// 从母本 runtime-audit 忠实搬运：TraceSession（traceId + 递增 seq）负责调用链归组；
// AuditWriter 注入（内存 / JSONL 文件两实现）。与 dsh 会话完全解耦。
//
// 重建算法（由消费方执行）：按 traceId 归组 + 按 seq 排序 → 恢复全链路。
// seq 承担定序职责（ts 是毫秒精度，同毫秒事件无法定序）。

export function newTraceId(prefix = "trace") {
  return `${prefix}-${Date.now()}-${Math.floor(Math.random() * 1_000_000)}`;
}

export class TraceSession {
  constructor(traceId) {
    this.traceId = traceId ?? newTraceId();
    this._seq = 0;
  }
  /** 产出一条事件（seq 递增） */
  next(type, payload = {}) {
    return {
      ts: new Date().toISOString(),
      traceId: this.traceId,
      seq: this._seq++,
      type,
      payload,
    };
  }
}

/** 内存审计 writer（测试 / 裸环境；events 可读） */
export function createMemoryAudit() {
  const events = [];
  return {
    events,
    async write(event) {
      events.push(event);
    },
    logPath() {
      return "(memory)";
    },
    maintain() {
      /* no-op */
    },
  };
}

/** JSONL 审计 writer（node:fs append-only，容量轮转 + TTL 清理可选） */
export function createJsonlAudit(opts) {
  const fs = opts && opts.fs ? opts.fs : null;
  const pathMod = opts && opts.pathMod ? opts.pathMod : null;
  if (!fs || !pathMod) {
    // 动态引入 node 内置，避免在非 node 环境硬失败
    return createMemoryAudit();
  }
  const logPath = opts.path;
  const ttlHours = opts.ttlHours ?? 24;
  const maxMb = opts.maxMb ?? 50;
  const maxBytes = maxMb > 0 ? maxMb * 1024 * 1024 : 0;

  function rotateIfNeeded() {
    if (maxBytes <= 0) return;
    try {
      if (fs.statSync(logPath).size >= maxBytes) {
        fs.renameSync(logPath, `${logPath}.${Date.now()}`);
      }
    } catch {
      /* 首次写：文件不存在 */
    }
  }
  function purgeExpired() {
    if (ttlHours <= 0) return;
    const dir = pathMod.dirname(logPath);
    const base = pathMod.basename(logPath);
    const cutoff = Date.now() - ttlHours * 3600000;
    let entries = [];
    try {
      entries = fs.readdirSync(dir);
    } catch {
      return;
    }
    for (const name of entries) {
      if (!name.startsWith(`${base}.`)) continue;
      const full = pathMod.join(dir, name);
      try {
        if (fs.statSync(full).mtimeMs < cutoff) fs.unlinkSync(full);
      } catch {
        /* 竞态容忍 */
      }
    }
  }

  return {
    async write(event) {
      rotateIfNeeded();
      fs.mkdirSync(pathMod.dirname(logPath), { recursive: true });
      fs.appendFileSync(logPath, `${JSON.stringify(event)}\n`, "utf8");
    },
    logPath() {
      return logPath;
    },
    maintain() {
      rotateIfNeeded();
      purgeExpired();
    },
  };
}

// ─── withAudit 中间件（每次执行记 inbound + tool-exec）─────────────
/**
 * 审计守卫：每次 dispatch 新建 TraceSession，记入站事件 + 工具执行结果事件。
 * writer 注入（内存/JSONL/任意 sink）。不审计不影响执行。
 */
export function withAudit(audit, opts = {}) {
  const traceIdFor = opts.traceIdFor || ((domain, action, params, context) => context && context.traceId);
  return (next) => async (domain, action, params, context) => {
    const session = new TraceSession(traceIdFor(domain, action, params, context));
    await audit.write(session.next("inbound", { domain, action, params }));
    try {
      const result = await next(domain, action, params, context);
      await audit.write(session.next("tool-exec", { domain, action, ok: !isErr(result) }));
      return result;
    } catch (e) {
      await audit.write(session.next("tool-exec", { domain, action, ok: false, error: e.message }));
      throw e;
    }
  };
}

function isErr(r) {
  return r && typeof r === "object" && typeof r.rst_err === "string" && r.rst_err !== "";
}
