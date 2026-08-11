// Cloudflare Workers text-cli gateway (Phase 6)
// Uses textcli-core pure-logic modules (parser, envelope, alias, registry).
// Loader file IO replaced with Workers KV Store.
//
// Deploy with:
//   wrangler deploy --var TEXTCLI_KV_NAMESPACE:<binding>
//
// Note: parser.js, envelope.js, alias.js, registry.js must be bundled
// (via esbuild) since Workers uses ES modules, not CommonJS.

// Import textcli-core pure-logic modules (bundled as ES modules)
import { parse } from './textcli-core/parser.js';
import { ok, err } from './textcli-core/envelope.js';
import { addAlias } from './textcli-core/alias.js';
import { register, dispatch } from './textcli-core/registry.js';

// ─── Bootstrap: load packages from KV ────────────────

let _bootstrapped = false;

async function bootstrap(env) {
  if (_bootstrapped) return;
  const kv = env.TEXTCLI_PACKAGES; // KV namespace binding
  if (!kv) {
    console.warn('[text-cli workers] KV binding TEXTCLI_PACKAGES not configured — running without packages');
    _bootstrapped = true;
    return;
  }

  // List all installed packages from KV metadata
  const list = await kv.list({ prefix: 'packages/' });
  for (const key of list.keys) {
    try {
      const schemaJSON = await kv.get(`${key.name}/schema.json`, 'json');
      const handlerCode = await kv.get(`${key.name}/handler.js`, 'text');
      if (!schemaJSON || !handlerCode) continue;

      // Workers can't use require() — handlers must be pre-registered
      // or loaded via dynamic import. For simplicity, this gateway
      // only registers package metadata and serves as a pure proxy.
      // Full handler execution requires a Node.js runtime behind it.

      for (const d of (schemaJSON.directives || [])) {
        // Register directive metadata (handler = null means "route to backend")
        register(d.domain, d.action, null, {
          domainAlias: d.domain_zh,
          actionAliases: d.action_zh ? { [d.action]: d.action_zh } : undefined,
        });
      }
      console.log(`[text-cli workers] registered package: ${schemaJSON.id}`);
    } catch (e) {
      console.error(`[text-cli workers] failed to load package ${key.name}:`, e.message);
    }
  }
  _bootstrapped = true;
}

// ─── Fetch handler ───────────────────────────────────

export default {
  async fetch(request, env, ctx) {
    await bootstrap(env);

    const url = new URL(request.url);
    const method = request.method;

    // GET /text-cli/health
    if (method === 'GET' && url.pathname === '/text-cli/health') {
      return jsonResponse(ok({ status: 'ok', version: '0.1.0', spec_version: '1.3.2' }));
    }

    // POST /text-cli/cli
    if (method === 'POST' && url.pathname === '/text-cli/cli') {
      let body;
      try {
        body = await request.json();
      } catch (e) {
        return jsonResponse(err('INVALID_PARAMS', 'invalid JSON body'));
      }

      const prompt = body.prompt;
      if (!prompt) {
        return jsonResponse(err('INVALID_PARAMS', 'prompt is required'));
      }

      // Parse directive
      const parsed = parse(prompt);
      if (parsed.error) {
        return jsonResponse(err(parsed.error, parsed.reason));
      }

      // Dispatch — handlers are registered as null (metadata-only),
      // so dispatch returns null to indicate "found in registry, execute on backend"
      const result = await dispatch(parsed.domain, parsed.action, parsed.params, { request, env });
      if (result === null || result === undefined) {
        // Directive found in registry — delegate to backend Node.js runtime.
        // In production this would proxy via fetch() to a service endpoint.
        return jsonResponse(ok({
          status: 'routed',
          domain: parsed.domain,
          action: parsed.action,
          note: 'directive found, execution delegated to backend runtime',
        }));
      }

      return jsonResponse(ok(result));
    }

    // 404
    return jsonResponse(err('ERR_NOT_FOUND', `not found: ${method} ${url.pathname}`), 200);
  },
};

function jsonResponse(envelope) {
  return new Response(JSON.stringify(envelope), {
    status: 200,
    headers: { 'Content-Type': 'application/json; charset=utf-8' },
  });
}
