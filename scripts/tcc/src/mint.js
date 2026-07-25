/**
 * TCC Mint Algorithm
 * ref: docs/Production_TCC_CN.md §2
 */

const DEFAULT_CONFIG = {
  scalingFactor: 100,
  dailyMintCap: 100,
  deltaBytesThreshold: 10,
  rawScoreThreshold: 200,
};

export function normalize(text) {
  if (typeof text !== 'string') return '';

  let result = text.normalize('NFKC');

  const lines = result.split('\n');
  const noBlank = lines.filter(line => line.trim() !== '');
  const deduped = noBlank.filter((line, i) => i === 0 || line !== noBlank[i - 1]);
  const trimmed = deduped.map(line => line.trimEnd());

  return trimmed.join('\n');
}

export async function sha256(content) {
  const encoder = new TextEncoder();
  const data = encoder.encode(content);
  const hashBuffer = await crypto.subtle.digest('SHA-256', data);
  return new Uint8Array(hashBuffer);
}

function xorBytes(a, b) {
  const result = new Uint8Array(32);
  for (let i = 0; i < 32; i++) {
    result[i] = a[i] ^ b[i];
  }
  return result;
}

function popcount(byte) {
  let count = 0;
  let n = byte;
  while (n) {
    count += n & 1;
    n >>>= 1;
  }
  return count;
}

function bytesToHex(bytes) {
  return Array.from(bytes).map(b => b.toString(16).padStart(2, '0')).join('');
}

export async function calculateMint(oldContent, newContent, config = {}) {
  const cfg = { ...DEFAULT_CONFIG, ...config };

  const normalizedOld = normalize(oldContent);
  const normalizedNew = normalize(newContent);
  const deltaBytes = normalizedNew.length - normalizedOld.length;

  if (deltaBytes < cfg.deltaBytesThreshold) {
    return {
      mint_ceiling: 0,
      reason: 'delta_too_small',
      delta_bytes: deltaBytes,
    };
  }

  const [oldHash, newHash] = await Promise.all([
    sha256(normalizedOld),
    sha256(normalizedNew),
  ]);

  const xorResult = xorBytes(oldHash, newHash);
  let hashDiffBits = 0;
  for (const byte of xorResult) {
    hashDiffBits += popcount(byte);
  }

  if (hashDiffBits === 0) {
    return {
      mint_ceiling: 0,
      reason: 'content_identical',
      hash_diff_bits: 0,
      delta_bytes: deltaBytes,
    };
  }

  const rawScore = hashDiffBits * Math.log(1 + deltaBytes);

  if (rawScore < cfg.rawScoreThreshold) {
    return {
      mint_ceiling: 0,
      reason: 'raw_score_below_threshold',
      hash_diff_bits: hashDiffBits,
      delta_bytes: deltaBytes,
      raw_score: Math.round(rawScore * 100) / 100,
    };
  }

  const suggestedMint = Math.round(rawScore / cfg.scalingFactor);
  const mintCeiling = Math.min(suggestedMint, cfg.dailyMintCap);

  return {
    type: 'daily',
    mint_ceiling: mintCeiling,
    hash_diff_bits: hashDiffBits,
    delta_bytes: deltaBytes,
    raw_score: Math.round(rawScore * 100) / 100,
    scaling_factor: cfg.scalingFactor,
    daily_cap: cfg.dailyMintCap,
    old_hash: bytesToHex(oldHash),
    new_hash: bytesToHex(newHash),
  };
}
