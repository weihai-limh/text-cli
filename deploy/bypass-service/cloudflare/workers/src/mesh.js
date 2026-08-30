// mesh — mesh 代理（其他运行时 token 代理）
//
// 定位：调用方只记 Cloudflare 一个入口；本地不命中 → mesh_routes → 目标 peer 双 token →
// 转发到 peer 的 /text-cli/cli（只注入目标 peer 的 Service-token，凭证按 peer 隔离）。
// 复用 tc-js-skeleton 的 withMesh（防环/跳数/退避/脱敏），remote 注入为 fetch 转发。

import { encryptValues, decryptValues } from "./key.js";

export async function registerPeer(db, secret, params) {
  // mesh;peer-register,<peer_id>,<endpoint>,<service_token>
  const [peerId, endpoint, serviceToken] = params;
  if (!peerId || !endpoint) return { ok: false, error: "usage: mesh;peer-register,<peer_id>,<endpoint>,<service_token>" };
  const cipher = serviceToken ? encryptPeerToken(secret, serviceToken) : null;
  await db
    .prepare(
      "INSERT INTO mesh_peers (peer_id, endpoint_url, access_token_cipher, service_token_cipher, created_at) VALUES (?, ?, NULL, ?, ?) " +
        "ON CONFLICT(peer_id) DO UPDATE SET endpoint_url = excluded.endpoint_url, service_token_cipher = excluded.service_token_cipher",
    )
    .bind(peerId, endpoint, cipher, Date.now())
    .run();
  return { ok: true, peer_id: peerId, endpoint };
}

export async function addRoute(db, params) {
  // mesh;route-add,<domain>,<action>,<peer_id>
  const [domain, action, peerId] = params;
  if (!domain || !action || !peerId) return { ok: false, error: "usage: mesh;route-add,<domain>,<action>,<peer_id>" };
  await db
    .prepare("INSERT INTO mesh_routes (domain, action, peer_id) VALUES (?, ?, ?) ON CONFLICT(domain, action) DO UPDATE SET peer_id = excluded.peer_id")
    .bind(domain, action, peerId)
    .run();
  return { ok: true, route: { domain, action, peer_id: peerId } };
}

export async function listPeers(db) {
  const res = await db.prepare("SELECT peer_id, endpoint_url, created_at FROM mesh_peers").all();
  return { ok: true, peers: res.results };
}

function encryptPeerToken(secret, token) {
  // 复用 key.js 的 AES-GCM（同一密钥派生），存加密明文以便转发时解密使用
  return encryptValues(secret, [token]);
}

/**
 * 创建 mesh remote：本地不命中时转发。
 * @param {object} deps { db, secret, fetchImpl }
 * @returns {Function} remote(peer, domain, action, params) => Promise<信封 data>
 */
export function createMeshRemote({ db, secret, fetchImpl }) {
  return async (peer, domain, action, params) => {
    // 取 peer 的加密 service_token 并解密（只注入目标 peer，凭证按 peer 隔离）
    const p = await db.prepare("SELECT endpoint_url, service_token_cipher FROM mesh_peers WHERE peer_id = ?").bind(peer.id).first();
    if (!p) return { rst_types: "text", rst_err: "ERR_ROUTING", rst_data: { reason: `peer not found: ${peer.id}` } };
    let serviceToken = null;
    if (p.service_token_cipher) {
      try {
        const values = decryptValues(secret, p.service_token_cipher);
        serviceToken = Array.isArray(values) ? values[0] : values;
      } catch {
        /* 解密失败 → 不带 token 转发（peer 拒绝则降级） */
      }
    }
    const prompt = `AI:${domain};${action},${(params || []).join(",")}`;
    const res = await fetchImpl(`${p.endpoint_url}/text-cli/cli`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(serviceToken ? { "Service-Token": serviceToken } : {}) },
      body: JSON.stringify({ prompt }),
    });
    const env = await res.json();
    return env.rst_data ?? env;
  };
}

/** localHas：核心 registry 有该指令，或保留域指令（text-cli/token/key/quota/mesh）均为本地 */
export function createLocalHas(getRegistered) {
  const RESERVED = new Set(["text-cli", "token", "key", "quota", "mesh"]);
  return (domain, action) => {
    if (RESERVED.has(domain)) return true;
    return getRegistered().some((r) => r.domain === domain && r.action === action);
  };
}
