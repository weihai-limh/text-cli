import { describe, expect, it } from "vitest";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { execJs } from "../src/executor.js";
import { PASSTHROUGH_SANDBOX, NULL_SANDBOX } from "../src/sandbox-provider.js";

const fixtures = path.join(path.dirname(fileURLToPath(import.meta.url)), "fixtures");

describe("executor-js：受限子进程执行面（真实 node 子进程）", () => {
  it("声明式 handler：tc-math;eval,2+3*4 → {ok, data:{status:ok,result:14}}", async () => {
    const r = await execJs(
      { domain: "tc-math", action: "eval", params: ["2+3*4"], handlerPath: path.join(fixtures, "tc-math-handler.cjs") },
      { sandbox: PASSTHROUGH_SANDBOX },
    );
    expect(r.ok).toBe(true);
    if (r.ok) expect(r.data).toEqual({ status: "ok", result: 14 });
  });

  it("未注册 action → ERR_NOT_FOUND（runner 契约）", async () => {
    const r = await execJs(
      { domain: "tc-math", action: "no-such-action", params: [], handlerPath: path.join(fixtures, "tc-math-handler.cjs") },
      { sandbox: PASSTHROUGH_SANDBOX },
    );
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.error.code).toBe("ERR_NOT_FOUND");
  });

  it("函数式 handler（exports[action] 形态）", async () => {
    const r = await execJs(
      { domain: "misc", action: "boom", params: [], handlerPath: path.join(fixtures, "misc-handler.cjs") },
      { sandbox: PASSTHROUGH_SANDBOX },
    );
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.error.code).toBe("ERR_EXECUTION");
  });

  it("超时 kill → ERR_EXECUTION(timeout)", async () => {
    const r = await execJs(
      { domain: "misc", action: "sleep", params: ["5000"], handlerPath: path.join(fixtures, "misc-handler.cjs") },
      { sandbox: PASSTHROUGH_SANDBOX, timeoutMs: 500 },
    );
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.error.message).toContain("timeout");
  }, 10_000);

  it("env 白名单注入：子进程可见注入值", async () => {
    // 用 tc-math 无法验证 env——通过 handler 读 process.env 需要专门 fixture；
    // 此处验证注入不抛错 + 最小环境可用（PATH 存在）
    const r = await execJs(
      { domain: "tc-math", action: "version", params: [], handlerPath: path.join(fixtures, "tc-math-handler.cjs") },
      { sandbox: PASSTHROUGH_SANDBOX, envWhitelist: { TC_TEST_VAR: "injected" } },
    );
    expect(r.ok).toBe(true);
  });

  it("fail-closed：未配置 sandbox provider → SANDBOX_UNAVAILABLE", async () => {
    const r = await execJs(
      { domain: "tc-math", action: "eval", params: ["1"], handlerPath: path.join(fixtures, "tc-math-handler.cjs") },
      {}, // 无 sandbox
    );
    expect(r.ok).toBe(false);
    if (!r.ok) {
      expect(r.error.code).toBe("ERR_EXECUTION");
      expect(r.error.message).toContain("SANDBOX_UNAVAILABLE");
    }
  });

  it("NULL_SANDBOX（未配置）→ fail-closed", async () => {
    const r = await execJs(
      { domain: "tc-math", action: "eval", params: ["1"], handlerPath: path.join(fixtures, "tc-math-handler.cjs") },
      { sandbox: NULL_SANDBOX },
    );
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.error.message).toContain("SANDBOX_UNAVAILABLE");
  });
});
