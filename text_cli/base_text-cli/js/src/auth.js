const SERVICE_TOKEN = globalThis.SERVICE_TOKEN || '';

async function sha256Hex(text) {
  const data = new TextEncoder().encode(text);
  const hash = await crypto.subtle.digest('SHA-256', data);
  return [...new Uint8Array(hash)].map(b => b.toString(16).padStart(2, '0')).join('');
}

export async function verifyServiceToken(token, db) {
  if (!token) {
    return { allowed: false, clientName: '', message: 'Service-token 缺失' };
  }

  const clean = token.trim();

  if (db) {
    const hash = await sha256Hex(clean);
    const row = await db
      .prepare(
        'SELECT client_name, quota, used, enabled FROM tokens WHERE token_hash = ?'
      )
      .bind(hash)
      .first();

    if (!row) {
      return { allowed: false, clientName: '', message: 'Service-token 无效' };
    }
    if (!row.enabled) {
      return { allowed: false, clientName: row.client_name, message: 'Token 已禁用' };
    }
    if (row.quota >= 0 && row.used >= row.quota) {
      return {
        allowed: false,
        clientName: row.client_name,
        message: `配额已用尽 (${row.used}/${row.quota})`,
      };
    }
    return { allowed: true, clientName: row.client_name, message: '', tokenHash: hash };
  }

  if (!SERVICE_TOKEN) {
    return { allowed: true, clientName: 'anonymous', message: '' };
  }
  if (clean !== SERVICE_TOKEN) {
    return { allowed: false, clientName: '', message: 'Service-token 无效' };
  }
  return { allowed: true, clientName: 'authenticated', message: '' };
}

export async function incrementUsage(db, tokenHash) {
  if (!db || !tokenHash) return;
  await db
    .prepare('UPDATE tokens SET used = used + 1 WHERE token_hash = ?')
    .bind(tokenHash)
    .run();
}
