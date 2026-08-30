import { describe, it, expect, vi } from "vitest";
import { ApprovalAnswerer } from "../src/index.js";
import type { ApprovalConfig, ApprovalDeps } from "../src/index.js";

const SECRET = "shared-secret";

function makeDeps(over: Partial<ApprovalDeps> = {}): ApprovalDeps {
  return {
    httpPost: vi.fn(async () => ({ status: 200, body: "{}", headers: {} })),
    hmacSign: (secret, payload) => `hmac:${secret}:${payload.length}`,
    now: () => 1_000_000,
    audit: vi.fn(),
    ...over,
  };
}

/** 构造一个会回显 callId 且用同 secret 签名的 webhook mock */
function webhook(respond: (req: any) => { allowed: boolean }, status = 200) {
  return vi.fn(async (_url: string, body: string) => {
    const req = JSON.parse(body);
    const respBody = JSON.stringify({ allowed: respond(req).allowed, callId: req.callId });
    return {
      status,
      body: respBody,
      headers: { "x-tc-response-signature": `hmac:${SECRET}:${respBody.length}` },
    };
  });
}

describe("runtime-approval answerer", () => {
  it("① 归属过滤（红线⑥）：agent 存在 → 委托，不决策不联网", async () => {
    const httpPost = vi.fn();
    const a = new ApprovalAnswerer({ webhookUrl: "http://hook", secret: SECRET }, makeDeps({ httpPost }));
    const d = await a.answer(
      { callId: "c1", toolName: "tc__x__y", agent: "dsh-agent-7" },
    );
    expect(d.decided).toBe(false);
    expect(httpPost).not.toHaveBeenCalled();
  });

  it("② 未配置 webhook → 恒 deny（fail-closed）", async () => {
    const a = new ApprovalAnswerer({}, makeDeps());
    const d = await a.answer({ callId: "c2", toolName: "tc__x__y" });
    expect(d.decided).toBe(true);
    expect(d.allowed).toBe(false);
    expect(d.decidedBy).toBe("unconfigured");
  });

  it("③ webhook 返回 allow → allow", async () => {
    const httpPost = webhook(() => ({ allowed: true }));
    const a = new ApprovalAnswerer({ webhookUrl: "http://hook", secret: SECRET }, makeDeps({ httpPost }));
    const d = await a.answer({ callId: "c3", toolName: "tc__x__y" });
    expect(d.allowed).toBe(true);
    expect(d.decidedBy).toBe("webhook");
  });

  it("④ webhook 返回 deny → deny", async () => {
    const httpPost = webhook(() => ({ allowed: false }));
    const a = new ApprovalAnswerer({ webhookUrl: "http://hook", secret: SECRET }, makeDeps({ httpPost }));
    const d = await a.answer({ callId: "c4", toolName: "tc__x__y" });
    expect(d.allowed).toBe(false);
    expect(d.decidedBy).toBe("webhook");
  });

  it("⑤ 超时 → unavailable（fail-closed）", async () => {
    const httpPost = vi.fn(async () => new Promise(() => {})); // 永不 resolve
    const a = new ApprovalAnswerer(
      { webhookUrl: "http://hook", secret: SECRET, timeoutMs: 10 },
      makeDeps({ httpPost, now: () => 1_000_000 }),
    );
    const d = await a.answer({ callId: "c5", toolName: "tc__x__y" });
    expect(d.allowed).toBe(false);
    expect(d.decidedBy).toBe("timeout");
  });

  it("⑥ 网络不可达 → unavailable", async () => {
    const httpPost = vi.fn(async () => {
      throw new Error("ECONNREFUSED");
    });
    const a = new ApprovalAnswerer({ webhookUrl: "http://hook", secret: SECRET }, makeDeps({ httpPost }));
    const d = await a.answer({ callId: "c6", toolName: "tc__x__y" });
    expect(d.allowed).toBe(false);
    expect(d.decidedBy).toBe("unavailable");
  });

  it("⑦ 非 2xx → unavailable", async () => {
    const httpPost = webhook(() => ({ allowed: true }), 500);
    const a = new ApprovalAnswerer({ webhookUrl: "http://hook", secret: SECRET }, makeDeps({ httpPost }));
    const d = await a.answer({ callId: "c7", toolName: "tc__x__y" });
    expect(d.allowed).toBe(false);
    expect(d.decidedBy).toBe("unavailable");
  });

  it("⑧ 回显校验失败（串线）→ forged", async () => {
    const httpPost = vi.fn(async (_u: string, body: string) => {
      const req = JSON.parse(body);
      const respBody = JSON.stringify({ allowed: true, callId: "EVIL-OTHER" });
      return { status: 200, body: respBody, headers: { "x-tc-response-signature": `hmac:${SECRET}:${respBody.length}` } };
    });
    const a = new ApprovalAnswerer({ webhookUrl: "http://hook", secret: SECRET }, makeDeps({ httpPost }));
    const d = await a.answer({ callId: "c8", toolName: "tc__x__y" });
    expect(d.allowed).toBe(false);
    expect(d.decidedBy).toBe("forged");
  });

  it("⑨ 响应签名校验失败（伪造）→ forged", async () => {
    const httpPost = vi.fn(async (_u: string, body: string) => {
      const req = JSON.parse(body);
      const respBody = JSON.stringify({ allowed: true, callId: req.callId });
      return { status: 200, body: respBody, headers: { "x-tc-response-signature": "tampered" } };
    });
    const a = new ApprovalAnswerer({ webhookUrl: "http://hook", secret: SECRET }, makeDeps({ httpPost }));
    const d = await a.answer({ callId: "c9", toolName: "tc__x__y" });
    expect(d.allowed).toBe(false);
    expect(d.decidedBy).toBe("forged");
  });

  it("⑩ 重放防护：同 callId 第二次不再触发 webhook", async () => {
    const httpPost = webhook(() => ({ allowed: true }));
    const a = new ApprovalAnswerer({ webhookUrl: "http://hook", secret: SECRET }, makeDeps({ httpPost }));
    await a.answer({ callId: "c10", toolName: "tc__x__y" });
    const d2 = await a.answer({ callId: "c10", toolName: "tc__x__y" });
    expect(httpPost).toHaveBeenCalledTimes(1);
    expect(d2.allowed).toBe(true);
  });

  it("⑪ 审计事件：asked + decided pair 产出", async () => {
    const audit = vi.fn();
    const httpPost = webhook(() => ({ allowed: true }));
    const a = new ApprovalAnswerer({ webhookUrl: "http://hook", secret: SECRET }, makeDeps({ httpPost, audit }));
    await a.answer({ callId: "c11", toolName: "tc__x__y" });
    const subs = audit.mock.calls.map((c) => (c[0] as any).sub);
    expect(subs).toContain("asked");
    expect(subs).toContain("decided");
  });
});
