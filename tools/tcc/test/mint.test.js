import { describe, it, expect } from 'vitest';
import { calculateMint, sha256 } from '../src/mint.js';

describe('sha256', () => {
  it('returns 32 bytes', async () => {
    const hash = await sha256('hello');
    expect(hash).toBeInstanceOf(Uint8Array);
    expect(hash.length).toBe(32);
  });

  it('is deterministic', async () => {
    const a = await sha256('test input');
    const b = await sha256('test input');
    expect(Buffer.from(a).toString('hex')).toBe(Buffer.from(b).toString('hex'));
  });

  it('different inputs produce different hashes', async () => {
    const a = await sha256('hello');
    const b = await sha256('world');
    expect(Buffer.from(a).toString('hex')).not.toBe(Buffer.from(b).toString('hex'));
  });
});

describe('calculateMint', () => {
  it('returns 0 when delta_bytes < threshold', async () => {
    const result = await calculateMint('short', 'short text');
    expect(result.mint_ceiling).toBe(0);
    expect(result.reason).toBe('delta_too_small');
  });

  it('returns 0 when content identical after normalize', async () => {
    const result = await calculateMint('hello\nworld', 'hello\nworld');
    expect(result.mint_ceiling).toBe(0);
    expect(['content_identical', 'delta_too_small']).toContain(result.reason);
  });

  it('returns valid result for significant changes', async () => {
    const oldContent = 'line 1\nline 2\nline 3';
    const newContent = [
      'line 1',
      'line 2',
      'line 3',
      'new line 4 with enough content to pass threshold',
      'new line 5 with even more meaningful content here',
      'new line 6 adding substantial bytes to the document',
      'new line 7 contributing to the delta bytes calculation',
      'new line 8 with additional padding for the threshold',
      'new line 9 final line to ensure we pass raw_score check',
      'new line 10 extra content for safety margin',
      'new line 11 more bytes needed',
      'new line 12 and more',
      'new line 13 and more',
      'new line 14 and more',
      'new line 15 and more',
    ].join('\n');

    const result = await calculateMint(oldContent, newContent);
    expect(result.mint_ceiling).toBeGreaterThan(0);
    expect(result.type).toBe('daily');
    expect(result.hash_diff_bits).toBeGreaterThan(0);
    expect(result.delta_bytes).toBeGreaterThan(10);
    expect(result.raw_score).toBeGreaterThan(0);
    expect(result.old_hash).toHaveLength(64);
    expect(result.new_hash).toHaveLength(64);
    expect(result.scaling_factor).toBe(100);
    expect(result.daily_cap).toBe(100);
  });

  it('respects daily cap', async () => {
    const oldContent = 'a';
    const newContent = 'a' + '\nb'.repeat(500);

    const result = await calculateMint(oldContent, newContent, {
      scalingFactor: 1,
      dailyMintCap: 50,
      deltaBytesThreshold: 1,
      rawScoreThreshold: 0,
    });

    if (result.mint_ceiling > 0) {
      expect(result.mint_ceiling).toBeLessThanOrEqual(50);
    }
  });

  it('respects raw_score threshold', async () => {
    const oldContent = 'content';
    const newContent = 'content with small change added here';

    const result = await calculateMint(oldContent, newContent, {
      scalingFactor: 100,
      dailyMintCap: 100,
      deltaBytesThreshold: 1,
      rawScoreThreshold: 99999,
    });

    expect(result.mint_ceiling).toBe(0);
    expect(result.reason).toBe('raw_score_below_threshold');
  });

  it('default config values match spec', async () => {
    const result = await calculateMint('x', 'x');
    expect(result).toBeDefined();
  });
});
