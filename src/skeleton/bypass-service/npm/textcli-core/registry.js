// textcli-core registry — Directive registration and dispatch
// Zero-dependency, isomorphic with Python textcli-loader registry.py @directive logic.
//
// register(domain, action, handler, opts?) — register a handler with optional aliases
// dispatch(domain, action, params, context?) — dispatch to registered handler
// unregister(domain, action) — remove a registration
// getRegistered() — list all registered directives

"use strict";

const { addAlias, resolve } = require("./alias.js");

/** @type {Map<string, Map<string, {handler:Function, meta:object}>>} */
const _registry = new Map();

/**
 * Register a directive handler.
 *
 * @param {string} domain - canonical domain name
 * @param {string} action - canonical action name
 * @param {Function} handler - async or sync handler function (params, context?) => any
 * @param {object} [opts] - optional configuration
 * @param {string} [opts.domainAlias] - alias for the domain (e.g. "天气" for "weather")
 * @param {object} [opts.actionAliases] - alias map for actions (e.g. {"query": "查询"})
 */
function register(domain, action, handler, opts) {
  const d = domain.toLowerCase();
  const a = action.toLowerCase();

  if (!_registry.has(d)) _registry.set(d, new Map());

  // warn on overwrite — isomorphic with Python logger.warning
  if (_registry.get(d).has(a)) {
    console.warn(`[textcli-core] directive ${domain};${action} already registered, overwriting`);
  }

  _registry.get(d).set(a, { handler, meta: opts || {} });

  // auto-register aliases
  if (opts) {
    if (opts.domainAlias && opts.actionAliases) {
      for (const [canonicalA, aliasA] of Object.entries(opts.actionAliases)) {
        addAlias(opts.domainAlias, aliasA, domain, canonicalA);
      }
    } else if (opts.domainAlias) {
      // domain alias without specific action aliases — register domain-only
      addAlias(opts.domainAlias, action, domain, action);
    }
  }
}

/**
 * Dispatch to a registered handler.
 *
 * @param {string} domain - domain name (may be aliased)
 * @param {string} action - action name (may be aliased)
 * @param {string[]} params - parsed parameters
 * @param {object} [context] - optional context passed through to handler
 * @returns {any|null} handler return value, or null if not found
 */
async function dispatch(domain, action, params, context) {
  const d = domain.toLowerCase();
  const a = action.toLowerCase();

  // 1. exact match
  let entries = _registry.get(d);
  let entry = entries ? entries.get(a) : null;

  // 2. alias resolution
  if (!entry) {
    const resolved = resolve(domain, action);
    if (resolved) {
      entries = _registry.get(resolved.domain.toLowerCase());
      entry = entries ? entries.get(resolved.action.toLowerCase()) : null;
    }
  }

  if (!entry) return null;

  try {
    const result = entry.handler(params, context);
    // support both sync and async handlers
    if (result instanceof Promise) return await result;
    return result;
  } catch (e) {
    throw e; // rethrow — caller wraps in ERR_EXECUTION
  }
}

/**
 * Remove a directive from the registry.
 *
 * @param {string} domain - canonical domain name
 * @param {string} action - canonical action name
 */
function unregister(domain, action) {
  const d = domain.toLowerCase();
  const a = action.toLowerCase();
  const entries = _registry.get(d);
  if (entries) entries.delete(a);
}

/**
 * List all registered directives.
 *
 * @returns {Array<{domain:string, action:string, meta:object}>}
 */
function getRegistered() {
  const result = [];
  for (const [domain, actions] of _registry) {
    for (const [action, { meta }] of actions) {
      result.push({ domain, action, meta });
    }
  }
  return result;
}

module.exports = { register, dispatch, unregister, getRegistered };
