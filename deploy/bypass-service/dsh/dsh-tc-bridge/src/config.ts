// 桥配置：端点三态 + 双令牌 + rank 降级链 + jsPkgDirs 白名单 + tc 白名单 + 模态自检。
// 默认值对齐 A0 SDK（DEFAULT_ENDPOINT = http://127.0.0.1:28050/text-cli/cli）。
import { type TcEndpointConfig } from './types.js';

/** A0 SDK 默认端点（SPEC 标准端口） */
export const DEFAULT_ENDPOINT = 'http://127.0.0.1:28050/text-cli/cli';

/** tc 指令白名单条目：粒度 domain;action，支持域级/通配（如 map;*） */
export type AllowlistEntry = string;

export interface BridgeConfig {
  /** 端点来源三态：'auto-self'（混合模式短路）/ 具体 URL（远端）/ 省略（桥接模式默认端点） */
  endpoint?: string | 'auto-self';
  accessToken?: string;
  serviceToken?: string;
  /** rank 降级链端点列表 */
  rankEndpoints?: string[];
  /** run_tc_js 的 pkg_dir 白名单（防 RCE/目录穿越，红线⑥） */
  jsPkgDirs: string[];
  /** tc 指令白名单（仅 tc 源，dsh_tool 不过滤；空 = 全暴露，向后兼容桥接模式） */
  tcAllowlist: AllowlistEntry[];
  /** 混合模式自检：是否检测 ctx.tools 的 tc__ 前缀工具以决定 bridging/hybrid */
  runtimeAutoDetect: boolean;
}

/** 缺省配置（env 优先级：环境变量 > 此默认值） */
export function defaultConfig(): BridgeConfig {
  return {
    endpoint: 'auto-self',
    accessToken: process.env.TC_ACCESS_TOKEN,
    serviceToken: process.env.TC_SERVICE_TOKEN,
    rankEndpoints: [DEFAULT_ENDPOINT],
    jsPkgDirs: [],
    tcAllowlist: [],
    runtimeAutoDetect: true,
  };
}

/** 归一 TcEndpointConfig：把 BridgeConfig 的三态 endpoint 解析成具体端点或短路标记 */
export function resolveEndpoint(cfg: BridgeConfig, override?: string): TcEndpointConfig {
  const e = override ?? cfg.endpoint;
  if (e === 'auto-self') {
    return { endpoint: 'auto-self', accessToken: cfg.accessToken, serviceToken: cfg.serviceToken, rankEndpoints: cfg.rankEndpoints };
  }
  if (typeof e === 'string' && e.length > 0) {
    return { endpoint: e, accessToken: cfg.accessToken, serviceToken: cfg.serviceToken, rankEndpoints: cfg.rankEndpoints };
  }
  return { accessToken: cfg.accessToken, serviceToken: cfg.serviceToken, rankEndpoints: cfg.rankEndpoints };
}
