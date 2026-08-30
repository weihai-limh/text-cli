// textcli-core — JS instruction package one-shot executor
// Zero external dependencies. npm install textcli-core to use.
//
// Usage:
//   const { loadPackageFromPath, execute, parse, health, discover } = require('textcli-core');
//   loadPackageFromPath('./my-js-package/');
//   const result = execute('AI:my-domain;my-action,param1');
//   const h = health();
//   const dirs = discover();
//
// This is the thin wrapper over the core modules:
//   parser.js  envelope.js  alias.js  registry.js  loader.js

"use strict";

const { parse } = require("./parser.js");
const { ok, err } = require("./envelope.js");
const { dispatch } = require("./registry.js");
const { loadPackageFromPath } = require("./loader.node.js");
const { getLoaderState } = require("./loader.node.js");

const VERSION = "0.1.1";
const SPEC_VERSION = "1.3.2";

/**
 * Parse + dispatch + envelope in one call.
 * Returns a protocol envelope (SPEC §1.2.2).
 *
 * @param {string} prompt - e.g. "AI:weather;query,Beijing"
 * @returns {{rst_types:string, rst_data:object, rst_err:string}}
 */
async function execute(prompt) {
  // 1. parse
  const parsed = parse(prompt);
  if (parsed.error) {
    return err(parsed.error, parsed.reason);
  }

  // 2. dispatch
  let result;
  try {
    result = await dispatch(parsed.domain, parsed.action, parsed.params);
  } catch (e) {
    return err("ERR_EXECUTION", e.message);
  }

  if (result === null || result === undefined) {
    return err("ERR_NOT_FOUND", `no matching directive: ${parsed.domain};${parsed.action}`);
  }

  // 3. envelope
  if (typeof result === "string") {
    return ok({ status: "ok", result });
  }
  return ok(result);
}

/**
 * Return loader version and supported protocol version.
 * Unified with pypi textcli-loader health() and standard runtime GET /text-cli/health.
 *
 * @returns {{status:string, body:string, version:string, spec_version:string, runtime:string}}
 */
function health() {
  return {
    status: "ok",
    body: "textcli-core",
    version: VERSION,
    spec_version: SPEC_VERSION,
    runtime: "node",
  };
}

/**
 * Return all registered directives from loaded packages. SPEC §1.2.7.
 *
 * @param {string} [filter] - optional filter (future use, currently no-op)
 * @returns {{directives: Array<{domain:string, action:string, ...}>}}
 */
function discover(filter) {
  const state = getLoaderState();
  const allDirectives = [];
  for (const pkgId of Object.keys(state._schemas || {})) {
    const schema = state._schemas[pkgId];
    const directivesRaw = schema.directives || [];
    const list = Array.isArray(directivesRaw) ? directivesRaw : Object.values(directivesRaw);
    for (const d of list) {
      const entry = { domain: d.domain || "", action: d.action || "" };
      for (const key of [
        "domain_zh", "action_zh",
        "usage", "usage_zh",
        "description", "description_zh",
        "params", "outputs", "estimated_time",
        "source", "verified", "stale_after", "doc_status",
      ]) {
        if (d[key] !== undefined) entry[key] = d[key];
      }
      entry.package = pkgId;
      allDirectives.push(entry);
    }
  }
  return { directives: allDirectives };
}

module.exports = {
  loadPackageFromPath,
  execute,
  parse,
  health,
  discover,
  ok,
  err,
};
