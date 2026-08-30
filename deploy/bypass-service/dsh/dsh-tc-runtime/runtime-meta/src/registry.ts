/**
 * registry.ts——tc 指令包注册表（功能设计 §7，附录 B 机制 7）
 *
 * 安装状态：id → {schema, handlerPath, policy, grants, directives}。
 * install 返回 disposer（注册即 effect、卸载即回收——对齐 Cordis effect 语义，
 * ubuntu 联调时映射到 `ctx.tools.register()` 的 disposer）。
 * 纯内存，可注入持久化（Phase 8 后可扩展）。
 */
import type { SandboxPolicy } from "@dsh-tc/runtime-sandbox";
import type { PackageGrants } from "@dsh-tc/runtime-credentials";

export interface InstalledDirective {
  domain: string;
  action: string;
  /** 工具名：tc__<domain>__<action>（对齐工具命名契约） */
  toolName: string;
}

export interface InstalledPackage {
  id: string;
  schema: Record<string, unknown>;
  /** 包 handler 入口（Phase 3 executor-js 的 handlerPath） */
  handlerPath: string;
  /** 沙箱策略；null = 宿主特权（安装被拒，不会出现在注册表） */
  policy: SandboxPolicy;
  /** 凭据授权（包↔凭据映射） */
  grants: PackageGrants;
  directives: InstalledDirective[];
  installedAt: string;
}

export class PackageRegistry {
  private readonly pkgs = new Map<string, InstalledPackage>();

  install(pkg: InstalledPackage): void {
    this.pkgs.set(pkg.id, pkg);
  }

  uninstall(id: string): boolean {
    return this.pkgs.delete(id);
  }

  get(id: string): InstalledPackage | undefined {
    return this.pkgs.get(id);
  }

  list(): InstalledPackage[] {
    return [...this.pkgs.values()];
  }

  /** 是否存在 */
  has(id: string): boolean {
    return this.pkgs.has(id);
  }
}
