/**
 * call.js — text-cli 指令调用（Node.js）
 *
 * 零依赖，仅用 Node.js 内置模块。
 *
 * 用法:
 *   const { callDirective } = require('./call');
 *
 *   const result = await callDirective('AI:weather;query,明天,威海');
 *   console.log(result);  // "明天威海: 晴, 15-22°C"
 *
 * 环境变量:
 *   TEXT_CLI_TOKEN     鉴权 Token
 *   TEXT_CLI_ENDPOINT  端点地址
 */

const DEFAULT_ENDPOINT = 'https://test.text-cli.com/cli/text_cli';
const DEFAULT_TIMEOUT = 10000;

/**
 * 调用 text-cli 指令，返回文本结果。
 *
 * @param {string} directive - 指令文本，格式 "AI:领域;动作,参数1,参数2"（`指令:` 仍兼容）
 * @param {object} [options]
 * @param {string} [options.endpoint] - 端点 URL
 * @param {string} [options.token] - Access Token / Service Token
 * @param {number} [options.timeout] - 超时毫秒数 (默认 10000)
 * @returns {Promise<string>} 指令执行结果文本
 * @throws {Error} HTTP 错误、网络不可达、超时
 */
async function callDirective(directive, options = {}) {
  const url = options.endpoint || process.env.TEXT_CLI_ENDPOINT || DEFAULT_ENDPOINT;
  const token = options.token || process.env.TEXT_CLI_TOKEN || '';
  const timeout = options.timeout || DEFAULT_TIMEOUT;

  const body = JSON.stringify({ prompt: directive });

  const headers = { 'Content-Type': 'application/json' };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);

  try {
    const resp = await fetch(url, {
      method: 'POST',
      headers,
      body,
      signal: controller.signal,
    });

    const data = await resp.json();

    if (!resp.ok) {
      const errText = data?.rst_data?.text || JSON.stringify(data);
      throw new Error(`HTTP ${resp.status}: ${errText}`);
    }

    if (data.rst_types === 'text') {
      return data.rst_data.text;
    }

    return JSON.stringify(data);
  } catch (e) {
    if (e.name === 'AbortError') {
      throw new Error(`请求超时 (${timeout}ms): ${url}`);
    }
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

/**
 * 批量调用多个指令（串行执行）。
 *
 * @param {string[]} directives - 指令数组
 * @param {object} [options] - 同 callDirective
 * @returns {Promise<Array<{directive: string, result: string, error: string|null}>>}
 */
async function callDirectiveBatch(directives, options = {}) {
  const results = [];
  for (const d of directives) {
    try {
      const result = await callDirective(d, options);
      results.push({ directive: d, result, error: null });
    } catch (e) {
      results.push({ directive: d, result: '', error: e.message });
    }
  }
  return results;
}

module.exports = { callDirective, callDirectiveBatch };

// ─── 命令行入口 ──────────────────────────────────────

if (require.main === module) {
  const directive = process.argv[2];
  if (!directive) {
    console.error('用法: node call.js "AI:领域;动作,参数1,参数2"');
    process.exit(1);
  }

  callDirective(directive)
    .then(r => { console.log(r); })
    .catch(e => { console.error(e.message); process.exit(1); });
}
