import { describe, expect, it } from "vitest";
import {
  buildDirectives,
  formatQuery,
  searchDirectives,
  toolSchemaToDirective,
  type ToolSchema,
} from "../src/dshToTc.js";

const schemas: ToolSchema[] = [
  {
    name: "tc__tc-math__eval",
    description: "Evaluate arithmetic expression",
    tc: {
      domain: "tc-math",
      action: "eval",
      package: "tc-math",
      runtime: "js",
      domain_zh: "数学工具",
      action_zh: "计算",
      usage: "tc-math;eval,<expr>",
      usage_zh: "数学工具;计算,<表达式>",
      params: ["expr"],
    },
  },
  {
    name: "tc__weather__query",
    description: "Query weather",
    tc: { domain: "weather", action: "query", package: "weather", runtime: "js" },
  },
  // MCP 桥工具（无 tc 元数据）——不应进入发现契约（Phase 11 转化链处理）
  { name: "mcp__server__tool", description: "MCP bridged tool" },
];

describe("toolSchemaToDirective", () => {
  it("带 tc 元数据 → canonical 条目（强制 domain/action + 可选增强）", () => {
    const entry = toolSchemaToDirective(schemas[0]);
    expect(entry).not.toBeNull();
    expect(entry).toMatchObject({
      domain: "tc-math",
      action: "eval",
      package: "tc-math",
      runtime: "js",
      domain_zh: "数学工具",
      usage: "tc-math;eval,<expr>",
      params: ["expr"],
    });
  });

  it("无 tc 元数据（MCP 桥）→ null（不推断，防错误契约）", () => {
    expect(toolSchemaToDirective(schemas[2])).toBeNull();
  });

  it("最小 tc 元数据 → 仅强制字段（无可选增强）", () => {
    const minimal: ToolSchema = {
      name: "tc__bare__act",
      tc: { domain: "bare", action: "act" },
    };
    expect(toolSchemaToDirective(minimal)).toEqual({ domain: "bare", action: "act" });
  });
});

describe("buildDirectives", () => {
  it("过滤非 tc 工具 + 按包排序", () => {
    const dirs = buildDirectives(schemas);
    expect(dirs).toHaveLength(2);
    expect(dirs[0].domain).toBe("tc-math"); // 按包排序（tc-math < weather）
    expect(dirs[1].domain).toBe("weather");
  });
});

describe("formatQuery：五模式（SPEC §1.2.7）", () => {
  const dirs = buildDirectives(schemas);

  it("json 模式：directives 容器 + 全量 locale 变体", () => {
    const out = formatQuery(dirs, { mode: "json" }) as { directives: Record<string, unknown>[] };
    expect(Array.isArray(out.directives)).toBe(true);
    expect(out.directives).toHaveLength(2);
    // canonical + locale 变体同返，服务端不做单语选择
    expect(out.directives[0]).toMatchObject({
      domain: "tc-math",
      action: "eval",
      domain_zh: "数学工具",
      usage: "tc-math;eval,<expr>",
      usage_zh: "数学工具;计算,<表达式>",
    });
    // usage 不含 AI: 前缀（前缀约定）
    expect(out.directives[0].usage).not.toMatch(/^AI:/);
  });

  it("compact 模式：每行 domain;action", () => {
    const out = formatQuery(dirs, { mode: "compact" }) as string;
    expect(out.split("\n")).toEqual(["tc-math;eval", "weather;query"]);
  });

  it("compact + zh：别名输出", () => {
    const out = formatQuery(dirs, { mode: "compact", lang: "zh" }) as string;
    expect(out.split("\n")[0]).toBe("数学工具;计算");
  });

  it("text 模式：按包分组纯文本", () => {
    const out = formatQuery(dirs, { mode: "text" }) as string;
    expect(out).toContain("# tc-math");
    expect(out).toContain("tc-math;eval");
    expect(out).toContain("# weather");
  });

  it("keyword 模式：模糊搜索 domain/action/description", () => {
    const out = formatQuery(dirs, { mode: "keyword", keyword: "weather" }) as string;
    expect(out.split("\n").join(" ")).toContain("weather;query");
    const zh = formatQuery(dirs, { mode: "keyword", keyword: "数学" }) as string;
    expect(zh).toContain("tc-math;eval");
  });

  it("空结果视为成功：directives: []（json）/ 空文本", () => {
    expect(formatQuery([], { mode: "json" })).toEqual({ directives: [] });
    expect(formatQuery([], { mode: "text" })).toBe("");
  });
});

describe("searchDirectives", () => {
  const dirs = buildDirectives(schemas);
  it("按中文别名搜索", () => {
    expect(searchDirectives(dirs, "数学")).toHaveLength(1);
  });
});
