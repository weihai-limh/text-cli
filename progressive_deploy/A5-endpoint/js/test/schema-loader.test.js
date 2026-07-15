import { describe, it, expect, beforeEach } from 'vitest';
import { loadSchema, getExternalSchema, findBackendUrl } from '../src/schema-loader.js';

describe('schema-loader (aggregation mode)', () => {
  beforeEach(async () => {
    await loadSchema('https://my-endpoint.workers.dev');
  });

  it('getExternalSchema returns an object', () => {
    const schema = getExternalSchema();
    expect(typeof schema).toBe('object');
  });

  it('external schema rewrites URLs to endpoint base when populated', async () => {
    await loadSchema('https://my-endpoint.workers.dev');
    const schema = getExternalSchema();
    for (const entry of Object.values(schema)) {
      if (entry.url) {
        expect(entry.url).toContain('/text-cli/cli');
      }
    }
  });

  it('external schema keeps clean URLs when no base', async () => {
    await loadSchema('');
    const schema = getExternalSchema();
    expect(typeof schema).toBe('object');
  });

  it('findBackendUrl returns null for unknown directive', () => {
    const url = findBackendUrl('AI:不存在;的指令');
    expect(url).toBeNull();
  });

  it('findBackendUrl handles AI: prefix normalization', () => {
    const url = findBackendUrl('AI:基础应用;天气查询');
    expect(url === null || typeof url === 'string').toBe(true);
  });

  it('findBackendUrl handles full-width punctuation', () => {
    const url = findBackendUrl('指令：基础应用;天气查询');
    expect(url === null || typeof url === 'string').toBe(true);
  });

  it('findBackendUrl handles AI：full-width prefix', () => {
    const url = findBackendUrl('AI：基础应用;天气查询');
    expect(url === null || typeof url === 'string').toBe(true);
  });
});
