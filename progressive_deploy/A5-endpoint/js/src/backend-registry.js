let _aggregateTable = {};
let _externalSchema = {};

function normalizeSkillId(skillId) {
  const prefixes = ['指令:', 'AI:', '指令：', 'AI：'];
  for (const p of prefixes) {
    if (skillId.startsWith(p)) return skillId.slice(p.length);
  }
  return skillId;
}

export async function refreshBackends(env) {
  const backendsRaw = env.A3_BACKENDS || '';
  if (!backendsRaw) return 0;

  const backends = backendsRaw.split(',').map((b) => b.trim().replace(/\/+$/, '')).filter(Boolean);
  const tokensRaw = env.A3_BACKEND_TOKENS || '';
  const tokens = tokensRaw ? tokensRaw.split(',').map((s) => s.trim()) : [];
  const stPrefixesRaw = env.A3_REGISTERED_PREFIXES || '';
  const stPrefixes = stPrefixesRaw ? stPrefixesRaw.split(',').map((s) => s.trim()) : [];

  const newTable = {};
  let count = 0;

  const results = await Promise.allSettled(
    backends.map((base, i) => {
      const token = tokens[i] || null;
      return fetchSkills(base, token);
    })
  );

  for (let i = 0; i < backends.length; i++) {
    const result = results[i];
    if (result.status !== 'fulfilled' || !result.value) continue;

    const backendBase = backends[i];
    const stPrefix = stPrefixes[i] || '';
    const skills = result.value;

    for (const skill of skills) {
      const skillId = skill.id || skill.directive;
      if (!skillId) continue;

      const normalized = normalizeSkillId(skillId);
      if (newTable[normalized]) continue;

      newTable[normalized] = {
        source: backendBase,
        st_prefix: stPrefix,
        id: skill.id || '',
        name: skill.name_cn || skill.name || '',
        category: skill.category || '',
        description: skill.description_cn || skill.description || '',
        directive: skill.directive || skillId,
        usage: skill.usage_cn || skill.usage || '',
        parameters: skill.params || [],
        prompt_template: skill.usage || '',
        trigger_keywords: skill.trigger_keywords || [],
        response_type: skill.response_type || 'text',
        response_example: skill.response_example || null,
      };
      count++;
    }
  }

  _aggregateTable = newTable;

  const { updateRegisteredPrefixes } = await import('./auth.js');
  const registered = new Set(
    Object.values(newTable)
      .map((e) => e.st_prefix)
      .filter(Boolean)
  );
  if (registered.size > 0) {
    updateRegisteredPrefixes(registered);
  }

  return count;
}

export function buildExternalSchema(endpointBaseUrl) {
  _externalSchema = {};

  if (!endpointBaseUrl) return {};

  const base = endpointBaseUrl.replace(/\/+$/, '');
  const targetUrl = `${base}/text-cli/cli`;

  for (const [key, entry] of Object.entries(_aggregateTable)) {
    _externalSchema[key] = {
      url: targetUrl,
      id: entry.id || key,
      name: entry.name,
      category: entry.category,
      description: entry.description,
      directive: entry.directive,
      parameters: entry.parameters,
      prompt_template: entry.prompt_template,
      trigger_keywords: entry.trigger_keywords,
      response_type: entry.response_type,
      response_example: entry.response_example,
    };
  }

  return _externalSchema;
}

export function findBackendSource(directiveKey) {
  const normalized = normalizeSkillId(directiveKey);
  const entry = _aggregateTable[normalized];
  return entry ? entry.source : null;
}

export function getExternalSchema() {
  return _externalSchema;
}

export function getBackendBaseUrl(env) {
  if (Object.keys(_aggregateTable).length === 0) {
    const backendsRaw = env.A3_BACKENDS || '';
    if (backendsRaw) {
      return backendsRaw.split(',')[0].trim().replace(/\/+$/, '');
    }
    return null;
  }

  for (const entry of Object.values(_aggregateTable)) {
    return entry.source;
  }
  return null;
}

export async function ensureSkillsLoaded(env) {
  if (Object.keys(_aggregateTable).length === 0 && (env.A3_BACKENDS || '')) {
    await refreshBackends(env);
  }
}

async function fetchSkills(backendBase, token) {
  const url = `${backendBase}/text-cli/skills`;
  const headers = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  try {
    const resp = await fetch(url, { headers });
    if (!resp.ok) return null;
    const data = await resp.json();
    if (Array.isArray(data)) return data;
    if (data && typeof data === 'object') return Object.values(data);
    return [];
  } catch {
    return null;
  }
}
