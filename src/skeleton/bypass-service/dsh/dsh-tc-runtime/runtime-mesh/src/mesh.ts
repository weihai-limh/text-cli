/**
 * mesh.ts——mesh 转发（功能设计 §10.2 / 附录 B 机制 8）
 *
 * 本地不命中 → 路由表查 peer → Typert Remote 出站 → 信封回传（delegated）
 * - visited 防环（同 key 不重复转发）
 * - MAX_HOP_DEPTH=5 跳数上限
 * - 指数退避重试 2 次（共 3 次尝试）
 * - sensitive 脱敏：跨节点前对参数脱敏（默认关 → 不脱敏）
 * - 凭证三原则：默认关，不前向凭据；开启时 peer 隔离 + _mesh_credential_degraded
 */
export const MAX_HOP_DEPTH = 5;
const RETRIES = 2; // 指数退避 2 次（共 3 次尝试）

export interface MeshPeer {
  id: string;
  endpoint: string;
}

export interface MeshDeps {
  /** 本地是否提供该指令 */
  localHas: (domain: string, action: string) => boolean;
  /** 本地派发 */
  dispatch: (domain: string, action: string, params: string[]) => Promise<unknown>;
  /** 跨节点出站（Typert Remote / Connection RPC） */
  remote: (peer: MeshPeer, domain: string, action: string, params: string[]) => Promise<unknown>;
  now?: () => number;
}

export interface MeshContext {
  routeTable: MeshPeer[];
  visited: Set<string>;
  hop: number;
  /** 跨节点脱敏（默认 false） */
  sensitive?: boolean;
  /** 凭证前向（默认 false，凭证三原则） */
  forwardCredentials?: boolean;
}

export class MeshCycleError extends Error {
  constructor() {
    super("MESH_CYCLE");
    this.name = "MeshCycleError";
  }
}
export class MeshHopExceeded extends Error {
  constructor() {
    super("MESH_HOP_EXCEEDED");
    this.name = "MeshHopExceeded";
  }
}

const SENSITIVE_KEYS = /(secret|password|token|credential|apikey|api_key)/i;

/** 跨节点脱敏：遮蔽敏感参数值 */
function desensitize(params: string[], sensitive: boolean): string[] {
  if (!sensitive) return params;
  return params.map((p) =>
    SENSITIVE_KEYS.test(p) ? p.replace(/=.*$/, "=***") : p,
  );
}

function backoff(attempt: number, now: () => number): Promise<void> {
  const ms = 2 ** attempt * 50; // 50, 100ms
  const start = now();
  return new Promise((resolve) => setTimeout(() => resolve(), ms) && void start);
}

export async function meshRoute(
  domain: string,
  action: string,
  params: string[],
  deps: MeshDeps,
  ctx: MeshContext,
): Promise<unknown> {
  // 本地命中 → 本地派发（不跨节点，不脱敏）
  if (deps.localHas(domain, action)) {
    return deps.dispatch(domain, action, params);
  }

  const key = `${domain};${action}`;
  if (ctx.visited.has(key)) throw new MeshCycleError();
  if (ctx.hop > MAX_HOP_DEPTH) throw new MeshHopExceeded();

  // 路由表查 peer（按 domain 匹配，否则取首个）
  const peer = ctx.routeTable.find((p) => p.id === domain) ?? ctx.routeTable[0];
  if (!peer) {
    return { rst_err: "ERR_NOT_FOUND", rst_data: { reason: "no-peer" } };
  }

  ctx.visited.add(key);
  const outParams = desensitize(params, !!ctx.sensitive);

  let lastErr: unknown;
  for (let attempt = 0; attempt <= RETRIES; attempt++) {
    try {
      const r = await deps.remote(peer, domain, action, outParams);
      return r; // 信封回传（delegated 语义由调用方解释）
    } catch (e) {
      lastErr = e;
      if (attempt < RETRIES) await backoff(attempt, deps.now ?? Date.now);
    }
  }
  throw lastErr ?? new Error("mesh forward failed");
}

/** 凭证三原则判断：默认关（不前向），开启时标记 degraded */
export function credentialForwardPolicy(ctx: MeshContext): { forward: boolean; degraded: boolean } {
  if (!ctx.forwardCredentials) return { forward: false, degraded: false };
  return { forward: true, degraded: true }; // peer 隔离 + _mesh_credential_degraded
}
