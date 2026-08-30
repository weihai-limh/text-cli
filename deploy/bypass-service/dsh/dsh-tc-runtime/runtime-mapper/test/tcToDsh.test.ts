import { describe, expect, it } from "vitest";
import { tcToDsh, normalizeName } from "../src/tcToDsh.js";

describe("tcToDsh：tc 指令 → dsh 工具调用映射", () => {
  it("AI: 前缀解析 + 工具名映射", () => {
    const r = tcToDsh("AI:tc-math;eval,2+3*4");
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.domain).toBe("tc-math");
    expect(r.action).toBe("eval");
    expect(r.params).toEqual(["2+3*4"]);
    expect(r.input.name).toBe("tc__tc-math__eval");
    expect(r.input.arguments).toEqual({ params: ["2+3*4"] });
    expect(r.input.callId).toMatch(/^tc-\d+-\d+$/);
  });

  it("指令: 前缀等效（过渡期双前缀）", () => {
    const r = tcToDsh("指令:tc-math;eval,1+1");
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.domain).toBe("tc-math");
    expect(r.params).toEqual(["1+1"]);
  });

  it("末位参数自由文本（含逗号）", () => {
    const r = tcToDsh("AI:web;search,北京,上海的天气,zh");
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.params).toEqual(["北京", "上海的天气", "zh"]);
  });

  it("callId 可注入（幂等/重放场景）", () => {
    const r = tcToDsh("AI:tc-math;eval,1", { callId: "fixed-001" });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.input.callId).toBe("fixed-001");
  });

  it("别名域映射（小写连字符规范化）", () => {
    const r = tcToDsh("AI:Weather API;Query,beijing");
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.input.name).toBe("tc__weather-api__query");
  });
});

describe("normalizeName", () => {
  it("小写 + 空格转连字符", () => {
    expect(normalizeName("  Weather  API ")).toBe("weather-api");
    expect(normalizeName("JSON")).toBe("json");
  });
});
