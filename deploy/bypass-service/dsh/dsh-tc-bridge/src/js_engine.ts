// JS 引擎：封装 textcli-core 的 loadPackageFromPath / execute / discover，供 run_tc_js 使用。
// 对齐 other/tc-js-skeleton/packages/textcli-core/{loader.node,index}.js（§8.2 事实 5/6/8/9）。
// 关键：装载后 schema 进 registry，execute(prompt) 一步到位 parse+dispatch+envelope。
import path from 'node:path';
import { loadPackageFromPath, discover as tcDiscover, execute as tcExecute } from 'textcli-core';
import { tcToDsh } from './envelope.js';
import type { TcDirectiveMeta, ToolResult } from './types.js';

export interface LoadedPackage {
  id: string;
  directives: TcDirectiveMeta[];
}

export interface JsEngineOpts {
  /** pkg_dir 白名单根（红线⑥，防 RCE/目录穿越）；空 = 允许相对路径装载（受 pkgDir 显式约束） */
  jsPkgDirs?: string[];
}

export class JsEngine {
  private jsPkgDirs: string[];
  private loaded = new Set<string>();

  constructor(opts: JsEngineOpts = {}) {
    this.jsPkgDirs = opts.jsPkgDirs ?? [];
  }

  /** 校验 pkg_dir 是否在白名单根内（路径前缀安全判断，防目录穿越） */
  private allowed(pkgDir: string): boolean {
    if (this.jsPkgDirs.length === 0) return true; // 未配置白名单 → 允许（由调用方显式约束）
    const abs = path.resolve(pkgDir);
    return this.jsPkgDirs.some((root) => {
      const r = path.resolve(root);
      return abs === r || abs.startsWith(r + path.sep);
    });
  }

  /** 是否已装载某 pkg_dir */
  has(pkgDir: string): boolean {
    const key = path.resolve(pkgDir);
    return this.loaded.has(key);
  }

  /** 装载本地包；reload:true 时强制重新装载（textcli-core 内部已清 require cache，支持热更新） */
  load(pkgDir: string, o: { reload?: boolean } = {}): LoadedPackage {
    if (!this.allowed(pkgDir)) {
      throw new Error(`pkg_dir not in jsPkgDirs allowlist: ${pkgDir}`);
    }
    const key = path.resolve(pkgDir);
    if (this.has(pkgDir) && !o.reload) {
      // 已装载且不强制重载：返回空（调用方应复用 discover 获取指令，不重复注册）
      return { id: '', directives: [] };
    }
    const result = loadPackageFromPath(key);
    this.loaded.add(key);
    // loadPackageFromPath 返回 { id, directives }（§8.2 事实 5）
    const id = typeof result === 'object' && result !== null && 'id' in result ? String((result as { id: unknown }).id) : '';
    const directives = Array.isArray((result as { directives?: unknown }).directives)
      ? ((result as { directives: unknown[] }).directives as TcDirectiveMeta[])
      : [];
    return { id, directives };
  }

  /** 执行：textcli-core execute(prompt) 一步到位，返回 tc 闭集信封 */
  async execute(prompt: string, _o: { signal?: AbortSignal } = {}): Promise<ToolResult> {
    const env = await tcExecute(prompt);
    return tcToDsh(env);
  }

  /** 发现：聚合已装载包的指令（schema 缓存） */
  discover(): { directives: TcDirectiveMeta[] } {
    const res = tcDiscover();
    const arr = Array.isArray(res && res.directives) ? (res.directives as unknown[]) : [];
    return { directives: arr.map((d) => d as TcDirectiveMeta) };
  }

  /** 已装载集合大小（防无限装载占内存，红线⑥） */
  get loadedCount(): number {
    return this.loaded.size;
  }
}
