/**
 * grant.ts——包↔凭据授权映射（功能设计 §6.2/§6.3，B5 第一防线）
 *
 * 从包 `schema.credentials` 声明自动生成（最小权限）：
 * - ref = `TC_<NAME>`（TC_ 前缀：审计可识别，非隔离，§6.3）
 * - envKey = ref（CredentialRef 即 POSIX 环境变量名——包 handler 读 process.env 零改动）
 * - 双凭据（gd-map key+secret）→ 拆成两个独立 grant（对齐 dsh 单值模型）
 *
 * 纯函数，无 IO。
 */

export interface CredentialGrant {
  /** 凭据引用（POSIX 环境变量名；TC_ 前缀命名空间） */
  ref: string;
  /** 注入受限执行环境的键（= ref） */
  envKey: string;
  /** 包 schema 声明的凭据名（原始） */
  sourceName: string;
}

export interface PackageGrants {
  packageId: string;
  grants: CredentialGrant[];
}

/** schema.credentials 声明投影 */
export interface CredentialDeclaration {
  /** 凭据名（如 my_api_key）——映射为 TC_MY_API_KEY */
  name: string;
}

/** 名称 → TC_ 前缀引用（大写 + 非字母数字转下划线） */
export function toRefName(name: string): string {
  const clean = name.toUpperCase().replace(/[^A-Z0-9]/g, "_");
  return `TC_${clean}`;
}

export function buildGrants(
  packageId: string,
  declarations: CredentialDeclaration[] | undefined,
): PackageGrants {
  const grants: CredentialGrant[] = (declarations ?? []).map((d) => {
    const ref = toRefName(d.name);
    return { ref, envKey: ref, sourceName: d.name };
  });
  return { packageId, grants };
}

/** 授权校验：包是否有权使用指定 ref */
export function isGranted(pkg: PackageGrants, ref: string): boolean {
  return pkg.grants.some((g) => g.ref === ref);
}
