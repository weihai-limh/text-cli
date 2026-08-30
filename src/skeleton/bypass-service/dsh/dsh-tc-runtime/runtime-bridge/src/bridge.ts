/**
 * bridge.ts——协议桥（mcp-client）：MCP tool → tc 指令（功能设计 §10.1）
 *
 * - `mcp__<server>__<tool>` 工具名（双下划线模式，对齐 mcp-client 实证）
 * - 自动生成 directive（MCP 与 native 指令平权，SPEC §5.7）
 * - `adapt_params` 双 adapter：
 *     passthrough ：按 param_names 顺序映射 args[name] = params[i]
 *     json_parse  ：首参 JSON.parse；失败 → ",".join(params) 再 parse；再失败 → {_raw: params[0]}
 *     参数声明缺失兜底：{_params: params}
 */
import type { AdapterMode, BridgeRegister, Directive, McpToolDef } from "./types.js";

/** 工具名 = `mcp__<server>__<tool>` */
export function mcpToolName(server: string, tool: string): string {
  return `mcp__${server}__${tool}`;
}

/**
 * 参数转化（tc positional → MCP 命名参数）。
 * @returns 适配后的命名参数对象，可直接作为 ctx.tools.execute 的 arguments
 */
export function adaptParams(def: McpToolDef, params: string[]): Record<string, unknown> {
  const adapter: AdapterMode = def.adapter ?? "passthrough";

  if (adapter === "passthrough") {
    // 参数声明缺失兜底
    if (!def.paramNames || def.paramNames.length === 0) {
      return { _params: params };
    }
    const args: Record<string, unknown> = {};
    def.paramNames.forEach((name, i) => {
      args[name] = params[i];
    });
    return args;
  }

  // json_parse
  if (params.length > 0) {
    try {
      return JSON.parse(params[0]) as Record<string, unknown>;
    } catch {
      try {
        return JSON.parse(params.join(",")) as Record<string, unknown>;
      } catch {
        return { _raw: params[0] };
      }
    }
  }
  return {};
}

/** 生成 directive（与 native 平权） */
export function toDirective(def: McpToolDef): Directive {
  const name = mcpToolName(def.server, def.tool);
  return {
    name,
    domain: "mcp",
    action: `${def.server}__${def.tool}`,
    usage: def.description,
  };
}

/** 注册单个 MCP tool 进 ctx.tools（通过注入的 register 回调） */
export function registerMcpTool(def: McpToolDef, register?: BridgeRegister): Directive {
  const directive = toDirective(def);
  register?.(directive.name, def);
  return directive;
}

/**
 * 协议桥收集器：挂载多个 MCP tool，产出 directives[]（供 dshToTc 平权发现）。
 * 注册即 effect（register 回调负责 dsh 侧 ctx.tools.register + 返回 disposer）。
 */
export class McpBridge {
  private directives: Directive[] = [];

  constructor(private readonly register?: BridgeRegister) {}

  /** 挂载一个 MCP tool，返回其 directive */
  mount(def: McpToolDef): Directive {
    const directive = registerMcpTool(def, this.register);
    this.directives.push(directive);
    return directive;
  }

  /** 批量挂载 */
  mountAll(defs: McpToolDef[]): Directive[] {
    return defs.map((d) => this.mount(d));
  }

  /** 已挂载的 directives（平权并入 directives[]） */
  directivesList(): Directive[] {
    return [...this.directives];
  }
}
