import { describe, it, expect, vi } from "vitest";
import {
  meshRoute,
  credentialForwardPolicy,
  MeshCycleError,
  MeshHopExceeded,
  MAX_HOP_DEPTH,
} from "../src/index.js";
import type { MeshContext, MeshDeps, MeshPeer } from "../src/index.js";

function baseCtx(over: Partial<MeshContext> = {}): MeshContext {
  return {
    routeTable: [{ id: "peer-a", endpoint: "http://peer-a" }],
    visited: new Set(),
    hop: 0,
    ...over,
  };
}

function baseDeps(over: Partial<MeshDeps> = {}): MeshDeps {
  return {
    localHas: () => false,
    dispatch: vi.fn(async () => ({ rst_err: "", rst_data: { local: 1 } })),
    remote: vi.fn(async () => ({ rst_err: "", rst_data: { remote: 1 } })),
    ...over,
  };
}

describe("meshRoute（§10.2 / 附录 B 机制 8）", () => {
  it("本地命中 → 本地派发，不跨节点", async () => {
    const dispatch = vi.fn(async () => ({ rst_err: "", rst_data: { local: 1 } }));
    const remote = vi.fn(async () => ({ rst_err: "", rst_data: { remote: 1 } }));
    const deps = baseDeps({ localHas: () => true, dispatch, remote });
    const r = await meshRoute("math", "add", ["1"], deps, baseCtx());
    expect((r as any).rst_data.local).toBe(1);
    expect(dispatch).toHaveBeenCalledTimes(1);
    expect(remote).not.toHaveBeenCalled();
  });

  it("本地未命中 + 无 peer → ERR_NOT_FOUND 信封", async () => {
    const r = await meshRoute("math", "add", ["1"], baseDeps(), baseCtx({ routeTable: [] }));
    expect((r as any).rst_err).toBe("ERR_NOT_FOUND");
    expect((r as any).rst_data.reason).toBe("no-peer");
  });

  it("visited 已含同 key → MeshCycleError（防环）", async () => {
    const ctx = baseCtx({ visited: new Set(["math;add"]) });
    await expect(meshRoute("math", "add", ["1"], baseDeps(), ctx)).rejects.toBeInstanceOf(
      MeshCycleError,
    );
  });

  it("hop > MAX_HOP_DEPTH → MeshHopExceeded", async () => {
    const ctx = baseCtx({ hop: MAX_HOP_DEPTH + 1 });
    await expect(meshRoute("math", "add", ["1"], baseDeps(), ctx)).rejects.toBeInstanceOf(
      MeshHopExceeded,
    );
  });

  it("本地未命中 + 有 peer → remote 出站并回传信封", async () => {
    const remote = vi.fn(async () => ({ rst_err: "", rst_data: { remote: 7 } }));
    const r = await meshRoute("math", "add", ["1"], baseDeps({ remote }), baseCtx());
    expect((r as any).rst_data.remote).toBe(7);
    expect(remote).toHaveBeenCalledTimes(1);
  });

  it("跨节点脱敏（sensitive=true）：遮蔽 secret/password/token 等参数值", async () => {
    const remote = vi.fn(async (_p: MeshPeer, _d: string, _a: string, params: string[]) => {
      return { rst_err: "", rst_data: { got: params } };
      ;
    });
    const params = ["user=alice", "secret=topsecret", "token=abc"];
    const r = await meshRoute("math", "add", params, baseDeps({ remote }), baseCtx({ sensitive: true }));
    const got = (r as any).rst_data.got as string[];
    expect(got[1]).toBe("secret=***");
    expect(got[2]).toBe("token=***");
    expect(got[0]).toBe("user=alice");
  });

  it("默认不脱敏（sensitive=false）：参数原样出站", async () => {
    const remote = vi.fn(async (_p: MeshPeer, _d: string, _a: string, params: string[]) => {
      return { rst_err: "", rst_data: { got: params } };
    });
    const params = ["secret=topsecret"];
    const r = await meshRoute("math", "add", params, baseDeps({ remote }), baseCtx());
    expect(((r as any).rst_data.got as string[])[0]).toBe("secret=topsecret");
  });

  it("重试：remote 前两次失败，第三次成功 → 回传成功信封", async () => {
    let n = 0;
    const remote = vi.fn(async () => {
      n++;
      if (n < 3) throw new Error("net blip");
      return { rst_err: "", rst_data: { ok: n } };
    });
    const r = await meshRoute("math", "add", ["1"], baseDeps({ remote }), baseCtx());
    expect((r as any).rst_data.ok).toBe(3);
    expect(remote).toHaveBeenCalledTimes(3);
  });

  it("重试耗尽：remote 始终失败 → 抛出末次错误", async () => {
    const remote = vi.fn(async () => {
      throw new Error("down");
    });
    await expect(meshRoute("math", "add", ["1"], baseDeps({ remote }), baseCtx())).rejects.toThrow(
      "down",
    );
    expect(remote).toHaveBeenCalledTimes(3); // 1 + RETRIES(2)
  });
});

describe("credentialForwardPolicy（凭证三原则）", () => {
  it("默认关（forwardCredentials=false）→ 不前向、不 degraded", () => {
    const r = credentialForwardPolicy(baseCtx());
    expect(r).toEqual({ forward: false, degraded: false });
  });

  it("开启 → forward + degraded（peer 隔离 + _mesh_credential_degraded）", () => {
    const r = credentialForwardPolicy(baseCtx({ forwardCredentials: true }));
    expect(r).toEqual({ forward: true, degraded: true });
  });
});
