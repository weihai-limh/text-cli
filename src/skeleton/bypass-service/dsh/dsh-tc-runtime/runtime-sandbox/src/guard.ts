/**
 * guard.ts——dispatchFn 单守卫（功能设计 §4.4.3 检测点收敛）
 *
 * 所有经 `ctx.tools.execute` 的执行（path step / 聚合 provider / native 执行 / 宿主指令）
 * 统一经 guardDispatch 进链：push 对应键 → execute → finally pop。
 * 环命中 = 结构性拒绝（CycleDetectedError → ERR_EXECUTION + reason=CYCLE_DETECTED，
 * 不触发审批，§4.4.5.3）。
 */
import { ancestorChain, type AncestorKey } from "./ancestor-chain.js";

/** 环命中错误（结构性拒绝，非审批拒绝） */
export class CycleDetectedError extends Error {
  readonly key: AncestorKey;
  constructor(key: AncestorKey) {
    super(`cycle detected: ${key}`);
    this.name = "CycleDetectedError";
    this.key = key;
  }
}

/** 键构造辅助（按调用方类型） */
export const cycleKey = {
  path: (id: string): AncestorKey => `path:${id}`,
  agg: (name: string): AncestorKey => `agg:${name}`,
  native: (domain: string, action: string): AncestorKey => `native:${domain};${action}`,
};

/**
 * 包装 dispatch 函数：进入 push 调用方键 → 执行 → finally pop。
 * 环命中 → throw CycleDetectedError（上层映射 ERR_EXECUTION + CYCLE_DETECTED）。
 */
export function guardDispatch<A extends unknown[], R>(
  fn: (...args: A) => Promise<R>,
  keyFor: (...args: A) => AncestorKey,
): (...args: A) => Promise<R> {
  return async (...args: A): Promise<R> => {
    const key = keyFor(...args);
    if (!ancestorChain.push(key)) {
      throw new CycleDetectedError(key);
    }
    try {
      return await fn(...args);
    } finally {
      ancestorChain.pop(key);
    }
  };
}
