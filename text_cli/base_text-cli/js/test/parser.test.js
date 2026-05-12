import { describe, it, expect } from 'vitest';
import { parseDirective, DirectiveParseError } from '../src/parser.js';

describe('parseDirective', () => {
  it('parses basic directive with params', () => {
    const result = parseDirective('指令:示例领域;回显,hello');
    expect(result.domain).toBe('示例领域');
    expect(result.action).toBe('回显');
    expect(result.params).toEqual(['hello']);
    expect(result.directiveKey).toBe('指令:示例领域;回显');
  });

  it('parses directive with multiple params', () => {
    const result = parseDirective('指令:天气;查询,明天,威海');
    expect(result.params).toEqual(['明天', '威海']);
  });

  it('parses directive without params', () => {
    const result = parseDirective('指令:示例领域;列表');
    expect(result.params).toEqual([]);
  });

  it('accepts full-width colon', () => {
    const result = parseDirective('指令：示例领域;回显,hi');
    expect(result.domain).toBe('示例领域');
  });

  it('trims whitespace', () => {
    const result = parseDirective('  指令: 领域 ; 动作 , a , b  ');
    expect(result.domain).toBe('领域');
    expect(result.action).toBe('动作');
    expect(result.params).toEqual(['a', 'b']);
  });

  it('throws on empty prompt', () => {
    expect(() => parseDirective('')).toThrow(DirectiveParseError);
    expect(() => parseDirective(null)).toThrow(DirectiveParseError);
    expect(() => parseDirective('   ')).toThrow(DirectiveParseError);
  });

  it('throws on invalid format', () => {
    expect(() => parseDirective('hello world')).toThrow(DirectiveParseError);
  });

  it('rejects empty domain (regex mismatch)', () => {
    expect(() => parseDirective('指令:;动作')).toThrow(DirectiveParseError);
  });

  it('rejects empty action (regex mismatch)', () => {
    expect(() => parseDirective('指令:领域;')).toThrow(DirectiveParseError);
  });

  it('throws on prompt exceeding max length', () => {
    const longPrompt = '指令:' + 'a'.repeat(520) + ';动作';
    expect(() => parseDirective(longPrompt)).toThrow('exceeds max length');
  });

  it('throws on too many params', () => {
    const params = Array(25).fill('p').join(',');
    expect(() => parseDirective(`指令:领域;动作,${params}`)).toThrow('too many parameters');
  });
});
