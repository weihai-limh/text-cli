import { describe, it, expect } from "vitest";
import { ProRegistry, ProNotFound, proAncestorKey, proDirective } from "../src/index.js";

describe("ProRegistry（短名 → path/aggregate 目标）", () => {
  it("register + resolve 往返", () => {
    const reg = new ProRegistry();
    reg.register("heavy", { kind: "path", pathId: "p1" });
    reg.register("best", { kind: "aggregate", aggName: "aggX" });
    expect(reg.resolve("heavy")).toEqual({ kind: "path", pathId: "p1" });
    expect(reg.resolve("best")).toEqual({ kind: "aggregate", aggName: "aggX" });
  });

  it("未注册 → ProNotFound", () => {
    const reg = new ProRegistry();
    expect(() => reg.resolve("nope")).toThrow(ProNotFound);
    expect(reg.has("nope")).toBe(false);
  });

  it("list 全量暴露（query 平权）", () => {
    const reg = new ProRegistry();
    reg.register("a", { kind: "path", pathId: "pa" });
    reg.register("b", { kind: "aggregate", aggName: "ab" });
    expect(reg.list().map((x) => x.name).sort()).toEqual(["a", "b"]);
  });
});

describe("proAncestorKey（「只查不推」—— 返回目标 key，不返回 pro 键）", () => {
  it("path 目标 → path:<id>（非 pro: 键）", () => {
    const reg = new ProRegistry();
    reg.register("h", { kind: "path", pathId: "p9" });
    expect(proAncestorKey("h", reg)).toBe("path:p9");
  });

  it("aggregate 目标 → agg:<name>", () => {
    const reg = new ProRegistry();
    reg.register("b", { kind: "aggregate", aggName: "aggZ" });
    expect(proAncestorKey("b", reg)).toBe("agg:aggZ");
  });

  it("语义验证：守卫应 contains 目标 key、不 push pro 键（防假报环）", () => {
    const reg = new ProRegistry();
    reg.register("shared", { kind: "path", pathId: "common" });
    const key = proAncestorKey("shared", reg);
    // 该 key 是目标，而非 pro:shared —— 多 path 复用 pro 不会各自占位
    expect(key).toBe("path:common");
    expect(key.startsWith("pro:")).toBe(false);
  });
});

describe("proDirective（平权：text-cli;pro,<name> 与原子指令同形）", () => {
  it("生成 {domain:text-cli, action:pro,<name>}", () => {
    expect(proDirective("heavy")).toEqual({ domain: "text-cli", action: "pro,heavy" });
  });
});
