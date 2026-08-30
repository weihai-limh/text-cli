/**
 * installer.ts——包生命周期（功能设计 §7，install/uninstall/export）
 *
 * - install：schema + handler → 注册 + 沙箱 policy + 凭据授权（注册即 effect，返回 disposer）
 * - uninstall：disposer 回收（注册项/策略/凭据授权/文件）
 * - export/export-all：重新打包源文件（不带私有策略）
 *
 * 比 tc 原生多做事：为包建沙箱策略与凭据隔离（策划 §4.2.2）。
 */
import tc from "textcli-core";
import {
  policyForPackage,
  type PackageCapability,
  type PackageKind,
} from "@dsh-tc/runtime-sandbox";
import { buildGrants, toRefName, type CredentialDeclaration } from "@dsh-tc/runtime-credentials";
import { PackageRegistry, type InstalledDirective, type InstalledPackage } from "./registry.js";

/** schema 投影（安装所需字段） */
export interface InstallSchema {
  id: string;
  type?: string;
  runtime?: string;
  credentials?: CredentialDeclaration[];
  /** 能力声明（由 type/runtime 启发式推导；ubuntu 联调时按真实包校准） */
  capability?: PackageCapability;
  directives?: Array<{ domain: string; action: string }>;
}

export interface InstallInput {
  schema: InstallSchema;
  /** 包 handler 入口（Phase 3 executor 的 handlerPath） */
  handlerPath: string;
}

export type InstallResult =
  | { ok: true; installed: InstalledPackage; disposer: () => void }
  | { ok: false; error: string };

/** schema → 包类型启发式（功能设计 §4.1 分层护栏；精确规则 ubuntu 联调校准） */
export function inferPackageKind(schema: InstallSchema): PackageKind {
  if (schema.type === "host-privileged") return "host-privileged";
  if (schema.capability) return schema.capability.kind;
  const hasCred = (schema.credentials ?? []).length > 0;
  if (hasCred) return "network-credential"; // 凭据包默认按网络+凭据（保守）
  if (schema.runtime === "js") return "pure"; // 无凭据 JS 包默认纯函数（保守最小权限）
  return "pure";
}

export function installPackage(
  registry: PackageRegistry,
  input: InstallInput,
): InstallResult {
  const { schema, handlerPath } = input;
  if (!schema.id) return { ok: false, error: "schema.id required" };

  const kind = inferPackageKind(schema);
  const policy = policyForPackage({
    kind,
    // env 白名单键 = TC_ 前缀 ref（与 grants 的 ref 一致——handler 读 process.env[ref]）
    credentials: (schema.credentials ?? []).map((c) => toRefName(c.name)),
  });
  if (policy === null) {
    return { ok: false, error: `host-privileged package not supported: ${schema.id}` };
  }

  const grants = buildGrants(schema.id, schema.credentials);
  const directives: InstalledDirective[] = (schema.directives ?? []).map((d) => ({
    domain: d.domain,
    action: d.action,
    toolName: `tc__${d.domain}__${d.action}`,
  }));

  const installed: InstalledPackage = {
    id: schema.id,
    schema: schema as unknown as Record<string, unknown>,
    handlerPath,
    policy,
    grants,
    directives,
    installedAt: new Date().toISOString(),
  };

  registry.install(installed);

  const disposer = () => {
    registry.uninstall(schema.id);
  };
  return { ok: true, installed, disposer };
}

export function uninstallPackage(registry: PackageRegistry, id: string): { ok: boolean; error?: string } {
  if (!registry.has(id)) return { ok: false, error: `package not installed: ${id}` };
  registry.uninstall(id);
  return { ok: true };
}

/** export：导出包源文件（不含私有策略——policy/grants 是运行时生成物，不导出） */
export function exportPackage(registry: PackageRegistry, id: string): EnvelopeLike {
  const pkg = registry.get(id);
  if (!pkg) return tc.err("ERR_NOT_FOUND", `package not installed: ${id}`);
  return tc.ok({
    id: pkg.id,
    schema: pkg.schema,
    handler_path: pkg.handlerPath,
    directives: pkg.directives.map((d) => ({ domain: d.domain, action: d.action })),
  });
}

export function exportAllPackages(registry: PackageRegistry): EnvelopeLike {
  return tc.ok({
    packages: registry.list().map((p) => ({
      id: p.id,
      directives: p.directives.map((d) => ({ domain: d.domain, action: d.action })),
    })),
  });
}

export function listPackages(registry: PackageRegistry): EnvelopeLike {
  return tc.ok({
    packages: registry.list().map((p) => ({
      id: p.id,
      directives: p.directives.length,
      installed_at: p.installedAt,
    })),
  });
}

type EnvelopeLike = ReturnType<typeof tc.ok>;
