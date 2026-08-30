/**
 * 入站处理器——六段管道（功能设计 §5.1）
 *
 * ① 解析（复用 parser.js）→ ② 路由（text-cli 保留域拦截占位）→ ③ 执行（dispatchFn 注入，
 * Phase 1 为 mock 直通，沙箱未接入前拒绝真实包执行）→ ⑤ 信封（复用 envelope.js）→ ⑥ 审计（Phase 6）
 *
 * 纯逻辑核心，dispatch 依赖注入（R10/R17）——不耦合 dsh ctx。
 */
import tc from "textcli-core";
import { tcToDsh, type ToolExecutionInput } from "@dsh-tc/runtime-mapper";
import { CycleDetectedError } from "@dsh-tc/runtime-sandbox";
import { TraceSession, type AuditWriter } from "@dsh-tc/runtime-audit";

export type DispatchFn = (input: ToolExecutionInput) => Promise<unknown>;
export type Envelope = ReturnType<typeof tc.ok>;

export interface HandlerDeps {
  dispatch: DispatchFn;
  /** 审计写入器（Phase 6：独立 JSONL；未注入则不审计） */
  audit?: AuditWriter;
  /** text-cli 保留域元指令处理器（Phase 7：handleMeta；未注入则返回未实现） */
  meta?: (action: string, params: string[]) => Promise<Envelope>;
  /** 入站生态归属分流（P8：调用方注入；返回非 null → 走该分支；null → 默认统一 dispatch）。
   *  基于 ecosystem.classifyDomain 做结构化分流，不依赖 LLM。 */
  route?: (mapped: { domain: string; action: string; params: string[] }) => Promise<Envelope | null>;
}

export interface HandleOptions {
  /** 外部传入的 traceId（幂等/重放场景）；缺省自动生成 */
  traceId?: string;
}

export async function handlePrompt(
  prompt: string,
  deps: HandlerDeps,
  opts: HandleOptions = {},
): Promise<Envelope> {
  // 审计会话：traceId + seq（⑥ 审计写入，append-only JSONL）
  const trace = new TraceSession(opts.traceId);
  const audit = (type: Parameters<TraceSession["next"]>[0], payload: Record<string, unknown> = {}) =>
    deps.audit?.write(trace.next(type, payload));

  await audit("inbound", { prompt });
  // ① 解析 + 映射（复用 textcli-core parser，零改动）
  const mapped = tcToDsh(prompt);
  if (!mapped.ok) {
    await audit("parse", { error: mapped.envelope.rst_err, reason: String(mapped.envelope.rst_data?.reason ?? "") });
    return mapped.envelope;
  }
  await audit("parse", { domain: mapped.domain, action: mapped.action, params: mapped.params });

  // ② 路由：text-cli 保留域直接拦截（元指令表面，Phase 7 handleMeta）
  if (mapped.domain === "text-cli") {
    await audit("route", { decision: "meta-reserved", action: mapped.action });
    const env = deps.meta
      ? await deps.meta(mapped.action, mapped.params)
      : tc.err("ERR_NOT_FOUND", `text-cli 元指令未实现（Phase 7）`);
    await audit("envelope", { rst_err: env.rst_err });
    return env;
  }

  // ②' P8：入站生态归属分流（调用方注入；非 null → 直接走该分支；null → 默认统一 dispatch）
  if (deps.route) {
    const routed = await deps.route({ domain: mapped.domain, action: mapped.action, params: mapped.params });
    if (routed) {
      await audit("route", { decision: "ecosystem-routed", domain: mapped.domain });
      await audit("envelope", { rst_err: routed.rst_err });
      return routed;
    }
  }

  // ③ 执行：注入的 dispatch（Phase 1 mock 直通；Phase 3 沙箱执行宿主替换）
  let result: unknown;
  try {
    result = await deps.dispatch(mapped.input);
  } catch (e) {
    // 环命中 = 结构性拒绝（§4.4.5.1：ERR_EXECUTION + reason=CYCLE_DETECTED，不触发审批）
    if (e instanceof CycleDetectedError) {
      const env = tc.err("ERR_EXECUTION", `CYCLE_DETECTED: ${e.key}`);
      await audit("tool-exec", { tool: mapped.input.name, error: env.rst_err, reason: String(env.rst_data?.reason ?? "") });
      await audit("envelope", { rst_err: env.rst_err });
      return env;
    }
    const env = tc.err("ERR_EXECUTION", e instanceof Error ? e.message : String(e));
    await audit("tool-exec", { tool: mapped.input.name, error: env.rst_err, reason: String(env.rst_data?.reason ?? "") });
    await audit("envelope", { rst_err: env.rst_err });
    return env;
  }

  if (result === null || result === undefined) {
    const env = tc.err("ERR_NOT_FOUND", `no matching directive: ${mapped.domain};${mapped.action}`);
    await audit("tool-exec", { tool: mapped.input.name, error: env.rst_err });
    await audit("envelope", { rst_err: env.rst_err });
    return env;
  }

  // ⑤ 信封（复用 envelope.js；pray_rst_types 提升 + 6 码闭集）
  const env = tc.ok(result);
  await audit("tool-exec", { tool: mapped.input.name, status: (env.rst_data as { status?: unknown })?.status });
  await audit("envelope", { rst_types: env.rst_types, rst_err: env.rst_err });
  return env;
}
