/**
 * types.ts——path 引擎类型（功能设计 §9，对齐 tc path_executor.py）
 */

/** 最小调用单元（指令 step） */
export interface CallStep {
  type?: "call";
  domain: string;
  action: string;
  params?: string[];
  /** step id（供 {stepId} / {stepId.field} 引用） */
  name?: string;
  /** 结果存入上下文变量名 */
  out?: string;
  /** 降级候选（domain;action 串），按序递补，末参显式指定不走降级 */
  fallback?: Array<{ domain: string; action: string }>;
}

/** 顺序管线 */
export interface SequenceStep {
  type: "sequence";
  steps: PathStep[];
}

/** 并行分支 */
export interface ParallelStep {
  type: "parallel";
  strategy: "first_ok" | "all";
  branches: PathStep[];
}

/** 映射（遍历数组） */
export interface MapStep {
  type: "map";
  /** 待遍历变量名（数组） */
  over: string;
  /** 单项变量名 */
  as: string;
  step: PathStep;
  on_error?: "stop" | "skip";
  /** 默认关；显式 enabled:true 才执行 */
  enabled?: boolean;
  concurrency?: number;
}

/** 条件 */
export interface IfStep {
  type: "if";
  cond: Condition;
  then: PathStep;
  else?: PathStep;
}

/** 跨节点派发 */
export interface HttpDispatchStep {
  type: "http_dispatch";
  node: string;
  domain: string;
  action: string;
  params?: string[];
}

/** 委托（无匹配指令非 error） */
export interface DelegatedStep {
  type: "delegated";
  domain: string;
  action: string;
  params?: string[];
}

export type PathStep =
  | CallStep
  | SequenceStep
  | ParallelStep
  | MapStep
  | IfStep
  | HttpDispatchStep
  | DelegatedStep;

export type Condition =
  | { kind: "string"; expr: string }
  | { kind: "equals"; left: string; right: string }
  | { kind: "contains"; left: string; right: string }
  | { kind: "matches"; left: string; right: string }
  | { kind: "exists"; expr: string }
  | { kind: "all"; conds: Condition[] }
  | { kind: "any"; conds: Condition[] };

export interface PathDef {
  name: string;
  description?: string;
  steps: PathStep[];
}

export interface PathDeps {
  /** 统一派发（每 step 过护栏/审计/审批/凭据/环检测）；返回工具结果（信封 data 或原始） */
  dispatch: (domain: string, action: string, params: string[]) => Promise<unknown>;
  /** 跨节点派发（http_dispatch）；缺省 → 本地回退 */
  httpDispatch?: (
    node: string,
    domain: string,
    action: string,
    params: string[],
  ) => Promise<unknown>;
  now?: () => number;
  /** 嵌套深度上限（默认 2） */
  maxDepth?: number;
  /** map 硬上限（默认 1000） */
  mapHardCap?: number;
  /** 初始上下文变量（如 map 的 over 数组来源） */
  initialVars?: Record<string, unknown>;
}

export interface PathResult {
  ok: boolean;
  output?: unknown;
  error?: string;
  /** 上下文变量 */
  vars: Record<string, unknown>;
  /** 各 step 结果（按 name） */
  steps: Record<string, unknown>;
  warnings: string[];
}
