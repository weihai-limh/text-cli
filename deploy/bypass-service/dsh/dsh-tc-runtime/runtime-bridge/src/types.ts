/**
 * types.ts——协议桥（mcp-client）类型（功能设计 §10.1 / 计划 Phase 11.1）
 */

/** 双 adapter 模式（对齐 tc mcp_dispatch.py 实测） */
export type AdapterMode = "passthrough" | "json_parse";

/** 一个 MCP tool 的桥接描述 */
export interface McpToolDef {
  /** MCP server 名 */
  server: string;
  /** MCP tool 名 */
  tool: string;
  /** 人类可读用途（→ directive.usage） */
  description?: string;
  /** passthrough 模式下的命名参数顺序（args[name] = params[i]） */
  paramNames?: string[];
  /** 参数转化 adapter；缺省 passthrough */
  adapter?: AdapterMode;
}

/** 经桥注册后生成的 tc 协议 directive（与 native 指令平权） */
export interface Directive {
  /** 工具名 = `mcp__<server>__<tool>` */
  name: string;
  /** 固定为 "mcp"（保留域，但非 text-cli 元指令域，可进 ctx.tools） */
  domain: "mcp";
  /** action = `<server>__<tool>` */
  action: string;
  usage?: string;
}

/** 注册回调（注入 dsh ctx.tools.register） */
export type BridgeRegister = (name: string, def: McpToolDef) => void;
