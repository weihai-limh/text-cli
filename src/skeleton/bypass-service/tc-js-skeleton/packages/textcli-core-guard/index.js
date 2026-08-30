// textcli-core-guard — 核心守卫组件（Phase 1，路径 A 纯搬运自 runtime-sandbox/ancestor-chain）
//
// 环检测共享基座：三种键
//   path:<id>   —— path 声明层自身重入
//   agg:<name>  —— aggregate 聚合自身重入
//   native:<domain>;<action> —— handler 经注入 dispatch 重入同一指令
//
// 与母本逐字一致：AsyncLocalStorage + MAX_CHAIN=32，零 dsh 依赖。
// 关键：path/aggregate 必须注入同一个 ancestorChain 实例，否则跨类型互环（agg→path→agg）漏检。

import { AsyncLocalStorage } from "node:async_hooks";

/** ancestor-chain 链长上限（防御性 + 协议一致性） */
export const MAX_CHAIN = 32;

/** 祖先链键类型 */
export const AncestorKey = {
  path: (id) => `path:${id}`,
  agg: (name) => `agg:${name}`,
  native: (domain, action) => `native:${domain};${action}`,
};

const storage = new AsyncLocalStorage();

export const ancestorChain = {
  /** 顶层入口：入站 / 任务恢复 */
  run(keys, fn) {
    return storage.run(keys, fn);
  },
  /** 是否已有 ALS 上下文（供运行时判断"顶层 vs 重入"） */
  hasContext() {
    return storage.getStore() !== undefined;
  },
  /** 无上下文 → 空数组 */
  current() {
    return storage.getStore() ?? [];
  },
  contains(key) {
    return (storage.getStore() ?? []).includes(key);
  },
  /** 返回 false = 拒绝（环 / 链满） */
  push(key) {
    const chain = storage.getStore();
    if (!chain) return true;
    if (chain.length >= MAX_CHAIN) return false;
    if (chain.includes(key)) return false;
    chain.push(key);
    return true;
  },
  /** LIFO 匹配 */
  pop(key) {
    const chain = storage.getStore();
    if (!chain) return;
    const i = chain.lastIndexOf(key);
    if (i >= 0) chain.splice(i, 1);
  },
  /** 断点A：任务启动捕获 */
  snapshot() {
    return [...(storage.getStore() ?? [])];
  },
  /** 断点A：enterWith 重建 */
  restore(keys) {
    storage.enterWith(keys);
  },
};

export class CycleDetectedError extends Error {
  constructor(key) {
    super(`cycle detected: ${key}`);
    this.name = "CycleDetectedError";
    this.key = key;
  }
}

export const cycleKey = {
  path: (id) => `path:${id}`,
  agg: (name) => `agg:${name}`,
  native: (domain, action) => `native:${domain};${action}`,
};

/**
 * 包裹任意异步函数做环检测（最内守卫）。
 * 调用前 push 键，失败抛 CycleDetectedError，finally 中 pop。
 */
export function guardDispatch(fn, keyFor) {
  return async (...args) => {
    const key = keyFor(...args);
    if (!ancestorChain.push(key)) throw new CycleDetectedError(key);
    try {
      return await fn(...args);
    } finally {
      ancestorChain.pop(key);
    }
  };
}

/**
 * 最内守卫中间件：拦 handler 经注入 dispatch 重入同一指令（native:<d>;<a> 键）。
 * 环命中 → 返回 ERR_EXECUTION + CYCLE_DETECTED 信封（不触发审批）。
 */
export function withNativeGuard(opts = {}) {
  const ancestor = opts.ancestorChain || ancestorChain;
  return (next) => async (domain, action, params, context) => {
    const key = cycleKey.native(domain, action);
    if (ancestor.contains(key)) {
      return { rst_types: "text", rst_err: "ERR_EXECUTION", rst_data: { reason: "CYCLE_DETECTED" } };
    }
    ancestor.push(key);
    try {
      return await next(domain, action, params, context);
    } finally {
      ancestor.pop(key);
    }
  };
}
