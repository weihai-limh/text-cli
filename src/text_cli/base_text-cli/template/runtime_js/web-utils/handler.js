// web-utils JS — refactored with textcli-core (Phase 5)
// Declarative handler registration. Eliminates CloudBase-specific envelope/parser.
// get_public_ip now uses an adapter layer instead of direct event._routerEvent access.

"use strict";

// ─── get_public_ip ──────────────────────────────────

function getPublicIpHandler(params, context) {
  const publicIp = extractPublicIp(context);
  if (publicIp === 'unknown') {
    return { status: 'error', reason: 'Unable to determine public IP' };
  }
  return { status: 'ok', result: publicIp };
}

function extractPublicIp(ctx) {
  // adapter layer: ctx is the platform event object
  if (!ctx) return 'unknown';

  // CloudBase path: event._routerEvent
  const routerEvent = ctx._routerEvent;
  if (routerEvent) {
    if (routerEvent.sourceIp) return routerEvent.sourceIp;
    const rh = routerEvent.headers || {};
    if (rh['x-forwarded-for']) return rh['x-forwarded-for'].split(',')[0].trim();
    if (rh['x-real-ip']) return rh['x-real-ip'];
  }

  // Direct HTTP path
  if (ctx.sourceIp) return ctx.sourceIp;
  const headers = ctx.headers || {};
  if (headers['x-forwarded-for']) return headers['x-forwarded-for'].split(',')[0].trim();
  if (headers['x-real-ip']) return headers['x-real-ip'];

  return 'unknown';
}

// ─── xor_encrypt / xor_decrypt ──────────────────────

function xorBytes(a, b) {
  const result = Buffer.alloc(Math.max(a.length, b.length));
  for (let i = 0; i < result.length; i++) {
    result[i] = a[i % a.length] ^ b[i % b.length];
  }
  return result;
}

function xorEncryptHandler(params) {
  const plaintext = params[0];
  const key = params[1];
  if (!plaintext || !key) {
    return { status: 'error', reason: 'plaintext and key are required' };
  }
  const plaintextBytes = Buffer.from(plaintext, 'utf8');
  const keyBytes = Buffer.from(key, 'utf8');
  const ciphertextBytes = xorBytes(plaintextBytes, keyBytes);
  return { status: 'ok', result: ciphertextBytes.toString('hex') };
}

function xorDecryptHandler(params) {
  const ciphertext = params[0];
  const key = params[1];
  if (!ciphertext || !key) {
    return { status: 'error', reason: 'ciphertext and key are required' };
  }
  if (!/^[0-9a-fA-F]+$/.test(ciphertext)) {
    return { status: 'error', reason: 'ciphertext must be a valid hex string' };
  }
  const ciphertextBytes = Buffer.from(ciphertext, 'hex');
  const keyBytes = Buffer.from(key, 'utf8');
  const plaintextBytes = xorBytes(ciphertextBytes, keyBytes);
  return { status: 'ok', result: plaintextBytes.toString('utf8') };
}

// ─── Declarative exports ────────────────────────────

module.exports = {
  domainAlias: 'Web\u5de5\u5177',
  directives: {
    get_public_ip: {
      handler: getPublicIpHandler,
      actionAliases: ['\u83b7\u53d6\u516c\u7f51IP'],
    },
    xor_encrypt: {
      handler: xorEncryptHandler,
      actionAliases: ['\u5f02\u6216\u52a0\u5bc6'],
    },
    xor_decrypt: {
      handler: xorDecryptHandler,
      actionAliases: ['\u5f02\u6216\u89e3\u5bc6'],
    },
  },
};
