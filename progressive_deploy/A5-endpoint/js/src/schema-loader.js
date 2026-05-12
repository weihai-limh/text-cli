import staticSchema from './config/schema.json';
import { normalizeDirectiveKey } from './parser.js';

let _internalSchema = {};
let _externalSchema = {};

export function loadSchema(endpointBaseUrl) {
  _internalSchema = {};

  for (const [key, entry] of Object.entries(staticSchema)) {
    if (key.startsWith('_')) continue;
    _internalSchema[key] = entry;
  }

  _externalSchema = JSON.parse(JSON.stringify(_internalSchema));

  if (endpointBaseUrl) {
    const base = endpointBaseUrl.replace(/\/+$/, '');
    const targetUrl = `${base}/cli/text_cli`;
    for (const key of Object.keys(_externalSchema)) {
      _externalSchema[key].url = targetUrl;
    }
  }

  return Object.keys(_internalSchema).length;
}

export function getInternalSchema() {
  return _internalSchema;
}

export function getExternalSchema() {
  return _externalSchema;
}

export function findBackendUrl(directiveKey) {
  const normalized = normalizeDirectiveKey(directiveKey);
  for (const entry of Object.values(_internalSchema)) {
    const entryNormalized = normalizeDirectiveKey(entry.directive || '');
    if (entryNormalized === normalized) {
      return entry.url;
    }
  }
  return null;
}

export function loadSchemaFromD1(db, endpointBaseUrl) {
  return db
    .prepare(
      `SELECT id, name, category, description, domain, action, backend_url,
              parameters_json, prompt_template, trigger_keywords_json,
              response_type, response_example_json, directive_key
       FROM directives WHERE enabled = 1`
    )
    .all()
    .then(({ results }) => {
      const schema = {};
      for (const row of results) {
        const base = endpointBaseUrl ? endpointBaseUrl.replace(/\/+$/, '') : '';
        schema[row.id] = {
          url: base ? `${base}/cli/text_cli` : row.backend_url,
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
    })
    .catch(() => null);
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
