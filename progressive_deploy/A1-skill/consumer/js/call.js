/**
 * call.js — text-cli 指令调用（Node.js）
 *
 * 零依赖，仅用 Node.js 内置模块。
 * 从 conf.json 或环境变量读取端点/令牌配置。
 *
 * 用法:
 *   const { callDirective } = require('./call');
 *   const result = await callDirective('AI:tc-datetime;now');
 *   console.log(result);
 *
 * 环境变量:
 *   TEXT_CLI_ENDPOINT          覆盖端点地址
 *   TEXT_CLI_SERVICE_TOKEN     覆盖 Service Token
 *   TEXT_CLI_ACCESS_TOKEN      覆盖 Access Token
 *
 * 配置文件:
 *   ../conf.json（与本文件相对路径）
 *   { "endpoint": "...", "service_token": "...", "access_token": "..." }
 */

const path = require('path');
const fs = require('fs');

const CONF_PATH = path.resolve(__dirname, 'conf.json');
const DEFAULT_ENDPOINT = 'https://test.text-cli.com/cli/text_cli';
const DEFAULT_TIMEOUT = 10000;

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
function getConfig(key, envName, defaultVal = '') {
  if (typeof process.env[envName] === 'string' && process.env[envName] !== '') {
    return process.env[envName];
  }
  const conf = loadConf();
  return conf[key] !== undefined ? conf[key] : defaultVal;
}

/**
 * 调用 text-cli 指令，返回文本结果。
 *
 * @param {string} directive - 指令文本
 * @param {object} [options]
 * @param {string} [options.endpoint] - 端点 URL
 * @param {string} [options.serviceToken] - Service Token
 * @param {string} [options.accessToken] - Access Token
 * @param {number} [options.timeout] - 超时毫秒 (默认 10000)
 * @returns {Promise<string>}
 */
async function callDirective(directive, options = {}) {
  const url = options.endpoint || getConfig('endpoint', 'TEXT_CLI_ENDPOINT', DEFAULT_ENDPOINT);
  const st = options.serviceToken || getConfig('service_token', 'TEXT_CLI_SERVICE_TOKEN');
  const at = options.accessToken || getConfig('access_token', 'TEXT_CLI_ACCESS_TOKEN');
  const timeout = options.timeout || DEFAULT_TIMEOUT;

  const headers = { 'Content-Type': 'application/json' };
  if (at) headers['Authorization'] = `Bearer ${at}`;
  if (st) headers['Service-token'] = st;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);

  try {
    const resp = await fetch(url, {
      method: 'POST',
      headers,
      body: JSON.stringify({ prompt: directive }),
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
 * @param {string[]} directives
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
    console.error('用法: node call.js "AI:域;动作,参数1,参数2"');
    process.exit(1);
  }

  callDirective(directive)
    .then(r => { console.log(r); })
    .catch(e => { console.error(e.message); process.exit(1); });
}
