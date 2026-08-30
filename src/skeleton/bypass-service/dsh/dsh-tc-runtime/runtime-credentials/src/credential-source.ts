/**
 * credential-source.ts——平台凭据源注入接口（功能设计 §6.1，对齐 dsh `ctx.credentials`）
 *
 * `CredentialRef` = 品牌化的 POSIX 环境变量名（引用非明文）；每次操作解析。
 * ubuntu 联调时接 `ctx.credentials.resolve(ref)`。
 */
export interface ResolvedCredential {
  /** 凭据值（明文——仅存在于 resolve 返回值，不落盘、不进包源码） */
  value: string;
}

export interface CredentialSource {
  /** 解析凭据引用；空值视为缺失 */
  resolve(ref: string): Promise<ResolvedCredential | undefined>;
}

/** 测试夹具：内存凭据源 */
export function createMemoryCredentialSource(
  entries: Record<string, string>,
): CredentialSource {
  return {
    async resolve(ref) {
      const value = entries[ref];
      return value === undefined ? undefined : { value };
    },
  };
}
