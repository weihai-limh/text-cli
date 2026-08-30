import { describe, it, expect, vi } from "vitest";
import {
  mcpToolName,
  adaptParams,
  toDirective,
  registerMcpTool,
  McpBridge,
} from "../src/index.js";
import type { McpToolDef } from "../src/index.js";

describe("mcpToolName（§10.1 双下划线模式）", () => {
  it("生成 mcp__<server>__<tool>", () => {
    expect(mcpToolName("web", "search")).toBe("mcp__web__search");
  });
});

describe("adaptParams —— passthrough（按 param_names 顺序映射）", () => {
  const def: McpToolDef = { server: "web", tool: "search", paramNames: ["q", "n"] };

  it("args[name] = params[i]", () => {
    expect(adaptParams(def, ["keyword", "5"])).toEqual({ q: "keyword", n: "5" });
  });

  it("参数声明缺失 → {_params: params} 兜底", () => {
    const noDecl: McpToolDef = { server: "web", tool: "search" };
    expect(adaptParams(noDecl, ["a", "b"])).toEqual({ _params: ["a", "b"] });
  });

  it("params 短于 paramNames → 多余 name 为 undefined（不抛）", () => {
    expect(adaptParams(def, ["only"])).toEqual({ q: "only", n: undefined });
  });
});

describe("adaptParams —— json_parse", () => {
  const def: McpToolDef = { server: "web", tool: "search", adapter: "json_parse" };

  it("首参 JSON.parse → 对象", () => {
    expect(adaptParams(def, ['{"q":"hi","n":3}'])).toEqual({ q: "hi", n: 3 });
  });

  it("首参失败 → 逗号重组 join(params) 再 parse", () => {
    // 单引号非法 JSON → 失败后 join(",") 仍非法 → 落到 _raw
    expect(adaptParams(def, ["a", "b"])).toEqual({ _raw: "a" });
  });

  it("params 空 → 返回空对象", () => {
    expect(adaptParams(def, [])).toEqual({});
  });
});

describe("toDirective / registerMcpTool（平权 directive）", () => {
  it("生成 {name, domain:mcp, action:<server>__<tool>}", () => {
    const d = toDirective({ server: "web", tool: "search", description: "search web" });
    expect(d).toEqual({
      name: "mcp__web__search",
      domain: "mcp",
      action: "web__search",
      usage: "search web",
    });
  });

  it("registerMcpTool 调用注入的 register 回调（name + def）", () => {
    const register = vi.fn();
    registerMcpTool({ server: "web", tool: "search" }, register);
    expect(register).toHaveBeenCalledWith("mcp__web__search", expect.objectContaining({ server: "web", tool: "search" }));
  });
});

describe("McpBridge 收集器（挂载 → directives[] 平权发现）", () => {
  it("mount 多个 tool → directivesList 全量平权", () => {
    const register = vi.fn();
    const bridge = new McpBridge(register);
    bridge.mountAll([
      { server: "web", tool: "search" },
      { server: "img", tool: "gen", adapter: "json_parse" },
    ]);
    const list = bridge.directivesList();
    expect(list.map((d) => d.name)).toEqual(["mcp__web__search", "mcp__img__gen"]);
    expect(register).toHaveBeenCalledTimes(2);
  });

  it("mount 返回的 directive 与 toDirective 一致", () => {
    const bridge = new McpBridge();
    const d = bridge.mount({ server: "x", tool: "y" });
    expect(d).toEqual(toDirective({ server: "x", tool: "y" }));
  });
});
