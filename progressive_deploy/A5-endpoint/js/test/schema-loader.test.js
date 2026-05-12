import { describe, it, expect, beforeEach } from 'vitest';
import { loadSchema, getInternalSchema, getExternalSchema, findBackendUrl } from '../src/schema-loader.js';

describe('schema-loader (static mode)', () => {
  beforeEach(() => {
    loadSchema('');
  });

  it('loads internal schema from static file', () => {
    const schema = getInternalSchema();
    expect(Object.keys(schema).length).toBeGreaterThan(0);
  });

  it('internal schema contains original backend URLs', () => {
    const schema = getInternalSchema();
    const first = Object.values(schema)[0];
    expect(first.url).toContain('example.com');
  });

  it('external schema rewrites URLs to endpoint base', () => {
    loadSchema('https://my-endpoint.workers.dev');
    const schema = getExternalSchema();
    const first = Object.values(schema)[0];
    expect(first.url).toBe('https://my-endpoint.workers.dev/cli/text_cli');
  });

  it('external schema keeps original URLs when no base', () => {
    loadSchema('');
    const schema = getExternalSchema();
    const first = Object.values(schema)[0];
    expect(first.url).toContain('example.com');
  });

  it('findBackendUrl returns url for known directive', () => {
    const url = findBackendUrl('指令:基础应用;天气查询');
    expect(url).toContain('example.com');
  });

  it('findBackendUrl returns null for unknown directive', () => {
    const url = findBackendUrl('指令:不存在;的指令');
    expect(url).toBeNull();
  });

  it('findBackendUrl matches AI: prefix against "指令:" schema', () => {
    const url = findBackendUrl('AI:基础应用;天气查询');
    expect(url).toContain('example.com');
  });

  it('findBackendUrl matches "指令：" full-width prefix', () => {
    const url = findBackendUrl('指令：基础应用;天气查询');
    expect(url).toContain('example.com');
  });

  it('findBackendUrl matches AI：full-width prefix', () => {
    const url = findBackendUrl('AI：基础应用;天气查询');
    expect(url).toContain('example.com');
  });
});
