/**
 * pro.ts——门面 pro（功能设计 §7 / §4.4.2 R16：环检测"只查不推"）
 *
 * pro 是短名 → path/aggregate 目标的别名解析器（门面），**非执行栈成员**。
 * 若把 pro 自身推入祖先链，会被多 path 复用而假报环——因此采用"只查不推"：
 *   进入时**查**目标 key 是否已在链上（防 pro→pro 互环），但**不占位**（不 push pro 键）。
 * 实际执行 push 的是被解析出的目标（path:<id> / agg:<name>），由对应守卫负责。
 */
import type { AncestorKey } from "@dsh-tc/runtime-sandbox";

export type ProTarget =
  | { kind: "path"; pathId: string }
  | { kind: "aggregate"; aggName: string };

export class ProNotFound extends Error {
  constructor(name: string) {
    super(`PRO_NOT_FOUND: ${name}`);
    this.name = "ProNotFound";
  }
}

export class ProRegistry {
  private readonly map = new Map<string, ProTarget>();

  /** 注册门面：短名 → 目标（path/aggregate） */
  register(name: string, target: ProTarget): void {
    this.map.set(name, target);
  }

  /** 解析（未注册 → ProNotFound） */
  resolve(name: string): ProTarget {
    const t = this.map.get(name);
    if (!t) throw new ProNotFound(name);
    return t;
  }

  /** 列出全部门面（供 query 平权暴露） */
  list(): { name: string; target: ProTarget }[] {
    return [...this.map.entries()].map(([name, target]) => ({ name, target }));
  }

  has(name: string): boolean {
    return this.map.has(name);
  }
}

/**
 * "只查不推"：pro 解析出的祖先键。
 * 返回目标的 key（path:<id> / agg:<name>）——用于 dispatch 守卫的 contains 检查，
 * 但调用方**不得** push `pro:<name>` 自身键。
 */
export function proAncestorKey(name: string, reg: ProRegistry): AncestorKey {
  const t = reg.resolve(name);
  return t.kind === "path" ? (`path:${t.pathId}` as const) : (`agg:${t.aggName}` as const);
}

/**
 * 平权 directive：text-cli;pro,<name> 与原子指令同形（经保留域拦截处理，不污染 ctx.tools）。
 */
export function proDirective(name: string): { domain: "text-cli"; action: string } {
  return { domain: "text-cli", action: `pro,${name}` };
}
