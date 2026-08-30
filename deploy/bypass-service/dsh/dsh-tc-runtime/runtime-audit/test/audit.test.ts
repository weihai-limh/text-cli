import { afterEach, beforeEach, describe, expect, it } from "vitest";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { TraceSession, newTraceId, type AuditEvent } from "../src/trace.js";
import { createJsonlAudit } from "../src/jsonl.js";

describe("TraceSession：trace 模型（功能设计 §1.1.1）", () => {
  it("traceId 格式：tc-<epochMs>-<rand6>", () => {
    expect(newTraceId()).toMatch(/^tc-\d+-\d{1,6}$/);
  });

  it("事件携带 traceId + seq 递增", () => {
    const session = new TraceSession("fixed-trace");
    const e1 = session.next("inbound", { prompt: "x" });
    const e2 = session.next("envelope", {});
    expect(e1.traceId).toBe("fixed-trace");
    expect(e1.seq).toBe(0);
    expect(e1.ts).toBeDefined();
    expect(e2.seq).toBe(1);
    expect(e2.traceId).toBe("fixed-trace");
  });

  it("外部 traceId 可注入（幂等/重放）", () => {
    const session = new TraceSession("replay-001");
    expect(session.traceId).toBe("replay-001");
  });
});

describe("createJsonlAudit：append-only JSONL + 生命周期双闸", () => {
  let dir: string;

  beforeEach(() => {
    dir = fs.mkdtempSync(path.join(os.tmpdir(), "tc-audit-"));
  });
  afterEach(() => {
    fs.rmSync(dir, { recursive: true, force: true });
  });

  it("追加写入：每行一个 JSON 事件", async () => {
    const logPath = path.join(dir, "audit.jsonl");
    const audit = createJsonlAudit({ path: logPath });
    const session = new TraceSession("t-1");
    await audit.write(session.next("inbound", { prompt: "AI:tc-math;eval,1" }));
    await audit.write(session.next("envelope", { rst_err: "" }));

    const lines = fs.readFileSync(logPath, "utf8").trim().split("\n");
    expect(lines).toHaveLength(2);
    const parsed = JSON.parse(lines[0]) as AuditEvent;
    expect(parsed.traceId).toBe("t-1");
    expect(parsed.type).toBe("inbound");
  });

  it("容量轮转：超 maxMb → 重命名旧文件并开新文件", async () => {
    const logPath = path.join(dir, "audit.jsonl");
    const audit = createJsonlAudit({ path: logPath, maxMb: 0.0001 }); // ~100B 上限
    const session = new TraceSession("t-2");
    for (let i = 0; i < 50; i++) {
      await audit.write(session.next("tool-exec", { i }));
    }
    const rotated = fs.readdirSync(dir).filter((n) => n.startsWith("audit.jsonl."));
    expect(rotated.length).toBeGreaterThan(0); // 至少一次轮转
    expect(fs.existsSync(logPath)).toBe(true); // 新文件存在
  });

  it("可重放：按 traceId 归组 + seq 排序重建全链路", async () => {
    const logPath = path.join(dir, "audit.jsonl");
    const audit = createJsonlAudit({ path: logPath });
    const session = new TraceSession("chain-1");
    await audit.write(session.next("inbound", {}));
    await audit.write(session.next("parse", { domain: "tc-math" }));
    await audit.write(session.next("tool-exec", {}));
    await audit.write(session.next("envelope", {}));

    const events = fs
      .readFileSync(logPath, "utf8")
      .trim()
      .split("\n")
      .map((l) => JSON.parse(l) as AuditEvent)
      .filter((e) => e.traceId === "chain-1")
      .sort((a, b) => a.seq - b.seq);
    expect(events.map((e) => e.type)).toEqual(["inbound", "parse", "tool-exec", "envelope"]);
  });
});
