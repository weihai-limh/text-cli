// textcli-core-mesh — mesh 转发（Phase 3，路径 C：接口重设计）
//
// 从母本 runtime-mesh/mesh.ts 复用算法，最大 dsh seam（Typert Remote）改为注入
// deps.remote(peer, domain, action, params)。状态（visited/hop/routeTable）由
// MeshContext 传入，组件不持有全局状态。
//
// 流程：本地命中→本地派发；否则防环 + 跳数上限 → 路由表选 peer →
// 跨节点脱敏（sensitive 默认关）→ 指数退避重试（3 次）→ 凭证前向开关。

export const MAX_HOP_DEPTH = 5;
const RETRIES = 2; // 额外重试次数（共 3 次尝试）
const SENSITIVE_KEYS = /(secret|password|token|credential|apikey|api_key)/i;

export class MeshCycleError extends Error {
  constructor() {
    super("mesh cycle detected");
    this.name = "MESH_CYCLE";
  }
}
export class MeshHopExceeded extends Error {
  constructor() {
    super("mesh hop exceeded");
    this.name = "MESH_HOP_EXCEEDED";
  }
}

function desensitize(params, sensitive) {
  if (!sensitive) return params;
  return params.map((p) => (SENSITIVE_KEYS.test(p) ? p.replace(/=.*$/, "=***") : p));
}
function backoff(attempt, now) {
  const ms = 2 ** attempt * 50;
  return new Promise((r) => setTimeout(r, ms));
}

/**
 * mesh 转发主流程。
 * @param {object} deps { localHas, dispatch, remote, now? }
 * @param {object} ctx { routeTable: MeshPeer[], visited: Set, hop, sensitive?, forwardCredentials? }
 */
export async function meshRoute(domain, action, params, deps, ctx, context) {
  // ① 本地命中 → 本地派发（context 透传，供 auth/审计等下游使用）
  if (deps.localHas(domain, action)) {
    return deps.dispatch(domain, action, params, context);
  }
  // ② 防环 + 跳数上限
  const key = `${domain};${action}`;
  if (ctx.visited.has(key)) throw new MeshCycleError();
  if (ctx.hop > MAX_HOP_DEPTH) throw new MeshHopExceeded();
  // ③ 路由表选 peer（精确匹配 domain，否则首 peer）
  const peer = ctx.routeTable.find((p) => p.id === domain) ?? ctx.routeTable[0];
  if (!peer) return { rst_types: "text", rst_err: "ERR_NOT_FOUND", rst_data: { reason: "no-peer" } };
  // ④ 跨节点脱敏
  const outParams = desensitize(params, !!ctx.sensitive);
  // ⑤ 指数退避重试
  let lastErr = null;
  for (let attempt = 0; attempt <= RETRIES; attempt++) {
    try {
      return await deps.remote(peer, domain, action, outParams);
    } catch (e) {
      lastErr = e;
      if (attempt < RETRIES) await backoff(attempt, deps.now || Date.now);
    }
  }
  throw lastErr ?? new Error("mesh forward failed");
}

/** 凭证前向策略（凭证三原则：peer 隔离，默认不转发） */
export function credentialForwardPolicy(ctx) {
  if (!ctx.forwardCredentials) return { forward: false, degraded: false };
  return { forward: true, degraded: true };
}

// ─── withMesh 中间件 ───────────────────────────────────────────────
/**
 * mesh 守卫：本地不命中 → 按路由表转发。
 * visited/hop 由 opts 提供（宿主跨跳传播），默认每调用新建。
 */
export function withMesh(opts = {}) {
  const makeCtx = opts.makeCtx
    ? opts.makeCtx
    : () => ({
        routeTable: opts.routeTable || [],
        visited: opts.visited || new Set(),
        hop: opts.hop || 0,
        sensitive: opts.sensitive,
        forwardCredentials: opts.forwardCredentials,
      });
  return (next) => async (domain, action, params, context) => {
    const deps = {
      localHas: opts.localHas,
      dispatch: next,
      remote: opts.remote,
      now: opts.now,
    };
    return meshRoute(domain, action, params, deps, makeCtx(), context);
  };
}
