import { describe, it, expect } from 'vitest';
import { extractTokenPrefix, extractServiceTokenPrefix } from '../src/auth.js';

describe('extractTokenPrefix', () => {
  it('returns first 8 chars of token', () => {
    expect(extractTokenPrefix('abcdefghijklmnop')).toBe('abcdefgh');
  });

  it('strips Bearer prefix', () => {
    expect(extractTokenPrefix('Bearer abcdefghijklmnop')).toBe('abcdefgh');
  });

  it('returns empty for null', () => {
    expect(extractTokenPrefix(null)).toBe('');
    expect(extractTokenPrefix('')).toBe('');
  });

  it('returns full token if shorter than 8', () => {
    expect(extractTokenPrefix('abc')).toBe('abc');
  });
});

describe('extractServiceTokenPrefix', () => {
  it('returns first 8 chars', () => {
    expect(extractServiceTokenPrefix('abcdefghijklmnop')).toBe('abcdefgh');
  });

  it('returns empty for null', () => {
    expect(extractServiceTokenPrefix(null)).toBe('');
  });

  it('returns full if shorter than 8', () => {
    expect(extractServiceTokenPrefix('abc')).toBe('abc');
  });
});
