// runtime — Cloudflare 专供版运行时拼装
//
// 复用 tc-js-skeleton 逻辑组件（纯逻辑 + deps 注入，零平台依赖）：
//   compose/isEnvelope（装配/信封穿透）、guard（共享 ancestorChain）、path（编排）、
//   auth（Service-token）、audit（trace）、mesh 思路 + 本地 mesh 路由适配。
// 新写平台面：D1 storage 适配、受限执行、D1 可执行包生命周期、Worker 端点表面。
//
// 中间件顺序（洋葱外→内）：
//   withAuth(required) → withCfMesh → withPath → withUsage → withAudit → withNativeGuard → core

import { createStorage } from "../../tc-js-skeleton/packages/textcli-core-storage/index.js";
import { createD1Storage } from "./d1-storage.js";
import { compose, isEnvelope } from "../../tc-js-skeleton/packages/textcli-core-compose/index.js";
import { ancestorChain, withNativeGuard } from "../../tc-js-skeleton/packages/textcli-core-guard/index.js";
import { withPath, PathRegistry } from "../../tc-js-skeleton/packages/textcli-core-path/index.js";
import { withAudit } from "../../tc-js-skeleton/packages/textcli-core-audit/index.js";
import { createAuth, withAuth } from "../../tc-js-skeleton/packages/textcli-core-auth/index.js";
import { register, unregister, getRegistered, dispatch } from "../../tc-js-skeleton/packages/textcli-core/registry.js";
import tc from "../../tc-js-skeleton/packages/textcli-core/index.js";

import { installPackage, uninstallPackage, listPackages, buildDirectives } from "./meta.js";
import { createTokenManager, issueToken, revokeToken, listTokens } from "./token.js";
import { registerKey, revokeKey, listKeys, getKeyValue } from "./key.js";
import { registerUsage, withUsage } from "./usage.js";
import { startTask, pollTask, cancelTask, reconcileAfterRestart, runNext } from "./tasks.js";
import { registerPeer, addRoute, listPeers, createMeshRemote, createLocalHas } from "./mesh.js";
import { runHandler } from "./executor.js";
import { createEndpoints } from "./endpoints.js";

const VERSION = "0.1.1";
const SPEC_VERSION = "1.3.2";
const MECHANISMS = ["directive_execution", "package_lifecycle", "discovery", "path", "async", "mesh"];

// tokenFor 契约：withAuth 以 (domain, action, params, context) 四参调用 —— 取第 4 参
function getTokenFromContext(domain, action, params, context) {
  if (!context) return undefined;
  if (context.token) return context.token;
  const h = context.headers;
  if (!h) return undefined;
  const get = (k) => (typeof h.get === "function" ? h.get(k) : h[k]);
  const st = get("service-token") || get("Service-Token");
  if (st) return st;
  const authz = get("authorization") || get("Authorization");
  if (authz && authz.startsWith("Bearer ")) return authz.slice(7);
  return undefined;
}

export function createWorkerRuntime(env, deps = {}) {
  const db = env.DB;
  const secret = env.AUTH_SECRET || "dev-secret";
  const keySecret = env.KEY_ENC_SECRET || "dev-key-secret";
  const sourceDir = env.PACKAGE_SOURCE_DIR || deps.packageSourceDir;

  // ── 持久化地基（D1 → StorageKV）──
  const store = createStorage(createD1Storage(db));

  // ── 鉴权：Service-token（单 token 闭环，可吊销）──
  const tm = createTokenManager({ db, tokenStore: store.namespace("tokens"), secret });
  const auth = tm.auth;

  // ── 受限执行 deps（fetch / 凭据解析，凭据白名单在 executor 侧）──
  const executorDeps = {
    fetch: deps.fetch,
    getKey: async (service) => getKeyValue(db, keySecret, service),
  };

  // ── 审计 writer（D1 kv audit 分区）──
  const auditWriter = {
    async write(e) {
      await store.namespace("audit").set(`e:${Date.now()}:${Math.random().toString(36).slice(2, 8)}`, JSON.stringify(e));
    },
    logPath() {
      return "(d1)";
    },
    maintain() {},
  };

  // ── 指令注册：生命周期 / token / key / usage / tasks / mesh ──
  register("text-cli", "install", async (params) => {
    const r = await installPackage({ packageId: params[0], sourceDir, db, register, executorDeps });
    return r.ok ? tc.ok({ status: "ok", installed: r.installed, directives: r.directives }) : tc.err("ERR_EXECUTION", r.error);
  });
  register("text-cli", "uninstall", async (params) => {
    const r = await uninstallPackage({ packageId: params[0], db, unregister });
    return r.ok ? tc.ok({ status: "ok", uninstalled: r.uninstalled }) : tc.err("ERR_EXECUTION", r.error);
  });
  register("text-cli", "packages", async () => tc.ok({ status: "ok", packages: await listPackages(db) }));
  register("text-cli", "query", async (params) => {
    const mode = params[0] || "text";
    const directives = [...(await buildDirectives(db)), ...paths.schemaEntries()];
    return tc.ok({ status: "ok", directives, mode });
  });

  register("token", "issue", async (params) => {
    const r = await issueToken(tm, db, params);
    return r.ok ? tc.ok({ status: "ok", token: r.token, requester_id: r.requester_id, tier: r.tier }) : tc.err("INVALID_PARAMS", r.error);
  });
  register("token", "revoke", async (params) => {
    const r = await revokeToken(tm, db, params);
    return r.ok ? tc.ok({ status: "ok", revoked: r.revoked }) : tc.err("INVALID_PARAMS", r.error);
  });
  register("token", "list", async () => tc.ok(await listTokens(db)));

  register("key", "register", async (params) => {
    const r = await registerKey(db, keySecret, params);
    return r.ok ? tc.ok({ status: "ok", service: r.service, key_type: r.key_type }) : tc.err("INVALID_PARAMS", r.error);
  });
  register("key", "revoke", async (params) => {
    const r = await revokeKey(db, params);
    return r.ok ? tc.ok({ status: "ok", service: r.service }) : tc.err("INVALID_PARAMS", r.error);
  });
  register("key", "list", async () => tc.ok(await listKeys(db)));

  register("quota", "register", async (params) => {
    const r = await registerUsage(db, params);
    return r.ok ? tc.ok({ status: "ok", target: r.target, limit: r.limit, cycle: r.cycle }) : tc.err("INVALID_PARAMS", r.error);
  });

  register("text-cli", "poll", async (params) => {
    const t = await pollTask(db, params[0]);
    return t.state === "not_found" ? tc.err("ERR_NOT_FOUND", `task not found: ${params[0]}`) : tc.ok({ status: "ok", task: t });
  });
  register("task", "cancel", async (params) => {
    const ok = await cancelTask(db, params[0]);
    return ok ? tc.ok({ status: "ok", cancelled: params[0] }) : tc.err("ERR_NOT_FOUND", `task not found or not cancellable: ${params[0]}`);
  });

  register("mesh", "peer-register", async (params) => {
    const r = await registerPeer(db, keySecret, params);
    return r.ok ? tc.ok({ status: "ok", peer_id: r.peer_id, endpoint: r.endpoint }) : tc.err("INVALID_PARAMS", r.error);
  });
  register("mesh", "route-add", async (params) => {
    const r = await addRoute(db, params);
    return r.ok ? tc.ok({ status: "ok", route: r.route }) : tc.err("INVALID_PARAMS", r.error);
  });
  register("mesh", "peer-list", async () => tc.ok(await listPeers(db)));

  // ── path 编排注册表 ──
  const paths = new PathRegistry();
  register("text-cli", "path", async () => undefined); // 占位：由 withPath 拦截，此处仅让保留域 localHas 命中

  // ── mesh：本地不命中 → D1 mesh_routes → peer 转发（凭证按 peer 隔离）──
  const remote = createMeshRemote({ db, secret: keySecret, fetchImpl: deps.fetch });
  const withCfMesh = (next) => async (domain, action, params, context) => {
    if (createLocalHas(getRegistered)(domain, action)) return next(domain, action, params, context);
    const row = await db.prepare("SELECT peer_id FROM mesh_routes WHERE domain = ? AND action = ?").bind(domain, action).first();
    if (!row) return next(domain, action, params, context); // 无路由 → 本地（NOT_FOUND 由 core 给出）
    return remote({ id: row.peer_id }, domain, action, params);
  };

  // ── 核心 dispatch（核心薄层单例；Worker 版无文件懒加载，包安装即注册）──
  const coreDispatch = (domain, action, params, context) => dispatch(domain, action, params, context);

  const chain = compose(
    withAuth(auth, { mode: "required", tokenFor: getTokenFromContext }),
    withCfMesh,
    withPath(paths, { ancestorChain }),
    withUsage({ db }),
    withAudit(auditWriter),
    withNativeGuard({ ancestorChain }),
  )(coreDispatch);

  async function run(prompt, context) {
    const parsed = tc.parse(prompt);
    if (parsed.error) return tc.err(parsed.error, parsed.reason);
    const exec = async () => {
      try {
        const result = await chain(parsed.domain, parsed.action, parsed.params, context);
        if (isEnvelope(result)) return result;
        if (result === null || result === undefined) {
          return tc.err("ERR_NOT_FOUND", `no matching directive: ${parsed.domain};${parsed.action}`);
        }
        return tc.ok(result);
      } catch (e) {
        if (e && e.name === "CycleDetectedError") return tc.err("ERR_EXECUTION", "CYCLE_DETECTED");
        return tc.err("ERR_EXECUTION", e && e.message ? e.message : String(e));
      }
    };
    return ancestorChain.hasContext() ? exec() : ancestorChain.run([], exec);
  }

  const rt = {
    run,
    chain,
    auth,
    db,
    store,
    paths,
    register,
    getRegistered,
    install: (id) => installPackage({ packageId: id, sourceDir, db, register, executorDeps }),
    uninstall: (id) => uninstallPackage({ packageId: id, db, unregister }),
    startTask: (d, a, p) => startTask(db, d, a, p),
    runNextTask: () => runNext(db, { runHandler, register }),
    pollTask: (id) => pollTask(db, id),
    cancelTask: (id) => cancelTask(db, id),
    reconcileTasks: () => reconcileAfterRestart(db),
    buildDirectives: async () => [...(await buildDirectives(db)), ...paths.schemaEntries()],
    runHandler,
    executorDeps,
    VERSION,
    SPEC_VERSION,
    MECHANISMS,
  };
  rt.handle = createEndpoints(rt);
  return rt;
}
