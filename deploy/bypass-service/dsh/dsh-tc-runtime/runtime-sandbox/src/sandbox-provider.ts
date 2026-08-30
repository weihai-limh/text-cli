/**
 * sandbox-provider.ts——平台沙箱注入接口（功能设计 §4.2 三层执行面）
 *
 * dsh `ctx.sandbox.confine(argv, policy)` 的抽象（ubuntu 联调接入）；
 * 未配置 provider → fail-closed（SandboxUnavailableError → ERR_EXECUTION）。
 */
import type { SandboxPolicy } from "./policy.js";

export class SandboxUnavailableError extends Error {
  constructor(message = "sandbox unavailable") {
    super(message);
    this.name = "SandboxUnavailableError";
  }
}

export interface SandboxProvider {
  /**
   * 包装 spawn argv（文件效果隔离；对齐 dsh `ctx.sandbox.confine`）。
   * 实现负责：SandboxMode 文件效果包裹 + SandboxUnavailableError 语义。
   */
  confine(argv: string[], policy?: SandboxPolicy): Promise<string[]>;
}

/** 未配置的沙箱——任何 confine 都 fail-closed 拒绝 */
export const NULL_SANDBOX: SandboxProvider = {
  async confine() {
    throw new SandboxUnavailableError("sandbox provider not configured");
  },
};

/** 直通沙箱（测试夹具：原样返回 argv，不施加隔离） */
export const PASSTHROUGH_SANDBOX: SandboxProvider = {
  async confine(argv) {
    return argv;
  },
};
