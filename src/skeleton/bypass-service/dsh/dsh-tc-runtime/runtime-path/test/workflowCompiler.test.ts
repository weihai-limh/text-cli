/**
 * runtime-path workflow 编译器测试（P9）
 * 覆盖：call/sequence/parallel 无损翻译、map/if/http_dispatch/delegated 有损标注。
 */
import { describe, expect, it } from "vitest";
import { compileToWorkflow } from "../src/workflowCompiler.js";
import type { PathDef } from "../src/types.js";

const def = (steps: PathDef["steps"]): PathDef => ({ name: "p", steps });

describe("语义同构 step：无损翻译", () => {
  it("call → run(domain, action, params)", () => {
    const { script, losses } = compileToWorkflow(def([{ domain: "tc-math", action: "eval", params: ["1+1"] }]));
    expect(script).toContain('run("tc-math", "eval", ["1+1"])');
    expect(losses).toHaveLength(0);
  });

  it("sequence → pipeline", () => {
    const { script, losses } = compileToWorkflow(def([
      { type: "sequence", steps: [{ domain: "a", action: "x" }, { domain: "b", action: "y" }] },
    ]));
    expect(script).toContain("pipeline");
    expect(losses).toHaveLength(0);
  });

  it("parallel → parallel(thunks, {strategy})", () => {
    const { script, losses } = compileToWorkflow(def([
      { type: "parallel", strategy: "first_ok", branches: [{ domain: "a", action: "x" }, { domain: "b", action: "y" }] },
    ]));
    expect(script).toContain("parallel");
    expect(script).toContain("first_ok");
    expect(losses).toHaveLength(0);
  });
});

describe("有损 step：显式标注（翻译纪律）", () => {
  it("http_dispatch → LOSSY 标注", () => {
    const { losses } = compileToWorkflow(def([{ type: "http_dispatch", node: "n1", domain: "a", action: "x" }]));
    expect(losses.some(l => l.step.startsWith("http_dispatch"))).toBe(true);
    expect(losses[0].reason).toContain("LOSSY");
  });

  it("map → LOSSY 标注（dsh 无一等 map hook）", () => {
    const { losses } = compileToWorkflow(def([
      { type: "map", over: "items", as: "item", step: { domain: "a", action: "x" } },
    ]));
    expect(losses.some(l => l.step.startsWith("map"))).toBe(true);
  });

  it("if → 条件映射标注 + then 编译", () => {
    const { script, losses } = compileToWorkflow(def([
      { type: "if", cond: { kind: "exists", expr: "x" }, then: { domain: "a", action: "x" } },
    ]));
    expect(script).toContain("evalCondition");
    expect(losses.some(l => l.step.startsWith("if"))).toBe(true);
  });

  it("delegated → LOSSY 标注", () => {
    const { losses } = compileToWorkflow(def([{ type: "delegated", domain: "a", action: "x" }]));
    expect(losses.some(l => l.step.startsWith("delegated"))).toBe(true);
  });
});

describe("翻译纪律", () => {
  it("有损项不得静默：losses 清单可查", () => {
    const { script, losses } = compileToWorkflow(def([
      { domain: "a", action: "ok" },
      { type: "http_dispatch", node: "n", domain: "b", action: "y" },
    ]));
    expect(losses.length).toBeGreaterThanOrEqual(1);
    // 无损失的部分仍生成可执行代码
    expect(script).toContain('run("a", "ok"');
  });
});
