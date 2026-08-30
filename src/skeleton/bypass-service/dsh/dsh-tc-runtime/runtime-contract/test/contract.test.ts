import { describe, it, expect, vi } from "vitest";
import tc from "textcli-core";
import {
  ok,
  err,
  validateEnvelope,
  CLOSED_CODES,
  ERROR_MAP,
  mapSignal,
  isClosedCode,
} from "../src/index.js";

describe("信封三字段不变量（§12.3）", () => {
  it("ok 信封恰三字段，rst_err 为空串", () => {
    const e = ok({ status: "ok", result: 14 });
    expect(Object.keys(e).sort()).toEqual(["rst_data", "rst_err", "rst_types"]);
    expect(e.rst_err).toBe("");
    expect(validateEnvelope(e).valid).toBe(true);
  });

  it("err 信封恰三字段，rst_err 落在闭集", () => {
    const e = err("ERR_NOT_FOUND", "no tool");
    expect(Object.keys(e).sort()).toEqual(["rst_data", "rst_err", "rst_types"]);
    expect(validateEnvelope(e).valid).toBe(true);
  });
});

describe("错误码闭集（6 码）", () => {
  it("闭集恰为 6 码", () => {
    expect([...CLOSED_CODES].sort()).toEqual(
      ["ACCESS_DENIED", "ERR_EXECUTION", "ERR_NOT_FOUND", "ERR_ROUTING", "INVALID_PARAMS", "SERVICE_DENIED"].sort(),
    );
  });

  it("映射表每条非空码均落在闭集内（映射表即契约）", () => {
    for (const row of ERROR_MAP) {
      if (row.code === null) continue; // 非错误（quota stop / DEGRADE_EXHAUSTED）
      expect(isClosedCode(row.code)).toBe(true);
    }
  });
});

describe("pray_rst_types 提升（SPEC §1.2.2）", () => {
  it("handler 返回含 pray_rst_types → 提升为 rst_types 并剥离", () => {
    const e = ok({ pray_rst_types: "picture", url: "http://x/y.png" });
    expect(e.rst_types).toBe("picture");
    expect((e.rst_data as Record<string, unknown>).pray_rst_types).toBeUndefined();
    expect((e.rst_data as Record<string, unknown>).url).toBe("http://x/y.png");
  });

  it("无 pray_rst_types → 默认 text", () => {
    expect(ok({ a: 1 }).rst_types).toBe("text");
  });
});

describe("未知错误码兜底（envelope.js 实证）", () => {
  it("非闭集码 → 回退 ERR_EXECUTION（不抛、不静默放行；传入 reason 保留）", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const e = err("TOTALLY_UNKNOWN", "my-reason");
    expect(e.rst_err).toBe("ERR_EXECUTION");
    expect((e.rst_data as { reason: string }).reason).toBe("my-reason");
    warn.mockRestore();
  });
});

describe("dsh→协议 全映射（mapSignal）", () => {
  it("UNKNOWN_TOOL → ERR_NOT_FOUND", () => {
    expect(mapSignal("UNKNOWN_TOOL").rst_err).toBe("ERR_NOT_FOUND");
  });
  it("INVALID_ARGS → INVALID_PARAMS", () => {
    expect(mapSignal("INVALID_ARGS").rst_err).toBe("INVALID_PARAMS");
  });
  it("SandboxUnavailableError → ERR_EXECUTION + reason=SANDBOX_UNAVAILABLE", () => {
    const e = mapSignal("SandboxUnavailableError");
    expect(e.rst_err).toBe("ERR_EXECUTION");
    expect((e.rst_data as { reason: string }).reason).toBe("SANDBOX_UNAVAILABLE");
  });
  it("祖先链命中 → ERR_EXECUTION + reason=CYCLE_DETECTED", () => {
    const e = mapSignal("祖先链命中（环检测 §4.4）");
    expect(e.rst_err).toBe("ERR_EXECUTION");
    expect((e.rst_data as { reason: string }).reason).toBe("CYCLE_DETECTED");
  });
  it("非错误信号（配额超限 code=null）→ 回退 ERR_EXECUTION（调用方应优先用 rst_data.status=stop）", () => {
    expect(mapSignal("配额超限").rst_err).toBe("ERR_EXECUTION");
  });
});

describe("双运行时信封一致（与 text-cli A9 同源 textcli-core）", () => {
  it("contract 信封与 textcli-core 直接产物逐字节一致", () => {
    // 注意：textcli-core ok() 会就地删除 pray_rst_types，故每次比较用全新对象工厂
    const factories = [
      () => ({ status: "ok", result: 14 }),
      () => ({ pray_rst_types: "video", url: "u" }),
      () => ({ items: [1, 2, 3] }),
    ];
    for (const make of factories) {
      expect(ok(make())).toEqual(tc.ok(make()));
    }
    const codes: [string, string][] = [
      ["ERR_NOT_FOUND", "nf"],
      ["ACCESS_DENIED", "denied"],
      ["SERVICE_DENIED", "svc"],
    ];
    for (const [c, r] of codes) {
      expect(err(c, r)).toEqual(tc.err(c, r));
    }
  });

  it("跨运行时契约：dsh-tc-runtime 不重写信封逻辑，仅桥接（零改动复用）", () => {
    // 直接复用 textcli-core，无任何包裹转换——保证双运行时一致
    expect(ok).toBe(tc.ok);
    expect(err).toBe(tc.err);
  });
});
