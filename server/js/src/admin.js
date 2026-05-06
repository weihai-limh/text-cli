import { hashToken } from './auth.js';
import { loadSchema as reloadSchema } from './schema-loader.js';

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function verifyAdmin(env) {
  const adminKey = env.ADMIN_API_KEY;
  if (!adminKey) {
    return { ok: false, response: json({ error: 'Admin API not configured' }, 403) };
  }
  return { ok: true, adminKey };
}

function checkAdminAuth(request, env) {
  const { ok, response, adminKey } = verifyAdmin(env);
  if (!ok) return response;
  const provided = request.headers.get('X-Admin-Key') || '';
  if (provided !== adminKey) {
    return json({ error: 'Invalid admin key' }, 401);
  }
  return null;
}

export async function handleHealth(request, env) {
  let dbOk = false;
  let directiveCount = 0;
  let backends = [];

  if (env.DB) {
    try {
      await env.DB.prepare('SELECT 1').first();
      dbOk = true;
    } catch {
      // db not available
    }

    try {
      const { results } = await env.DB
        .prepare('SELECT DISTINCT backend_url, COUNT(*) as cnt FROM directives WHERE enabled = 1 GROUP BY backend_url')
        .all();
      backends = results.map((r) => ({ url: r.backend_url, directive_count: r.cnt }));
      directiveCount = results.reduce((sum, r) => sum + r.cnt, 0);
    } catch {
      // no directives table
    }
  }

  return json({
    liveness: true,
    readiness: {
      database: dbOk,
      schema: directiveCount > 0,
      backends,
    },
  });
}

export async function handleStatsSummary(request, env) {
  const denied = checkAdminAuth(request, env);
  if (denied) return denied;

  if (!env.DB) return json({ error: 'D1 not configured' }, 503);

  const [total, success, tokens, days] = await Promise.all([
    env.DB.prepare('SELECT COUNT(*) as cnt FROM call_logs').first(),
    env.DB.prepare('SELECT COUNT(*) as cnt FROM call_logs WHERE status_code = 200').first(),
    env.DB.prepare('SELECT COUNT(*) as cnt FROM access_tokens WHERE is_active = 1').first(),
    env.DB.prepare('SELECT COUNT(DISTINCT date) as cnt FROM daily_stats').first(),
  ]);

  return json({
    total_calls: total?.cnt || 0,
    total_success: success?.cnt || 0,
    active_tokens: tokens?.cnt || 0,
    tracked_days: days?.cnt || 0,
  });
}

export async function handleStatsDaily(request, env) {
  const denied = checkAdminAuth(request, env);
  if (denied) return denied;

  if (!env.DB) return json({ error: 'D1 not configured' }, 503);

  const url = new URL(request.url);
  let date = url.searchParams.get('date');
  if (!date) {
    date = new Date().toISOString().slice(0, 10);
  }

  const { results } = await env.DB
    .prepare(
      'SELECT domain, action, call_count, success_count, avg_response_ms ' +
      'FROM daily_stats WHERE date = ? ORDER BY call_count DESC'
    )
    .bind(date)
    .all();

  return json({ date, directives: results });
}

export async function handleStatsToken(request, env) {
  const denied = checkAdminAuth(request, env);
  if (denied) return denied;

  if (!env.DB) return json({ error: 'D1 not configured' }, 503);

  const url = new URL(request.url);
  const parts = url.pathname.split('/');
  const prefix = parts[parts.length - 1];

  const token = await env.DB
    .prepare(
      'SELECT client_name, used_count, quota, is_active, created_at ' +
      'FROM access_tokens WHERE token_prefix = ?'
    )
    .bind(prefix)
    .first();

  if (!token) return json({ error: 'token not found', prefix }, 404);

  const { results: calls } = await env.DB
    .prepare(
      'SELECT directive, status_code, response_time_ms, created_at ' +
      'FROM call_logs WHERE access_token_prefix = ? ORDER BY created_at DESC LIMIT 50'
    )
    .bind(prefix)
    .all();

  return json({ token, recent_calls: calls });
}

export async function handleTokensList(request, env) {
  const denied = checkAdminAuth(request, env);
  if (denied) return denied;

  if (!env.DB) return json({ error: 'D1 not configured' }, 503);

  const { results } = await env.DB
    .prepare(
      'SELECT id, token_prefix, client_name, quota, used_count, ' +
      'max_requests_per_minute, is_active, created_at FROM access_tokens ' +
      'ORDER BY created_at DESC'
    )
    .all();

  return json({ tokens: results });
}

export async function handleTokensCreate(request, env) {
  const denied = checkAdminAuth(request, env);
  if (denied) return denied;

  if (!env.DB) return json({ error: 'D1 not configured' }, 503);

  let body;
  try {
    body = await request.json();
  } catch {
    return json({ error: 'Invalid JSON' }, 400);
  }

  const clientName = body?.client_name || '';
  const quota = body?.quota ?? -1;
  const maxRpm = body?.max_requests_per_minute ?? 60;

  const rawToken = crypto.randomUUID().replace(/-/g, '') + crypto.randomUUID().replace(/-/g, '');
  const tokenHash = await hashToken(rawToken);
  const tokenPrefix = rawToken.slice(0, 8);

  const result = await env.DB
    .prepare(
      'INSERT INTO access_tokens (token_hash, token_prefix, client_name, quota, max_requests_per_minute) ' +
      'VALUES (?, ?, ?, ?, ?)'
    )
    .bind(tokenHash, tokenPrefix, clientName, quota, maxRpm)
    .run();

  return json({
    id: result.meta?.last_row_id,
    token: rawToken,
    token_prefix: tokenPrefix,
    client_name: clientName,
    quota,
  }, 201);
}

export async function handleTokensUpdate(request, env, tokenId) {
  const denied = checkAdminAuth(request, env);
  if (denied) return denied;

  if (!env.DB) return json({ error: 'D1 not configured' }, 503);

  const existing = await env.DB
    .prepare('SELECT id FROM access_tokens WHERE id = ?')
    .bind(tokenId)
    .first();

  if (!existing) return json({ error: 'Token not found' }, 404);

  let body;
  try {
    body = await request.json();
  } catch {
    return json({ error: 'Invalid JSON' }, 400);
  }

  const fields = [];
  const params = [];

  if (body?.client_name !== undefined) {
    fields.push('client_name = ?');
    params.push(body.client_name);
  }
  if (body?.quota !== undefined) {
    fields.push('quota = ?');
    params.push(body.quota);
  }
  if (body?.max_requests_per_minute !== undefined) {
    fields.push('max_requests_per_minute = ?');
    params.push(body.max_requests_per_minute);
  }
  if (body?.is_active !== undefined) {
    fields.push('is_active = ?');
    params.push(body.is_active ? 1 : 0);
  }

  if (fields.length === 0) return json({ message: 'no fields to update' });

  params.push(tokenId);
  await env.DB
    .prepare(`UPDATE access_tokens SET ${fields.join(', ')} WHERE id = ?`)
    .bind(...params)
    .run();

  return json({ message: 'updated', id: tokenId });
}

export async function handleTokensDelete(request, env, tokenId) {
  const denied = checkAdminAuth(request, env);
  if (denied) return denied;

  if (!env.DB) return json({ error: 'D1 not configured' }, 503);

  const existing = await env.DB
    .prepare('SELECT id FROM access_tokens WHERE id = ?')
    .bind(tokenId)
    .first();

  if (!existing) return json({ error: 'Token not found' }, 404);

  await env.DB.prepare('DELETE FROM access_tokens WHERE id = ?').bind(tokenId).run();
  return json({ message: 'deleted', id: tokenId });
}

export async function handleSchemaReload(request, env) {
  const denied = checkAdminAuth(request, env);
  if (denied) return denied;

  const baseUrl = env.ENDPOINT_BASE_URL || '';
  const count = reloadSchema(baseUrl);
  return json({ message: 'schema reloaded', directive_count: count });
}

export async function handleDirectivesList(request, env) {
  const denied = checkAdminAuth(request, env);
  if (denied) return denied;
  if (!env.DB) return json({ error: 'D1 not configured' }, 503);
  const { results } = await env.DB
    .prepare('SELECT * FROM directives ORDER BY domain, action')
    .all();
  return json({ directives: results });
}

export async function handleDirectivesRegister(request, env) {
  const denied = checkAdminAuth(request, env);
  if (denied) return denied;
  if (!env.DB) return json({ error: 'D1 not configured' }, 503);
  let body;
  try { body = await request.json(); } catch { return json({ error: 'Invalid JSON' }, 400); }
  const domain = body?.domain?.trim();
  const action = body?.action?.trim();
  const backendUrl = body?.backend_url?.trim() || body?.endpoint?.trim();
  if (!domain || !action) return json({ error: 'domain and action are required' }, 400);
  if (!backendUrl) return json({ error: 'backend_url or endpoint is required' }, 400);
  const directiveKey = `${domain}:${action}`;
  const id = directiveKey.toLowerCase().replace(/[^a-z0-9:-]/g, '_');
  const name = body?.name || `${domain}-${action}`;
  const category = body?.category || domain;
  const description = body?.description || '';
  const params = Array.isArray(body?.params) ? body.params : [];
  const promptTemplate = body?.prompt_template || '';
  const triggerKeywords = Array.isArray(body?.trigger_keywords) ? body.trigger_keywords : [];
  const responseType = body?.response_type || 'text';
  const existing = await env.DB
    .prepare('SELECT id FROM directives WHERE directive_key = ?')
    .bind(directiveKey).first();
  if (existing) {
    await env.DB.prepare(
      `UPDATE directives SET name=?, category=?, description=?, backend_url=?,
       parameters_json=?, prompt_template=?, trigger_keywords_json=?,
       response_type=?, enabled=1 WHERE directive_key=?`
    ).bind(name, category, description, backendUrl,
      JSON.stringify(params), promptTemplate, JSON.stringify(triggerKeywords),
      responseType, directiveKey).run();
    return json({ status: 'updated', directive_key: directiveKey, id: existing.id });
  }
  await env.DB.prepare(
    `INSERT INTO directives (id,name,category,description,domain,action,backend_url,
     parameters_json,prompt_template,trigger_keywords_json,response_type,directive_key)
     VALUES (?,?,?,?,?,?,?,?,?,?,?,?)`
  ).bind(id, name, category, description, domain, action, backendUrl,
    JSON.stringify(params), promptTemplate, JSON.stringify(triggerKeywords),
    responseType, directiveKey).run();
  return json({ status: 'registered', directive_key: directiveKey, id }, 201);
}

export async function handleDirectivesDiscover(request, env) {
  const denied = checkAdminAuth(request, env);
  if (denied) return denied;
  if (!env.DB) return json({ error: 'D1 not configured' }, 503);
  let body;
  try { body = await request.json(); } catch { return json({ error: 'Invalid JSON' }, 400); }
  const serviceUrl = body?.service_url?.trim();
  if (!serviceUrl) return json({ error: 'service_url is required' }, 400);
  const schemaUrl = serviceUrl.replace(/\/+$/, '') + '/schema';
  let schema;
  try {
    const resp = await fetch(schemaUrl, {
      headers: { 'Accept': 'application/json' },
      signal: AbortSignal.timeout(10000),
    });
    if (!resp.ok) return json({ error: `Service returned ${resp.status}`, schema_url: schemaUrl }, 502);
    schema = await resp.json();
  } catch (e) {
    return json({ error: `Failed to fetch schema: ${e.message}`, schema_url: schemaUrl }, 502);
  }
  const domain = schema?.domain;
  const actions = schema?.actions || [];
  if (!domain || actions.length === 0) return json({ error: 'Schema missing domain or actions', schema }, 400);
  const results = [];
  for (const action of actions) {
    const actionName = action?.action;
    const endpoint = action?.endpoint || `${serviceUrl.replace(/\/+$/, '')}/query`;
    const params = action?.params || [];
    const description = action?.note || action?.description || '';
    const format = action?.format || '';
    const directiveKey = `${domain}:${actionName}`;
    const id = directiveKey.toLowerCase().replace(/[^a-z0-9:-]/g, '_');
    const existing = await env.DB
      .prepare('SELECT id FROM directives WHERE directive_key = ?')
      .bind(directiveKey).first();
    if (existing) {
      await env.DB.prepare(
        `UPDATE directives SET backend_url=?, parameters_json=?, description=?,
         prompt_template=?, enabled=1 WHERE directive_key=?`
      ).bind(endpoint, JSON.stringify(params), description, format, directiveKey).run();
      results.push({ directive_key: directiveKey, status: 'updated' });
    } else {
      await env.DB.prepare(
        `INSERT INTO directives (id,name,category,description,domain,action,backend_url,
         parameters_json,prompt_template,trigger_keywords_json,response_type,directive_key)
         VALUES (?,?,?,?,?,?,?,?,?,?,'text',?)`
      ).bind(id, `${domain}-${actionName}`, domain, description,
        domain, actionName, endpoint, JSON.stringify(params), format, JSON.stringify([]),
        directiveKey).run();
      results.push({ directive_key: directiveKey, status: 'registered' });
    }
  }
  return json({ service_url: serviceUrl, domain, registered: results.length, results });
}

export async function handleDirectivesDelete(request, env, directiveId) {
  const denied = checkAdminAuth(request, env);
  if (denied) return denied;
  if (!env.DB) return json({ error: 'D1 not configured' }, 503);
  const existing = await env.DB
    .prepare('SELECT id FROM directives WHERE id = ? OR directive_key = ?')
    .bind(directiveId, directiveId).first();
  if (!existing) return json({ error: 'directive not found', id: directiveId }, 404);
  await env.DB.prepare('UPDATE directives SET enabled = 0 WHERE id = ?')
    .bind(existing.id).run();
  return json({ message: 'disabled', id: existing.id });
}

export function routeAdmin(path, method, request, env) {
  if (method === 'GET' && path === '/api/health') {
    return handleHealth(request, env);
  }

  if (method === 'GET' && path === '/api/stats/summary') {
    return handleStatsSummary(request, env);
  }

  if (method === 'GET' && path.startsWith('/api/stats/daily')) {
    return handleStatsDaily(request, env);
  }

  if (method === 'GET' && path.startsWith('/api/stats/token/')) {
    return handleStatsToken(request, env);
  }

  if (method === 'GET' && path === '/api/tokens') {
    return handleTokensList(request, env);
  }

  if (method === 'POST' && path === '/api/tokens') {
    return handleTokensCreate(request, env);
  }

  const updateMatch = path.match(/^\/api\/tokens\/(\d+)$/);
  if (updateMatch) {
    const tokenId = parseInt(updateMatch[1], 10);
    if (method === 'PUT') return handleTokensUpdate(request, env, tokenId);
    if (method === 'DELETE') return handleTokensDelete(request, env, tokenId);
  }

  if (method === 'POST' && path === '/api/schema/reload') {
    return handleSchemaReload(request, env);
  }

  if (method === 'GET' && path === '/api/directives') {
    return handleDirectivesList(request, env);
  }
  if (method === 'POST' && path === '/api/directives') {
    return handleDirectivesRegister(request, env);
  }
  if (method === 'POST' && path === '/api/directives/discover') {
    return handleDirectivesDiscover(request, env);
  }

  const directiveMatch = path.match(/^\/api\/directives\/(.+)$/);
  if (directiveMatch) {
    const directiveId = directiveMatch[1];
    if (method === 'DELETE') return handleDirectivesDelete(request, env, directiveId);
  }

  return null;
}
