// textcli-core loader — Core package loading interface (no IO)
// Zero-dependency. Platform adapters (loader.node.js, loader.workers.js)
// are responsible for obtaining schemaJSON and handlerMap, then calling
// this core interface to register directives into the registry.
//
// loadPackage(schemaJSON, handlerMap) — register directives from schema + handlers

"use strict";

const { register } = require("./registry.js");

/**
 * Load a package from pre-parsed schema and handler map.
 *
 * This is the core loading interface — it does NOT perform file IO.
 * Platform adapters are responsible for reading schema.json and
 * loading handler modules, then passing them here.
 *
 * Supports two handler registration modes:
 *   1. Declarative (recommended): handlerMap = require('handler.js'),
 *      where handler.js exports {domain, domainAlias, directives: {action: {handler, actionAliases}}}
 *   2. Functional (fallback): handlerMap = {action: handlerFunc}
 *
 * @param {object} schemaJSON - parsed schema.json
 * @param {object} handlerMap - action -> handler function mapping
 * @returns {{id:string, directives:Array, registered:number}}
 */
function loadPackage(schemaJSON, handlerMap) {
  if (!schemaJSON || !schemaJSON.id) {
    throw new Error("invalid schema: missing id");
  }

  const packageId = schemaJSON.id;
  const directives = schemaJSON.directives || [];
  let registered = 0;

  for (const d of directives) {
    const domain = d.domain;
    const action = d.action;
    let handler = null;
    let opts = {};

    // detect handler registration mode
    if (handlerMap && handlerMap.directives && handlerMap.directives[action]) {
      // declarative mode — handler.js exports {directives: {action: {handler, actionAliases}}}
      const decl = handlerMap.directives[action];
      handler = decl.handler;
      opts = {
        domainAlias: handlerMap.domainAlias || d.domain_zh || undefined,
        actionAliases: decl.actionAliases
          ? decl.actionAliases.reduce((acc, a) => { acc[action] = a; return acc; }, {})
          : (d.action_zh ? { [action]: d.action_zh } : undefined),
      };
    } else if (handlerMap && typeof handlerMap[action] === "function") {
      // functional mode — handlerMap = {action: handlerFunc}
      handler = handlerMap[action];
      opts = {
        domainAlias: d.domain_zh,
        actionAliases: d.action_zh ? { [action]: d.action_zh } : undefined,
      };
    }

    if (handler) {
      register(domain, action, handler, opts);
      registered++;
    }
  }

  return { id: packageId, directives, registered };
}

module.exports = { loadPackage };
