/**
 * host.ts——宿主指令表面（功能设计 §8.3）
 *
 * 六指令：dsh-sandbox;run / dsh-credential;get / dsh-approval;require /
 * dsh-log;analyze / dsh-job;start,poll / dsh-skill;catalog
 *
 * 关键指令（sandbox/credential/approval）必经审批闸：
 * - 有通道且允许 → 执行
 * - 有通道但拒绝 / 委托未决 → deny（ERR_EXECUTION）
 * - 无通道 → deny（ERR_EXECUTION，ask 退化为 deny）
 *
 * 形态 B 专属（compact/subagent/memory/model）不登记 → ERR_NOT_FOUND。
 */
import tc from "textcli-core";
import type { ApprovalDecision, ApprovalRequest } from "@dsh-tc/runtime-approval";
import { EXCLUDED_FORM_B, type HostDeps } from "./types.js";

function newCallId(now: () => number): string {
  return `host-${now()}-${Math.floor(Math.random() * 1_000_000)}`;
}

/** 审批闸：返回是否放行；缺通道或无决策 → 不放行 */
async function gate(
  deps: HostDeps,
  toolName: string,
  reason: string,
  now: () => number,
): Promise<{ ok: true } | { ok: false; envelope: ReturnType<typeof tc.err> }> {
  if (!deps.requireApproval) {
    return { ok: false, envelope: tc.err("ERR_EXECUTION", "approval channel unavailable") };
  }
  const req: ApprovalRequest = { callId: newCallId(now), toolName, reason };
  const d: ApprovalDecision = await deps.requireApproval(req);
  if (!d.decided || !d.allowed) {
    return { ok: false, envelope: tc.err("ERR_EXECUTION", `approval denied: ${d.decidedBy ?? "no-decision"}`) };
  }
  return { ok: true };
}

export async function handleHostInstruction(
  domain: string,
  action: string,
  params: string[],
  deps: HostDeps,
): Promise<ReturnType<typeof tc.ok>> {
  const now = deps.now ?? Date.now;

  // 形态 B 专属剔除
  if ((EXCLUDED_FORM_B as readonly string[]).includes(domain)) {
    return tc.err("ERR_NOT_FOUND", `form-B instruction excluded: ${domain}`);
  }

  switch (domain) {
    case "dsh-sandbox": {
      if (action !== "run") return tc.err("ERR_NOT_FOUND", `unknown action: dsh-sandbox;${action}`);
      const g = await gate(deps, `dsh-sandbox;run`, params.join(" "), now);
      if (!g.ok) return g.envelope;
      if (!deps.sandbox) return tc.err("ERR_EXECUTION", "sandbox capability unavailable");
      return tc.ok(await deps.sandbox.run(params));
    }

    case "dsh-credential": {
      if (action !== "get") return tc.err("ERR_NOT_FOUND", `unknown action: dsh-credential;${action}`);
      const ref = params[0];
      if (!ref) return tc.err("INVALID_PARAMS", "dsh-credential;get requires a ref");
      const g = await gate(deps, `dsh-credential;get`, ref, now);
      if (!g.ok) return g.envelope;
      if (!deps.credentials) return tc.err("ERR_EXECUTION", "credentials capability unavailable");
      return tc.ok(await deps.credentials.get(ref));
    }

    case "dsh-approval": {
      if (action !== "require") return tc.err("ERR_NOT_FOUND", `unknown action: dsh-approval;${action}`);
      // 该指令本身即审批请求：经闸后回传决策
      const g = await gate(deps, `dsh-approval;require`, params.join(" "), now);
      if (!g.ok) return g.envelope;
      return tc.ok({ status: "approved", reason: params.join(" ") });
    }

    case "dsh-log": {
      if (action !== "analyze") return tc.err("ERR_NOT_FOUND", `unknown action: dsh-log;${action}`);
      if (!deps.log) return tc.err("ERR_EXECUTION", "log capability unavailable");
      return tc.ok(await deps.log.analyze(params));
    }

    case "dsh-job": {
      if (action === "start") {
        if (!deps.jobs) return tc.err("ERR_EXECUTION", "jobs capability unavailable");
        const r = await deps.jobs.start(params);
        return tc.ok(r);
      }
      if (action === "poll") {
        const taskId = params[0];
        if (!taskId) return tc.err("INVALID_PARAMS", "dsh-job;poll requires taskId");
        if (!deps.jobs) return tc.err("ERR_EXECUTION", "jobs capability unavailable");
        return tc.ok(await deps.jobs.poll(taskId));
      }
      return tc.err("ERR_NOT_FOUND", `unknown action: dsh-job;${action}`);
    }

    case "dsh-skill": {
      if (action !== "catalog") return tc.err("ERR_NOT_FOUND", `unknown action: dsh-skill;${action}`);
      if (!deps.skills) return tc.err("ERR_EXECUTION", "skills capability unavailable");
      return tc.ok(await deps.skills.catalog());
    }

    default:
      return tc.err("ERR_NOT_FOUND", `unknown host domain: ${domain}`);
  }
}
