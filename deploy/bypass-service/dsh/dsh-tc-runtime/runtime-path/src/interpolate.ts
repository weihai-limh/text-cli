/**
 * interpolate.ts——变量插值（功能设计 §9.1 两层）
 *
 * - `{var}`：上下文变量 / 整步结果（按 name）
 * - `{stepId.field.path}`：从指定 step 结果取嵌套字段（INLINE_RE）
 * - 未定义 → 空串 + WARNING
 */
import type { PathResult } from "./types.js";

const TOKEN_RE = /\{([^}]+)\}/g;

/** 从对象按点路径取值 */
function dig(obj: unknown, path: string): unknown {
  let cur: unknown = obj;
  for (const seg of path.split(".")) {
    if (cur == null) return undefined;
    cur = (cur as Record<string, unknown>)[seg];
  }
  return cur;
}

export function interpolate(
  template: string,
  ctx: { vars: Record<string, unknown>; steps: Record<string, unknown> },
  warnings: string[],
): string {
  return template.replace(TOKEN_RE, (_m, inner: string) => {
    const token = String(inner).trim();
    if (!token) return "";

    if (token.includes(".")) {
      const [stepId, ...rest] = token.split(".");
      const stepVal = ctx.steps[stepId];
      if (stepVal === undefined) {
        warnings.push(`interpolate: undefined step "${stepId}"`);
        return "";
      }
      const val = dig(stepVal, rest.join("."));
      if (val === undefined) {
        warnings.push(`interpolate: undefined field "${token}"`);
        return "";
      }
      return String(val);
    }

    if (token in ctx.vars) {
      const v = ctx.vars[token];
      return v === undefined ? "" : String(v);
    }
    if (token in ctx.steps) {
      const v = ctx.steps[token];
      return v === undefined ? "" : String(v);
    }
    warnings.push(`interpolate: undefined variable "${token}"`);
    return "";
  });
}

/** 插值一个参数数组 */
export function interpolateParams(
  params: string[] | undefined,
  ctx: { vars: Record<string, unknown>; steps: Record<string, unknown> },
  warnings: string[],
): string[] {
  return (params ?? []).map((p) => interpolate(p, ctx, warnings));
}
