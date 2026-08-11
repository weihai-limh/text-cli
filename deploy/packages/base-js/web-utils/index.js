// Platform-neutral entry: exports.main(event, context) works on any JS runtime.
// No wx-server-sdk dependency — business logic only uses host-injected event fields.

const { ok, err } = require('./instructions/envelope');
const { splitParamsOutsideBrackets } = require('./parser');
const schema = require('./schema.json');

// T4: 从 schema.json 的 directives[] 自动派生指令路由，消除手写 INSTRUCTIONS map 与 schema 漂移 (C3)。
// 每个 action 对应 ./instructions/<action>.js，缺失时告警而非静默失败。
const INSTRUCTIONS = {};
for (const d of schema.directives || []) {
  const action = d.action;
  if (!action) continue;
  try {
    INSTRUCTIONS[action] = require(`./instructions/${action}`);
  } catch (e) {
    console.warn(`[web-utils] no handler module for action '${action}': ${e.message}`);
  }
}

exports.main = async (event, context) => {
  // SDK 调用（云函数间 callFunction）无 httpMethod，走 prompt 通道
  if (!event.httpMethod) {
    if (event.action === 'get_schema') {
      return { schema: schema };
    }
    const prompt = event.prompt;
    if (!prompt) {
      return err('MISSING_PROMPT', 'prompt is required for SDK call');
    }
    return await executeInstruction(prompt, event);
  }

  const path = event.path || '';

  if (event.httpMethod === 'GET' && path === '/health') {
    return { status: 'ok', service: 'web-utils', version: '0.1.2' };
  }

  if (event.httpMethod === 'POST' && path === '/cli/text_cli') {
    let body;
    try {
      body = typeof event.body === 'string' ? JSON.parse(event.body) : event.body;
    } catch (e) {
      return err('INVALID_BODY', 'event.body is not valid JSON');
    }

    const prompt = body.prompt;
    if (!prompt) {
      return err('MISSING_PROMPT', 'prompt is required');
    }

    return await executeInstruction(prompt, event);
  }

  return err('UNKNOWN_PATH', `${event.httpMethod} ${path}`);
};

async function executeInstruction(prompt, event) {
  const match = prompt.match(/^AI:\s*([^;]+);\s*([^(]+)(?:\(.*\))?$/);
  if (!match) {
    return err('INVALID_PROMPT', prompt);
  }

  const actionAndParams = match[2].trim();

  // 第一个逗号分隔 action 与 params；其后参数按协议深度追踪算法拆分
  const firstComma = actionAndParams.indexOf(',');
  let action, paramsStr;
  if (firstComma === -1) {
    action = actionAndParams;
    paramsStr = '';
  } else {
    action = actionAndParams.substring(0, firstComma);
    paramsStr = actionAndParams.substring(firstComma + 1);
  }
  action = action.trim();

  // T3: 与 Python service 一致的括号深度追踪逗号拆分
  const params = splitParamsOutsideBrackets(paramsStr);

  const handler = INSTRUCTIONS[action];
  if (!handler) {
    return err('ACTION_NOT_FOUND', action);
  }

  try {
    // handler 自身返回现代协议信封
    return await handler.handler(params, event);
  } catch (error) {
    return err('EXECUTION_ERROR', error.message);
  }
}
