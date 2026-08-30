/**
 * ancestor-chain——祖先环检测（功能设计 §4.4，对齐 tc `_ANCESTOR_CHAIN`）
 *
 * AsyncLocalStorage 实现：沿 promise 链自动传播（parallel 分支天然继承，无需手动 copy）。
 * 三种键（按调用方类型）：`path:<id>` / `agg:<name>` / `native:<domain>;<action>`。
 *
 * 三断点（功能设计 §4.4.3）：
 * - 断点 A（jobs 恢复）：snapshot()/restore()——任务启动时捕获，恢复时 enterWith 重建
 * - 断点 B（沙箱子进程）：沙箱内无环可检（边界声明——包只能经注入通道回宿主请求，
 *   检测统一在宿主侧 dispatchFn 单守卫）
 * - 断点 C（宿主指令互调）：宿主指令执行也进链（native:<d>;<a>）
 */
import { AsyncLocalStorage } from "node:async_hooks";

export type AncestorKey = `path:${string}` | `agg:${string}` | `native:${string}`;

/** 链长上限（防御病态链式输入；tc 仅靠 key 重复检测，dsh 补防御性上限，§4.4.5.2） */
export const MAX_CHAIN = 32;

const storage = new AsyncLocalStorage<AncestorKey[]>();

export const ancestorChain = {
  /** 在指定链上下文内执行（顶层入口：入站请求/任务恢复） */
  run<T>(keys: AncestorKey[], fn: () => T): T {
    return storage.run(keys, fn);
  },

  /** 当前链（无上下文 → 空数组） */
  current(): AncestorKey[] {
    return storage.getStore() ?? [];
  },

  /** 键是否已在链上 */
  contains(key: AncestorKey): boolean {
    return (storage.getStore() ?? []).includes(key);
  },

  /**
   * 入链。返回 false = 拒绝（环命中或链满）。
   * 无链上下文（不在 run 内）→ 不检测（顶层透传，由调用方保证 run 包裹）。
   */
  push(key: AncestorKey): boolean {
    const chain = storage.getStore();
    if (!chain) return true;
    if (chain.length >= MAX_CHAIN) return false;
    if (chain.includes(key)) return false;
    chain.push(key);
    return true;
  },

  /** 出链（LIFO 匹配） */
  pop(key: AncestorKey): void {
    const chain = storage.getStore();
    if (!chain) return;
    const i = chain.lastIndexOf(key);
    if (i >= 0) chain.splice(i, 1);
  },

  /** 链快照（断点 A：任务启动时捕获） */
  snapshot(): AncestorKey[] {
    return [...(storage.getStore() ?? [])];
  },

  /** 恢复链上下文（断点 A：任务恢复时 enterWith 重建） */
  restore(keys: AncestorKey[]): void {
    storage.enterWith(keys);
  },
};
