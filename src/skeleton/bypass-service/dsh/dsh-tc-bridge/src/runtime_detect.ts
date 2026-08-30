// 模态探测：判断当前 dsh 是否挂 dsh-tc-runtime（查 ctx.tools 是否有 tc__ 前缀工具）。
// 对齐 dsh-tc-bridge.md §0.4 + §2.3.5（纯探测，无副作用；决定 call_tc 短路 / find_tc 映射+白名单）。
import { isTcTool } from './mapper.js';
import type { BridgeMode, ToolRegistry } from './types.js';

/**
 * 探测当前模态：
 * - 'hybrid'：ctx.tools 中存在 tc__ 前缀工具（dsh-tc-runtime 在位）→ 混合模式（短路 + 白名单 + 映射）。
 * - 'bridging'：无 tc__ 工具 → 桥接模式（远端 HTTP + 全暴露）。
 */
export function detectMode(toolRegistry: ToolRegistry): BridgeMode {
  for (const name of toolRegistry.names()) {
    if (isTcTool(name)) return 'hybrid';
  }
  return 'bridging';
}

/**
 * 受 runtimeAutoDetect 配置约束的探测：
 * - runtimeAutoDetect=false → 强制 bridging（用户显式关闭混合模式）。
 * - 否则走 detectMode。
 */
export function detectModeWithConfig(toolRegistry: ToolRegistry, runtimeAutoDetect: boolean): BridgeMode {
  if (!runtimeAutoDetect) return 'bridging';
  return detectMode(toolRegistry);
}

/**
 * 便捷：检测某 tc 域/动作是否已在 runtime 注册为 tc__ 工具（短路路由前检查）。
 */
export function hasRuntimeTool(toolRegistry: ToolRegistry, toolName: string): boolean {
  return toolRegistry.has(toolName);
}
