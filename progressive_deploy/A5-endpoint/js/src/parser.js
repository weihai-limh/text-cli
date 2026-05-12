const DIRECTIVE_PATTERN = /^\s*(?:指令|AI)[：:]([^;]+);([^,]+)(?:,(.+))?\s*$/;
const PREFIX_PATTERN = /^(指令|AI)[：:]/;
const MAX_DIRECTIVE_LENGTH = 512;
const MAX_PARAMS = 10;

export class DirectiveParseError extends Error {
  constructor(message, code = 'INVALID_DIRECTIVE_FORMAT') {
    super(message);
    this.code = code;
  }
}

export function normalizeDirectiveKey(key) {
  for (const prefix of ['指令:', 'AI:', '指令：', 'AI：']) {
    if (key.startsWith(prefix)) {
      return key.slice(prefix.length);
    }
  }
  return key;
}

export function parseDirective(prompt) {
  if (!prompt || !prompt.trim()) {
    throw new DirectiveParseError('prompt is required');
  }

  const cleaned = prompt.trim();

  if (cleaned.length > MAX_DIRECTIVE_LENGTH) {
    throw new DirectiveParseError(
      `directive exceeds max length (${MAX_DIRECTIVE_LENGTH})`
    );
  }

  const match = DIRECTIVE_PATTERN.exec(cleaned);
  if (!match) {
    throw new DirectiveParseError(`invalid directive format: ${cleaned}`);
  }

  const domain = match[1].trim();
  const action = match[2].trim();
  const rawParams = match[3];

  const params = [];
  if (rawParams) {
    for (const p of rawParams.split(',')) {
      const trimmed = p.trim();
      if (trimmed) params.push(trimmed);
    }
  }

  if (params.length > MAX_PARAMS) {
    throw new DirectiveParseError(
      `too many parameters (${params.length}), max ${MAX_PARAMS}`
    );
  }

  for (const p of params) {
    if (/[,;\n\r]/.test(p)) {
      throw new DirectiveParseError(`parameter contains forbidden characters: ${p}`);
    }
  }

  if (!domain) throw new DirectiveParseError('domain is empty');
  if (!action) throw new DirectiveParseError('action is empty');

  const prefixMatch = PREFIX_PATTERN.exec(cleaned);
  const prefix = prefixMatch ? prefixMatch[1] : '指令';

  return {
    domain,
    action,
    params,
    raw: cleaned,
    directiveKey: `${prefix}:${domain};${action}`,
  };
}
