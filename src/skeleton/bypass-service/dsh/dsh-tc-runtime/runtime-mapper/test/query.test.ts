import { describe, expect, it } from "vitest";
import { handleQuery, parseQueryArgs } from "../src/query.js";
import { buildDirectives, type ToolSchema } from "../src/dshToTc.js";

const schemas: ToolSchema[] = [
  {
    name: "tc__tc-math__eval",
    description: "Evaluate arithmetic expression",
    tc: { domain: "tc-math", action: "eval", package: "tc-math", runtime: "js", domain_zh: "数学工具", action_zh: "计算" },
  },
  {
    name: "tc__weather__query",
    description: "Query weather",
    tc: { domain: "weather", action: "query", package: "weather", runtime: "js" },
  },
];
const directives = buildDirectives(schemas);

describe("parseQueryArgs：query 参数解析", () => {
  it("无参 → text 模式", () => {
    expect(parseQueryArgs([])).toEqual({ mode: "text", keyword: undefined, lang: undefined });
  });
  it("json → json 模式", () => {
    expect(parseQueryArgs(["json"]).mode).toBe("json");
  });
  it("compact → compact 模式", () => {
    expect(parseQueryArgs(["compact"]).mode).toBe("compact");
  });
  it("关键词 → keyword 模式", () => {
    expect(parseQueryArgs(["weather"]).mode).toBe("keyword");
    expect(parseQueryArgs(["weather"]).keyword).toBe("weather");
  });
  it("尾参 zh/en → lang", () => {
    expect(parseQueryArgs(["json", "zh"]).lang).toBe("zh");
    expect(parseQueryArgs(["compact", "en"]).lang).toBe("en");
  });
  it("runtime 过滤词（可选能力）不报错、不改变模式", () => {
    expect(parseQueryArgs(["js"]).mode).toBe("text");
  });
});

describe("handleQuery：text-cli;query → 发现契约信封", () => {
  it("query,json → directives[] canonical（rst_err 空）", () => {
    const env = handleQuery(["json"], { directives });
    expect(env.rst_err).toBe("");
    const data = env.rst_data as { directives: unknown[] };
    expect(Array.isArray(data.directives)).toBe(true);
    expect(data.directives).toHaveLength(2);
  });
  it("query,compact → 每行 domain;action", () => {
    const env = handleQuery(["compact"], { directives });
    expect(env.rst_data).toBe("tc-math;eval\nweather;query");
  });
  it("query,weather → 关键词搜索", () => {
    const env = handleQuery(["weather"], { directives });
    expect(env.rst_data).toContain("weather;query");
  });
  it("query,json,zh → 全量 locale 变体", () => {
    const env = handleQuery(["json", "zh"], { directives });
    const data = env.rst_data as { directives: Array<Record<string, unknown>> };
    expect(data.directives[0].domain_zh).toBe("数学工具");
  });
  it("空结果视为成功（rst_err 空，directives: []）", () => {
    const env = handleQuery(["json"], { directives: [] });
    expect(env.rst_err).toBe("");
    expect(env.rst_data).toEqual({ directives: [] });
  });
});
