import { describe, expect, it } from "vitest";
import { handlePrompt } from "../src/handler.js";
import { createMockDispatch } from "../src/mock.js";

const deps = { dispatch: createMockDispatch() };

describe("handlePrompt：六段管道（Phase 1 mock 直通）", () => {
  it("AI:tc-math;eval,2+3*4 → 信封 {rst_types, rst_data:{status:ok,result:14}, rst_err:''}", async () => {
    const env = await handlePrompt("AI:tc-math;eval,2+3*4", deps);
    expect(env.rst_err).toBe("");
    expect(env.rst_types).toBe("text");
    expect(env.rst_data).toEqual({ status: "ok", result: 14 });
  });

  it("指令: 前缀等效", async () => {
    const env = await handlePrompt("指令:tc-math;eval,1+1", deps);
    expect(env.rst_err).toBe("");
    expect(env.rst_data).toEqual({ status: "ok", result: 2 });
  });

  it("tc-datetime;now → mock 纯函数", async () => {
    const env = await handlePrompt("AI:tc-datetime;now", deps);
    expect(env.rst_err).toBe("");
    expect(env.rst_data).toMatchObject({ status: "ok" });
  });

  it("未知指令 → ERR_NOT_FOUND（闭集）", async () => {
    const env = await handlePrompt("AI:no-such-domain;foo,1", deps);
    expect(env.rst_err).toBe("ERR_NOT_FOUND");
    expect(env.rst_data).toMatchObject({ status: "error" });
  });

  it("text-cli 保留域拦截（Phase 7 前占位）→ ERR_NOT_FOUND", async () => {
    const env = await handlePrompt("AI:text-cli;query", deps);
    expect(env.rst_err).toBe("ERR_NOT_FOUND");
  });

  it("执行异常 → ERR_EXECUTION（闭集；0/0 = NaN 触发 mock 夹具拒绝）", async () => {
    const env = await handlePrompt("AI:tc-math;eval,0/0", deps);
    expect(env.rst_err).toBe("ERR_EXECUTION");
  });

  it("危险表达式被 mock 夹具拒绝（沙箱未接入，红线③兼容）", async () => {
    const env = await handlePrompt("AI:tc-math;eval,process.exit()", deps);
    expect(env.rst_err).toBe("ERR_EXECUTION");
  });

  it("pray_rst_types 提升（复用 envelope.js）", async () => {
    const env = await handlePrompt("AI:tc-math;eval,1", {
      dispatch: async () => ({ status: "ok", url: "https://x/y.png", pray_rst_types: "picture" }),
    });
    expect(env.rst_types).toBe("picture");
    expect(env.rst_data).not.toHaveProperty("pray_rst_types");
  });
});
