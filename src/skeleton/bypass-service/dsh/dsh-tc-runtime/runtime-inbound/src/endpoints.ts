/**
 * 协议端点处理器（功能设计 §3.4，SPEC §1.2.4/1.2.5/1.2.6）
 *
 * - GET /text-cli/health——健康检查（spec_version + mechanism 9 机制词表）
 * - GET /text-cli/skills——公开技能列表（service_manifest.public_directives 白名单）
 * - GET /text-cli/tasks/{task_id}——异步任务查询（ctx.jobs 桥接，Phase 10 接线）
 *
 * 纯逻辑，数据源注入（ubuntu 联调时接 ctx.jobs / service_manifest）。
 */
import tc from "textcli-core";
import type { DirectiveEntry } from "@dsh-tc/runtime-mapper";
import type { Envelope } from "./handler.js";

/** SPEC §1.2.5 机制标识词表 */
export const MECHANISMS = [
  "directive_execution",
  "package_lifecycle",
  "discovery",
  "path",
  "async",
  "aggregate",
  "mesh",
  "bridge",
  "facade",
] as const;

export interface HealthInfo {
  version: string;
  spec_version: string;
  /** 运行时自身版本（与 spec_version 正交） */
}

export function handleHealth(info: HealthInfo): Envelope {
  return tc.ok({
    status: "ok",
    body: "dsh-tc-runtime",
    version: info.version,
    spec_version: info.spec_version,
    mechanism: MECHANISMS,
  });
}

/**
 * 公开技能列表（SPEC §1.2.4）：service_manifest.public_directives 白名单控制。
 * 白名单为空 = 全部暴露；有内容时只暴露列出的条目（domain;action）。
 */
export function handleSkills(directives: DirectiveEntry[], whitelist: string[]): Envelope {
  const list = directives
    .filter((d) => {
      const key = `${d.domain};${d.action}`;
      return whitelist.length === 0 || whitelist.includes(key);
    })
    .map((d) => ({ domain: d.domain, action: d.action }));
  return tc.ok({ skills: list });
}

export interface TaskInfo {
  task_id: string;
  domain: string;
  action: string;
  state: "pending" | "running" | "done" | "error" | "cancelled";
  result?: unknown;
  progress?: string;
}

export interface TaskQueryDeps {
  /** 任务读取器（Phase 10 接 ctx.jobs.read）；不存在 → null */
  readTask(taskId: string): Promise<TaskInfo | null>;
}

/**
 * 任务查询（SPEC §1.2.6）：成功 → {status:ok, task:{...}} 信封；
 * 不存在 → 404 语义由 HTTP 层处理（此处返回 null 供上层判定）。
 */
export async function handleTaskQuery(
  taskId: string,
  deps: TaskQueryDeps,
): Promise<Envelope | null> {
  const task = await deps.readTask(taskId);
  if (!task) return null; // HTTP 层 → 404 + {"rst_err":"not_found"}
  return tc.ok({ status: "ok", task });
}
