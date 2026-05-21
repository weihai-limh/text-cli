async function sha256Hex(text) {
  const data = new TextEncoder().encode(text);
  const hash = await crypto.subtle.digest('SHA-256', data);
  return [...new Uint8Array(hash)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

let _registeredPrefixes = null;
let _blockedPrefixes = null;

function loadSTPrefixes(env) {
  const rawReg = env.A3_REGISTERED_PREFIXES || '';
  _registeredPrefixes = new Set(rawReg.split(',').map((s) => s.trim()).filter(Boolean));
  const rawBlk = env.ST_PREFIX_BLACKLIST || '';
  _blockedPrefixes = new Set(rawBlk.split(',').map((s) => s.trim()).filter(Boolean));
}

export function updateRegisteredPrefixes(prefixes) {
  _registeredPrefixes = new Set(prefixes);
}

export function isSTPrefixBlocked(prefix, env) {
  if (_blockedPrefixes === null) loadSTPrefixes(env);
  return _blockedPrefixes.has(prefix);
}

export function isSTPrefixRegistered(prefix, env) {
  if (_registeredPrefixes === null) loadSTPrefixes(env);
  if (_registeredPrefixes.size === 0) return true;
  return _registeredPrefixes.has(prefix);
}

export function extractTokenPrefix(token) {
  if (!token) return '';
  const clean = token.startsWith('Bearer ') ? token.slice(7).trim() : token.trim();
  return clean.length >= 8 ? clean.slice(0, 8) : clean;
}

export function extractServiceTokenPrefix(serviceToken) {
  if (!serviceToken) return '';
  return serviceToken.length >= 8 ? serviceToken.slice(0, 8) : serviceToken;
}

export async function verifyAccessToken(authHeader, db, required = true) {
  if (!required) return null;

  if (!authHeader) return null;

  let clean = authHeader;
  if (clean.startsWith('Bearer ')) {
    clean = clean.slice(7).trim();
  } else {
    clean = clean.trim();
  }

  if (!clean) return null;

  const tokenHash = await sha256Hex(clean);

  const row = await db
    .prepare(
      'SELECT id, token_prefix, client_name, quota, used_count, max_requests_per_minute, is_active ' +
      'FROM access_tokens WHERE token_hash = ? AND is_active = 1'
    )
    .bind(tokenHash)
    .first();

  if (!row) return null;

  if (row.quota >= 0 && row.used_count >= row.quota) {
    return null;
  }

  const rateOk = await checkRateLimit(db, tokenHash, row.max_requests_per_minute);
  if (!rateOk) return null;

  return { ...row, tokenHash };
}

async function checkRateLimit(db, tokenHash, maxRpm) {
  try {
    const row = await db
      .prepare(
        "SELECT COUNT(*) as cnt FROM call_logs WHERE access_token_hash = ? AND created_at > datetime('now', '-60 seconds')"
      )
      .bind(tokenHash)
      .first();

    return (row?.cnt || 0) < maxRpm;
  } catch {
    return true;
  }
}

export async function incrementTokenUsage(db, tokenPrefix) {
  if (!db || !tokenPrefix) return;
  try {
    await db
      .prepare('UPDATE access_tokens SET used_count = used_count + 1 WHERE token_prefix = ?')
      .bind(tokenPrefix)
      .run();
  } catch {
    // ignore
  }
}

export async function hashToken(token) {
  return sha256Hex(token);
}
