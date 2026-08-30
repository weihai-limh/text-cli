import { describe, expect, it } from "vitest";
import { PackageRegistry } from "../src/registry.js";
import { installPackage, uninstallPackage, exportPackage, exportAllPackages, listPackages, inferPackageKind, type InstallSchema } from "../src/installer.js";
import { handleMeta, META_ACTIONS } from "../src/meta.js";

const pureSchema: InstallSchema = {
  id: "tc-math",
  type: "native",
  runtime: "js",
  directives: [{ domain: "tc-math", action: "eval" }],
};

const credSchema: InstallSchema = {
  id: "bd-map",
  type: "native",
  runtime: "js",
  credentials: [{ name: "bd_map_key" }, { name: "bd_map_secret" }],
  directives: [{ domain: "bd-map", action: "geocode" }],
};

const hostPrivilegedSchema: InstallSchema = {
  id: "evil-host",
  type: "host-privileged",
  runtime: "js",
};

describe("inferPackageKind：schema → 包类型启发式", () => {
  it("宿主特权 → host-privileged（排除）", () => {
    expect(inferPackageKind(hostPrivilegedSchema)).toBe("host-privileged");
  });
  it("凭据包 → network-credential（保守）", () => {
    expect(inferPackageKind(credSchema)).toBe("network-credential");
  });
  it("无凭据 JS 包 → pure（保守最小权限）", () => {
    expect(inferPackageKind(pureSchema)).toBe("pure");
  });
});

describe("installPackage / uninstallPackage：包生命周期", () => {
  it("纯函数包安装：policy read-only + 空 grants + 工具名映射", () => {
    const registry = new PackageRegistry();
    const r = installPackage(registry, { schema: pureSchema, handlerPath: "/pkgs/tc-math/handler.cjs" });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.installed.policy).toMatchObject({ mode: "read-only", networkWhitelist: [], envWhitelistKeys: [] });
    expect(r.installed.grants.grants).toEqual([]);
    expect(r.installed.directives).toEqual([
      { domain: "tc-math", action: "eval", toolName: "tc__tc-math__eval" },
    ]);
    expect(registry.has("tc-math")).toBe(true);
  });

  it("凭据包安装：policy network-credential + grants 双凭据拆分", () => {
    const registry = new PackageRegistry();
    const r = installPackage(registry, { schema: credSchema, handlerPath: "/pkgs/bd-map/handler.cjs" });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.installed.policy.envWhitelistKeys).toEqual(["TC_BD_MAP_KEY", "TC_BD_MAP_SECRET"]);
    expect(r.installed.grants.grants).toHaveLength(2);
  });

  it("宿主特权包 → 安装拒绝（不属本运行时）", () => {
    const registry = new PackageRegistry();
    const r = installPackage(registry, { schema: hostPrivilegedSchema, handlerPath: "/pkgs/x.cjs" });
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.error).toContain("host-privileged");
    expect(registry.has("evil-host")).toBe(false);
  });

  it("disposer 回收 + uninstall：install → uninstall 完整闭环", () => {
    const registry = new PackageRegistry();
    const r = installPackage(registry, { schema: pureSchema, handlerPath: "/pkgs/tc-math/handler.cjs" });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    // disposer 回收
    r.disposer();
    expect(registry.has("tc-math")).toBe(false);
    // 重新安装 + uninstall
    installPackage(registry, { schema: pureSchema, handlerPath: "/pkgs/tc-math/handler.cjs" });
    const u = uninstallPackage(registry, "tc-math");
    expect(u.ok).toBe(true);
    expect(registry.has("tc-math")).toBe(false);
    // 未安装包 uninstall → 失败
    expect(uninstallPackage(registry, "nope").ok).toBe(false);
  });

  it("export 不带私有策略（policy/grants 不导出）", () => {
    const registry = new PackageRegistry();
    installPackage(registry, { schema: credSchema, handlerPath: "/pkgs/bd-map/handler.cjs" });
    const env = exportPackage(registry, "bd-map");
    expect(env.rst_err).toBe("");
    const data = env.rst_data as Record<string, unknown>;
    expect(data.id).toBe("bd-map");
    expect(data).not.toHaveProperty("policy");
    expect(data).not.toHaveProperty("grants");
    // 未安装导出 → ERR_NOT_FOUND
    expect(exportPackage(registry, "nope").rst_err).toBe("ERR_NOT_FOUND");
  });
});

describe("handleMeta：text-cli;* 八元指令表面", () => {
  it("八元指令闭集", () => {
    expect(META_ACTIONS).toEqual(["install", "uninstall", "export", "export-all", "packages", "query", "path", "pro"]);
  });

  it("query 转发发现契约（数据源注入）", async () => {
    const registry = new PackageRegistry();
    const env = await handleMeta("query", ["json"], {
      registry,
      directives: [{ domain: "tc-math", action: "eval" }],
    });
    expect(env.rst_err).toBe("");
    expect((env.rst_data as { directives: unknown[] }).directives).toHaveLength(1);
  });

  it("packages 列出已安装包", async () => {
    const registry = new PackageRegistry();
    installPackage(registry, { schema: pureSchema, handlerPath: "/p.cjs" });
    const env = await handleMeta("packages", [], { registry, directives: [] });
    expect((env.rst_data as { packages: unknown[] }).packages).toHaveLength(1);
  });

  it("install 需包源（ubuntu 联调接入）→ INVALID_PARAMS", async () => {
    const registry = new PackageRegistry();
    const env = await handleMeta("install", [], { registry, directives: [] });
    expect(env.rst_err).toBe("INVALID_PARAMS");
  });

  it("path 无参数 → INVALID_PARAMS", async () => {
    const registry = new PackageRegistry();
    expect((await handleMeta("path", [], { registry, directives: [] })).rst_err).toBe("INVALID_PARAMS");
  });

  it("path 未注入 runPath → ERR_NOT_FOUND（fail-closed，P0 前）", async () => {
    const registry = new PackageRegistry();
    const env = await handleMeta("path", ["my-path"], { registry, directives: [] });
    expect(env.rst_err).toBe("ERR_NOT_FOUND");
  });

  it("path 注入 runPath 执行器 → 转发执行", async () => {
    const registry = new PackageRegistry();
    const runPath = async (pathName: string, params: string[]) => {
      expect(pathName).toBe("my-path");
      expect(params).toEqual(["1", "2"]);
      return { rst_types: "text", rst_data: { status: "ok", output: "ran" }, rst_err: "" };
    };
    const env = await handleMeta("path", ["my-path", "1", "2"], { registry, directives: [], runPath });
    expect(env.rst_err).toBe("");
    expect((env.rst_data as { output?: string }).output).toBe("ran");
  });

  it("pro 占位 → ERR_NOT_FOUND（Phase 11）", async () => {
    const registry = new PackageRegistry();
    expect((await handleMeta("pro", [], { registry, directives: [] })).rst_err).toBe("ERR_NOT_FOUND");
  });

  it("未知 action → ERR_NOT_FOUND", async () => {
    const registry = new PackageRegistry();
    expect((await handleMeta("hack", [], { registry, directives: [] })).rst_err).toBe("ERR_NOT_FOUND");
  });
});

describe("listPackages / exportAllPackages", () => {
  it("全量导出 + 列表", () => {
    const registry = new PackageRegistry();
    installPackage(registry, { schema: pureSchema, handlerPath: "/p.cjs" });
    const all = exportAllPackages(registry);
    expect((all.rst_data as { packages: unknown[] }).packages).toHaveLength(1);
    const list = listPackages(registry);
    expect((list.rst_data as { packages: unknown[] }).packages).toHaveLength(1);
  });
});
