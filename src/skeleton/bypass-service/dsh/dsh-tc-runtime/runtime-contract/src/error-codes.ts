/**
 * error-codes.ts——协议错误码闭集 + dsh→协议 全映射表（功能设计 §3.2）
 *
 * 映射表本身即契约测试用例（§12.3）：每条 dsh 侧信号必须落到 6 码闭集内，
 * 或显式标注为非错误（quota stop / DEGRADE_EXHAUSTED 走 rst_data.status）。
 */
import tc from "textcli-core";

/** 协议错误码闭集（SPEC §1.2.8） */
export const ERROR_CODES = [
  "ERR_NOT_FOUND",
  "ERR_EXECUTION",
  "ERR_ROUTING",
  "INVALID_PARAMS",
  "ACCESS_DENIED",
  "SERVICE_DENIED",
] as const;

export type ProtocolErrorCode = (typeof ERROR_CODES)[number];

export interface ErrorMapRow {
  /** dsh 侧信号（可为复合，"/" 分隔） */
  signal: string;
  /** 落地的协议码；null = 非错误（走 rst_data.status 降级信号） */
  code: ProtocolErrorCode | null;
  /** 显式 reason 覆盖（如 SANDBOX_UNAVAILABLE / CYCLE_DETECTED） */
  reason?: string;
  /** 说明 */
  note: string;
}

/** 错误码全映射表（dsh 侧信号 → 协议 6 码闭集） */
export const ERROR_MAP: ErrorMapRow[] = [
  { signal: "UNKNOWN_TOOL", code: "ERR_NOT_FOUND", note: "工具未注册" },
  { signal: "INVALID_ARGS", code: "INVALID_PARAMS", note: "参数非法" },
  { signal: "INVALID_TOOL_OUTPUT", code: "ERR_EXECUTION", note: "工具输出不合法 = 执行失败" },
  { signal: "TOOL_TIMEOUT/ABORTED/ABORTED_BEFORE_DISPATCH", code: "ERR_EXECUTION", note: "超时/中止归执行失败" },
  { signal: "SandboxUnavailableError", code: "ERR_EXECUTION", reason: "SANDBOX_UNAVAILABLE", note: "沙箱系统不可用（基础设施故障）" },
  { signal: "沙箱 policy 拒绝（非白名单能力）", code: "ACCESS_DENIED", note: "能力未授权" },
  { signal: "网络白名单拒绝", code: "ACCESS_DENIED", note: "出站域名未授权" },
  { signal: "审批 deny / unavailable（fail-closed）", code: "ACCESS_DENIED", note: "人机门拒绝" },
  { signal: "凭据授权映射未命中", code: "ACCESS_DENIED", note: "包取未授权凭据" },
  { signal: "凭据缺失（resolve 空值）", code: "SERVICE_DENIED", note: "服务侧凭据不可用" },
  { signal: "跨终端鉴权失败", code: "SERVICE_DENIED", note: "token 校验拒绝" },
  { signal: "mesh 路由不可达 / 转发失败", code: "ERR_ROUTING", note: "跨节点失败" },
  { signal: "祖先链命中（环检测 §4.4）", code: "ERR_EXECUTION", reason: "CYCLE_DETECTED", note: "结构性拒绝，不触发审批" },
  { signal: "配额超限", code: null, note: "非错误：rst_data.status=stop 降级信号" },
  { signal: "聚合降级链耗尽", code: null, reason: "DEGRADE_EXHAUSTED", note: "rst_data.status=error + reason" },
  { signal: "未知/未列入", code: "ERR_EXECUTION", note: "envelope.js 实证兜底" },
];

/**
 * 将 dsh 信号映射为协议信封（经 textcli-core err：闭集校验 + 未知回退 ERR_EXECUTION）。
 * 非错误信号（code=null）回退 ERR_EXECUTION（调用方应优先用 rst_data.status 表达降级）。
 */
export function mapSignal(signal: string): ReturnType<typeof tc.err> {
  const row = ERROR_MAP.find((r) => r.signal === signal && r.code !== null);
  if (!row || row.code === null) {
    return tc.err("ERR_EXECUTION", signal);
  }
  return tc.err(row.code, row.reason ?? signal);
}

/** 信号是否落在 6 码闭集内 */
export function isClosedCode(code: string): code is ProtocolErrorCode {
  return (ERROR_CODES as readonly string[]).includes(code);
}
