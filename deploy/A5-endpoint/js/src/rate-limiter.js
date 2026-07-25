export async function checkRateLimit(db, env, isGet = false) {
  if (!db) return true;

  const limit = isGet
    ? parseInt(env.RATE_LIMIT_GET_PER_HOUR || '10000', 10)
    : parseInt(env.RATE_LIMIT_PER_HOUR || '1000', 10);

  const cutoff = new Date(Date.now() - 3600000).toISOString();

  await db
    .prepare('DELETE FROM rate_limits WHERE created_at < ?')
    .bind(cutoff)
    .run();

  const row = await db
    .prepare(
      'SELECT COUNT(*) as cnt FROM rate_limits WHERE is_get = ? AND created_at >= ?'
    )
    .bind(isGet ? 1 : 0, cutoff)
    .first();

  if ((row?.cnt || 0) >= limit) {
    return false;
  }

  await db
    .prepare('INSERT INTO rate_limits (is_get, created_at) VALUES (?, ?)')
    .bind(isGet ? 1 : 0, new Date().toISOString())
    .run();

  return true;
}
