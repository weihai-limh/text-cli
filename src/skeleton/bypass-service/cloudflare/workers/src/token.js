// token — Service-token 指令化管理（签发/撤销/列表）
//
// 运行时 = 能力提供方：token;issue 签发，入口只校验 Service-token（单 token 闭环）。
// 复用 tc-js-skeleton 的 createAuth（HMAC 自签 + tokenStore 可吊销）；
// tokens 业务表存 hash 供 list / 审计查询面。

import { createHash } from "node:crypto";
import { createAuth } from "../../tc-js-skeleton/packages/textcli-core-auth/index.js";

const hashOf = (token) => createHash("sha256").update(token).digest("hex");

export function createTokenManager({ db, tokenStore, secret, now }) {
  const auth = createAuth({ secret, tokenStore, now });
  return { auth, hashOf };
}

export async function issueToken(tm, db, params) {
  const requesterId = params[0];
  if (!requesterId) return { ok: false, error: "requester_id required" };
  const tier = params[1] || "standard";
  const { token, payload } = await tm.auth.issue(requesterId, { tier });
  // 业务表存 hash（查询面 / 审计）
  await db
    .prepare(
      "INSERT INTO tokens (token_hash, requester_id, tier, created_at, revoked_at) VALUES (?, ?, ?, ?, NULL) " +
        "ON CONFLICT(token_hash) DO UPDATE SET requester_id = excluded.requester_id, tier = excluded.tier",
    )
    .bind(tm.hashOf(token), requesterId, tier, payload.iat)
    .run();
  return { ok: true, token, requester_id: requesterId, tier };
}

export async function revokeToken(tm, db, params) {
  const token = params[0];
  if (!token) return { ok: false, error: "token required" };
  const revoked = await tm.auth.revoke(token);
  if (revoked) {
    await db.prepare("UPDATE tokens SET revoked_at = ? WHERE token_hash = ?").bind(Date.now(), tm.hashOf(token)).run();
  }
  return { ok: revoked, revoked };
}

export async function listTokens(db) {
  const res = await db.prepare("SELECT token_hash, requester_id, tier, created_at, revoked_at FROM tokens").all();
  return {
    ok: true,
    tokens: res.results.map((r) => ({
      token_hash_prefix: r.token_hash.slice(0, 12),
      requester_id: r.requester_id,
      tier: r.tier,
      created_at: r.created_at,
      revoked: r.revoked_at != null,
    })),
  };
}
