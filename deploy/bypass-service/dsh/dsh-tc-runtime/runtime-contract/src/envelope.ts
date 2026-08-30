/**
 * envelope.ts——规范信封（复用 textcli-core，零改动）+ 契约不变量校验（§12.3）
 */
import tc from "textcli-core";
import { ERROR_CODES, isClosedCode } from "./error-codes.js";

/** 成功信封：pray_rst_types 提升 + 6 码闭集（直接复用 textcli-core） */
export const ok = tc.ok;
/** 错误信封：闭集校验 + 未知码回退 ERR_EXECUTION */
export const err = tc.err;

export interface EnvelopeShape {
  rst_types: string;
  rst_data: unknown;
  rst_err: string;
}

/**
 * 信封不变量校验：
 * - 恰三字段（rst_types / rst_data / rst_err）
 * - rst_err ∈ 闭集 或 空串（成功）
 */
export function validateEnvelope(env: unknown): { valid: boolean; reason?: string } {
  if (!env || typeof env !== "object") return { valid: false, reason: "not-object" };
  const keys = Object.keys(env as Record<string, unknown>).sort();
  if (keys.join(",") !== "rst_data,rst_err,rst_types") {
    return { valid: false, reason: `fields=${keys.join(",")}` };
  }
  const e = env as EnvelopeShape;
  if (typeof e.rst_err !== "string") return { valid: false, reason: "rst_err-not-string" };
  if (e.rst_err !== "" && !isClosedCode(e.rst_err)) {
    return { valid: false, reason: `code-not-closed:${e.rst_err}` };
  }
  return { valid: true };
}

/** 闭集码列表（导出供契约测试断言） */
export const CLOSED_CODES = ERROR_CODES;
