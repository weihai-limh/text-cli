const DIRECTIVE_PATTERN = /^\s*指令[：:]([^;]+);([^,]+)(?:,(.+))?\s*$/;
const MAX_DIRECTIVE_LENGTH = 512;
const MAX_PARAMS = 20;

export class DirectiveParseError extends Error {
  constructor(message, code = 'INVALID_DIRECTIVE_FORMAT') {
    super(message);
    this.code = code;
  }
}

export function parseDirective(prompt) {
  if (!prompt || !prompt.trim()) {
    throw new DirectiveParseError('prompt is required');
  }

  prompt = prompt.trim();

  if (prompt.length > MAX_DIRECTIVE_LENGTH) {
    throw new DirectiveParseError(
      `directive exceeds max length (${MAX_DIRECTIVE_LENGTH})`
    );
  }

  const match = DIRECTIVE_PATTERN.exec(prompt);
  if (!match) {
    throw new DirectiveParseError(`invalid directive format: ${prompt}`);
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

  if (!domain) throw new DirectiveParseError('domain is empty');
  if (!action) throw new DirectiveParseError('action is empty');

  return {
    domain,
    action,
    params,
    raw: prompt,
    directiveKey: `指令:${domain};${action}`,
  };
}
