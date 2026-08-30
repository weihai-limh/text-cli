/**
 * conditions.ts——if 四形式（功能设计 §9.1）
 *
 * string / equals / contains / matches / exists / all / any
 * 比较前对 left/right/expr 做变量插值。
 */
import { interpolate } from "./interpolate.js";
import type { Condition } from "./types.js";

interface Ctx {
  vars: Record<string, unknown>;
  steps: Record<string, unknown>;
  warnings: string[];
}

function truthy(v: unknown): boolean {
  if (v == null) return false;
  if (typeof v === "boolean") return v;
  if (typeof v === "number") return v !== 0;
  if (typeof v === "string") return v.length > 0 && v !== "false" && v !== "0";
  return true;
}

function isEmpty(v: unknown): boolean {
  if (v == null) return true;
  if (typeof v === "string") return v.length === 0;
  if (Array.isArray(v)) return v.length === 0;
  if (typeof v === "object") return Object.keys(v as object).length === 0;
  return false;
}

export function evalCondition(cond: Condition, ctx: Ctx): boolean {
  switch (cond.kind) {
    case "string":
      return truthy(interpolate(cond.expr, ctx, ctx.warnings));
    case "exists": {
      const v = interpolate(cond.expr, ctx, ctx.warnings);
      // exists：插值后非空且非 "undefined"
      return v !== "" && v !== "undefined";
    }
    case "equals":
      return (
        interpolate(cond.left, ctx, ctx.warnings) ===
        interpolate(cond.right, ctx, ctx.warnings)
      );
    case "contains":
      return interpolate(cond.left, ctx, ctx.warnings).includes(
        interpolate(cond.right, ctx, ctx.warnings),
      );
    case "matches": {
      const subject = interpolate(cond.left, ctx, ctx.warnings);
      const re = interpolate(cond.right, ctx, ctx.warnings);
      try {
        return new RegExp(re).test(subject);
      } catch {
        ctx.warnings.push(`condition matches: bad regex "${re}"`);
        return false;
      }
    }
    case "all":
      return cond.conds.every((c) => evalCondition(c, ctx));
    case "any":
      return cond.conds.some((c) => evalCondition(c, ctx));
  }
}
