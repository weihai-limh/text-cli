// textcli-core-compose — 旁路运行时骨架/门面（Phase 0）
//
// 设计稿核心：compose 不是纯装配器，而是"旁路运行时的定义性骨架"。它内建三件事：
//   能力A 装配：把各能力组件按序包成 dispatch（reduceRight）
//   能力B 包生命周期：text-cli;install / text-cli;uninstall（对称），落本地受控目录 root，JSON 索引记录位置
//   能力C 多包指令消费：dispatch 时 domain;action → 包 反查，懒加载命中热装指令
//
// 对外统一中间件形状：(next) => (domain, action, params, context) => Promise<unknown>
// run(prompt) 负责解析 + 走链路 + 信封化（对齐 textcli-core.execute，但走可插拔链路）。

import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";

import { register, dispatch, unregister } from "../textcli-core/registry.js";
import tc from "../textcli-core/index.js";
import { ancestorChain } from "../textcli-core-guard/index.js";

const require = createRequire(import.meta.url);
const { loadPackageFromPath } = require("../textcli-core/loader.node.js");

// ─── 统一中间件组装 ─────────────────────────────────────────────
// compose(...layers)(core) = layers.reduceRight((acc, l) => l(acc), core)
export function compose(...layers) {
  return (core) => layers.reduceRight((acc, layer) => layer(acc), core);
}

// 信封穿透检测：中间件短路返回的错误信封不应被 run 二次包裹
export function isEnvelope(v) {
  return (
    v &&
    typeof v === "object" &&
    !Array.isArray(v) &&
    "rst_err" in v &&
    "rst_data" in v &&
    "rst_types" in v
  );
}

/**
 * 创建一个旁路运行时。
 * @param {object} [options]
 * @param {string} [options.root]        安装落点（默认 ./tc-packages）
 * @param {string} [options.sourceDir]   包源仓库（默认 ./examples/packages），install 从此拷贝
 * @param {Array}  [options.middleware]   外挂能力中间件（guard/path/aggregate/quota/audit/mesh...）
 * @param {Function} [options.deleter]   卸载时的物理删除器（默认 fs.rmSync；宿主可注入 sandbox-safe 删除）
 */
export function createRuntime(options = {}) {
  const root = options.root || path.resolve("./.tc-packages");
  const sourceDir = options.sourceDir || path.resolve("./examples/packages");
  const middleware = options.middleware || [];
  const deleter = options.deleter || fs.rmSync;
  const indexFile = path.join(root, ".index.json");

  // ── JSON 索引（包管理定义性能力的内核）──
  function loadIndex() {
    try {
      return JSON.parse(fs.readFileSync(indexFile, "utf-8"));
    } catch {
      return { packages: {}, byDirective: {} };
    }
  }
  function saveIndex(idx) {
    fs.mkdirSync(root, { recursive: true });
    fs.writeFileSync(indexFile, JSON.stringify(idx, null, 2));
  }

  // ── 包生命周期：install / uninstall（能力B）──
  function install(packageId) {
    if (!packageId) return { ok: false, error: "package id required" };
    const src = path.join(sourceDir, packageId);
    const dest = path.join(root, packageId);
    if (!fs.existsSync(path.join(src, "schema.json"))) {
      return { ok: false, error: `package not found in source: ${packageId}` };
    }
    fs.cpSync(src, dest, { recursive: true });

    // 注册指令到核心 registry（物理加载 handler）
    loadPackageFromPath(dest);

    const schema = JSON.parse(fs.readFileSync(path.join(dest, "schema.json"), "utf-8"));
    const directives = (schema.directives || []).map((d) => ({
      domain: d.domain,
      action: d.action,
    }));

    const idx = loadIndex();
    idx.packages[packageId] = {
      location: dest,
      directives,
      installedAt: new Date().toISOString(),
    };
    for (const d of directives) {
      idx.byDirective[`${d.domain};${d.action}`] = packageId;
    }
    saveIndex(idx);
    return { ok: true, installed: packageId, directives };
  }

  function uninstall(packageId) {
    const dest = path.join(root, packageId);
    const idx = loadIndex();
    const entry = idx.packages[packageId];
    if (!entry) return { ok: false, error: `package not installed: ${packageId}` };

    // 反注册指令
    for (const d of entry.directives) {
      unregister(d.domain, d.action);
      delete idx.byDirective[`${d.domain};${d.action}`];
    }
    // 删除物理目录（完整回收文件；删除器可注入，默认 fs.rmSync）
    deleter(dest, { recursive: true, force: true });
    delete idx.packages[packageId];
    saveIndex(idx);
    return { ok: true, uninstalled: packageId };
  }

  function listPackages() {
    return loadIndex().packages;
  }

  // ── 多包指令消费：懒加载反查（能力C）──
  // 若 dispatch 未命中，但 JSON 索引记录该 domain;action 由某包提供，则热装后重试。
  function withLazyConsumption(next) {
    return async (domain, action, params, context) => {
      let result = await next(domain, action, params, context);
      if (result === null || result === undefined) {
        const idx = loadIndex();
        const pid = idx.byDirective[`${domain};${action}`];
        if (pid) {
          const dest = path.join(root, pid);
          if (fs.existsSync(dest)) {
            loadPackageFromPath(dest);
            result = await next(domain, action, params, context);
          }
        }
      }
      return result;
    };
  }

  // ── 核心 dispatch（核心薄层单例）──
  const coreDispatch = (domain, action, params, context) =>
    dispatch(domain, action, params, context);

  // 链路 = 外挂中间件(最外) ∘ 多包消费(最内) ∘ 核心dispatch
  const chain = compose(...middleware)(withLazyConsumption(coreDispatch));

  // ── 内建元指令（compose 定义性能力，注册到核心 registry）──
  register("text-cli", "install", async (params) => {
    const r = install(params[0]);
    return r.ok ? tc.ok({ status: "ok", installed: r.installed, directives: r.directives }) : tc.err("ERR_EXECUTION", r.error);
  });
  register("text-cli", "uninstall", async (params) => {
    const r = uninstall(params[0]);
    return r.ok ? tc.ok({ status: "ok", uninstalled: r.uninstalled }) : tc.err("ERR_EXECUTION", r.error);
  });
  register("text-cli", "packages", async () => {
    return tc.ok({ status: "ok", packages: listPackages() });
  });

  /**
   * 解析 + 走链路 + 信封化（对齐 textcli-core.execute）。
   * 只在无 ALS 上下文时建立（顶层入口）；重入（handler 经注入 dispatch 再调 run）
   * 复用当前上下文，否则环检测链会被重置而漏检。
   * @param {string} prompt e.g. "AI:weather;query,北京"
   * @param {object} [context] 透传上下文
   */
  async function run(prompt, context) {
    const parsed = tc.parse(prompt);
    if (parsed.error) return tc.err(parsed.error, parsed.reason);
    const exec = async () => {
      try {
        const result = await chain(parsed.domain, parsed.action, parsed.params, context);
        if (isEnvelope(result)) return result; // 中间件短路信封，原样透传
        if (result === null || result === undefined) {
          return tc.err("ERR_NOT_FOUND", `no matching directive: ${parsed.domain};${parsed.action}`);
        }
        return tc.ok(result);
      } catch (e) {
        if (e && e.name === "CycleDetectedError") {
          return tc.err("ERR_EXECUTION", "CYCLE_DETECTED");
        }
        return tc.err("ERR_EXECUTION", e && e.message ? e.message : String(e));
      }
    };
    return ancestorChain.hasContext() ? exec() : ancestorChain.run([], exec);
  }

  return {
    install,
    uninstall,
    listPackages,
    run,
    /** 裸链路 dispatch（供组件内部注入为 deps.dispatch） */
    dispatch: chain,
    coreDispatch,
    register,
    health: tc.health,
    discover: tc.discover,
    root,
    sourceDir,
  };
}
