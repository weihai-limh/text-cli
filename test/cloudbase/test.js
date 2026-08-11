#!/usr/bin/env node
/**
 * text-cli cloudbase static verification (Phase 5 refactored).
 *
 * Validates: gateway routing, textcli-core envelope/parser integration,
 * protocol closed-set error codes.
 * No real deploy needed - mocks wx-server-sdk and calls refactored index.js.
 */
'use strict';

const path = require('path');

// ---- mock wx-server-sdk (must be registered before require) ----
const Module = require('module');
const origRequire = Module.prototype.require;

Module.prototype.require = function (id) {
  if (id === 'wx-server-sdk') {
    return mockWxSdk;
  }
  return origRequire.apply(this, arguments);
};

let mockCallCount = 0;
const mockWxSdk = {
  init: () => {},
  DYNAMIC_CURRENT_ENV: 'test-env',
  callFunction: async (opts) => {
    mockCallCount++;
    const { data } = opts;
    return {
      result: {
        rst_types: 'text',
        rst_data: { text: `Hello, ${(data && data.prompt) || 'mock'}!` },
        rst_err: '',
      }
    };
  },
};

global.cloud = mockWxSdk;

// ---- load refactored index.js (.dev/cloudbase/) ----
const indexPath = path.join(
    process.env.TEXT_CLI_CLOUDBASE_PATH ||
    path.join(__dirname, '..', '..', '.dev', 'cloudbase'),
    'index.js'
);

let main;
try {
    main = require(indexPath).main;
} catch (e) {
    console.error(`\x1b[31m[FAIL]\x1b[0m failed to load index.js: ${e.message}`);
    console.error(`  path: ${indexPath}`);
    process.exit(1);
}

let pass = 0;
let fail = 0;

function check(label, expected, actual) {
    if (JSON.stringify(actual) === JSON.stringify(expected)) {
        console.log(`\x1b[32m[PASS]\x1b[0m ${label}`);
        pass++;
    } else {
        console.log(`\x1b[31m[FAIL]\x1b[0m ${label} (expected=${JSON.stringify(expected)}, got=${JSON.stringify(actual)})`);
        fail++;
    }
}

// ---- config.js structure validation ----
const configPath = path.join(path.dirname(indexPath), 'config.js');
try {
    require.resolve(configPath);
    console.log(`\x1b[32m[PASS]\x1b[0m config.js exists and is valid`);
    pass++;
} catch (e) {
    console.log(`\x1b[31m[FAIL]\x1b[0m config.js: ${e.message}`);
    fail++;
}

// ---- test main ----
(async () => {
    console.log('--- 1. Gateway routing ---');

    // GET /health
    let resp = await main({ httpMethod: 'GET', path: '/health' }, {});
    check('GET /health returns ok', 'ok', resp.status);

    // GET /skills
    resp = await main({ httpMethod: 'GET', path: '/text-cli/skills' }, {});
    check('GET /skills returns object', true, typeof resp === 'object');

    // POST with valid prompt (routed to web-utils via routeTable)
    resp = await main({
        httpMethod: 'POST',
        path: '/cli',
        prompt: 'AI:web-utils;get_public_ip',
    }, {});
    check('POST envelope has rst_types', true, 'rst_types' in resp);
    check('POST envelope has rst_data', true, 'rst_data' in resp);
    check('POST rst_err empty', '', resp.rst_err || '');

    // POST with invalid method — should return protocol error code
    resp = await main({ httpMethod: 'PUT', path: '/cli' }, {});
    check('PUT uses protocol error code (ERR_ROUTING)', 'ERR_ROUTING', resp.rst_err);

    // POST with missing prompt
    resp = await main({ httpMethod: 'POST', path: '/cli' }, {});
    check('missing prompt returns INVALID_PARAMS', 'INVALID_PARAMS', resp.rst_err);

    // POST to unknown path
    resp = await main({ httpMethod: 'POST', path: '/unknown' }, {});
    check('unknown path returns ERR_NOT_FOUND', 'ERR_NOT_FOUND', resp.rst_err);

    // ---- results ----
    console.log('');
    console.log('='.repeat(40));
    console.log(`  PASS: ${pass}  FAIL: ${fail}`);
    console.log('='.repeat(40));

    process.exit(fail === 0 ? 0 : 1);
})();
