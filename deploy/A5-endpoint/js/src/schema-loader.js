import {
  refreshBackends,
  buildExternalSchema,
  findBackendSource,
  getExternalSchema as getAggregatedSchema,
  getBackendBaseUrl as getAggregatedBaseUrl,
  ensureSkillsLoaded,
} from './backend-registry.js';
import { normalizeDirectiveKey } from './parser.js';

let _externalSchema = {};

export function loadSchema(endpointBaseUrl) {
  _externalSchema = buildExternalSchema(endpointBaseUrl);
  return Object.keys(_externalSchema).length;
}

export async function loadSkillsFromBackends(env, endpointBaseUrl) {
  await refreshBackends(env);
  _externalSchema = buildExternalSchema(endpointBaseUrl);
  return Object.keys(_externalSchema).length;
}

export async function loadSchemaFromD1(db, endpointBaseUrl) {
  if (db) {
    try {
      const { results } = await db
        .prepare(
          `SELECT id, name, category, description, domain, action, backend_url,
                  parameters_json, prompt_template, trigger_keywords_json,
                  response_type, response_example_json, directive_key
           FROM directives WHERE enabled = 1`
        )
        .all();

      const schema = {};
      for (const row of results) {
        const base = endpointBaseUrl ? endpointBaseUrl.replace(/\/+$/, '') : '';
        schema[row.id] = {
          url: base ? `${base}/text-cli/cli` : row.backend_url,
          id: row.id,
          name: row.name,
          category: row.category,
          description: row.description,
          directive: row.directive_key,
          parameters: JSON.parse(row.parameters_json || '[]'),
          prompt_template: row.prompt_template,
          trigger_keywords: JSON.parse(row.trigger_keywords_json || '[]'),
          response_type: row.response_type,
          response_example: row.response_example_json
            ? JSON.parse(row.response_example_json)
            : undefined,
        };
      }
      _externalSchema = schema;
      return schema;
    } catch {
      return null;
    }
  }
  return null;
}

export function getExternalSchema() {
  if (Object.keys(_externalSchema).length > 0) return _externalSchema;
  return getAggregatedSchema();
}

export function findBackendUrl(directiveKey) {
  const source = findBackendSource(directiveKey);
  if (source) return source;

  const normalized = normalizeDirectiveKey(directiveKey);
  for (const entry of Object.values(_externalSchema)) {
    const entryNormalized = normalizeDirectiveKey(entry.directive || '');
    if (entryNormalized === normalized) {
      return entry.url;
    }
  }
  return null;
}

export function getBackendBaseUrl(env) {
  return getAggregatedBaseUrl(env);
}

export function findBackendUrlFromD1(db, directiveKey) {
  const normalized = normalizeDirectiveKey(directiveKey);
  return db
    .prepare(
      'SELECT backend_url, directive_key FROM directives WHERE enabled = 1'
    )
    .all()
    .then(({ results }) => {
      for (const row of results) {
        if (normalizeDirectiveKey(row.directive_key || '') === normalized) {
          return row.backend_url;
        }
      }
      return null;
    })
    .catch(() => null);
}
