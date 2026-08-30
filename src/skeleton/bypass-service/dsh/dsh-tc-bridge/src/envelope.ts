// 信封层：把 tc 闭集信封 / dsh tool 原生结果，统一转换成 dsh 侧看到的 ToolResult。
// 对齐 textcli-core/envelope.js + index.js execute()（§8.2 事实 2/3/8）。
import type { Envelope } from 'textcli-core';
import { TC_ERROR_CODES, type TcErrorCode, type ToolResult } from './types.js';

/**
 * 在 rst_err==='' 时仍视为失败的业务 status 信号（§3 信封歧义：tc 降级响应）。
 * 有些 handler 在信封层 rst_err===''，但 rst_data.status 揭示"未找到/失败"。
 */
const NON_OK_STATUS = new Set(['not_found', 'error']);

/**
 * 吸收 tc 闭集信封 → dsh ToolResult。
 *
 * - ok = (rst_err === '')，types 透传 rst_types。
 * - 歧义：rst_err==='' 但 rst_data.status ∈ {not_found, error} → 视为失败
 *   （§3：ok = (rst_err === '' && status !== 'not_found-like')）。
 * - err 未填时取业务 status；仍无则 ERR_EXECUTION。
 */
export function tcToDsh(env: Envelope): ToolResult {
  const err = env.rst_err || '';
  const data = env.rst_data;

  // 取 rst_data.status（仅当 rst_data 是非数组对象时）
  let status: unknown;
  if (data && typeof data === 'object' && !Array.isArray(data) && 'status' in data) {
    status = (data as Record<string, unknown>).status;
  }

  let ok = err === '';
  if (ok && typeof status === 'string' && NON_OK_STATUS.has(status)) {
    ok = false;
  }

  return {
    ok,
    data,
    types: env.rst_types,
    err: ok ? undefined : err || (typeof status === 'string' ? status : 'ERR_EXECUTION'),
  };
}

/**
 * 吸收 dsh tool 原生结果 → 统一 ToolResult（tool_avatar 分支）。
 * - 若结果已是 ToolResult 形状（含 ok 字段）→ 原样归一。
 * - 否则视为成功，data 直接承载。
 */
export function toolToDsh(result: unknown): ToolResult {
  if (result && typeof result === 'object' && 'ok' in (result as object)) {
    const r = result as ToolResult;
    return { ok: r.ok, data: r.data, err: r.err, types: r.types };
  }
  return { ok: true, data: result };
}

/**
 * 校验错误码落在协议闭集，否则 fallback ERR_EXECUTION（红线②）。
 */
export function normalizeErrCode(code: string): TcErrorCode {
  return (TC_ERROR_CODES as readonly string[]).includes(code) ? (code as TcErrorCode) : 'ERR_EXECUTION';
}

/**
 * DirectiveResult（tc_client 远程通路产物）→ ToolResult（dsh 侧统一形状）。
 * ok = r.ok；err 未填时回退 ERR_EXECUTION。
 */
export function directiveResultToToolResult(r: {
  ok: boolean;
  data: unknown;
  rtype: string;
  err_code: string;
  is_async: boolean;
  task_id?: string;
}): ToolResult & { is_async: boolean; task_id?: string } {
  return {
    ok: r.ok,
    data: r.data,
    types: r.rtype,
    err: r.ok ? undefined : r.err_code || 'ERR_EXECUTION',
    is_async: r.is_async,
    task_id: r.task_id,
  };
}
