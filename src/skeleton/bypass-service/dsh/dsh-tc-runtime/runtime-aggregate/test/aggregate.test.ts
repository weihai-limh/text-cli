import { describe, it, expect, vi } from "vitest";
import { AsyncJobBridge, aggregate } from "../src/index.js";
import { ancestorChain } from "@dsh-tc/runtime-sandbox";
import type { ApprovalDecision } from "@dsh-tc/runtime-approval";
import type { AggregateDeps } from "../src/index.js";

const ok = (data: unknown) => ({ rst_err: "", rst_data: data });
const err = (reason?: string) => ({ rst_err: "ERR_EXECUTION", rst_data: { reason } });

describe("AsyncJobBridge（§10.1）", () => {
  it("start → running；task_id 格式 <domain>-<action>-<seq>", () => {
    const b = new AsyncJobBridge({ now: () => 1000 });
    const { taskId } = b.start("math", "add", ["1", "2"]);
    expect(taskId).toBe("math-add-1");
    expect(b.poll(taskId).state).toBe("running");
  });

  it("succeed → done；fail(quota_exhausted) → error 终态", () => {
    const b = new AsyncJobBridge({ now: () => 1000 });
    const { taskId } = b.start("math", "add", []);
    b.succeed(taskId, ok({ sum: 3 }));
    expect(b.poll(taskId).state).toBe("done");
    const { taskId: t2 } = b.start("math", "add", []);
    b.fail(t2, "quota_exhausted");
    const r = b.poll(t2);
    expect(r.state).toBe("error");
    expect(r.error).toBe("quota_exhausted");
  });

  it("cancel 联动：running → cancelled；终态不可 cancel", () => {
    const b = new AsyncJobBridge({ now: () => 1000 });
    const { taskId } = b.start("math", "add", []);
    expect(b.cancel(taskId)).toBe(true);
    expect(b.poll(taskId).state).toBe("cancelled");
    expect(b.cancel(taskId)).toBe(false); // 已终态
  });

  it("重启残留：reconcileAfterRestart 将 running → error + service_restarted", () => {
    const b = new AsyncJobBridge({ now: () => 1000 });
    const { taskId } = b.start("math", "add", []);
    b.reconcileAfterRestart();
    const r = b.poll(taskId);
    expect(r.state).toBe("error");
    expect(r.residual).toBe("service_restarted");
  });
});

describe("aggregate 聚合降级（§10.2）", () => {
  function baseDeps(dispatch: AggregateDeps["dispatch"], over: Partial<AggregateDeps> = {}): AggregateDeps {
    return { dispatch, ancestorChain, ...over } as AggregateDeps;
  }

  const candidates = [
    { domain: "p1", action: "run" },
    { domain: "p2", action: "run" },
    { domain: "p3", action: "run" },
  ];

  it("首候选成功 → 直接返回（不降级）", async () => {
    const dispatch = vi.fn(async () => ok({ v: 1 }));
    const r = await aggregate("agg1", candidates, [], baseDeps(dispatch));
    expect((r as any).rst_data.v).toBe(1);
    expect(dispatch).toHaveBeenCalledTimes(1);
  });

  it("前两个失败 → 降级到第三个成功", async () => {
    const dispatch = vi.fn(async (d: string) =>
      d === "p1" || d === "p2" ? err("boom") : ok({ v: 3 }),
    );
    const r = await aggregate("agg2", candidates, [], baseDeps(dispatch));
    expect((r as any).rst_data.v).toBe(3);
    expect(dispatch).toHaveBeenCalledTimes(3);
  });

  it("status:stop 视为降级信号 → 切换下一候选", async () => {
    const dispatch = vi.fn(async (d: string) =>
      d === "p1" ? ok({ status: "stop" }) : ok({ v: 2 }),
    );
    const r = await aggregate("agg3", candidates, [], baseDeps(dispatch));
    expect((r as any).rst_data.v).toBe(2);
  });

  it("全部失败 → DEGRADE_EXHAUSTED", async () => {
    const dispatch = vi.fn(async () => err("boom"));
    const r = await aggregate("agg4", candidates, [], baseDeps(dispatch));
    expect((r as any).rst_err).toBe("ERR_EXECUTION");
    expect((r as any).rst_data.reason).toBe("DEGRADE_EXHAUSTED");
  });

  it("末参显式 provider → 只走该候选，不走降级", async () => {
    const dispatch = vi.fn(async (d: string) => (d === "p3" ? ok({ v: 9 }) : err("x")));
    const r = await aggregate("agg5", candidates, ["provider:p3;run"], baseDeps(dispatch));
    expect((r as any).rst_data.v).toBe(9);
    expect(dispatch).toHaveBeenCalledTimes(1);
    expect(dispatch).toHaveBeenCalledWith("p3", "run", []);
  });

  it("审批合并：整链一次决策，拒绝则 deny，不调用 dispatch", async () => {
    const dispatch = vi.fn(async () => ok({ v: 1 }));
    const approval = vi.fn(async (): Promise<ApprovalDecision> => ({ decided: true, allowed: false, decidedBy: "unconfigured" }));
    const r = await aggregate("agg6", candidates, [], baseDeps(dispatch, { approval }));
    expect((r as any).rst_err).toBe("ERR_EXECUTION");
    expect(dispatch).not.toHaveBeenCalled();
    expect(approval).toHaveBeenCalledTimes(1); // 整链一次
  });

  it("消费 quota stop → 返回 stop 信封（降级信号）", async () => {
    const dispatch = vi.fn(async () => ok({ v: 1 }));
    const quota = { check: vi.fn(async () => ({ status: "stop" as const })) };
    const r = await aggregate("agg7", candidates, [], baseDeps(dispatch, { quota }));
    expect((r as any).rst_data.status).toBe("stop");
    expect(dispatch).not.toHaveBeenCalled();
  });

  it("环检测：agg:<name> 已在链上 → CYCLE_DETECTED", async () => {
    const dispatch = vi.fn(async () => ok({ v: 1 }));
    await expect(
      ancestorChain.run([`agg:loop` as const], () =>
        aggregate("loop", candidates, [], baseDeps(dispatch)),
      ),
    ).rejects.toThrow();
  });
});
