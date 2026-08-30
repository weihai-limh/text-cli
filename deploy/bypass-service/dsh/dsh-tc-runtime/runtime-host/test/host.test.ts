import { describe, it, expect, vi } from "vitest";
import { handleHostInstruction } from "../src/index.js";
import type { HostDeps } from "../src/index.js";
import type { ApprovalDecision } from "@dsh-tc/runtime-approval";

const allow: ApprovalDecision = { decided: true, allowed: true, decidedBy: "webhook" };
const deny: ApprovalDecision = { decided: true, allowed: false, decidedBy: "unconfigured" };

function baseDeps(over: Partial<HostDeps> = {}): HostDeps {
  return {
    now: () => 1_000,
    requireApproval: vi.fn(async () => allow),
    sandbox: { run: vi.fn(async (p) => ({ ran: p })) },
    credentials: { get: vi.fn(async (ref) => ({ ref, secret: "x" })) },
    jobs: {
      start: vi.fn(async (p) => ({ taskId: `job-${p[0]}` })),
      poll: vi.fn(async (id) => ({ taskId: id, status: "done" })),
    },
    skills: { catalog: vi.fn(async () => ({ skills: ["a", "b"] })) },
    log: { analyze: vi.fn(async (p) => ({ analyzed: p })) },
    ...over,
  };
}

describe("runtime-host 宿主指令", () => {
  it("dsh-sandbox;run 经审批闸放行后执行", async () => {
    const d = baseDeps();
    const env = await handleHostInstruction("dsh-sandbox", "run", ["echo hi"], d);
    expect(env.rst_err).toBe("");
    expect((env.rst_data as any).ran).toEqual(["echo hi"]);
    expect(d.requireApproval).toHaveBeenCalled();
  });

  it("dsh-sandbox;run 审批拒绝 → ERR_EXECUTION deny", async () => {
    const d = baseDeps({ requireApproval: vi.fn(async () => deny) });
    const env = await handleHostInstruction("dsh-sandbox", "run", ["x"], d);
    expect(env.rst_err).toBe("ERR_EXECUTION");
  });

  it("dsh-sandbox;run 无审批通道 → deny（ask 退化为 deny）", async () => {
    const d = baseDeps({ requireApproval: undefined });
    const env = await handleHostInstruction("dsh-sandbox", "run", ["x"], d);
    expect(env.rst_err).toBe("ERR_EXECUTION");
  });

  it("dsh-credential;get 取凭据", async () => {
    const d = baseDeps();
    const env = await handleHostInstruction("dsh-credential", "get", ["TC_BD_OCR"], d);
    expect((env.rst_data as any).ref).toBe("TC_BD_OCR");
  });

  it("dsh-credential;get 缺 ref → INVALID_PARAMS", async () => {
    const d = baseDeps();
    const env = await handleHostInstruction("dsh-credential", "get", [], d);
    expect(env.rst_err).toBe("INVALID_PARAMS");
  });

  it("dsh-approval;require 经闸后回传 approved", async () => {
    const d = baseDeps();
    const env = await handleHostInstruction("dsh-approval", "require", ["need access"], d);
    expect((env.rst_data as any).status).toBe("approved");
  });

  it("dsh-log;analyze 无需闸", async () => {
    const d = baseDeps();
    const env = await handleHostInstruction("dsh-log", "analyze", ["--last 10"], d);
    expect((env.rst_data as any).analyzed).toEqual(["--last 10"]);
    expect(d.requireApproval).not.toHaveBeenCalled();
  });

  it("dsh-job;start / poll", async () => {
    const d = baseDeps();
    const s = await handleHostInstruction("dsh-job", "start", ["build"], d);
    const taskId = (s.rst_data as any).taskId;
    const p = await handleHostInstruction("dsh-job", "poll", [taskId], d);
    expect((p.rst_data as any).status).toBe("done");
  });

  it("dsh-job;poll 缺 taskId → INVALID_PARAMS", async () => {
    const d = baseDeps();
    const env = await handleHostInstruction("dsh-job", "poll", [], d);
    expect(env.rst_err).toBe("INVALID_PARAMS");
  });

  it("dsh-skill;catalog", async () => {
    const d = baseDeps();
    const env = await handleHostInstruction("dsh-skill", "catalog", [], d);
    expect((env.rst_data as any).skills).toEqual(["a", "b"]);
  });

  it("形态 B 专属（compact/subagent/memory/model）剔除 → ERR_NOT_FOUND", async () => {
    const d = baseDeps();
    for (const dom of ["dsh-compact", "dsh-subagent", "dsh-memory", "dsh-model"]) {
      const env = await handleHostInstruction(dom, "run", [], d);
      expect(env.rst_err).toBe("ERR_NOT_FOUND");
    }
  });

  it("未知宿主域/动作 → ERR_NOT_FOUND", async () => {
    const d = baseDeps();
    expect((await handleHostInstruction("dsh-unknown", "x", [], d)).rst_err).toBe("ERR_NOT_FOUND");
    expect((await handleHostInstruction("dsh-sandbox", "explode", [], d)).rst_err).toBe("ERR_NOT_FOUND");
  });
});
