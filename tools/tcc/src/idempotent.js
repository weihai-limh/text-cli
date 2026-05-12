/**
 * D1 Idempotency Guard
 * ref: docs/Production_TCC_CN.md §3.3
 */

const INIT_SQL = `CREATE TABLE IF NOT EXISTS processed_commits (sha TEXT PRIMARY KEY, processed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)`;

export async function initIdempotencyTable(db) {
  await db.prepare(INIT_SQL).run();
}

export async function isProcessed(db, sha) {
  const row = await db
    .prepare('SELECT 1 FROM processed_commits WHERE sha = ?')
    .bind(sha)
    .first();
  return row !== null;
}

export async function markProcessed(db, sha) {
  await db
    .prepare('INSERT OR IGNORE INTO processed_commits (sha) VALUES (?)')
    .bind(sha)
    .run();
}
