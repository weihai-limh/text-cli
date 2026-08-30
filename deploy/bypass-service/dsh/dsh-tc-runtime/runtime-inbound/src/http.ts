/**
 * Phase 1-2 HTTP 入口（测试服务器）——协议端点表面（SPEC §1.2）
 *
 * - POST /text-cli/cli——主入站（六段管道）
 * - GET  /text-cli/health——健康检查（spec_version + mechanism）
 * - GET  /text-cli/skills——公开技能列表（public_directives 白名单）
 * - GET  /text-cli/tasks/{task_id}——异步任务查询（404 + not_found 语义）
 * - GET  /text-cli/cli?prompt=——应急通道，默认关闭（404）
 *
 * node:http 最小实现；Phase 2+ 接入 dsh `ctx.webServer` 注册路由时替换本层
 * （处理器函数与 deps 注入保持不变，仅换挂载面）。
 */
import http from "node:http";
import { handlePrompt, type HandlerDeps, type Envelope } from "./handler.js";
import { handleHealth, handleSkills, handleTaskQuery, type TaskQueryDeps, type HealthInfo } from "./endpoints.js";
import type { DirectiveEntry } from "@dsh-tc/runtime-mapper";

export interface TcServerOptions {
  host?: string;
  port?: number;
  health?: HealthInfo;
  /** skills 白名单（service_manifest.public_directives；空 = 全暴露） */
  skillsWhitelist?: string[];
  /** skills 数据源（directives） */
  skillsDirectives?: DirectiveEntry[];
  /** 任务读取器（Phase 10 接 ctx.jobs） */
  tasks?: TaskQueryDeps;
}

export interface TcServer {
  close(): Promise<void>;
  port(): number;
}

export function createTcServer(
  deps: HandlerDeps,
  opts: TcServerOptions = {},
): TcServer {
  const host = opts.host ?? "127.0.0.1";
  const port = opts.port ?? 0;
  const healthInfo: HealthInfo = opts.health ?? { version: "0.1.1", spec_version: "1.3.2" };

  const json = (res: http.ServerResponse, status: number, body: unknown) => {
    res.writeHead(status, { "Content-Type": "application/json" });
    res.end(JSON.stringify(body));
  };

  const server = http.createServer((req, res) => {
    const url = new URL(req.url ?? "/", `http://${host}`);

    // POST /text-cli/cli——主入站
    if (req.method === "POST" && url.pathname === "/text-cli/cli") {
      let body = "";
      req.on("data", (chunk) => {
        body += chunk;
        if (body.length > 64 * 1024) req.destroy();
      });
      req.on("end", async () => {
        try {
          const parsed = JSON.parse(body || "{}") as { prompt?: unknown };
          const prompt = typeof parsed.prompt === "string" ? parsed.prompt : "";
          const envelope: Envelope = await handlePrompt(prompt, deps);
          json(res, 200, envelope);
        } catch {
          json(res, 400, { rst_types: "text", rst_data: { status: "error", reason: "bad_request" }, rst_err: "INVALID_PARAMS" });
        }
      });
      return;
    }

    // GET /text-cli/health
    if (req.method === "GET" && url.pathname === "/text-cli/health") {
      json(res, 200, handleHealth(healthInfo));
      return;
    }

    // GET /text-cli/skills
    if (req.method === "GET" && url.pathname === "/text-cli/skills") {
      const directives = opts.skillsDirectives ?? [];
      json(res, 200, handleSkills(directives, opts.skillsWhitelist ?? []));
      return;
    }

    // GET /text-cli/tasks/{task_id}
    const tasksMatch = /^\/text-cli\/tasks\/([^/]+)$/.exec(url.pathname);
    if (req.method === "GET" && tasksMatch && opts.tasks) {
      handleTaskQuery(decodeURIComponent(tasksMatch[1]), opts.tasks)
        .then((env) => {
          if (env) json(res, 200, env);
          else json(res, 404, { rst_types: "text", rst_data: { status: "error", reason: "not_found" }, rst_err: "not_found" });
        })
        .catch(() => json(res, 500, { rst_types: "text", rst_data: { status: "error", reason: "internal" }, rst_err: "ERR_EXECUTION" }));
      return;
    }

    // 其他（含 GET /text-cli/cli?prompt= 应急通道默认关闭）
    json(res, 404, { rst_types: "text", rst_data: { status: "error", reason: "not_found" }, rst_err: "ERR_NOT_FOUND" });
  });

  server.listen(port, host);

  return {
    close: () => new Promise((resolve) => server.close(() => resolve())),
    port: () => {
      const addr = server.address();
      return typeof addr === "object" && addr ? addr.port : 0;
    },
  };
}
