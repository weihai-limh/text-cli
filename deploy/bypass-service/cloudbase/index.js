// CloudBase text-cli gateway — refactored with textcli-core (Phase 5)
// Replaces inline envelope/parser with textcli-core modules.
// All error codes now use protocol closed set (SPEC §1.2.8).

const cloud = require('wx-server-sdk');
cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV });

const { routeTable, packages } = require('./config');
const { ok, err } = require('../textcli-core/envelope.js');
const { parse } = require('../textcli-core/parser.js');

exports.main = async (event, context) => {
  if (event.httpMethod === 'GET') {
    return handleGet(event);
  }
  if (event.httpMethod === 'POST') {
    return handlePost(event);
  }
  return err('ERR_ROUTING', `unsupported method: ${event.httpMethod}`);
};

function handleGet(event) {
  const path = event.path || '';
  if (path === '/health') {
    return { status: 'ok', service: 'text-cli-router', version: '1.0.0', spec_version: '1.3.2' };
  }
  if (path === '/text-cli/skills') {
    return {};
  }
  return err('ERR_NOT_FOUND', `GET ${path}`);
}

async function handlePost(event) {
  const path = event.path || '';
  if (path === '/cli') {
    let body;
    try {
      body = typeof event.body === 'string' ? JSON.parse(event.body) : (event.body || event);
    } catch (e) {
      return err('INVALID_PARAMS', 'event.body is not valid JSON');
    }

    const prompt = body.prompt || event.prompt;
    if (!prompt) {
      return err('INVALID_PARAMS', 'prompt is required');
    }

    if (prompt.startsWith('AI:text-cli;query')) {
      return await handleQuery(prompt);
    }

    return await routeInstruction(prompt, event);
  }
  return err('ERR_NOT_FOUND', `POST ${path}`);
}

async function handleQuery(prompt) {
  const params = prompt.substring('AI:text-cli;query'.length).trim();
  const mode = params ? params.split(',')[0].trim() : 'text';

  const schemaPromises = packages.map(pkg =>
    cloud.callFunction({
      name: pkg,
      data: { action: 'get_schema' }
    }).catch(err2 => ({ error: err2.message, pkg }))
  );
  const schemaResults = await Promise.all(schemaPromises);

  const schemas = [];
  for (const result of schemaResults) {
    if (result.error) {
      console.error(`Failed to get schema from ${result.pkg}:`, result.error);
      continue;
    }
    if (result.result && result.result.schema) {
      schemas.push(result.result.schema);
    }
  }

  const directives = flattenSchemas(schemas);

  if (mode === 'json') {
    return ok({ directives });
  }
  if (mode === 'compact') {
    const lines = directives.map(d => `${d.domain};${d.action}`);
    return ok({ text: lines.join('\n') });
  }
  return ok({ text: renderText(directives) });
}

function flattenSchemas(schemas) {
  const directives = [];
  for (const schema of schemas) {
    for (const directive of schema.directives || []) {
      directives.push({
        ...directive,
        package: schema.id,
        runtime: schema.runtime,
      });
    }
  }
  return directives;
}

function renderText(directives) {
  let text = 'Available directives:\n\n';
  for (const d of directives) {
    text += `  ${d.domain};${d.action}\n`;
    text += `    ${d.description || ''}\n`;
    if (d.params && d.params.length > 0) {
      text += `    params: ${Array.isArray(d.params[0]) ? d.params.map(p => p.name + (p.required ? '*' : '')).join(', ') : d.params.join(', ')}\n`;
    }
    text += '\n';
  }
  return text;
}

async function routeInstruction(prompt, event) {
  // Use textcli-core parser (fixes regex defect that filtered bracket content)
  const parsed = parse(prompt);
  if (parsed.error) {
    return err(parsed.error, parsed.reason);
  }

  const domain = parsed.domain;
  const functionName = routeTable[domain];
  if (!functionName) {
    return err('ERR_NOT_FOUND', `domain not found: ${domain}`);
  }

  try {
    const result = await cloud.callFunction({
      name: functionName,
      data: {
        prompt: prompt,
        _routerEvent: event,
      }
    });
    return result.result;
  } catch (error) {
    return err('ERR_EXECUTION', error.message);
  }
}
