import { describe, it, expect } from 'vitest';
import { formatDailyResult, formatGenesisMessage, formatAlert } from '../src/format.js';

describe('formatDailyResult', () => {
  it('formats zero mint_ceiling result', () => {
    const result = {
      mint_ceiling: 0,
      reason: 'delta_too_small',
      delta_bytes: 5,
    };
    const output = formatDailyResult(result, 'abc123');
    expect(output).toContain('未触发铸造');
    expect(output).toContain('delta_too_small');
    expect(output).toContain('abc123');
  });

  it('formats positive mint_ceiling result', () => {
    const result = {
      type: 'daily',
      mint_ceiling: 42,
      hash_diff_bits: 180,
      delta_bytes: 500,
      raw_score: 11086.55,
      scaling_factor: 100,
      daily_cap: 100,
      old_hash: 'a'.repeat(64),
      new_hash: 'b'.repeat(64),
    };
    const output = formatDailyResult(result, 'def456');
    expect(output).toContain('42 TCC');
    expect(output).toContain('180');
    expect(output).toContain('500');
    expect(output).toContain('lemondy');
  });
});

describe('formatGenesisMessage', () => {
  it('mentions genesis mint', () => {
    const output = formatGenesisMessage();
    expect(output).toContain('创世铸造');
    expect(output).toContain('lemondy');
  });
});

describe('formatAlert', () => {
  it('includes module and error', () => {
    const output = formatAlert('scheduled', 'Token expired');
    expect(output).toContain('scheduled');
    expect(output).toContain('Token expired');
    expect(output).toContain('告警');
  });
});
