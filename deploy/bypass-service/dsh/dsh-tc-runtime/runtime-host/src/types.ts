/**
 * types.ts——宿主指令依赖与类型（功能设计 §8.3）
 *
 * 宿主指令运行在「插件侧」，经注入的 ctx 能力执行；裸环境用 mock。
 * 关键指令（sandbox/credential/approval）必经审批闸——无通道退化为 deny。
 */
import type { ApprovalDecision, ApprovalRequest } from "@dsh-tc/runtime-approval";

/** 各 ctx 能力的注入接口（真实环境接 dsh ctx；裸环境 mock） */
export interface HostCapabilities {
  sandbox?: { run: (params: string[]) => Promise<unknown> | unknown };
  credentials?: { get: (ref: string) => Promise<unknown> | unknown };
  jobs?: {
    start: (params: string[]) => Promise<{ taskId: string }> | { taskId: string };
    poll: (taskId: string) => Promise<unknown> | unknown;
  };
  skills?: { catalog: () => Promise<unknown> | unknown };
  log?: { analyze: (params: string[]) => Promise<unknown> | unknown };
  /** 审批闸：返回决策；缺省 → 关键指令退化为 deny */
  requireApproval?: (req: ApprovalRequest) => Promise<ApprovalDecision>;
}

export interface HostDeps extends HostCapabilities {
  now?: () => number;
}

/** 形态 B 专属 dsh 指令（compact/subagent/memory/model）——不登记为宿主指令 */
export const EXCLUDED_FORM_B = [
  "dsh-compact",
  "dsh-subagent",
  "dsh-memory",
  "dsh-model",
] as const;
