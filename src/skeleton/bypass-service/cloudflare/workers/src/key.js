// key — key 指令化凭据（注册/撤销/列表 + AES-GCM 加密存储 + sandbox 注入通道）
//
// keys 表 values_cipher 存密文（密钥 = Worker Secrets 派生）；明文不落 D1。
// sandbox.credential.get(service) 由 executor 注入，此处实现解密解析。
// 授权映射第一防线：按包 schema capability.credentials 白名单（executor 侧校验）。

import { createCipheriv, createDecipheriv, createHash, randomBytes } from "node:crypto";

function derive(secret) {
  return createHash("sha256").update(String(secret)).digest();
}

export function encryptValues(secret, values) {
  const key = derive(secret);
  const iv = randomBytes(12);
  const cipher = createCipheriv("aes-256-gcm", key, iv);
  const ct = Buffer.concat([cipher.update(JSON.stringify(values), "utf8"), cipher.final()]);
  const tag = cipher.getAuthTag();
  return `${iv.toString("base64url")}:${tag.toString("base64url")}:${ct.toString("base64url")}`;
}

export function decryptValues(secret, cipherText) {
  const key = derive(secret);
  const [ivB, tagB, ctB] = String(cipherText).split(":");
  const decipher = createDecipheriv("aes-256-gcm", key, Buffer.from(ivB, "base64url"));
  decipher.setAuthTag(Buffer.from(tagB, "base64url"));
  const plain = Buffer.concat([decipher.update(Buffer.from(ctB, "base64url")), decipher.final()]);
  return JSON.parse(plain.toString("utf8"));
}

export async function registerKey(db, secret, params) {
  // key;register,<service>,<value1>[,<value2>],<key_type>
  const service = params[0];
  const keyType = params[params.length - 1];
  const values = params.slice(1, -1);
  if (!service || !values.length || !keyType) return { ok: false, error: "usage: key;register,<service>,<value...>,<key_type>" };
  const cipher = encryptValues(secret, values);
  await db
    .prepare(
      "INSERT INTO keys (service, key_type, values_cipher, registered_at, quota_track) VALUES (?, ?, ?, ?, NULL) " +
        "ON CONFLICT(service) DO UPDATE SET key_type = excluded.key_type, values_cipher = excluded.values_cipher, registered_at = excluded.registered_at",
    )
    .bind(service, keyType, cipher, Date.now())
    .run();
  return { ok: true, service, key_type: keyType };
}

export async function revokeKey(db, params) {
  const service = params[0];
  if (!service) return { ok: false, error: "service required" };
  await db.prepare("DELETE FROM keys WHERE service = ?").bind(service).run();
  return { ok: true, service };
}

export async function listKeys(db) {
  const res = await db.prepare("SELECT service, key_type, registered_at FROM keys").all();
  return { ok: true, keys: res.results };
}

/** 解密取用（供 sandbox.credential.get；返回首值，多值返回对象） */
export async function getKeyValue(db, secret, service) {
  const row = await db.prepare("SELECT values_cipher FROM keys WHERE service = ?").bind(service).first();
  if (!row) return undefined;
  const values = decryptValues(secret, row.values_cipher);
  return values.length > 1 ? values : values[0];
}
