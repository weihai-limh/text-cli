// 工具代理：tool_avatar 的执行底座——同进程代理 dsh 已注册 tool（含 mcp tool）。
// 对齐 dsh-tc-bridge.md §2.2 工具三 + §4.4（防重入 / 不二次降级 / 方向单向，红线⑤）。
import { toolToDsh } from './envelope.js';
import { BRIDGE_TOOL_NAMES, type ToolResult, type ToolRegistry } from './types.js';

export interface ProxyOpts {
  /** 被代理 tool 的超时（毫秒）；未传由 tool 自身处理 */
  timeoutMs?: number;
}

/** 判断是否命中 bridge 自身 tool（防自代理/递归环，红线⑤） */
export function isBridgeTool(name: string): boolean {
  return (BRIDGE_TOOL_NAMES as readonly string[]).includes(name);
}

/**
 * 同进程代理 dsh 已注册 tool。
 *
 * - 未注册 → `{ ok:false, err:'tool_not_found' }`（不 throw，返回失败值）。
 * - 命中 bridge 自身 tool → 拒绝（防 agent→tool_avatar→call_tc→... 环）。
 * - 同进程调用（非子进程、非再发 HTTP）；mcp tool 的真实执行由 dsh-mcp-client 完成，proxy 只透传。
 * - 不二次降级：被代理 tool 自身失败由原实现处理，proxy 仅透传结果经 toolToDsh 归一。
 * - 方向单向：只调 dsh 已注册 tool，不反向暴露 dsh 能力给 tc。
 */
export async function proxyTool(
  name: string,
  args: Record<string, unknown>,
  registry: ToolRegistry,
  exec: { signal?: AbortSignal },
  opts: ProxyOpts = {},
): Promise<ToolResult> {
  // 防自代理/递归环（红线⑤）
  if (isBridgeTool(name)) {
    return { ok: false, data: null, err: 'bridge_tool_forbidden' };
  }
  const tool = registry.get(name);
  if (!tool) {
    return { ok: false, data: null, err: 'tool_not_found' };
  }
  try {
    const result = await tool.execute(args, exec);
    return toolToDsh(result);
  } catch (e) {
    // 被代理 tool 抛错 → 透传为失败值（不 throw，不二次降级）
    return { ok: false, data: null, err: e instanceof Error ? e.message : String(e) };
  }
}
