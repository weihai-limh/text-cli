/**
 * jobs.ts——异步任务桥接 ctx.jobs（功能设计 §10.1）
 *
 * - task_id = `<domain>-<action>-<seq>`
 * - 五态：pending/running/done/error/cancelled
 * - 重启残留：running → error + residual=`service_restarted`
 * - 语义区分：
 *   · 同步 `status:stop` → 降级信号（由聚合层消费，非终态）
 *   · 异步终态 error + `quota_exhausted` → 终态（SPEC §1.2.6）
 * - task;cancel 联动
 */
import type { JobRecord, JobState } from "./types.js";
export class AsyncJobBridge {
  private jobs = new Map<string, JobRecord>();
  private seq = 0;
  private readonly now: () => number;

  constructor(opts: { now?: () => number } = {}) {
    this.now = opts.now ?? Date.now;
  }

  start(domain: string, action: string, params: string[]): { taskId: string } {
    const seq = ++this.seq;
    const taskId = `${domain}-${action}-${seq}`;
    const rec: JobRecord = {
      taskId,
      domain,
      action,
      params,
      state: "running",
      seq,
      startedAt: this.now(),
    };
    this.jobs.set(taskId, rec);
    return { taskId };
  }

  cancel(taskId: string): boolean {
    const rec = this.jobs.get(taskId);
    if (!rec) return false;
    if (rec.state !== "running") return false; // 仅 running 可取消；终态/已取消不可再取消
    rec.state = "cancelled";
    return true;
  }

  /** 终态：成功 */
  succeed(taskId: string, result: unknown): boolean {
    const rec = this.jobs.get(taskId);
    if (!rec) return false;
    rec.state = "done";
    rec.result = result;
    return true;
  }

  /** 终态：失败（code 可为 quota_exhausted 等） */
  fail(taskId: string, code = "ERR_EXECUTION"): boolean {
    const rec = this.jobs.get(taskId);
    if (!rec) return false;
    rec.state = "error";
    rec.error = code;
    return true;
  }

  /** 重启对账：所有 running 标记为 error + service_restarted 残留 */
  reconcileAfterRestart(): void {
    for (const rec of this.jobs.values()) {
      if (rec.state === "running") {
        rec.state = "error";
        rec.error = "service_restarted";
        rec.residual = "service_restarted";
      }
    }
  }

  poll(taskId: string): JobRecord | (Omit<JobRecord, "state"> & { state: "not_found" }) {
    const rec = this.jobs.get(taskId);
    if (!rec) return { taskId, domain: "", action: "", params: [], state: "not_found" as const, seq: 0, startedAt: 0 };
    return rec;
  }
}
