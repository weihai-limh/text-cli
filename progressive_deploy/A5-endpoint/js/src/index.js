import { parseDirective, DirectiveParseError } from './parser.js';
import {
  loadSchema,
  loadSchemaFromD1,
  loadSkillsFromBackends,
  findBackendUrl,
  findBackendUrlFromD1,
  getExternalSchema,
  getBackendBaseUrl,
} from './schema-loader.js';
import { ensureSkillsLoaded } from './backend-registry.js';
import {
  verifyAccessToken,
  incrementTokenUsage,
  extractTokenPrefix,
  extractServiceTokenPrefix,
  isSTPrefixBlocked,
  isSTPrefixRegistered,
} from './auth.js';
import { forwardRequest } from './forwarder.js';
import { routeAdmin } from './admin.js';
import { isIPBlocked } from './ip-guard.js';
import { checkRateLimit } from './rate-limiter.js';

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

  await ensureSkillsLoaded(env);

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

    const clientIp = request.headers.get('CF-Connecting-IP') || request.headers.get('X-Forwarded-For')?.split(',')[0]?.trim() || '';

    if (isIPBlocked(clientIp, env)) {
      return textError('IP_BLOCKED', 403);
    }

    if (method === 'POST' && path === '/cli/text_cli') {
      const serviceToken = request.headers.get('Service-token') || '';
      if (serviceToken) {
        const prefix = extractServiceTokenPrefix(serviceToken);
        if (isSTPrefixBlocked(prefix, env)) {
          return textError('TOKEN_PREFIX_BLOCKED', 403);
        }
        if (!isSTPrefixRegistered(prefix, env)) {
          return textError('TOKEN_PREFIX_UNKNOWN', 403);
        }
      }
    }

    if (path === '/cli/text_cli' || (path === '/text-cli/cli' && method === 'GET')) {
      if (env.DB) {
        const allowed = await checkRateLimit(env.DB, env, method === 'GET');
        if (!allowed) {
          return textError('RATE_LIMIT_EXCEEDED', 429);
        }
      }
    }

    if (method === 'POST' && path === '/cli/text_cli') {
      return handleTextCli(request, env);
    }

    if (method === 'GET' && path === '/text_cli_schema.json') {
      const baseUrl = env.ENDPOINT_BASE_URL || '';
      const backendsRaw = env.A3_BACKENDS || '';
      if (backendsRaw) {
        await loadSkillsFromBackends(env, baseUrl);
      } else if (env.DB) {
        await loadSchemaFromD1(env.DB, baseUrl);
      }
      return json(getExternalSchema());
    }

    if (method === 'GET' && path === '/health') {
      const baseUrl = env.ENDPOINT_BASE_URL || '';
      const backendsRaw = env.A3_BACKENDS || '';
      if (backendsRaw) {
        await loadSkillsFromBackends(env, baseUrl);
      } else {
        await loadSchema(baseUrl);
      }
      return json({
        status: 'ok',
        directives: Object.keys(getExternalSchema()).length,
      });
    }

    if (method === 'GET' && path === '/text-cli/cli') {
      if (env.ENABLE_PUBLIC_CLI !== 'true') {
        return textError('PUBLIC_CLI_DISABLED', 404);
      }

      const skillId = url.searchParams.get('skill_id');
      if (!skillId) {
        return textError('INVALID_PARAMS: skill_id is required', 400);
      }

      const backendBase = getBackendBaseUrl(env);
      if (!backendBase) {
        return textError('BACKEND_UNAVAILABLE', 502);
      }

      const body = {};
      for (const [key, value] of url.searchParams.entries()) {
        if (key !== 'skill_id') {
          body[key] = value;
        }
      }

      const serviceToken = request.headers.get('Service-token') || '';
      const skillUrl = `${backendBase.replace(/\/+$/, '')}/text-cli/skills/${skillId}`;
      const fwdHeaders = { 'Content-Type': 'application/json' };
      if (serviceToken) {
        fwdHeaders['Service-token'] = serviceToken;
      }

      try {
        const resp = await fetch(skillUrl, {
          method: 'POST',
          headers: fwdHeaders,
          body: JSON.stringify(body),
        });
        const respBody = await resp.text();
        let parsed;
        try {
          parsed = JSON.parse(respBody);
        } catch {
          parsed = respBody;
        }
        return json(
          typeof parsed === 'object' ? parsed : { rst_types: 'text', rst_data: { text: parsed } },
          resp.status,
        );
      } catch {
        return textError('BACKEND_UNAVAILABLE', 502);
      }
    }

    const adminResponse = routeAdmin(path, method, request, env);
    if (adminResponse) return adminResponse;

    return json({ error: 'Not Found' }, 404);
  },
};
