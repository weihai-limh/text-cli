/**
 * period.ts——配额周期窗口计算（UTC，确定性便于测试）
 */
import type { QuotaPeriod } from "./types.js";

const DAY = 86_400_000;

export interface Window {
  start: number;
  /** forever 周期为 Infinity */
  end: number;
}

/** 给定时刻所属周期窗口 */
export function windowFor(period: QuotaPeriod, now: number, createdAt: number): Window {
  const d = new Date(now);
  const y = d.getUTCFullYear();
  const m = d.getUTCMonth();
  const day = d.getUTCDate();

  switch (period) {
    case "day":
      return { start: Date.UTC(y, m, day), end: Date.UTC(y, m, day) + DAY };
    case "week": {
      // ISO 周：周一为起点
      const dow = d.getUTCDay(); // 0=Sun..6=Sat
      const diffToMonday = (dow + 6) % 7;
      const monday = Date.UTC(y, m, day - diffToMonday);
      return { start: monday, end: monday + 7 * DAY };
    }
    case "month":
      return { start: Date.UTC(y, m, 1), end: Date.UTC(y, m + 1, 1) };
    case "year":
      return { start: Date.UTC(y, 0, 1), end: Date.UTC(y + 1, 0, 1) };
    case "forever":
      return { start: createdAt, end: Infinity };
  }
}

/** 是否需要翻转窗口（now 超出当前窗口，或窗口起点漂移） */
export function needsFlip(recWindowStart: number, period: QuotaPeriod, now: number, createdAt: number): boolean {
  const w = windowFor(period, now, createdAt);
  return now >= w.end || recWindowStart !== w.start;
}
