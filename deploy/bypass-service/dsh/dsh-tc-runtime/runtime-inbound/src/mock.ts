/**
 * Phase 1 mock 执行面（沙箱未接入前的测试夹具）
 *
 * 设计约定（功能设计 §5.1 + 计划 Phase 1 范围说明）：沙箱未接入前**拒绝真实包执行**，
 * 仅 mock 直通纯函数包用于验证"解析→路由→信封"链路。真实执行在 Phase 3
 * executor-js 沙箱接入后替换（红线③兼容）。
 */
import type { ToolExecutionInput } from "@dsh-tc/runtime-mapper";

/** mock 包注册表：工具名 → 执行函数 */
type MockHandler = (params: string[]) => unknown;

function createRegistry(): Map<string, MockHandler> {
  const registry = new Map<string, MockHandler>();

  // tc-math;eval——受限表达式计算（测试夹具，非真实包；仅接受纯算术）
  registry.set("tc__tc-math__eval", (params) => {
    const expr = (params[0] ?? "0").trim();
    if (!/^[0-9+\-*/().\s]+$/.test(expr)) {
      throw new Error(`unsafe expression: ${expr}`);
    }
    // 纯算术表达式——Function 构造在 mock 夹具内可接受，真实执行走沙箱（Phase 3）
    const value = Function(`"use strict"; return (${expr});`)();
    if (typeof value !== "number" || Number.isNaN(value)) {
      throw new Error(`non-numeric result: ${expr}`);
    }
    return { status: "ok", result: value };
  });

  // tc-datetime;now——纯函数（mock）
  registry.set("tc__tc-datetime__now", () => ({
    status: "ok",
    result: new Date().toISOString(),
  }));

  return registry;
}

/** 构造 mock dispatch（Phase 1 测试用）——未注册工具返回 null（→ ERR_NOT_FOUND 语义） */
export function createMockDispatch(): (input: ToolExecutionInput) => Promise<unknown> {
  const registry = createRegistry();
  return async (input: ToolExecutionInput) => {
    const handler = registry.get(input.name);
    if (!handler) {
      return null; // 未注册 → handlePrompt 映射 ERR_NOT_FOUND（对齐 §3.2 UNKNOWN_TOOL 映射）
    }
    const params = (input.arguments.params as string[]) ?? [];
    return handler(params);
  };
}
