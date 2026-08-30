// textcli-core-credentials — 凭据按包隔离（Phase 3，路径 C：接口重设计）
//
// 从母本 runtime-credentials 复用算法，dsh seam（ctx.credentials.resolve）改为注入
// CredentialSource.resolve(ref)。解析链顺序（B5 第一防线）：
//   1 授权映射(ACCESS_DENIED) → 2 配额预留(QUOTA_STOP) → 3 source.resolve(SERVICE_DENIED)
//   → 4 注入 env 白名单 → 5 审计
// 明文仅存在于 resolve 返回值，不进包源码、不落盘。

// ─── grant：TC_ ref + 按包授权映射 ─────────────────────────────────
export function toRefName(name) {
  const clean = String(name).toUpperCase().replace(/[^A-Z0-9]/g, "_");
  return `TC_${clean}`;
}

/**
 * 构建包授权：声明 → grants（双凭据 key+secret 拆成独立 grant）。
 * @param {string} packageId
 * @param {Array<{name:string}|{names:string[]}>} declarations
 */
export function buildGrants(packageId, declarations) {
  const grants = [];
  for (const decl of declarations || []) {
    const names = Array.isArray(decl.names) ? decl.names : [decl.name];
    for (const n of names) {
      const ref = toRefName(n);
      grants.push({ ref, envKey: ref, sourceName: n });
    }
  }
  return { packageId, grants };
}

export function isGranted(pkg, ref) {
  return !!(pkg && pkg.grants.some((g) => g.ref === ref));
}

// ─── CredentialSource（注入面）─────────────────────────────────────
/**
 * 凭据源：resolve(ref) → {value} | undefined（undefined = 缺失）。
 * 宿主用自己 secrets 后端实现同一签名即可。
 */
export function createMemoryCredentialSource(entries = {}) {
  return {
    async resolve(ref) {
      return ref in entries ? { value: entries[ref] } : undefined;
    },
  };
}

// ─── resolve 链 ────────────────────────────────────────────────────
/**
 * 解析单个凭据引用。
 * @returns {{ok:true, env:Record<string,string>} | {ok:false, code:"ACCESS_DENIED"|"SERVICE_DENIED"|"QUOTA_STOP", reason:string}}
 */
export async function resolveForPackage(ref, deps) {
  if (!isGranted(deps.grants, ref)) {
    deps.onResolve && deps.onResolve({ packageId: deps.packageId, ref, envKey: ref, ok: false, reason: "ACCESS_DENIED" });
    return { ok: false, code: "ACCESS_DENIED", reason: `credential not granted: ${ref}` };
  }
  if (deps.quotaCheck) {
    const allowed = await deps.quotaCheck(ref);
    if (!allowed) {
      return { ok: false, code: "QUOTA_STOP", reason: `quota stop: ${ref}` };
    }
  }
  const credential = await deps.source.resolve(ref);
  if (!credential) {
    return { ok: false, code: "SERVICE_DENIED", reason: `credential missing: ${ref}` };
  }
  deps.onResolve && deps.onResolve({ packageId: deps.packageId, ref, envKey: ref, ok: true });
  return { ok: true, env: { [ref]: credential.value } };
}

/**
 * 批量解析：ACCESS_DENIED/QUOTA_STOP 整体拒绝；SERVICE_DENIED（缺失）跳过该项继续。
 */
export async function resolveAllForPackage(deps) {
  const env = {};
  for (const g of deps.grants.grants) {
    const r = await resolveForPackage(g.ref, deps);
    if (r.ok) {
      Object.assign(env, r.env);
    } else if (r.code === "ACCESS_DENIED" || r.code === "QUOTA_STOP") {
      return { ok: false, code: r.code, reason: r.reason };
    }
    // SERVICE_DENIED → 跳过（缺失凭据项不影响其余）
  }
  return { ok: true, env };
}

// ─── withCredentials 中间件（按包隔离注入 env 到 context）─────────
/**
 * 凭据守卫：为指令所属包解析全部凭据注入 context.env；
 * ACCESS_DENIED → 拒绝信封；QUOTA_STOP → stop 信封；SERVICE_DENIED → 拒绝信封。
 */
export function withCredentials(opts) {
  return (next) => async (domain, action, params, context) => {
    const packageId = opts.packageIdFor ? opts.packageIdFor(domain, action, params, context) : undefined;
    if (!packageId) return next(domain, action, params, context);
    const grants = opts.grants(packageId) || { packageId, grants: [] };
    const r = await resolveAllForPackage({
      packageId,
      grants,
      source: opts.source,
      onResolve: opts.onResolve,
      quotaCheck: opts.quotaCheck,
    });
    if (!r.ok) {
      if (r.code === "ACCESS_DENIED") return { rst_types: "text", rst_err: "ACCESS_DENIED", rst_data: { reason: r.reason } };
      if (r.code === "QUOTA_STOP") return { rst_types: "text", rst_err: "", rst_data: { status: "stop", reason: r.reason } };
      return { rst_types: "text", rst_err: "SERVICE_DENIED", rst_data: { reason: r.reason } };
    }
    const nextContext = { ...(context || {}), env: { ...(context && context.env), ...r.env } };
    return next(domain, action, params, nextContext);
  };
}
