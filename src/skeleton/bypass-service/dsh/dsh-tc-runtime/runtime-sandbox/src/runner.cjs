/**
 * runner.js——受限子进程执行面（Phase 3 雏形，独立 CJS 脚本）
 *
 * 协议（stdin/stdout JSON，对齐 tc `js_bridge.py` 实测契约 + 功能设计 §4.3）：
 *   stdin : {"domain","action","params","handlerPath"}
 *   stdout: {"ok":true,"data":<handler 返回>} | {"ok":false,"error":{"code","message"}}
 *
 * 沙箱模型（裸开发层）：
 * - 子进程隔离：包 handler 在独立进程运行，不共享宿主内存/上下文
 * - env 最小化：spawn 侧只注入白名单 env（本脚本读 process.env 时只能看到注入值）
 * - 文件效果/网络隔离：由宿主侧 dsh `ctx.sandbox.confine` 包裹 spawn（ubuntu 联调接入，
 *   见 executor.ts 的 SandboxProvider）；本 runner 不提供额外拦截
 * - handler 形态兼容：声明式 {directives:{action:{handler}}} / 函数式 exports[action]
 */
"use strict";

let input = "";
process.stdin.on("data", (chunk) => {
  input += chunk;
  if (input.length > 1_000_000) {
    process.stdout.write(JSON.stringify({ ok: false, error: { code: "ERR_EXECUTION", message: "stdin overflow" } }));
    process.exit(0);
  }
});

function reply(obj) {
  process.stdout.write(JSON.stringify(obj));
}

process.stdin.on("end", () => {
  let req;
  try {
    req = JSON.parse(input || "{}");
  } catch (e) {
    reply({ ok: false, error: { code: "INVALID_PARAMS", message: `bad request json: ${e.message}` } });
    return;
  }

  const { domain, action, params, handlerPath } = req;
  if (!handlerPath || typeof action !== "string") {
    reply({ ok: false, error: { code: "INVALID_PARAMS", message: "missing handlerPath/action" } });
    return;
  }

  let handlerMod;
  try {
    // 裸 require——沙箱接管点在宿主侧 confine（ubuntu 联调），本层保持契约稳定
    handlerMod = require(handlerPath);
  } catch (e) {
    reply({ ok: false, error: { code: "ERR_EXECUTION", message: `load handler failed: ${e.message}` } });
    return;
  }

  let handler = null;
  if (handlerMod && typeof handlerMod === "object") {
    if (handlerMod.directives && handlerMod.directives[action]) {
      handler = handlerMod.directives[action].handler;
    } else if (typeof handlerMod[action] === "function") {
      handler = handlerMod[action];
    }
  }
  if (typeof handler !== "function") {
    reply({ ok: false, error: { code: "ERR_NOT_FOUND", message: `no handler for action: ${action}` } });
    return;
  }

  try {
    Promise.resolve(handler(params || [], { domain } /* context 平台注入点（Phase 5 凭据） */))
      .then((data) => reply({ ok: true, data: data ?? null }))
      .catch((e) => reply({ ok: false, error: { code: "ERR_EXECUTION", message: e instanceof Error ? e.message : String(e) } }));
  } catch (e) {
    reply({ ok: false, error: { code: "ERR_EXECUTION", message: e instanceof Error ? e.message : String(e) } });
  }
});
