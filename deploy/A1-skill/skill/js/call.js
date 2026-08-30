/**
 * call.js — text-cli 指令调用（Node.js）
 *
 * 零依赖，仅用 Node.js 内置模块。
 * 从 conf.json 或环境变量读取端点/令牌配置。
 *
 * 用法:
 *   const { call, callBatch, poll, wait, discover, DirectiveResult } = require('./call');
 *   const result = await call('AI:tc-datetime;now');
 *   console.log(result.data);
 *
 * 环境变量:
 *   TEXT_CLI_ENDPOINT          覆盖端点地址
 *   TEXT_CLI_SERVICE_TOKEN     覆盖 Service Token
 *   TEXT_CLI_ACCESS_TOKEN      覆盖 Access Token
 *
 * 配置文件:
 *   ./conf.json
 *   { "endpoint": "...", "service_token": "...", "access_token": "..." }
 */

const path = require('path');
const fs = require('fs');

// ─── 配置 ────────────────────────────────────────────

const CONF_PATH = path.resolve(__dirname, 'conf.json');
const DEFAULT_ENDPOINT = 'http://127.0.0.1:28050/text-cli/cli';
const DEFAULT_TIMEOUT = 30;

/**
 * 加载 conf.json
 */
function loadConf() {
  try {
    if (fs.existsSync(CONF_PATH)) {
      return JSON.parse(fs.readFileSync(CONF_PATH, 'utf-8'));
    }
  } catch (_) { /* 文件不存在或格式错误，使用默认值 */ }
  return {};
}

/**
 * 按优先级取值: 环境变量 > conf.json > default
 */
function getConfig(key, envName, defaultVal) {
  if (typeof process.env[envName] === 'string' && process.env[envName] !== '') {
    return process.env[envName];
  }
  const conf = loadConf();
  if (conf[key] !== undefined && conf[key] !== null) {
    return conf[key];
  }
  return defaultVal;
}

function config() {
  return {
    endpoint: getConfig('endpoint', 'TEXT_CLI_ENDPOINT', DEFAULT_ENDPOINT),
    serviceToken: getConfig('service_token', 'TEXT_CLI_SERVICE_TOKEN', ''),
    accessToken: getConfig('access_token', 'TEXT_CLI_ACCESS_TOKEN', ''),
  };
}

// ─── DirectiveResult ─────────────────────────────────

class DirectiveResult {
  /**
   * @param {object} params
   * @param {boolean}  params.ok
   * @param {*}        params.data        - rst_data 直接值
   * @param {string}   params.rtype       - 结果类型
   * @param {string}   params.err_code    - 错误码
   * @param {string}   params.directive   - 原始指令
   * @param {boolean}  params.is_async    - 是否异步任务
   * @param {string}   [params.task_id]   - 异步任务 id
   */
  constructor({ ok, data, rtype, err_code, directive, is_async, task_id }) {
    this.ok = ok;
    this.data = data;
    this.rtype = rtype || '';
    this.err_code = err_code || '';
    this.directive = directive || '';
    this.is_async = is_async || false;
    this._task_id = task_id || null;
  }

  get task_id() {
    return this._task_id;
  }
}

// ─── 请求构建 ────────────────────────────────────────

/**
 * 构建请求头，支持 per-call 令牌覆盖。
 *
 * @param {object} [overrides]
 * @param {string|null} [overrides.accessToken]  - 覆盖 Access Token（null 则用全局配置）
 * @param {string|null} [overrides.serviceToken] - 覆盖 Service Token（null 则用全局配置）
 * @returns {object} 请求头
 */
function buildHeaders({ accessToken = null, serviceToken = null } = {}) {
  const cfg = config();
  const headers = { 'Content-Type': 'application/json' };
  const at = accessToken !== null ? accessToken : cfg.accessToken;
  const st = serviceToken !== null ? serviceToken : cfg.serviceToken;
  if (at) headers['Authorization'] = `Bearer ${at}`;
  if (st) headers['Service-token'] = st;
  return headers;
}

/**
 * 超时 AbortController
 */
function timeoutSignal(seconds) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), seconds * 1000);
  return { controller, timer };
}

// ─── 信封解析 ────────────────────────────────────────

/**
 * Parse response envelope into DirectiveResult.
 * - rst_data read directly (no .text nesting)
 * - rst_err determines ok
 * - is_async detected via rst_data.status=="pending" && task_id present
 */
function parseEnvelope(payload, directive) {
  const rd = payload.rst_data || {};
  const rst_err = payload.rst_err || '';
  const rtype = payload.rst_types || '';
  const data = rd !== null ? rd : null;

  const ok = rst_err === '';
  const is_async = (
    typeof rd === 'object' && rd !== null &&
    rd.status === 'pending' && 'task_id' in rd
  );
  const task_id = is_async ? (rd.task_id || null) : null;

  return new DirectiveResult({
    ok,
    data,
    rtype,
    err_code: rst_err,
    directive,
    is_async,
    task_id,
  });
}

/**
 * 从 HTTP Response 提取 JSON 并解析信封
 */
async function parseResponse(response, directive) {
  const payload = await response.json();

  // Always try envelope parsing first — text-cli protocol returns
  // envelopes even on HTTP errors (rst_err carries the error code).
  return parseEnvelope(payload, directive);
}

// ─── _request（内部请求函数）─────────────────────────

/**
 * 内部请求函数，支持 per-call 终点/令牌覆盖。
 * 当覆盖参数为 null 时，回退到全局 config / 环境变量。
 *
 * @param {object} opts
 * @param {string}      opts.directive                 - 指令文本
 * @param {number}      [opts.timeout=30]              - 超时秒数
 * @param {string|null} [opts.endpoint=null]           - 覆盖端点地址
 * @param {string|null} [opts.accessToken=null]        - 覆盖 Access Token
 * @param {string|null} [opts.serviceToken=null]       - 覆盖 Service Token
 * @returns {Promise<DirectiveResult>}
 */
async function _request({ directive, timeout = DEFAULT_TIMEOUT, endpoint = null, accessToken = null, serviceToken = null }) {
  const cfg = config();
  const url = endpoint !== null ? endpoint : cfg.endpoint;
  const headers = buildHeaders({ accessToken, serviceToken });
  const { controller, timer } = timeoutSignal(timeout);

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers,
      body: JSON.stringify({ prompt: directive }),
      signal: controller.signal,
    });

    return await parseResponse(response, directive);
  } catch (e) {
    if (e.name === 'AbortError') {
      return new DirectiveResult({
        ok: false,
        data: null,
        rtype: '',
        err_code: `TASK_TIMEOUT`,
        directive,
        is_async: false,
        task_id: null,
      });
    }
    // Network errors (connection refused, DNS failure, unreachable)
    return new DirectiveResult({
      ok: false,
      data: null,
      rtype: '',
      err_code: 'ENDPOINT_UNREACHABLE',
      directive,
      is_async: false,
      task_id: null,
    });
  } finally {
    clearTimeout(timer);
  }
}

// ─── call ────────────────────────────────────────────

/**
 * 调用 text-cli 指令，总是立即返回 DirectiveResult。
 *
 * @param {string} dictive - 指令文本
 * @param {object} [opts]  - 可选参数
 * @param {number}      [opts.timeout=30]              - 超时秒数
 * @param {string|null} [opts.endpoint=null]           - 覆盖端点地址（null 则用全局配置）
 * @param {string|null} [opts.accessToken=null]        - 覆盖 Access Token（null 则用全局配置）
 * @param {string|null} [opts.serviceToken=null]       - 覆盖 Service Token（null 则用全局配置）
 * @returns {Promise<DirectiveResult>}
 *
 * @example
 *   // 使用全局配置
 *   const result = await call('AI:tc-datetime;now');
 *
 *   // 使用 per-call 自定义令牌
 *   const result = await call('AI:tc-datetime;now', {
 *     accessToken: 'my-custom-token',
 *     serviceToken: 'my-service-token'
 *   });
 *
 *   // 使用自定义端点
 *   const result = await call('AI:tc-datetime;now', {
 *     endpoint: 'https://other-api.example.com/text-cli/cli',
 *     accessToken: 'other-token'
 *   });
 */
async function call(directive, { timeout = DEFAULT_TIMEOUT, endpoint = null, accessToken = null, serviceToken = null } = {}) {
  return _request({ directive, timeout, endpoint, accessToken, serviceToken });
}

// ─── callBatch ───────────────────────────────────────

/**
 * 批量调用多个指令。
 *
 * @param {Array<{directive: string, timeout?: number, endpoint?: string, accessToken?: string, serviceToken?: string}>|string[]} directives - 指令或指令数组
 * @param {number} [timeout=30] - 默认超时秒数
 * @returns {Promise<DirectiveResult[]>}
 */
async function callBatch(directives, timeout = DEFAULT_TIMEOUT) {
  const results = [];
  for (const item of directives) {
    if (typeof item === 'string') {
      results.push(await call(item, { timeout }));
    } else {
      results.push(await call(item.directive, {
        timeout: item.timeout || timeout,
        endpoint: item.endpoint || null,
        accessToken: item.accessToken || null,
        serviceToken: item.serviceToken || null,
      }));
    }
  }
  return results;
}

// ─── poll ────────────────────────────────────────────

/**
 * Query async task status via the directive pipeline.
 * Uses AI:task;status,{taskId} — same channel as Python SDK for consistency.
 * While task is pending/running, result.is_async stays true.
 *
 * @param {string} taskId - Task ID
 * @returns {Promise<DirectiveResult>}
 */
async function poll(taskId) {
  const result = await _request({ directive: `AI:task;status,${taskId}` });

  if (!result.ok) {
    return result;
  }

  const taskData = result.data;
  if (taskData && typeof taskData === 'object') {
    const state = taskData.state || taskData.status || '';
    if (state === 'pending' || state === 'running') {
      result.is_async = true;
      result._task_id = taskId;
    } else if (state === 'done') {
      result.is_async = false;
      // Unwrap task result into data
      const inner = taskData.result;
      if (inner && typeof inner === 'object') {
        result.data = inner;
        result.ok = true;
      }
    } else if (state === 'error') {
      result.is_async = false;
      result.ok = false;
      result.err_code = 'TASK_ERROR';
    }
  }

  return result;
}

// ─── wait ────────────────────────────────────────────

/**
 * 等待异步任务完成。
 * 指数退避 + onStatus 回调。
 *
 * @param {string}   taskId                - 任务 ID
 * @param {function} [onStatus]            - 状态回调 (currentResult, elapsed, attempt)
 * @param {number}   [maxWait=60]          - 最大等待秒数
 * @param {number}   [interval=2]          - 起始轮询间隔秒数
 * @returns {Promise<DirectiveResult>}
 */
async function wait(taskId, onStatus, maxWait = 60, interval = 2) {
  const startTime = Date.now();
  let attempt = 0;
  let currentInterval = interval;

  while (true) {
    attempt++;
    const elapsed = (Date.now() - startTime) / 1000;

    if (elapsed >= maxWait) {
      return new DirectiveResult({
        ok: false,
        data: null,
        rtype: '',
        err_code: `wait timeout (${maxWait}s)`,
        directive: '',
        is_async: false,
        task_id: taskId,
      });
    }

    const result = await poll(taskId);

    if (typeof onStatus === 'function') {
      onStatus(result, elapsed, attempt);
    }

    if (!result.is_async) {
      return result;
    }

    // 指数退避: currentInterval = min(interval * 2^(attempt-1), 30)
    currentInterval = Math.min(interval * Math.pow(2, attempt - 1), 30);
    await sleep(currentInterval * 1000);
  }
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// ─── discover ────────────────────────────────────────

let _discoverCache = null;           // Cached directives array, keyed by lang
let _discoverCacheLang = 'auto';

/**
 * Discover available directives via AI:text-cli;query,json.
 * First call fetches full list and caches; subsequent calls filter client-side.
 * Use forceRefresh=true or clearDiscoverCache() after installing new packages.
 *
 * @param {object}  [opts]
 * @param {string}  [opts.runtime]       - Runtime filter (python/js/mcp)
 * @param {string}  [opts.category]      - Category filter
 * @param {string}  [opts.search]        - Keyword search across canonical fields
 * @param {string}  [opts.lang]          - Language for localized fields (zh/en/auto)
 * @param {boolean} [opts.forceRefresh]  - Bypass cache and re-fetch
 * @returns {Promise<Array>}
 */
async function discover({ runtime, category, search, lang = 'auto', forceRefresh = false } = {}) {
  const cacheKey = lang;

  if (forceRefresh || _discoverCacheLang !== lang || _discoverCache === null) {
    // Fetch full directive list with language parameter
    const query = lang !== 'auto' ? `AI:text-cli;query,json,${lang}` : 'AI:text-cli;query,json';
    const result = await call(query);

    if (!result.ok) {
      throw new Error(`discover failed: ${result.err_code}`);
    }

    // result.data = {"directives": [{domain, action, usage, description, runtime, package, ...}, ...]}
    _discoverCache = (result.data && Array.isArray(result.data.directives))
      ? result.data.directives
      : [];

    _discoverCacheLang = lang;
  }

  let items = [..._discoverCache];

  // Client-side filtering against canonical fields from _render_json()
  if (runtime) {
    items = items.filter(d =>
      (d.runtime || '').toLowerCase() === runtime.toLowerCase()
    );
  }
  if (search) {
    const q = search.toLowerCase();
    items = items.filter(d =>
      (d.domain || '').toLowerCase().includes(q) ||
      (d.action || '').toLowerCase().includes(q) ||
      (d.usage || '').toLowerCase().includes(q) ||
      (d.description || '').toLowerCase().includes(q) ||
      (d.domain_zh || '').toLowerCase().includes(q) ||
      (d.action_zh || '').toLowerCase().includes(q) ||
      (d.description_zh || '').toLowerCase().includes(q) ||
      (d.package || '').toLowerCase().includes(q)
    );
  }
  // category: note — _render_json strips _package, so category may not be at
  // directive level. Filter is best-effort via package metadata if present.
  if (category) {
    items = items.filter(d =>
      (d.category || d._package?.category || '') === category
    );
  }

  return items;
}

/**
 * Clear the discover() cache. Use after installing new directive packages.
 */
function clearDiscoverCache() {
  _discoverCache = null;
  _discoverCacheLang = 'auto';
}

// ─── 导出 ────────────────────────────────────────────

module.exports = {
  DirectiveResult,
  call,
  _request,
  callBatch,
  poll,
  wait,
  discover,
  clearDiscoverCache,
};

// ─── 命令行入口 ──────────────────────────────────────

if (require.main === module) {
  const directive = process.argv[2];
  if (!directive) {
    console.error('usage: node call.js "AI:domain;action,params1,params2"');
    process.exit(1);
  }

  call(directive)
    .then(r => { console.log(JSON.stringify(r, null, 2)); })
    .catch(e => { console.error(e.message); process.exit(1); });
}
