// textcli-core-contract — 协议语义组件（Phase 1）
//
// 复用 textcli-core 的信封原语（ok/err/parse/health），并补上：
//   - 6 错误码闭集（SPEC §1.2.8）
//   - 信封不变量校验 validateEnvelope
//   - dsh→协议信号映射 mapSignal
//
// 与母本 runtime-contract 的契约一致：信封零重写、闭集兜底 ERR_EXECUTION。

import tc from "../textcli-core/index.js";

export const ok = tc.ok;
export const err = tc.err;
export const parse = tc.parse;
export const health = tc.health;

/** 协议闭集（SPEC §1.2.8） */
export const ERROR_CODES = [
  "ERR_NOT_FOUND",
  "ERR_EXECUTION",
  "ERR_ROUTING",
  "INVALID_PARAMS",
  "ACCESS_DENIED",
  "SERVICE_DENIED",
];

export function isClosedCode(code) {
  return ERROR_CODES.includes(code);
}

/**
 * 校验协议信封不变量（三字段 + rst_err 闭集）。
 * @returns {{valid:boolean, reason?:string}}
 */
export function validateEnvelope(env) {
  if (!env || typeof env !== "object") return { valid: false, reason: "not-object" };
  const keys = Object.keys(env).sort().join(",");
  if (keys !== "rst_data,rst_err,rst_types") {
    return { valid: false, reason: `fields=${keys}` };
  }
  if (typeof env.rst_err !== "string") return { valid: false, reason: "rst_err-not-string" };
  if (env.rst_err !== "" && !isClosedCode(env.rst_err)) {
    return { valid: false, reason: `code-not-closed:${env.rst_err}` };
  }
  return { valid: true };
}

// dsh→协议信号映射（母本 ERROR_MAP 的闭集投影；非错误信号回退 ERR_EXECUTION）
const ERROR_MAP = [
  ["UNKNOWN_TOOL", "ERR_NOT_FOUND"],
  ["INVALID_ARGS", "INVALID_PARAMS"],
  ["INVALID_TOOL_OUTPUT", "ERR_EXECUTION"],
  ["TOOL_TIMEOUT", "ERR_EXECUTION"],
  ["ABORTED", "ERR_EXECUTION"],
  ["ABORTED_BEFORE_DISPATCH", "ERR_EXECUTION"],
  ["SANDBOX_UNAVAILABLE", "ERR_EXECUTION"],
  "ACCESS_DENIED",
  "SERVICE_DENIED",
  "ERR_ROUTING",
  ["CYCLE_DETECTED", "ERR_EXECUTION"],
];

function _lookup(signal) {
  for (const row of ERROR_MAP) {
    const sig = Array.isArray(row) ? row[0] : row;
    const code = Array.isArray(row) ? row[1] : row;
    if (sig === signal) return code;
  }
  return null;
}

/**
 * 把 dsh 侧信号规范化为协议错误信封。
 * 未知/未列入 → ERR_EXECUTION（兜底）。
 */
export function mapSignal(signal) {
  const code = _lookup(signal);
  if (!code) return tc.err("ERR_EXECUTION", signal);
  return tc.err(code, signal);
}
