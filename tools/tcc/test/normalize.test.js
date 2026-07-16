import { describe, it, expect } from 'vitest';
import { normalize } from '../src/mint.js';

describe('normalize', () => {
  it('NFKC normalizes fullwidth ASCII to halfwidth', () => {
    const input = '\uFF21\uFF22\uFF23';
    expect(normalize(input)).toBe('ABC');
  });

  it('removes blank lines', () => {
    const input = 'line1\n\n\nline2\n   \nline3';
    expect(normalize(input)).toBe('line1\nline2\nline3');
  });

  it('deduplicates consecutive identical lines', () => {
    const input = 'aaa\naaa\nbbb\nbbb\nbbb\nccc';
    expect(normalize(input)).toBe('aaa\nbbb\nccc');
  });

  it('trims trailing whitespace per line', () => {
    const input = 'hello   \nworld\t\t';
    expect(normalize(input)).toBe('hello\nworld');
  });

  it('handles empty string', () => {
    expect(normalize('')).toBe('');
  });

  it('handles null/undefined gracefully', () => {
    expect(normalize(null)).toBe('');
    expect(normalize(undefined)).toBe('');
  });

  it('preserves non-consecutive duplicate lines', () => {
    const input = 'aaa\nbbb\naaa';
    expect(normalize(input)).toBe('aaa\nbbb\naaa');
  });

  it('complex combined case', () => {
    const input = [
      '# Title  ',
      '',
      '  ',
      'content line',
      'content line',
      '',
      'another line   ',
      'another line   ',
      '',
    ].join('\n');
    const expected = [
      '# Title',
      'content line',
      'another line',
    ].join('\n');
    expect(normalize(input)).toBe(expected);
  });

  it('is idempotent', () => {
    const input = 'hello\n\nworld\nworld\n';
    expect(normalize(normalize(input))).toBe(normalize(input));
  });
});
