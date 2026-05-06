// admin.js 指令注册 API 测试
import { describe, it, expect, vi } from 'vitest';
import {
  handleDirectivesList,
  handleDirectivesRegister,
  handleDirectivesDiscover,
  handleDirectivesDelete,
} from '../src/admin.js';

// Mock D1
function mockDB(results = [], firstResult = null) {
  const db = {
    prepare() {
      const stmt = {
        bind(...args) {
          this._args = args;
          return this;
        },
        first() { return Promise.resolve(firstResult); },
        all() { return Promise.resolve({ results: Array.isArray(results) ? results : results }); },
        run() { return Promise.resolve({ success: true }); },
      };
      return stmt;
    },
  };
  return db;
}

const env = {
  ADMIN_API_KEY: 'test-admin-key',
  DB: mockDB([]),
};

function requestWithKey(body, path = '/api/directives') {
  return new Request(`https://test/${path}`, {
    method: 'POST',
    headers: {
      'X-Admin-Key': 'test-admin-key',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });
}

describe('指令注册 API', () => {
  it('GET /api/directives 返回空列表', async () => {
    const env = { ADMIN_API_KEY: 'test-admin-key', DB: mockDB([]) };
    const req = new Request('https://test/api/directives', {
      headers: { 'X-Admin-Key': 'test-admin-key' },
    });
    const resp = await handleDirectivesList(req, env);
    const data = await resp.json();
    expect(data.directives).toEqual([]);
  });

  it('POST /api/directives 注册新指令', async () => {
    const env = {
      ADMIN_API_KEY: 'test-admin-key',
      DB: mockDB([], null),
    };
    const req = new Request('https://test/api/directives', {
      method: 'POST',
      headers: {
        'X-Admin-Key': 'test-admin-key',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        domain: '智能空间',
        action: '记忆检索',
        endpoint: 'https://hero-fragments.instantiated.space/query',
        description: '检索AI协作者经验',
        params: ['意图描述', '关键词'],
      }),
    });
    const resp = await handleDirectivesRegister(req, env);
    const data = await resp.json();
    expect(data.status).toBe('registered');
    expect(data.directive_key).toBe('智能空间:记忆检索');
  });

  it('POST /api/directives 拒绝无效请求', async () => {
    const req = new Request('https://test/api/directives', {
      method: 'POST',
      headers: {
        'X-Admin-Key': 'test-admin-key',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ domain: '' }),
    });
    const resp = await handleDirectivesRegister(req, env);
    expect(resp.status).toBe(400);
  });

  it('POST /api/directives 未授权拒绝', async () => {
    const env = { ADMIN_API_KEY: 'test-admin-key' };
    const req = new Request('https://test/api/directives', {
      method: 'POST',
      headers: { 'X-Admin-Key': 'wrong-key' },
      body: JSON.stringify({ domain: 'x', action: 'y', endpoint: 'http://e' }),
    });
    const resp = await handleDirectivesRegister(req, env);
    expect(resp.status).toBe(401);
  });
});
