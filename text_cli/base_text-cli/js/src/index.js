import { parseDirective, DirectiveParseError } from './parser.js';
import { dispatch, getRegisteredDirectives } from './registry.js';
import { verifyServiceToken, incrementUsage } from './auth.js';
import { getSchema } from './schema.js';
import './handlers/index.js';

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function ok(text) {
  return json({ rst_types: 'text', rst_data: { text } });
}

function errorResponse(text, status = 400) {
  return json({ rst_types: 'text', rst_data: { text: `指令执行失败: ${text}` } }, status);
}

async function handleDirective(request, env) {
  const serviceToken = request.headers.get('Service-token');
  const auth = await verifyServiceToken(serviceToken, env.DB);

  if (!auth.allowed) {
    return json({ rst_types: 'text', rst_data: { text: `无权访问: ${auth.message}` } }, 403);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return errorResponse('请求体不是有效 JSON');
  }

  const prompt = body?.prompt;
  if (!prompt) {
    return errorResponse('缺少 prompt 字段');
  }

  let parsed;
  try {
    parsed = parseDirective(prompt);
  } catch (e) {
    if (e instanceof DirectiveParseError) {
      return errorResponse(`${e.code}: ${e.message}`);
    }
    throw e;
  }

  const start = Date.now();
  const result = dispatch(parsed.domain, parsed.action, parsed.params);
  const elapsed = Date.now() - start;

  if (env.DB) {
    env.DB.prepare(
      `INSERT INTO usage_logs (directive_key, token_hash, params_json, result_status, response_time_ms)
       VALUES (?, ?, ?, ?, ?)`
    )
      .bind(parsed.directiveKey, auth.tokenHash || null, JSON.stringify(parsed.params), 'ok', elapsed)
      .run()
      .catch(() => {});
  }

  incrementUsage(env.DB, auth.tokenHash).catch(() => {});

  return ok(result);
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;

    if (request.method === 'POST' && path === '/cli/text_cli') {
      return handleDirective(request, env);
    }

    if (request.method === 'GET' && path === '/health') {
      return json({ status: 'ok', directives: getRegisteredDirectives() });
    }

    if (request.method === 'GET' && path === '/text_cli_schema.json') {
      const schema = await getSchema(env.DB);
      return json(schema);
    }

    return json({ error: 'Not Found' }, 404);
  },
};
