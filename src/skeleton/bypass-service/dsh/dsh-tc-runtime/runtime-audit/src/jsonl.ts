/**
 * jsonl.ts——append-only JSONL 审计写入器（功能设计 §1.1.1 审计通道）
 *
 * - append-only：每次写一行 JSON（不读回、不改写）
 * - 生命周期双闸：容量上限（maxMb，超限轮转旧文件）+ TTL（ttlHours，删除超龄旧文件）
 * - 与 dsh agent 会话完全解耦（不写 ctx.sessions，红线⑦）
 */
import fs from "node:fs";
import path from "node:path";
import type { AuditEvent } from "./trace.js";

export interface JsonlAuditOptions {
  /** 日志文件路径 */
  path: string;
  /** TTL 小时（默认 24；0 = 不清理） */
  ttlHours?: number;
  /** 容量上限 MB（默认 50；0 = 不轮转） */
  maxMb?: number;
}

export interface AuditWriter {
  write(event: AuditEvent): Promise<void>;
  /** 当前日志文件路径 */
  logPath(): string;
  /** 立即执行生命周期维护（轮转/清理）——测试与定时器调用 */
  maintain(): void;
}

export function createJsonlAudit(opts: JsonlAuditOptions): AuditWriter {
  const ttlHours = opts.ttlHours ?? 24;
  const maxMb = opts.maxMb ?? 50;
  const maxBytes = maxMb > 0 ? maxMb * 1024 * 1024 : 0;

  /** 容量轮转：超限 → 重命名 <path>.<ts> 并开新文件 */
  function rotateIfNeeded(): void {
    if (maxBytes <= 0) return;
    let size = 0;
    try {
      size = fs.statSync(opts.path).size;
    } catch {
      return; // 文件不存在（首次写）
    }
    if (size >= maxBytes) {
      const rotated = `${opts.path}.${Date.now()}`;
      try {
        fs.renameSync(opts.path, rotated);
      } catch {
        /* 竞态容忍：轮转失败不影响追加 */
      }
    }
  }

  /** TTL 清理：删除超龄轮转文件（<path>.<ts>） */
  function purgeExpired(): void {
    if (ttlHours <= 0) return;
    const dir = path.dirname(opts.path);
    const base = path.basename(opts.path);
    const cutoff = Date.now() - ttlHours * 3600_000;
    let entries: string[] = [];
    try {
      entries = fs.readdirSync(dir);
    } catch {
      return;
    }
    for (const name of entries) {
      if (!name.startsWith(`${base}.`)) continue; // 仅轮转文件（<path>.<ts>）
      const full = path.join(dir, name);
      try {
        const mtime = fs.statSync(full).mtimeMs;
        if (mtime < cutoff) fs.unlinkSync(full);
      } catch {
        /* 忽略竞态 */
      }
    }
  }

  return {
    async write(event) {
      rotateIfNeeded();
      fs.mkdirSync(path.dirname(opts.path), { recursive: true });
      fs.appendFileSync(opts.path, `${JSON.stringify(event)}\n`, "utf8");
    },
    logPath() {
      return opts.path;
    },
    maintain() {
      rotateIfNeeded();
      purgeExpired();
    },
  };
}
