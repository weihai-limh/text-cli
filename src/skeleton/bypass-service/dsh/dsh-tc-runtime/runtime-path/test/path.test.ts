import { describe, it, expect, vi } from "vitest";
import { runPath } from "../src/index.js";
import type { PathDeps } from "../src/index.js";

const tools: Record<string, (p: string[]) => unknown> = {
  "tc__greet__hi": (p) => ({ rst_err: "", rst_data: { msg: "hi " + (p[0] ?? "") } }),
  "tc__math__add": (p) => ({ rst_err: "", rst_data: { sum: Number(p[0]) + Number(p[1]) } }),
  "tc__math__double": (p) => ({ rst_err: "", rst_data: { v: Number(p[0]) * 2 } }),
  "tc__upper__go": (p) => ({ rst: "", rst_data: { out: String(p[0] ?? "").toUpperCase() } }),
  "tc__flaky__boom": () => ({ rst_err: "ERR_EXECUTION", rst_data: {} }),
};

function makeDeps(over: Partial<PathDeps> = {}): PathDeps {
  return {
    dispatch: vi.fn(async (domain: string, action: string, params: string[]) => {
      const fn = tools[`tc__${domain}__${action}`];
      if (!fn) return { rst_err: "ERR_NOT_FOUND", rst_data: {} };
      return fn(params);
    }),
    ...over,
  };
}

describe("runtime-path 引擎", () => {
  it("hello-chain：顺序 + 变量插值 {step.field}", async () => {
    const r = await runPath(
      {
        name: "hello-chain",
        steps: [
          { domain: "greet", action: "hi", params: ["bob"], name: "g" },
          { domain: "upper", action: "go", params: ["{g.rst_data.msg}"], name: "u" },
        ],
      },
      makeDeps(),
    );
    expect(r.ok).toBe(true);
    expect((r.steps["u"] as any).rst_data.out).toBe("HI BOB");
    expect(r.output).toBeDefined();
  });

  it("branch-demo：if 命中为真分支", async () => {
    const r = await runPath(
      {
        name: "branch-demo",
        steps: [
          { domain: "math", action: "add", params: ["2", "3"], name: "a" },
          {
            type: "if",
            cond: { kind: "equals", left: "{a.rst_data.sum}", right: "5" },
            then: { domain: "greet", action: "hi", params: ["ok"], name: "b" },
            else: { domain: "greet", action: "hi", params: ["no"], name: "b" },
          },
        ],
      },
      makeDeps(),
    );
    expect(r.ok).toBe(true);
    expect((r.steps["b"] as any).rst_data.msg).toBe("hi ok");
  });

  it("branch-demo：if 命中为假分支", async () => {
    const r = await runPath(
      {
        name: "branch-false",
        steps: [
          { domain: "math", action: "add", params: ["2", "3"], name: "a" },
          {
            type: "if",
            cond: { kind: "equals", left: "{a.rst_data.sum}", right: "99" },
            then: { domain: "greet", action: "hi", params: ["ok"], name: "b" },
            else: { domain: "greet", action: "hi", params: ["no"], name: "b" },
          },
        ],
      },
      makeDeps(),
    );
    expect((r.steps["b"] as any).rst_data.msg).toBe("hi no");
  });

  it("degrade-demo：主调用失败 → fallback 递补成功", async () => {
    const r = await runPath(
      {
        name: "degrade-demo",
        steps: [
          {
            domain: "flaky",
            action: "boom",
            params: ["1", "2"],
            name: "r",
            fallback: [{ domain: "math", action: "add" }],
          },
        ],
      },
      makeDeps(),
    );
    expect(r.ok).toBe(true);
    expect((r.steps["r"] as any).rst_data.sum).toBe(3);
  });

  it("degrade-demo：全部失败 → DEGRADE_EXHAUSTED", async () => {
    const r = await runPath(
      {
        name: "degrade-fail",
        steps: [
          {
            domain: "flaky",
            action: "boom",
            name: "r",
            fallback: [{ domain: "flaky", action: "boom" }],
          },
        ],
      },
      makeDeps(),
    );
    expect(r.ok).toBe(false);
    expect(r.error).toBe("DEGRADE_EXHAUSTED");
  });

  it("parallel-demo：first_ok 取到首个成功分支", async () => {
    const r = await runPath(
      {
        name: "parallel-first-ok",
        steps: [
          {
            type: "parallel",
            strategy: "first_ok",
            branches: [
              { domain: "flaky", action: "boom" },
              { domain: "math", action: "add", params: ["1", "1"], name: "ok" },
            ],
          },
        ],
      },
      makeDeps(),
    );
    expect(r.ok).toBe(true);
    expect((r.output as any).rst_data.sum).toBe(2);
  });

  it("parallel-demo：all 返回全部结果数组", async () => {
    const r = await runPath(
      {
        name: "parallel-all",
        steps: [
          {
            type: "parallel",
            strategy: "all",
            branches: [
              { domain: "math", action: "add", params: ["1", "1"] },
              { domain: "math", action: "add", params: ["2", "2"] },
            ],
          },
        ],
      },
      makeDeps(),
    );
    expect(r.ok).toBe(true);
    expect(Array.isArray(r.output)).toBe(true);
    expect((r.output as any[]).length).toBe(2);
  });

  it("map：遍历数组（enabled）", async () => {
    const r = await runPath(
      {
        name: "map-demo",
        steps: [
          { type: "map", over: "nums", as: "n", enabled: true, step: { domain: "math", action: "double", params: ["{n}"], name: "d" } },
        ],
      },
      makeDeps({ initialVars: { nums: ["1", "2", "3"] } }),
    );
    expect(r.ok).toBe(true);
    expect(Array.isArray(r.output)).toBe(true);
    expect((r.output as any[]).map((x: any) => x.rst_data.v)).toEqual([2, 4, 6]);
  });

  it("map：默认关（enabled=false）→ 跳过 + 告警", async () => {
    const r = await runPath(
      {
        name: "map-disabled",
        steps: [
          { type: "map", over: "nums", as: "n", step: { domain: "math", action: "double", params: ["{n}"] } },
        ],
      },
      makeDeps(),
    );
    expect(r.ok).toBe(true);
    expect(r.warnings.some((w) => w.includes("skipped"))).toBe(true);
  });

  it("http_dispatch：跨节点取 rst_data", async () => {
    const httpDispatch = vi.fn(async (_node: string, _d: string, _a: string, p: string[]) => ({
      rst_err: "",
      rst_data: { node: "remote", got: p },
    }));
    const r = await runPath(
      {
        name: "http-dispatch",
        steps: [{ type: "http_dispatch", node: "peer1", domain: "math", action: "add", params: ["1", "2"] }],
      },
      makeDeps({ httpDispatch }),
    );
    expect(r.ok).toBe(true);
    expect((r.output as any).got).toEqual(["1", "2"]);
  });

  it("delegated：无匹配指令非 error", async () => {
    const r = await runPath(
      {
        name: "delegated",
        steps: [{ type: "delegated", domain: "ghost", action: "x", params: [] }],
      },
      makeDeps(),
    );
    expect(r.ok).toBe(true);
    expect((r.output as any).delegated).toBe(false);
  });

  it("嵌套深度 > 2 → NESTING_EXCEEDED", async () => {
    const deep = (): any => ({
      type: "parallel",
      strategy: "all",
      branches: [{ type: "parallel", strategy: "all", branches: [{ type: "parallel", strategy: "all", branches: [{ domain: "math", action: "add", params: ["1", "1"] }] }] }],
    });
    const r = await runPath({ name: "deep", steps: [deep()] }, makeDeps());
    expect(r.ok).toBe(false);
    expect(r.error).toBe("NESTING_EXCEEDED");
  });
});
