/**
 * executor-js——受限 JS 执行面（功能设计 §4.3，对齐 tc `js_bridge.py` 实测）
 *
 * spawn 独立 node 子进程执行 runner.js：
 * - stdin 传 `{domain,action,params,handlerPath}` JSON / stdout 收结果 / 非零退出码 = error
 * - 超时 kill（默认 30s）/ stdin 上限 / maxBuffer 上限
 * - env 最小化：只注入必要基础变量 + 白名单（凭据 ref 解析值，Phase 5 接入）
 * - SandboxProvider 注入：`confine(argv, policy)` 包裹 spawn（ubuntu 联调接
 *   `ctx.sandbox.confine`；未配置 → fail-closed 拒绝执行）
 */
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";
import type { SandboxPolicy } from "./policy.js";
import { SandboxUnavailableError, type SandboxProvider } from "./sandbox-provider.js";

export interface ExecRequest {
  domain: string;
  action: string;
  params: string[];
  handlerPath: string;
}

export interface ExecOptions {
  /** 超时毫秒（默认 30000） */
  timeoutMs?: number;
  /** env 白名单（凭据 ref 解析值 + 包需要的基础变量；不注入宿主全量 env） */
  envWhitelist?: Record<string, string>;
  maxBuffer?: number;
  /** 沙箱策略（ubuntu 联调时由 policy.ts 生成） */
  policy?: SandboxPolicy;
  /** 沙箱 provider（confine 包裹 spawn；未注入 → fail-closed） */
  sandbox?: SandboxProvider;
}

export type ExecResult =
  | { ok: true; data: unknown }
  | { ok: false; error: { code: string; message: string } };

const RUNNER_PATH = path.join(path.dirname(fileURLToPath(import.meta.url)), "runner.cjs");
const NODE_PATH = process.execPath;

/** 最小基础环境：不继承宿主全量 env（防包读宿主敏感 env） */
function minimalEnv(whitelist: Record<string, string>): NodeJS.ProcessEnv {
  const env: NodeJS.ProcessEnv = {
    PATH: process.env.PATH ?? "",
  };
  for (const [k, v] of Object.entries(whitelist)) env[k] = v;
  return env;
}

export async function execJs(req: ExecRequest, opts: ExecOptions = {}): Promise<ExecResult> {
  const timeoutMs = opts.timeoutMs ?? 30_000;
  const maxBuffer = opts.maxBuffer ?? 4 * 1024 * 1024;

  // 沙箱 provider：confine 包裹 spawn argv（文件效果隔离）。未配置 → fail-closed
  let argv: string[] = [NODE_PATH, RUNNER_PATH];
  if (opts.sandbox) {
    try {
      argv = await opts.sandbox.confine(argv, opts.policy);
    } catch (e) {
      if (e instanceof SandboxUnavailableError) {
        return { ok: false, error: { code: "ERR_EXECUTION", message: "SANDBOX_UNAVAILABLE" } };
      }
      throw e;
    }
  } else {
    return { ok: false, error: { code: "ERR_EXECUTION", message: "SANDBOX_UNAVAILABLE: sandbox provider required (fail-closed)" } };
  }

  return new Promise<ExecResult>((resolve) => {
    const child = spawn(argv[0], argv.slice(1), {
      stdio: ["pipe", "pipe", "pipe"],
      env: minimalEnv(opts.envWhitelist ?? {}),
    });

    const timer = setTimeout(() => {
      child.kill("SIGKILL");
    }, timeoutMs);

    let stdout = "";
    let stderr = "";
    let settled = false;

    const finish = (result: ExecResult) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve(result);
    };

    child.stdout.on("data", (c: Buffer) => {
      stdout += c.toString("utf8");
      if (stdout.length > maxBuffer) {
        child.kill("SIGKILL");
        finish({ ok: false, error: { code: "ERR_EXECUTION", message: "output overflow" } });
      }
    });
    child.stderr.on("data", (c: Buffer) => {
      stderr += c.toString("utf8");
    });
    child.on("error", (e) => finish({ ok: false, error: { code: "ERR_EXECUTION", message: `spawn failed: ${e.message}` } }));
    child.on("close", (code, signal) => {
      if (settled) return;
      if (signal === "SIGKILL") {
        finish({ ok: false, error: { code: "ERR_EXECUTION", message: "timeout" } });
        return;
      }
      if (code !== 0) {
        finish({ ok: false, error: { code: "ERR_EXECUTION", message: `exit ${code}: ${stderr.trim().slice(0, 500)}` } });
        return;
      }
      // 解析 stdout 契约
      let parsed: { ok?: boolean; data?: unknown; error?: { code?: string; message?: string } };
      try {
        parsed = JSON.parse(stdout);
      } catch {
        finish({ ok: false, error: { code: "ERR_EXECUTION", message: `invalid runner output: ${stdout.slice(0, 200)}` } });
        return;
      }
      if (parsed.ok === true) {
        finish({ ok: true, data: parsed.data });
      } else {
        finish({ ok: false, error: { code: parsed.error?.code ?? "ERR_EXECUTION", message: parsed.error?.message ?? "runner error" } });
      }
    });

    child.stdin.write(JSON.stringify(req));
    child.stdin.end();
  });
}
