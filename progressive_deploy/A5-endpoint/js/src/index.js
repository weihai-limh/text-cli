import { parseDirective, DirectiveParseError } from './parser.js';
import {
  loadSchema,
  loadSchemaFromD1,
  findBackendUrl,
  findBackendUrlFromD1,
  getExternalSchema,
} from './schema-loader.js';
import { verifyAccessToken, incrementTokenUsage, extractTokenPrefix, extractServiceTokenPrefix } from './auth.js';
import { forwardRequest } from './forwarder.js';
import { routeAdmin } from './admin.js';

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function textError(text, status = 400) {
  return json({ rst_types: 'text', rst_data: { text } }, status);
}

async function handleTextCli(request, env) {
  const ACCESS_TOKEN_REQUIRED = env.ACCESS_TOKEN_REQUIRED !== 'false';

  const authHeader = request.headers.get('Authorization') || '';
  const serviceToken = request.headers.get('Service-token') || '';

  let tokenRecord = null;
  if (ACCESS_TOKEN_REQUIRED) {
    tokenRecord = await verifyAccessToken(authHeader, env.DB, true);
    if (!tokenRecord) {
      return textError('ACCESS_DENIED', 401);
    }
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return textError('INVALID_JSON', 400);
  }

  const prompt = body?.prompt;
  if (!prompt) {
    return textError('INVALID_DIRECTIVE_FORMAT: prompt is required', 400);
  }

  let parsed;
  try {
    parsed = parseDirective(prompt);
  } catch (e) {
    if (e instanceof DirectiveParseError) {
      return textError(`${e.code}: ${e.message}`, 400);
    }
    throw e;
  }

  const baseUrl = env.ENDPOINT_BASE_URL || '';
  let backendUrl;

  if (env.DB) {
    backendUrl = await findBackendUrlFromD1(env.DB, parsed.directiveKey);
    if (!backendUrl) {
      backendUrl = findBackendUrl(parsed.directiveKey);
    }
  } else {
    backendUrl = findBackendUrl(parsed.directiveKey);
  }

  if (!backendUrl) {
    return textError(`DIRECTIVE_NOT_FOUND: ${parsed.directiveKey}`, 400);
  }

  const accessTokenPrefix = authHeader.startsWith('Bearer ')
    ? extractTokenPrefix(authHeader.slice(7))
    : '';

  const timeout = env.FORWARD_TIMEOUT ? parseInt(env.FORWARD_TIMEOUT, 10) * 1000 : undefined;
  const maxRetries = env.FORWARD_MAX_RETRIES ? parseInt(env.FORWARD_MAX_RETRIES, 10) : undefined;

  const result = await forwardRequest({
    parsed,
    backendUrl,
    prompt,
    serviceToken,
    accessTokenPrefix,
    db: env.DB,
    timeout,
    maxRetries,
  });

  if (tokenRecord) {
    incrementTokenUsage(env.DB, tokenRecord.token_prefix).catch(() => {});
  }

  return new Response(result.body, {
    status: result.statusCode,
    headers: { 'Content-Type': 'application/json' },
  });
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;
    const method = request.method;

    if (method === 'POST' && path === '/cli/text_cli') {
      return handleTextCli(request, env);
    }

    if (method === 'GET' && path === '/text_cli_schema.json') {
      const baseUrl = env.ENDPOINT_BASE_URL || '';
      if (env.DB) {
        await loadSchemaFromD1(env.DB, baseUrl);
      }
      return json(getExternalSchema());
    }

    if (method === 'GET' && path === '/health') {
      const baseUrl = env.ENDPOINT_BASE_URL || '';
      loadSchema(baseUrl);
      const { getInternalSchema } = await import('./schema-loader.js');
      return json({
        status: 'ok',
        directives: Object.keys(getInternalSchema()).length,
      });
    }

    const adminResponse = routeAdmin(path, method, request, env);
    if (adminResponse) return adminResponse;

    return json({ error: 'Not Found' }, 404);
  },
};
