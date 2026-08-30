// 桥内部类型：统一 dsh tool 形状、tc 信封结果、依赖注入接口。
// 目标是让 P1~P6 的纯逻辑不依赖 dsh 内核（ToolRegistry 以接口注入，可单测）。

/** tc 协议错误码闭集（SPEC v1.3.2，envelope.err 校验） */
export const TC_ERROR_CODES = [
  'ERR_NOT_FOUND',
  'ERR_EXECUTION',
  'ERR_ROUTING',
  'INVALID_PARAMS',
  'ACCESS_DENIED',
  'SERVICE_DENIED',
] as const;
export type TcErrorCode = (typeof TC_ERROR_CODES)[number];

/** A0 SDK 的 DirectiveResult 形状（tc_client.ts / wait_tc 使用） */
export interface DirectiveResult {
  ok: boolean;
  data: unknown;
  rtype: string;
  err_code: string;
  directive: string;
  is_async: boolean;
  task_id?: string;
}

/** 桥统一 tool 返回值（envelope.ts 产出，dsh 侧看到的就是它） */
export interface ToolResult {
  ok: boolean;
  data: unknown;
  err?: string;
  /** 可选：rst_types 透传（tc 分支） */
  types?: string;
}

/** tc 端点配置（Config 的一部分） */
export interface TcEndpointConfig {
  /** 端点来源三态：'auto-self'（混合模式短路）/ 具体 URL（远端）/ undefined（用默认） */
  endpoint?: string;
  accessToken?: string;
  serviceToken?: string;
  /** rank 降级链端点列表 */
  rankEndpoints?: string[];
}

/** 模态类型 */
export type BridgeMode = 'bridging' | 'hybrid';

/**
 * dsh tool 注册表的抽象（供 tool_avatar / find_tc 的 dsh_tool 源 / 模态检测使用）。
 * 通过依赖注入（P6 装配时由 apply(ctx) 提供真实实现），纯逻辑可 mock 单测。
 */
export interface ToolRegistry {
  /** 是否存在指定名字的 tool */
  has(name: string): boolean;
  /** 取一个 tool 的执行器 */
  get(name: string): ToolExecutor | undefined;
  /** 枚举所有 tool 名 */
  names(): string[];
}

/** dsh tool 执行器抽象（同进程 ctx.tools.get(name).execute 的接口化） */
export interface ToolExecutor {
  readonly name: string;
  execute(args: Record<string, unknown>, exec: ToolExecutionContext): Promise<ToolResult>;
}

/** 工具执行上下文（exec.signal 用于取消；桥内部可复用） */
export interface ToolExecutionContext {
  signal?: AbortSignal;
  [key: string]: unknown;
}

/** bridge 对外暴露的五个 tool 的名称（防 tool_avatar 自代理的闭集） */
export const BRIDGE_TOOL_NAMES = [
  'call_tc',
  'wait_tc',
  'run_tc_js',
  'tool_avatar',
  'find_tc',
] as const;
export type BridgeToolName = (typeof BRIDGE_TOOL_NAMES)[number];

/** textcli-core 指令发现聚合项（find_tc 的 tc_local 源 / P3 discover 输出） */
export interface TcDirectiveMeta {
  domain: string;
  action: string;
  domain_zh?: string;
  action_zh?: string;
  usage?: string;
  usage_zh?: string;
  description?: string;
  description_zh?: string;
  params?: unknown;
  outputs?: unknown;
  rank?: number;
  source?: string;
  package?: string;
  /** 指令/端点来源（A0 discover 透传） */
  runtime?: string;
  category?: string;
}
