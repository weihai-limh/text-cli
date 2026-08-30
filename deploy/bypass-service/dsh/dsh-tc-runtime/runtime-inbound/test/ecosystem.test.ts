/**
 * runtime-inbound 入站生态归属分流测试（P8）
 * 覆盖：单指令归属分类、多步 path 归属（全 dsh/全 tc/混合）、route 注入分流。
 */
import { describe, expect, it } from "vitest";
import { classifyDomain, classifyDirective, classifyPathOwnership } from "../src/ecosystem.js";
import { handlePrompt, type DispatchFn } from "../src/handler.js";

describe("classifyDomain：单指令域生态归属", () => {
  it("dsh 宿主域 → dsh", () => {
    expect(classifyDomain("dsh-sandbox")).toBe("dsh");
    expect(classifyDomain("dsh-approval")).toBe("dsh");
    expect(classifyDomain("dsh-credential")).toBe("dsh");
  });

  it("tc 指令包域 → tc", () => {
    expect(classifyDomain("tc-math")).toBe("tc");
    expect(classifyDomain("tc-weather")).toBe("tc");
  });

  it("未知域 → unknown", () => {
    expect(classifyDomain("custom-app")).toBe("unknown");
    expect(classifyDomain("")).toBe("unknown");
  });
});

describe("classifyDirective：未知域默认 tc（开放注册）", () => {
  it("未知域归为 tc", () => {
    expect(classifyDirective("custom-app")).toBe("tc");
    expect(classifyDirective("dsh-sandbox")).toBe("dsh");
    expect(classifyDirective("tc-math")).toBe("tc");
  });
});

describe("classifyPathOwnership：多步 path 归属", () => {
  it("全 dsh → dsh", () => {
    expect(classifyPathOwnership(["dsh-sandbox", "dsh-approval"])).toBe("dsh");
  });

  it("全 tc → tc", () => {
    expect(classifyPathOwnership(["tc-math", "tc-weather"])).toBe("tc");
    expect(classifyPathOwnership(["custom-app"])).toBe("tc");
  });

  it("混合 → mixed", () => {
    expect(classifyPathOwnership(["tc-math", "dsh-approval"])).toBe("mixed");
  });

  it("空 → tc（保守默认）", () => {
    expect(classifyPathOwnership([])).toBe("tc");
  });
});

describe("handler 的 route 注入分流（P8）", () => {
  it("route 返回非 null → 走分流分支，不触发 dispatch", async () => {
    const dispatch: DispatchFn = async () => {
      throw new Error("should not be called");
    };
    const env = await handlePrompt("AI:tc-math;eval,1+1", {
      dispatch,
      route: async () => ({ rst_types: "text", rst_data: { status: "ok", routed: true }, rst_err: "" }),
    });
    expect(env.rst_err).toBe("");
    expect((env.rst_data as { routed?: boolean }).routed).toBe(true);
  });

  it("route 返回 null → 走默认统一 dispatch", async () => {
    let dispatched = false;
    const dispatch: DispatchFn = async () => { dispatched = true; return { status: "ok", result: "ok" }; };
    const env = await handlePrompt("AI:tc-math;eval,1+1", {
      dispatch,
      route: async () => null,
    });
    expect(dispatched).toBe(true);
    expect(env.rst_err).toBe("");
  });
});
