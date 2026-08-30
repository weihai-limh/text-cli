// endpoints — Worker 端点表面（对齐 SPEC §1.2，方案 A 补全）
//
//   POST /text-cli/cli           主指令入口（Service-token）
//   GET  /text-cli/tasks/{id}    异步任务五态查询（Service-token）
//   GET  /text-cli/skills        公开技能列表（service_manifest 白名单）
//   GET  /text-cli/health        健康检查（公开层）+ mechanism 声明
//   GET  /text-cli/health?auth=1 鉴权层完整 capabilities（Service-token）
//   GET  /text-cli/cli?prompt=   GET 应急通道（默认关 → 404）

function json(status, obj) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function bearerToken(headers) {
  const get = (k) => (typeof headers.get === "function" ? headers.get(k) : headers[k]);
  const st = get("service-token") || get("Service-Token");
  if (st) return st;
  const authz = get("authorization") || get("Authorization");
  if (authz && authz.startsWith("Bearer ")) return authz.slice(7);
  return undefined;
}

export function createEndpoints(rt) {
  async function handleCli(request) {
    const token = bearerToken(request.headers);
    const verify = await rt.auth.verify(token).catch(() => null);
    if (!verify) {
      return json(401, { rst_types: "text", rst_err: "SERVICE_DENIED", rst_data: { reason: "missing or invalid service token" } });
    }
    const body = await request.json().catch(() => null);
    const prompt = body && body.prompt;
    if (!prompt) return json(400, { rst_types: "text", rst_err: "INVALID_PARAMS", rst_data: { reason: "prompt required" } });
    const result = await rt.run(prompt, { headers: request.headers, token, auth: verify });
    return json(200, result);
  }

  async function handleHealth(request, url) {
    const base = {
      status: "ok",
      body: "textcli-cloudflare",
      version: rt.VERSION,
      spec_version: rt.SPEC_VERSION,
      public_skills: (await rt.buildDirectives()).map((d) => `${d.domain};${d.action}`),
    };
    if (url.searchParams.has("auth")) {
      const token = bearerToken(request.headers);
      const verify = await rt.auth.verify(token).catch(() => null);
      if (!verify) return json(401, { rst_types: "text", rst_err: "SERVICE_DENIED", rst_data: { reason: "invalid service token" } });
      return json(200, {
        ...base,
        capabilities: {
          mechanisms: rt.MECHANISMS,
          package_lifecycle: true,
          path: true,
          mesh: true,
          async: true,
          auth: true,
        },
      });
    }
    return json(200, base);
  }

  async function handleSkills() {
    // service_manifest 白名单（暂定 {} 全开）；暴露面只做输出过滤，不兼作执行准入
    const row = await rt.db.prepare("SELECT public_directives FROM service_manifest WHERE id = 1").first();
    const whitelist = row ? JSON.parse(row.public_directives) : {};
    const all = await rt.buildDirectives();
    const keys = Object.keys(whitelist || {});
    const directives = keys.length ? all.filter((d) => keys.includes(`${d.domain};${d.action}`)) : all;
    return json(200, { status: "ok", directives });
  }

  async function handleTaskQuery(request, pathname) {
    const token = bearerToken(request.headers);
    const verify = await rt.auth.verify(token).catch(() => null);
    if (!verify) return json(401, { rst_types: "text", rst_err: "SERVICE_DENIED", rst_data: { reason: "missing or invalid service token" } });
    const taskId = decodeURIComponent(pathname.slice("/text-cli/tasks/".length));
    const task = await rt.pollTask(taskId);
    if (task.state === "not_found") {
      return json(404, { rst_types: "text", rst_err: "ERR_NOT_FOUND", rst_data: { reason: "not_found" } });
    }
    return json(200, { status: "ok", task });
  }

  return async function handle(request) {
    const url = new URL(request.url);
    const p = url.pathname;
    if (p === "/text-cli/cli") {
      if (request.method === "POST") return handleCli(request);
      if (request.method === "GET") {
        // GET 应急通道默认关（显式开启才可用）
        return json(404, { rst_types: "text", rst_err: "ERR_NOT_FOUND", rst_data: { reason: "get fallback disabled" } });
      }
      return json(405, { rst_types: "text", rst_err: "ERR_NOT_FOUND", rst_data: { reason: "method not allowed" } });
    }
    if (p === "/text-cli/health") return handleHealth(request, url);
    if (p === "/text-cli/skills") return handleSkills();
    if (p.startsWith("/text-cli/tasks/")) return handleTaskQuery(request, p);
    return json(404, { rst_types: "text", rst_err: "ERR_NOT_FOUND", rst_data: { reason: "not found" } });
  };
}
