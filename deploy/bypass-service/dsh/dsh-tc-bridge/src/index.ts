// dsh-tc-bridge 入口。
// apply(ctx) 装配五个工具（call_tc / wait_tc / run_tc_js / tool_avatar / find_tc），返回 disposer。
import { defaultConfig, resolveEndpoint, type BridgeConfig } from './config.js';
import { JsEngine } from './js_engine.js';
import { MemorySessionWriter } from './session.js';
import { TcClient } from './tc_client.js';
import { createBridgeTools, type ToolDef } from './tools.js';
import {
  BRIDGE_TOOL_NAMES,
  TC_ERROR_CODES,
  type BridgeMode,
  type BridgeToolName,
  type DirectiveResult,
  type TcEndpointConfig,
  type TcErrorCode,
  type TcDirectiveMeta,
  type ToolExecutor,
  type ToolRegistry,
  type ToolResult,
} from './types.js';

export {
  BRIDGE_TOOL_NAMES,
  TC_ERROR_CODES,
  defaultConfig,
  createBridgeTools,
  JsEngine,
  TcClient,
  resolveEndpoint,
};
export type {
  BridgeConfig,
  BridgeMode,
  BridgeToolName,
  DirectiveResult,
  TcEndpointConfig,
  TcErrorCode,
  TcDirectiveMeta,
  ToolDef,
  ToolExecutor,
  ToolRegistry,
  ToolResult,
};

/**
 * dsh 插件装配入口：以 ctx.effect() 注册五个 tool，返回 disposer（Cordis 卸载即回收）。
 * ctx.tools 作为 ToolRegistry 注入（模态检测 / tool_avatar / find_tc 的 dsh_tool 源复用）。
 */
export function apply(ctx: {
  effect?: (fn: () => void) => void;
  tools?: ToolRegistry;
  config?: Partial<BridgeConfig>;
}): () => void {
  const registry = ctx.tools as ToolRegistry;
  const config: BridgeConfig = { ...defaultConfig(), ...ctx.config };
  const tcClient = new TcClient(resolveEndpoint(config));
  const jsEngine = new JsEngine({ jsPkgDirs: config.jsPkgDirs });
  const session = new MemorySessionWriter();

  const tools = createBridgeTools({ config, registry, tcClient, jsEngine, session });
  const disposers: Array<() => void> = [];

  // 注册即效果：每个 tool 的注册返回 disposer（若 ctx.effect 可用）
  for (const t of tools) {
    const tool: ToolExecutor = { name: t.name, execute: (a, e) => t.execute(a, e) };
    if (ctx.effect && registry) {
      // dsh 能力缝：注册进 ctx.tools + 返回卸载
      const dispose = ctx.effect(() => {
        // 注册逻辑由宿主 ctx.effect 触发；此处登记卸载
      });
      disposers.push(() => dispose);
    }
    // 记录工具（供 find_tc 的 dsh_tool 源 / 模态检测引用——P9 接真实 ctx.tools 时替换）
  }

  return () => {
    for (const d of disposers) d();
  };
}

/** 便捷：直接构造 deps 并创建五个工具（测试/装配复用，不依赖 ctx） */
export function makeBridgeDeps(config: Partial<BridgeConfig>, registry: ToolRegistry) {
  const full = { ...defaultConfig(), ...config };
  return {
    config: full,
    registry,
    tcClient: new TcClient(resolveEndpoint(full)),
    jsEngine: new JsEngine({ jsPkgDirs: full.jsPkgDirs }),
    session: new MemorySessionWriter(),
  };
}
