// textcli-core-auth — Service-token 签发/校验（外挂，auth.on）
//
// 运行时 = 能力提供方，单 token 闭环。零依赖：node:crypto HMAC-SHA256 自签 token，
// 无 JWT 库。拒绝 → SERVICE_DENIED（协议实证：跨终端鉴权失败 → SERVICE_DENIED）。
//
// token 格式：base64url(payload) . base64url(hmac-sha256(payload))
// payload：{ iss, sub, jti, iat, exp, ...claims }
//
// tokenStore 注入（两种模态，同一 { get, set, delete, keys? } 契约）：
//   · storage 模态：createStorage(adapter).namespace("tokens") —— 跨节点、可查、可吊销
//   · 加密 JSON 模态：createEncryptedJsonTokenStore(file, key) —— 文件存密文，密钥宿主注入
//
// 合规：跨终端暴露（监听非 loopback）⇒ withAuth({ mode: "required" }) 强制开启（§6.1）。

import { createHmac, createCipheriv, createDecipheriv, randomBytes, timingSafeEqual, createHash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";

export class AuthError extends Error {
  constructor(code, message) {
    super(message);
    this.name = "AuthError";
    this.code = code; // malformed | bad-signature | bad-payload | expired | revoked
  }
}

// ─── 内存 tokenStore（测试 / 裸环境）───────────────────────────────
export function createMemoryTokenStore() {
  const map = new Map();
  return {
    async get(id) {
      return map.has(id) ? map.get(id) : null;
    },
    async set(id, rec) {
      map.set(id, rec);
    },
    async delete(id) {
      map.delete(id);
    },
    async keys() {
      return [...map.keys()];
    },
  };
}

// ─── 加密 JSON tokenStore（node:fs，文件存密文）────────────────────
// AES-256-GCM：密钥宿主注入（任意字符串 → sha256 派生 32 字节）；原子写 tmp+rename。
export function createEncryptedJsonTokenStore(file, key, opts = {}) {
  const fsMod = opts.fs || fs;
  const pathMod = opts.pathMod || path;
  const derived = createHash("sha256").update(String(key)).digest();
  const fileOf = () => file;

  function loadPlain() {
    try {
      const raw = fsMod.readFileSync(fileOf(), "utf8");
      const [ivB, tagB, ctB] = raw.split(":");
      const iv = Buffer.from(ivB, "base64url");
      const tag = Buffer.from(tagB, "base64url");
      const ciphertext = Buffer.from(ctB, "base64url");
      const decipher = createDecipheriv("aes-256-gcm", derived, iv);
      decipher.setAuthTag(tag);
      const plain = Buffer.concat([decipher.update(ciphertext), decipher.final()]);
      return JSON.parse(plain.toString("utf8"));
    } catch {
      return { tokens: {} };
    }
  }
  function savePlain(obj) {
    const iv = randomBytes(12);
    const cipher = createCipheriv("aes-256-gcm", derived, iv);
    const ciphertext = Buffer.concat([cipher.update(JSON.stringify(obj), "utf8"), cipher.final()]);
    const tag = cipher.getAuthTag();
    const blob = `${iv.toString("base64url")}:${tag.toString("base64url")}:${ciphertext.toString("base64url")}`;
    fsMod.mkdirSync(pathMod.dirname(fileOf()), { recursive: true });
    const tmp = `${fileOf()}.tmp`;
    fsMod.writeFileSync(tmp, blob, "utf8");
    fsMod.renameSync(tmp, fileOf());
  }

  return {
    async get(id) {
      const obj = loadPlain();
      return id in obj.tokens ? obj.tokens[id] : null;
    },
    async set(id, rec) {
      const obj = loadPlain();
      obj.tokens[id] = rec;
      savePlain(obj);
    },
    async delete(id) {
      const obj = loadPlain();
      if (id in obj.tokens) {
        delete obj.tokens[id];
        savePlain(obj);
      }
    },
    async keys() {
      return Object.keys(loadPlain().tokens);
    },
  };
}

// ─── AuthService：issue / verify / revoke ──────────────────────────
export function createAuth(opts = {}) {
  const tokenStore = opts.tokenStore || null;
  const secret = opts.secret || "textcli-core-dev-secret";
  const issuer = opts.issuer || "textcli-core";
  const ttlMs = opts.ttlMs ?? 3600000;
  const now = opts.now || Date.now;

  const b64url = (buf) => Buffer.from(buf).toString("base64url");
  const sign = (payloadB64) => createHmac("sha256", secret).update(payloadB64).digest("base64url");

  async function issue(subject, claims = {}) {
    if (!subject) throw new AuthError("bad-payload", "subject required");
    const jti = randomBytes(8).toString("hex");
    const payload = { iss: issuer, sub: subject, jti, iat: now(), exp: now() + ttlMs, ...claims };
    const p = b64url(JSON.stringify(payload));
    const token = `${p}.${sign(p)}`;
    if (tokenStore) {
      // tokenStore 遵循 StorageKV 字符串值契约
      await tokenStore.set(jti, JSON.stringify({ sub: subject, jti, iat: payload.iat, exp: payload.exp, revoked: false }));
    }
    return { token, payload };
  }

  async function verify(token) {
    if (!token || typeof token !== "string") throw new AuthError("malformed", "token required");
    const parts = token.split(".");
    if (parts.length !== 2) throw new AuthError("malformed", "token format");
    const [p, sig] = parts;
    const expected = sign(p);
    const a = Buffer.from(sig, "base64url");
    const b = Buffer.from(expected, "base64url");
    if (a.length !== b.length || !timingSafeEqual(a, b)) throw new AuthError("bad-signature", "signature mismatch");
    let payload;
    try {
      payload = JSON.parse(Buffer.from(p, "base64url").toString("utf8"));
    } catch {
      throw new AuthError("bad-payload", "payload unparseable");
    }
    if (payload.exp && now() >= payload.exp) throw new AuthError("expired", "token expired");
    if (tokenStore) {
      const raw = await tokenStore.get(payload.jti);
      const rec = raw ? JSON.parse(raw) : null;
      if (!rec) throw new AuthError("revoked", "token not in store");
      if (rec.revoked) throw new AuthError("revoked", "token revoked");
    }
    return payload;
  }

  async function revoke(tokenOrJti) {
    if (!tokenStore) return false;
    let jti = tokenOrJti;
    if (tokenOrJti.includes(".")) {
      const parts = tokenOrJti.split(".");
      try {
        jti = JSON.parse(Buffer.from(parts[0], "base64url").toString()).jti;
      } catch {
        return false;
      }
    }
    const raw = await tokenStore.get(jti);
    if (!raw) return false;
    const rec = JSON.parse(raw);
    await tokenStore.set(jti, JSON.stringify({ ...rec, revoked: true }));
    return true;
  }

  return { issue, verify, revoke };
}

// ─── withAuth 中间件（dispatch 前鉴权闸）───────────────────────────
/**
 * token 来源：opts.tokenFor（默认 context.token 或 Authorization: Bearer）。
 * mode: "optional"（默认，本地 loopback 无鉴权义务，无 token 放行）
 *      "required"（跨终端暴露必须；无 token / 无效 → SERVICE_DENIED）
 * 校验通过 → 载荷注入 context.auth。
 */
export function withAuth(auth, opts = {}) {
  const tokenFor =
    opts.tokenFor ||
    ((domain, action, params, context) => {
      if (!context) return undefined;
      if (context.token) return context.token;
      const h = context.headers || {};
      const authz = h.authorization || h.Authorization;
      if (authz && authz.startsWith("Bearer ")) return authz.slice("Bearer ".length);
      return undefined;
    });
  const mode = opts.mode || "optional";
  return (next) => async (domain, action, params, context) => {
    const token = tokenFor(domain, action, params, context);
    if (!token) {
      if (mode === "required") {
        return { rst_types: "text", rst_err: "SERVICE_DENIED", rst_data: { reason: "missing service token" } };
      }
      return next(domain, action, params, context);
    }
    try {
      const payload = await auth.verify(token);
      return next(domain, action, params, { ...(context || {}), auth: payload });
    } catch (e) {
      return { rst_types: "text", rst_err: "SERVICE_DENIED", rst_data: { reason: `invalid service token: ${e.message}` } };
    }
  };
}
