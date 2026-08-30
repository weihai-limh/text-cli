// textcli-core（CJS）的类型声明——ESM default import 互操作已实测通过
// 复用于 dsh-tc-runtime/types/textcli-core.d.ts（与 `file:.../textcli-core` 依赖对齐）
declare module 'textcli-core' {
  export interface ParsedInstruction {
    domain: string;
    action: string;
    params: string[];
    /** parse 失败时携带错误码（协议闭集） */
    error?: string;
    /** parse 失败时的人类可读原因 */
    reason?: string;
  }

  export interface Envelope {
    rst_types: string;
    rst_data: Record<string, unknown> | null;
    rst_err: string;
  }

  export function parse(prompt: string): ParsedInstruction;
  export function ok(data: unknown, rstType?: string): Envelope;
  export function err(code: string, reason?: string): Envelope;
  export function execute(prompt: string): Promise<Envelope>;
  export function health(): {
    status: string;
    body: string;
    version: string;
    spec_version: string;
    runtime: string;
  };
  export function discover(filter?: string): { directives: Array<Record<string, unknown>> };
  export function loadPackageFromPath(pkgDir: string): unknown;

  const tc: {
    parse: typeof parse;
    ok: typeof ok;
    err: typeof err;
    execute: typeof execute;
    health: typeof health;
    discover: typeof discover;
    loadPackageFromPath: typeof loadPackageFromPath;
  };
  export default tc;
}

declare module 'textcli-core/loader.node' {
  export function loadPackageFromPath(pkgDir: string): unknown;
  export function getLoaderState(): unknown;
}
