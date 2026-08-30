// tc 客户端：封装 A0 SDK 的 call/discover/poll/wait，但用可注入 fetch（可单测、可取消）。
// 对齐 text-cli/src/skeleton/base/A0-protocol/js/call.js（§8.3）。
import type { Envelope } from 'textcli-core';
import { normalizeErrCode } from './envelope.js';
import type { DirectiveResult, TcDirectiveMeta } from './types.js';

export const DEFAULT_TIMEOUT_MS = 30_000;

/** 可注入的 HTTP 客户端（默认用全局 fetch；测试/运行时可替换） */
export type FetchLike = (input: string, init: { method: string; headers: Record<string, string>; body: string; signal?: AbortSignal }) => Promise<{ ok: boolean; status: number; json(): Promise<unknown> }>;

export interface TcClientOpts {
  /** 端点（远端 URL 或 'auto-self' 标记） */
  endpoint?: string;
  accessToken?: string;
  serviceToken?: string;
  /** rank 降级链端点列表 */
  rankEndpoints?: string[];
  /** 可注入 fetch（默认全局 fetch） */
  fetch?: FetchLike;
}

interface RequestOpts {
  prompt: string;
  timeoutMs?: number;
  endpoint?: string;
  accessToken?: string | null;
  serviceToken?: string | null;
  signal?: AbortSignal;
}

/** 从响应解析成 tc 信封（A0 parseEnvelope 的协议层；rst_err 是唯一错误信号） */
function parseEnvelope(payload: unknown, directive: string): DirectiveResult {
  const p = (payload && typeof payload === 'object' ? payload : {}) as Record<string, unknown>;
  const rd = (p.rst_data && typeof p.rst_data === 'object' ? p.rst_data : null) as Record<string, unknown> | null;
  const rstErr = typeof p.rst_err === 'string' ? p.rst_err : '';
  const rtype = typeof p.rst_types === 'string' ? p.rst_types : '';
  const ok = rstErr === '';
  const isAsync = !!(rd && rd.status === 'pending' && 'task_id' in rd);
  return {
    ok,
    data: rd,
    rtype,
    err_code: rstErr,
    directive,
    is_async: isAsync,
    task_id: isAsync && rd.task_id ? String(rd.task_id) : undefined,
  };
}

export class TcClient {
  private opts: TcClientOpts;
  private fetchImpl: FetchLike;
  private discoverCache: TcDirectiveMeta[] | null = null;
  private discoverCacheLang = 'auto';

  constructor(opts: TcClientOpts) {
    this.opts = opts;
    this.fetchImpl = opts.fetch ?? (globalThis.fetch as unknown as FetchLike);
  }

  /** 构建请求头（双令牌，per-call 覆盖优先） */
  private headers(accessToken: string | null | undefined, serviceToken: string | null | undefined): Record<string, string> {
    const h: Record<string, string> = { 'Content-Type': 'application/json' };
    const at = accessToken ?? this.opts.accessToken;
    const st = serviceToken ?? this.opts.serviceToken;
    if (at) h.Authorization = `Bearer ${at}`;
    if (st) h['Service-token'] = st;
    return h;
  }

  /** 从调用参数选端点：显式 > 单端点 > rank 链首 */
  private pickEndpoint(override?: string): string {
    if (override && override !== 'auto-self') return override;
    if (this.opts.endpoint && this.opts.endpoint !== 'auto-self') return this.opts.endpoint;
    if (this.opts.rankEndpoints && this.opts.rankEndpoints.length > 0) return this.opts.rankEndpoints[0]!;
    return 'http://127.0.0.1:28050/text-cli/cli';
  }

  /** 带超时 + 可取消的一次 POST（返回信封） */
  private async post(prompt: string, o: RequestOpts): Promise<Envelope> {
    const url = this.pickEndpoint(o.endpoint);
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), o.timeoutMs ?? DEFAULT_TIMEOUT_MS);
    const signal = this.combineSignal(controller.signal, o.signal);
    try {
      const res = await this.fetchImpl(url, {
        method: 'POST',
        headers: this.headers(o.accessToken, o.serviceToken),
        body: JSON.stringify({ prompt }),
        signal,
      });
      const payload = await res.json();
      return (payload && typeof payload === 'object' ? payload : {}) as Envelope;
    } finally {
      clearTimeout(timer);
    }
  }

  /** 合并外部 AbortSignal 与内部超时信号 */
  private combineSignal(internal: AbortSignal, external?: AbortSignal): AbortSignal {
    if (!external) return internal;
    const ctrl = new AbortController();
    const onInternal = () => ctrl.abort(internal.reason);
    const onExternal = () => ctrl.abort(external.reason);
    internal.addEventListener('abort', onInternal, { once: true });
    external.addEventListener('abort', onExternal, { once: true });
    return ctrl.signal;
  }

  /**
   * call：POST {endpoint}/text-cli/cli，带 rank 降级链。
   * 降级触发：ERR_NOT_FOUND / ERR_ROUTING / HTTP 不可达（A0 语义）；参数错误/鉴权失败不降级。
   */
  async call(prompt: string, o: { endpoint?: string; accessToken?: string | null; serviceToken?: string | null; timeoutMs?: number; signal?: AbortSignal } = {}): Promise<DirectiveResult> {
    const candidates = this.endpointCandidates(o.endpoint);
    let lastErr = 'ERR_ROUTING';
    let sawNetwork = false;
    for (let i = 0; i < candidates.length; i++) {
      const ep = candidates[i];
      const isLast = i === candidates.length - 1;
      try {
        const env = await this.post(prompt, { prompt, ...o, endpoint: ep });
        const result = parseEnvelope(env, prompt);
        // 可降级错误：ERR_NOT_FOUND/ERR_ROUTING——仅当还有下一个 rank 端点时才切
        if ((result.err_code === 'ERR_NOT_FOUND' || result.err_code === 'ERR_ROUTING') && !isLast) {
          lastErr = result.err_code;
          continue;
        }
        return result;
      } catch {
        sawNetwork = true;
        if (!isLast) continue; // 网络不可达 → 切下一个
        break;
      }
    }
    // 全部尝试完：返回最后一个真实错误（纯网络失败 → ERR_ROUTING；否则回传实际 err_code）
    return {
      ok: false,
      data: null,
      rtype: '',
      err_code: sawNetwork ? 'ERR_ROUTING' : lastErr,
      directive: prompt,
      is_async: false,
    };
  }

  /** rank 降级候选：显式 > 单端点 > rankEndpoints 全链 */
  private endpointCandidates(override?: string): string[] {
    if (override && override !== 'auto-self') return [override];
    if (this.opts.endpoint && this.opts.endpoint !== 'auto-self') return [this.opts.endpoint];
    const chain = this.opts.rankEndpoints && this.opts.rankEndpoints.length > 0 ? this.opts.rankEndpoints : ['http://127.0.0.1:28050/text-cli/cli'];
    return chain;
  }

  /** discover：AI:text-cli;query,json[,lang]，带缓存 + 客户端过滤 */
  async discover(o: { runtime?: string; category?: string; search?: string; lang?: string; forceRefresh?: boolean; endpoint?: string; signal?: AbortSignal } = {}): Promise<TcDirectiveMeta[]> {
    const lang = o.lang ?? 'auto';
    if (o.forceRefresh || this.discoverCache === null || this.discoverCacheLang !== lang) {
      const query = lang !== 'auto' ? `AI:text-cli;query,json,${lang}` : 'AI:text-cli;query,json';
      const result = await this.call(query, { endpoint: o.endpoint, signal: o.signal });
      if (!result.ok) {
        throw new Error(`discover failed: ${result.err_code}`);
      }
      const data = result.data as Record<string, unknown> | null;
      const arr = data && Array.isArray(data.directives) ? (data.directives as unknown[]) : [];
      this.discoverCache = arr.map((d) => d as TcDirectiveMeta);
      this.discoverCacheLang = lang;
    }
    const items = [...this.discoverCache!];
    // 客户端过滤
    if (o.runtime) {
      return items.filter((d) => (d.runtime as string | undefined)?.toLowerCase() === o.runtime!.toLowerCase());
    }
    if (o.category) {
      return items.filter((d) => (d.category as string | undefined) === o.category);
    }
    if (o.search) {
      const q = o.search.toLowerCase();
      return items.filter((d) => [
        d.domain, d.action, d.usage, d.description, d.domain_zh, d.action_zh, d.description_zh, d.package, d.category,
      ].some((v) => typeof v === 'string' && v.toLowerCase().includes(q)));
    }
    return items;
  }

  /** poll：AI:task;status,{taskId} 同通道查询（A0 语义） */
  async poll(taskId: string, o: { endpoint?: string; signal?: AbortSignal } = {}): Promise<DirectiveResult> {
    const result = await this.call(`AI:task;status,${taskId}`, { endpoint: o.endpoint, signal: o.signal });
    if (!result.ok) return result;
    const data = result.data as Record<string, unknown> | null;
    const state = data ? (data.state as string | undefined) || (data.status as string | undefined) || '' : '';
    if (state === 'pending' || state === 'running') {
      return { ...result, is_async: true, task_id: taskId };
    }
    if (state === 'done') {
      const inner = data && data.result && typeof data.result === 'object' ? data.result : null;
      return { ...result, is_async: false, data: inner, ok: true };
    }
    if (state === 'error') {
      return { ...result, is_async: false, ok: false, err_code: 'TASK_ERROR' };
    }
    return result;
  }

  /** wait：指数退避轮询至完成或超时（A0 语义） */
  async wait(taskId: string, o: { onStatus?: (r: DirectiveResult) => void; maxWaitMs?: number; initialMs?: number; endpoint?: string; signal?: AbortSignal } = {}): Promise<DirectiveResult> {
    const start = Date.now();
    const maxWait = o.maxWaitMs ?? 60_000;
    const initial = o.initialMs ?? 2_000;
    let attempt = 0;
    let interval = initial;
    while (true) {
      attempt++;
      const elapsed = Date.now() - start;
      if (elapsed >= maxWait) {
        return { ok: false, data: null, rtype: '', err_code: 'wait timeout', directive: '', is_async: true, task_id: taskId };
      }
      const result = await this.poll(taskId, { endpoint: o.endpoint, signal: o.signal });
      if (o.onStatus) o.onStatus(result);
      if (!result.is_async) return result;
      interval = Math.min(initial * Math.pow(2, attempt - 1), 30_000);
      await sleep(interval);
    }
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
