/**
 * types.ts——异步任务桥接 + 聚合降级 类型（功能设计 §10.2 / §5.2.1 / §1.2.6）
 */
import type { ApprovalDecision, ApprovalRequest } from "@dsh-tc/runtime-approval";

/** 五态（对齐 SPEC §1.2.6） */
export type JobState = "pending" | "running" | "done" | "error" | "cancelled";

export interface JobRecord {
  taskId: string;
  domain: string;
  action: string;
  params: string[];
  state: JobState;
  seq: number;
  startedAt: number;
  error?: string;
  /** 重启残留标记 */
  residual?: "service_restarted";
  result?: unknown;
}

export interface QuotaLike {
  check: (id: string) => Promise<{ status: "ok" | "stop" }>;
}

export interface AggregateDeps {
  dispatch: (domain: string, action: string, params: string[]) => Promise<unknown>;
  /** 审批合并：整链一次决策 */
  approval?: (req: ApprovalRequest) => Promise<ApprovalDecision>;
  /** 配额（消费 stop 信号） */
  quota?: QuotaLike;
  /** 环检测祖先链（agg:<name>） */
  ancestorChain: { contains: (k: `agg:${string}`) => boolean; push: (k: `agg:${string}`) => boolean; pop: (k: `agg:${string}`) => void };
  now?: () => number;
}

export interface AggProvider {
  domain: string;
  action: string;
}
