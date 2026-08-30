// 五个工具的定义与装配逻辑（依赖注入 deps，纯逻辑可单测）。
// 对齐 dsh-tc-bridge.md §2.2 工具一~五 + §4.4。
import { parse } from 'textcli-core';
import { directiveResultToToolResult } from './envelope.js';
import { filterTcDirectives, makeAllowlist } from './allowlist.js';
import { fromToolName, isTcTool } from './mapper.js';
import { detectModeWithConfig } from './runtime_detect.js';
import { proxyTool } from './tool_proxy.js';
import { makeSessionRecord } from './session.js';
import type { BridgeConfig } from './config.js';
import type { JsEngine } from './js_engine.js';
import type { SessionWriter } from './session.js';
import type { TcClient } from './tc_client.js';
import type { TcDirectiveMeta, ToolExecutionContext, ToolRegistry, ToolResult } from './types.js';

/** 桥对外工具的泛型定义 */
export interface ToolDef {
  name: string;
  description: string;
  execute(args: Record<string, unknown>, exec: ToolExecutionContext): Promise<ToolResult>;
}

/** 桥依赖注入（apply(ctx) 时由真实 dsh 提供；单测用 mock） */
export interface BridgeDeps {
  config: BridgeConfig;
  registry: ToolRegistry;
  tcClient: TcClient;
  jsEngine: JsEngine;
  /** session 透写（红线⑧ Model-visible ⟺ logged） */
  session: SessionWriter;
}

/** 执行包裹：记录 session + 透传错误（所有 tool 共用） */
async function runWithSession(
  deps: BridgeDeps,
  toolName: string,
  promptDesc: string,
  fn: () => Promise<ToolResult>,
): Promise<ToolResult> {
  try {
    const result = await fn();
    deps.session.write(makeSessionRecord(toolName, promptDesc, result));
    return result;
  } catch (e) {
    const err = e instanceof Error ? e.message : String(e);
    deps.session.write(makeSessionRecord(toolName, promptDesc, undefined, err));
    return { ok: false, data: null, err };
  }
}

/** 从 AI:d;a,params 解析 domain/action（短路路由前使用，复用 textcli-core parse） */
function parseDirective(prompt: string): { domain: string; action: string } | null {
  const p = parse(prompt);
  if (!p || !p.domain || !p.action || p.error) return null;
  return { domain: p.domain, action: p.action };
}

/** tc 指令 → find_tc 字典条目 */
function directiveEntry(d: TcDirectiveMeta, callTool: 'call_tc' | 'run_tc_js'): { cli: string; usage: string; call_tool: string; rank: number } {
  return {
    cli: `AI:${d.domain};${d.action},<参数>`,
    usage: `${callTool}({ prompt: 'AI:${d.domain};${d.action}' })`,
    call_tool: callTool,
    rank: typeof d.rank === 'number' ? d.rank : 0,
  };
}

/** 工具一：call_tc */
function buildCallTc(deps: BridgeDeps): ToolDef {
  return {
    name: 'call_tc',
    description: '调用 tc 指令：AI:<域>;<动作>,<参数>。混合模式（dsh 同时是 tc 运行时）下同进程短路调已注册 tc__ 工具；桥接模式走远端 tc 端点。',
    async execute(args, exec) {
      const prompt = typeof args.prompt === 'string' ? args.prompt : '';
      if (!prompt) return { ok: false, data: null, err: 'prompt required' };
      return runWithSession(deps, 'call_tc', prompt, async () => {
        const explicitEndpoint = typeof args.endpoint === 'string' && args.endpoint !== 'auto-self' ? args.endpoint : undefined;
        const mode = detectModeWithConfig(deps.registry, deps.config.runtimeAutoDetect);

        // 混合模式短路：未显式指定远端端点
        if (mode === 'hybrid' && !explicitEndpoint) {
          const parsed = parseDirective(prompt);
          if (parsed) {
            const tool = deps.registry.get(`tc__${parsed.domain}__${parsed.action}`);
            if (tool) {
              const r = await tool.execute({ prompt }, exec);
              return r;
            }
          }
        }

        // 桥接模式 / 显式远端
        const r = await deps.tcClient.call(prompt, {
          endpoint: explicitEndpoint,
          signal: exec.signal,
          accessToken: typeof args.accessToken === 'string' ? args.accessToken : null,
          serviceToken: typeof args.serviceToken === 'string' ? args.serviceToken : null,
          timeoutMs: typeof args.timeout_ms === 'number' ? args.timeout_ms : undefined,
        });
        const result = directiveResultToToolResult(r);
        // 异步 + wait=true → 轮询至完成
        if (args.wait === true && result.is_async && r.task_id) {
          const final = await deps.tcClient.wait(r.task_id, {
            endpoint: explicitEndpoint,
            signal: exec.signal,
            maxWaitMs: typeof args.timeout_ms === 'number' ? args.timeout_ms : undefined,
          });
          return directiveResultToToolResult(final);
        }
        return result;
      });
    },
  };
}

/** 工具二：wait_tc */
function buildWaitTc(deps: BridgeDeps): ToolDef {
  return {
    name: 'wait_tc',
    description: '轮询 tc 异步长任务（call_tc 返回 is_async 且 task_id 时使用），指数退避直至完成或超时。',
    async execute(args, exec) {
      const taskId = typeof args.task_id === 'string' ? args.task_id : '';
      if (!taskId) return { ok: false, data: null, err: 'task_id required' };
      return runWithSession(deps, 'wait_tc', `wait:${taskId}`, async () => {
        const explicitEndpoint = typeof args.endpoint === 'string' && args.endpoint !== 'auto-self' ? args.endpoint : undefined;
        const r = await deps.tcClient.wait(taskId, {
          endpoint: explicitEndpoint,
          signal: exec.signal,
          maxWaitMs: typeof args.timeout_ms === 'number' ? args.timeout_ms : undefined,
        });
        return directiveResultToToolResult(r);
      });
    },
  };
}

/** 工具四：run_tc_js */
function buildRunTcJs(deps: BridgeDeps): ToolDef {
  return {
    name: 'run_tc_js',
    description: '进程内零网络执行本地 tc JS 包（经 textcli-core）。pkg_dir 受 jsPkgDirs 白名单约束。',
    async execute(args, exec) {
      const pkgDir = typeof args.pkg_dir === 'string' ? args.pkg_dir : '';
      const prompt = typeof args.prompt === 'string' ? args.prompt : '';
      if (!pkgDir || !prompt) return { ok: false, data: null, err: 'pkg_dir and prompt required' };
      return runWithSession(deps, 'run_tc_js', `${pkgDir} :: ${prompt}`, async () => {
        if (args.reload === true || !deps.jsEngine.has(pkgDir)) {
          deps.jsEngine.load(pkgDir, { reload: args.reload === true });
        }
        return await deps.jsEngine.execute(prompt);
      });
    },
  };
}

/** 工具三：tool_avatar */
function buildToolAvatar(deps: BridgeDeps): ToolDef {
  return {
    name: 'tool_avatar',
    description: '同进程代理 dsh 已注册的任意 tool（含 mcp tool）。方向单向，仅 dsh agent 调 dsh 自身 tool。',
    async execute(args, exec) {
      const name = typeof args.name === 'string' ? args.name : '';
      if (!name) return { ok: false, data: null, err: 'name required' };
      const a = args.args && typeof args.args === 'object' ? (args.args as Record<string, unknown>) : {};
      return runWithSession(deps, 'tool_avatar', name, async () =>
        proxyTool(name, a, deps.registry, exec, { timeoutMs: typeof args.timeout_ms === 'number' ? args.timeout_ms : undefined }),
      );
    },
  };
}

/** 工具五：find_tc */
function buildFindTc(deps: BridgeDeps): ToolDef {
  return {
    name: 'find_tc',
    description: '桥内可调能力的统一发现面（tc_remote / tc_local / dsh_tool）。tc 源按 allowlist 过滤（仅 tc 源）；dsh_tool 源全量暴露（tool_avatar 省 token 通道）。',
    async execute(args, exec) {
      const source = typeof args.source === 'string' ? args.source : 'all';
      return runWithSession(deps, 'find_tc', `source:${source}`, async () => {
        const dict = await discoverAll(deps, args, exec);
        return { ok: true, data: dict };
      });
    },
  };
}

/** discover 聚合（对齐设计 §2.3.4 discover.ts）：三源 → 扁平字典 + key/limit/rank */
async function discoverAll(
  deps: BridgeDeps,
  args: Record<string, unknown>,
  exec: ToolExecutionContext,
): Promise<Record<string, { cli: string; usage: string; call_tool: string; rank: number }>> {
  const source = typeof args.source === 'string' ? args.source : 'all';
  const explicitEndpoint = typeof args.endpoint === 'string' && args.endpoint !== 'auto-self' ? args.endpoint : undefined;
  const mode = detectModeWithConfig(deps.registry, deps.config.runtimeAutoDetect);
  const allow = makeAllowlist(deps.config.tcAllowlist);
  const dict: Record<string, { cli: string; usage: string; call_tool: string; rank: number }> = {};

  // tc_remote 源：A0 discover
  if (source === 'all' || source === 'tc_remote') {
    let dirs: TcDirectiveMeta[] = [];
    try {
      dirs = await deps.tcClient.discover({ endpoint: explicitEndpoint, signal: exec.signal });
    } catch {
      dirs = [];
    }
    for (const d of filterTcDirectives(dirs, allow)) {
      dict[`${d.domain}_${d.action}`] = directiveEntry(d, 'call_tc');
    }
  }

  // tc_local 源：jsEngine discover
  if (source === 'all' || source === 'tc_local') {
    const dirs = deps.jsEngine.discover().directives;
    for (const d of filterTcDirectives(dirs, allow)) {
      dict[`${d.domain}_${d.action}`] = directiveEntry(d, 'run_tc_js');
    }
  }

  // dsh_tool 源：registry 全名（tc__ 工具映射回 AI: 并受 allowlist；非 tc__ 全量暴露经 tool_avatar）
  if (source === 'all' || source === 'dsh_tool') {
    for (const name of deps.registry.names()) {
      if (isTcTool(name)) {
        if (mode !== 'hybrid') continue; // 桥接模式不应出现 tc__ 工具
        const mapped = fromToolName(name);
        if (!mapped) continue;
        const meta: TcDirectiveMeta = { domain: mapped.domain, action: mapped.action, rank: 0 };
        if (filterTcDirectives([meta], allow).length > 0) {
          dict[`${mapped.domain}_${mapped.action}`] = directiveEntry(meta, 'call_tc');
        }
      } else {
        dict[name] = { cli: name, usage: `tool_avatar({ name: '${name}', args: {...} })`, call_tool: 'tool_avatar', rank: 0 };
      }
    }
  }

  // key 过滤
  let entries = Object.entries(dict);
  if (typeof args.key === 'string' && args.key.length > 0) {
    const q = args.key;
    entries = entries.filter(([k]) => k.includes(q));
  }
  // rank 降序
  entries.sort((a, b) => (b[1].rank ?? 0) - (a[1].rank ?? 0));
  // limit 截断
  if (typeof args.limit === 'number' && args.limit > 0) {
    entries = entries.slice(0, args.limit);
  }
  return Object.fromEntries(entries);
}

/** 创建五个工具的完整集合 */
export function createBridgeTools(deps: BridgeDeps): ToolDef[] {
  return [
    buildCallTc(deps),
    buildWaitTc(deps),
    buildToolAvatar(deps),
    buildRunTcJs(deps),
    buildFindTc(deps),
  ];
}
