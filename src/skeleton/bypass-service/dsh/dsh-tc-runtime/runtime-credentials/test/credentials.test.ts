import { describe, expect, it } from "vitest";
import { buildGrants, isGranted, toRefName } from "../src/grant.js";
import { resolveForPackage, resolveAllForPackage } from "../src/resolver.js";
import { createMemoryCredentialSource } from "../src/credential-source.js";

describe("grant：包↔凭据授权映射（B5 第一防线）", () => {
  it("TC_ 前缀命名空间（大写 + 特殊字符转下划线）", () => {
    expect(toRefName("my_api_key")).toBe("TC_MY_API_KEY");
    expect(toRefName("bd-ocr")).toBe("TC_BD_OCR");
  });

  it("单凭据 → 单 grant；ref = envKey（POSIX 环境变量名）", () => {
    const p = buildGrants("bd-map", [{ name: "bd_map_key" }]);
    expect(p.grants).toEqual([{ ref: "TC_BD_MAP_KEY", envKey: "TC_BD_MAP_KEY", sourceName: "bd_map_key" }]);
  });

  it("双凭据（gd-map key+secret）→ 拆两个独立 grant", () => {
    const p = buildGrants("gd-map", [{ name: "gd_key" }, { name: "gd_secret" }]);
    expect(p.grants).toHaveLength(2);
    expect(p.grants[0].ref).toBe("TC_GD_KEY");
    expect(p.grants[1].ref).toBe("TC_GD_SECRET");
  });

  it("无凭据声明 → 空 grants", () => {
    expect(buildGrants("tc-math", undefined).grants).toEqual([]);
  });

  it("授权校验：本包凭据放行，他包凭据拒绝（bd-map 取不到 bd-ocr）", () => {
    const bdMap = buildGrants("bd-map", [{ name: "bd_map_key" }]);
    expect(isGranted(bdMap, "TC_BD_MAP_KEY")).toBe(true);
    expect(isGranted(bdMap, "TC_BD_OCR")).toBe(false);
  });
});

describe("resolveForPackage：resolve 链（功能设计 §6.2）", () => {
  const source = createMemoryCredentialSource({
    TC_BD_MAP_KEY: "secret-key-1",
    TC_BD_OCR: "secret-ocr",
  });

  it("授权命中 → 注入 env 白名单（值来自 resolve，非硬编码）", async () => {
    const r = await resolveForPackage("TC_BD_MAP_KEY", {
      packageId: "bd-map",
      grants: buildGrants("bd-map", [{ name: "bd_map_key" }]),
      source,
    });
    expect(r.ok).toBe(true);
    if (r.ok) expect(r.env).toEqual({ TC_BD_MAP_KEY: "secret-key-1" });
  });

  it("未授权（包取别的包凭据）→ ACCESS_DENIED + 审计事件", async () => {
    const events: unknown[] = [];
    const r = await resolveForPackage("TC_BD_OCR", {
      packageId: "bd-map",
      grants: buildGrants("bd-map", [{ name: "bd_map_key" }]),
      source,
      onResolve: (e) => events.push(e),
    });
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.code).toBe("ACCESS_DENIED");
    expect(events).toHaveLength(1);
    expect(events[0]).toMatchObject({ packageId: "bd-map", ref: "TC_BD_OCR", ok: false, reason: "ACCESS_DENIED" });
  });

  it("凭据缺失（resolve 空值）→ SERVICE_DENIED（错误码映射表）", async () => {
    const r = await resolveForPackage("TC_MISSING", {
      packageId: "bd-map",
      grants: buildGrants("bd-map", [{ name: "missing" }]),
      source,
    });
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.code).toBe("SERVICE_DENIED");
  });

  it("配额接口预留：quotaCheck false → QUOTA_STOP（Phase 8 接 dsh-quota）", async () => {
    const r = await resolveForPackage("TC_BD_MAP_KEY", {
      packageId: "bd-map",
      grants: buildGrants("bd-map", [{ name: "bd_map_key" }]),
      source,
      quotaCheck: async () => false,
    });
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.code).toBe("QUOTA_STOP");
  });

  it("每次取用写审计（onResolve 必触发）", async () => {
    const events: unknown[] = [];
    await resolveForPackage("TC_BD_MAP_KEY", {
      packageId: "bd-map",
      grants: buildGrants("bd-map", [{ name: "bd_map_key" }]),
      source,
      onResolve: (e) => events.push(e),
    });
    expect(events).toHaveLength(1);
    expect(events[0]).toMatchObject({ ok: true, ref: "TC_BD_MAP_KEY" });
  });
});

describe("resolveAllForPackage：批量装配 env 白名单", () => {
  it("全部授权 → 合并 env；缺失凭据跳过（优雅降级）", async () => {
    const source = createMemoryCredentialSource({ TC_GD_KEY: "k" });
    const r = await resolveAllForPackage({
      packageId: "gd-map",
      grants: buildGrants("gd-map", [{ name: "gd_key" }, { name: "gd_secret" }]),
      source,
    });
    expect(r.ok).toBe(true);
    if (r.ok) expect(r.env).toEqual({ TC_GD_KEY: "k" }); // gd_secret 缺失 → 跳过
  });

  it("QUOTA_STOP → 整体拒绝（配额语义优先）", async () => {
    const source = createMemoryCredentialSource({ TC_GD_KEY: "k" });
    const r = await resolveAllForPackage({
      packageId: "gd-map",
      grants: buildGrants("gd-map", [{ name: "gd_key" }]),
      source,
      quotaCheck: async () => false,
    });
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.code).toBe("QUOTA_STOP");
  });
});
