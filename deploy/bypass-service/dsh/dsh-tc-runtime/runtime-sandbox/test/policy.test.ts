import { describe, expect, it } from "vitest";
import { policyForPackage, isNetworkAllowed, isEnvKeyAllowed, type PackageCapability } from "../src/policy.js";

describe("policyForPackage：7 类包类型 → 沙箱策略（功能设计 §4.1）", () => {
  it("纯函数 → read-only，无网络，无 env", () => {
    expect(policyForPackage({ kind: "pure" })).toEqual({
      mode: "read-only",
      networkWhitelist: [],
      envWhitelistKeys: [],
    });
  });

  it("免密网络 → read-only + 网络白名单", () => {
    const p = policyForPackage({ kind: "network", networkDomains: ["api.openweathermap.org"] });
    expect(p).toMatchObject({ mode: "read-only", networkWhitelist: ["api.openweathermap.org"] });
    expect(p?.envWhitelistKeys).toEqual([]);
  });

  it("配置注入型 → read-only + env 白名单（凭据键）", () => {
    const p = policyForPackage({ kind: "config-inject", credentials: ["AI_API_KEY"] });
    expect(p).toMatchObject({ mode: "read-only", envWhitelistKeys: ["AI_API_KEY"], networkWhitelist: [] });
  });

  it("网络+凭据 → read-only + 网络白名单 + env 白名单", () => {
    const p = policyForPackage({
      kind: "network-credential",
      networkDomains: ["api.map.baidu.com"],
      credentials: ["BD_MAP_KEY", "BD_MAP_SECRET"],
    });
    expect(p).toMatchObject({
      mode: "read-only",
      networkWhitelist: ["api.map.baidu.com"],
      envWhitelistKeys: ["BD_MAP_KEY", "BD_MAP_SECRET"],
    });
  });

  it("文件 IO / 图片 → workspace-write + 工作区根", () => {
    expect(policyForPackage({ kind: "file-io", workspaceRoot: "/data/tc" })).toMatchObject({
      mode: "workspace-write",
      workspaceRoot: "/data/tc",
    });
    expect(policyForPackage({ kind: "image", workspaceRoot: "/data/img" }).mode).toBe("workspace-write");
  });

  it("宿主特权 → null（排除，不属本运行时）", () => {
    expect(policyForPackage({ kind: "host-privileged" })).toBeNull();
  });
});

describe("isNetworkAllowed：域名白名单（精确 + 子域后缀）", () => {
  it("精确匹配 + 子域后缀", () => {
    const w = ["api.map.baidu.com"];
    expect(isNetworkAllowed("api.map.baidu.com", w)).toBe(true);
    expect(isNetworkAllowed("sub.api.map.baidu.com", w)).toBe(true);
    expect(isNetworkAllowed("evil.com", w)).toBe(false);
    expect(isNetworkAllowed("map.baidu.com", w)).toBe(false); // 前缀域不算
  });
  it("空白名单 = 无网络", () => {
    expect(isNetworkAllowed("any.com", [])).toBe(false);
  });
});

describe("isEnvKeyAllowed", () => {
  it("白名单键放行，其余拒绝", () => {
    const keys = ["BD_MAP_KEY"];
    expect(isEnvKeyAllowed("BD_MAP_KEY", keys)).toBe(true);
    expect(isEnvKeyAllowed("HOST_SECRET", keys)).toBe(false);
  });
});
