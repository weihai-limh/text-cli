import { describe, it, expect } from 'vitest';
import { parseDirective, normalizeDirectiveKey, DirectiveParseError } from '../src/parser.js';

describe('parseDirective ("指令:" prefix)', () => {
  it('parses domain and action without params', () => {
    const r = parseDirective('指令:基础应用;天气查询');
    expect(r.domain).toBe('基础应用');
    expect(r.action).toBe('天气查询');
    expect(r.params).toEqual([]);
    expect(r.directiveKey).toBe('指令:基础应用;天气查询');
  });

  it('parses domain, action, and params', () => {
    const r = parseDirective('指令:基础应用;天气查询,明天,威海');
    expect(r.domain).toBe('基础应用');
    expect(r.action).toBe('天气查询');
    expect(r.params).toEqual(['明天', '威海']);
  });

  it('trims whitespace', () => {
    const r = parseDirective('  指令:基础应用;天气查询,明天  ');
    expect(r.domain).toBe('基础应用');
    expect(r.params).toEqual(['明天']);
  });

  it('accepts full-width colon', () => {
    const r = parseDirective('指令：基础应用;天气查询');
    expect(r.domain).toBe('基础应用');
    expect(r.directiveKey).toBe('指令:基础应用;天气查询');
  });

  it('throws on empty prompt', () => {
    expect(() => parseDirective('')).toThrow(DirectiveParseError);
    expect(() => parseDirective(null)).toThrow(DirectiveParseError);
  });

  it('throws on invalid format', () => {
    expect(() => parseDirective('hello world')).toThrow(DirectiveParseError);
  });

  it('throws on missing semicolon', () => {
    expect(() => parseDirective('指令:基础应用')).toThrow(DirectiveParseError);
  });

  it('throws on exceeding max params', () => {
    const params = Array(11).fill('a').join(',');
    expect(() => parseDirective(`指令:领域;动作,${params}`)).toThrow(DirectiveParseError);
  });

  it('throws on forbidden characters in params', () => {
    expect(() => parseDirective('指令:领域;动作,a;b')).toThrow(DirectiveParseError);
    expect(() => parseDirective('指令:领域;动作,a\nb')).toThrow(DirectiveParseError);
  });

  it('throws on exceeding max length', () => {
    const long = '指令:领域;动作,' + 'x'.repeat(600);
    expect(() => parseDirective(long)).toThrow(DirectiveParseError);
  });

  it('sets raw to trimmed prompt', () => {
    const r = parseDirective('  指令:领域;动作  ');
    expect(r.raw).toBe('指令:领域;动作');
  });
});

describe('parseDirective (AI: prefix)', () => {
  it('parses AI: with half-width colon', () => {
    const r = parseDirective('AI:weather;query,tomorrow,weihai');
    expect(r.domain).toBe('weather');
    expect(r.action).toBe('query');
    expect(r.params).toEqual(['tomorrow', 'weihai']);
    expect(r.directiveKey).toBe('AI:weather;query');
  });

  it('parses AI：with full-width colon', () => {
    const r = parseDirective('AI：weather;query');
    expect(r.domain).toBe('weather');
    expect(r.action).toBe('query');
    expect(r.directiveKey).toBe('AI:weather;query');
  });

  it('parses AI: with Chinese domain and action', () => {
    const r = parseDirective('AI:基础应用;天气查询,明天');
    expect(r.domain).toBe('基础应用');
    expect(r.action).toBe('天气查询');
    expect(r.directiveKey).toBe('AI:基础应用;天气查询');
  });

  it('throws on invalid AI prefix format', () => {
    expect(() => parseDirective('AI;weather;query')).toThrow(DirectiveParseError);
  });
});

describe('normalizeDirectiveKey', () => {
  it('strips "指令:" prefix', () => {
    expect(normalizeDirectiveKey('指令:基础应用;天气查询')).toBe('基础应用;天气查询');
  });

  it('strips AI: prefix', () => {
    expect(normalizeDirectiveKey('AI:weather;query')).toBe('weather;query');
  });

  it('strips "指令：" full-width prefix', () => {
    expect(normalizeDirectiveKey('指令：基础应用;天气查询')).toBe('基础应用;天气查询');
  });

  it('strips AI：full-width prefix', () => {
    expect(normalizeDirectiveKey('AI：weather;query')).toBe('weather;query');
  });

  it('returns key as-is when no prefix', () => {
    expect(normalizeDirectiveKey('基础应用;天气查询')).toBe('基础应用;天气查询');
  });
});
