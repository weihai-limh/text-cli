import { describe, it, expect, beforeEach } from 'vitest';
import {
  registerHandler,
  dispatch,
  getRegisteredDirectives,
  getRegistrySize,
  clearRegistry,
} from '../src/registry.js';

describe('registry', () => {
  beforeEach(() => {
    clearRegistry();
  });

  it('registers and dispatches a handler', () => {
    registerHandler('测试', '回显', (params) => `echo: ${params.join(',')}`);
    const result = dispatch('测试', '回显', ['a', 'b']);
    expect(result).toBe('echo: a,b');
  });

  it('returns error message for unregistered directive', () => {
    const result = dispatch('不存在', '动作', []);
    expect(result).toContain('未找到匹配的指令');
  });

  it('tracks registered directives', () => {
    registerHandler('A', 'a1', () => '');
    registerHandler('A', 'a2', () => '');
    registerHandler('B', 'b1', () => '');

    const dirs = getRegisteredDirectives();
    expect(dirs['A']).toEqual(['a1', 'a2']);
    expect(dirs['B']).toEqual(['b1']);
  });

  it('returns correct registry size', () => {
    registerHandler('X', 'x1', () => '');
    registerHandler('X', 'x2', () => '');
    expect(getRegistrySize()).toBe(2);
  });

  it('clearRegistry removes all handlers', () => {
    registerHandler('X', 'x1', () => '');
    clearRegistry();
    expect(getRegistrySize()).toBe(0);
    expect(dispatch('X', 'x1', [])).toContain('未找到匹配的指令');
  });
});
