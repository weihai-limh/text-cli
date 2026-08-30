/**
 * policy.ts——包 → 沙箱策略映射（功能设计 §4.1 分层护栏，7 类包类型）
 *
 * 纯函数：schema 声明 → SandboxPolicy（mode/workspaceRoot/networkWhitelist/envWhitelistKeys）。
 * 精确分类规则在 ubuntu 联调时按真实包（standard-python 集合）校准。
 */

/** 沙箱模式（对齐 dsh `SandboxMode` 三档） */
export type SandboxMode = "read-only" | "workspace-write" | "danger-full-access";

export interface SandboxPolicy {
  mode: SandboxMode;
  /** workspace-write 时的限域根 */
  workspaceRoot?: string;
  /** 出站域名白名单（空 = 无网络） */
  networkWhitelist: string[];
  /** env 白名单键（包可读的凭据 ref 解析值） */
  envWhitelistKeys: string[];
}

/** 包能力声明（schema 投影；ubuntu 联调时从 schema.json 映射） */
export interface PackageCapability {
  /** 包类型（标准-python 集合实证：纯函数/免密网络/文件IO/图片/配置注入/网络+凭据/宿主特权） */
  kind: PackageKind;
  /** 网络域名白名单（免密网络/网络+凭据类） */
  networkDomains?: string[];
  /** 凭据名列表（网络+凭据/配置注入类；映射 env 白名单键） */
  credentials?: string[];
  /** 工作区根（文件 IO/图片类） */
  workspaceRoot?: string;
}

export type PackageKind =
  | "pure" // 纯函数：tc-math/json/diff/datetime/table
  | "network" // 免密网络：weather（双源免密降级）
  | "file-io" // 文件 IO：tc-markdown/archive（路径白名单 + zip bomb 防御沿用）
  | "image" // 图片处理：image（Pillow）
  | "config-inject" // 配置注入型：ai-inference（供应商/模型经配置注入）
  | "network-credential" // 网络+凭据：bd-map/gd-map/tx-map/bd-cloud 等
  | "host-privileged"; // 宿主特权：tc-ubuntu/copilot——排除（不属本运行时）

/** 宿主特权包 → 拒绝（返回 null 表示不可承载） */
export function policyForPackage(cap: PackageCapability): SandboxPolicy | null {
  switch (cap.kind) {
    case "host-privileged":
      return null; // 排除（功能设计 §4.1 / §0.4 承载边界）
    case "pure":
      return { mode: "read-only", networkWhitelist: [], envWhitelistKeys: [] };
    case "network":
      return { mode: "read-only", networkWhitelist: cap.networkDomains ?? [], envWhitelistKeys: [] };
    case "config-inject":
      return { mode: "read-only", networkWhitelist: [], envWhitelistKeys: cap.credentials ?? [] };
    case "network-credential":
      return {
        mode: "read-only",
        networkWhitelist: cap.networkDomains ?? [],
        envWhitelistKeys: cap.credentials ?? [],
      };
    case "file-io":
    case "image":
      return {
        mode: "workspace-write",
        workspaceRoot: cap.workspaceRoot,
        networkWhitelist: [],
        envWhitelistKeys: [],
      };
  }
}

/** 网络白名单校验：域名是否被授权（精确匹配 + 子域后缀） */
export function isNetworkAllowed(hostname: string, whitelist: string[]): boolean {
  const h = hostname.toLowerCase();
  return whitelist.some((w) => {
    const domain = w.toLowerCase().replace(/^\./, "");
    return h === domain || h.endsWith(`.${domain}`);
  });
}

/** env 白名单校验：键是否被授权 */
export function isEnvKeyAllowed(key: string, whitelistKeys: string[]): boolean {
  return whitelistKeys.includes(key);
}
