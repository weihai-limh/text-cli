import { describe, it, expect } from 'vitest';
import { verifySignature } from '../src/verify.js';

async function hmacSha256Hex(secret, payload) {
  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    'raw',
    encoder.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign'],
  );
  const sig = await crypto.subtle.sign('HMAC', key, encoder.encode(payload));
  return 'sha256=' + Array.from(new Uint8Array(sig))
    .map(b => b.toString(16).padStart(2, '0'))
    .join('');
}

describe('verifySignature', () => {
  const secret = 'test-webhook-secret';
  const payload = '{"action":"push"}';

  it('returns true for valid signature', async () => {
    const signature = await hmacSha256Hex(secret, payload);
    const result = await verifySignature(payload, signature, secret);
    expect(result).toBe(true);
  });

  it('returns false for invalid signature', async () => {
    const result = await verifySignature(payload, 'sha256=0000deadbeef', secret);
    expect(result).toBe(false);
  });

  it('returns false when signature header is missing', async () => {
    const result = await verifySignature(payload, null, secret);
    expect(result).toBe(false);
  });

  it('returns true when secret is missing (skip verification)', async () => {
    const signature = await hmacSha256Hex(secret, payload);
    const result = await verifySignature(payload, signature, null);
    expect(result).toBe(true);
  });

  it('returns false for wrong prefix', async () => {
    const signature = await hmacSha256Hex(secret, payload);
    const wrongPrefix = signature.replace('sha256=', 'sha1=');
    const result = await verifySignature(payload, wrongPrefix, secret);
    expect(result).toBe(false);
  });

  it('returns false for tampered payload', async () => {
    const signature = await hmacSha256Hex(secret, payload);
    const result = await verifySignature('tampered', signature, secret);
    expect(result).toBe(false);
  });
});
