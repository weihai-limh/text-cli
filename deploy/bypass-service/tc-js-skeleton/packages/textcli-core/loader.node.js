// textcli-core loader.node — Node.js platform adapter
// Uses fs + require to load packages from disk, then delegates
// to the core loadPackage() for directive registration.

"use strict";

const fs = require("fs");
const path = require("path");
const { loadPackage } = require("./loader.js");

/**
 * Load an instruction package from a directory on disk.
 *
 * Expected directory structure:
 *   package-dir/
 *     schema.json          — package metadata + directive declarations
 *     handler.js           — (recommended) declarative exports: {directives: {action: {handler, actionAliases}}}
 *     instructions/        — (legacy fallback) <action>.js per directive
 *
 * Supports runtime: "js" (canonical) and runtime: "node" (legacy compat).
 *
 * @param {string} packageDir - absolute or relative path to package directory
 * @returns {{id:string, directives:Array, registered:number}}
 */
function loadPackageFromPath(packageDir) {
  const dir = path.resolve(packageDir);
  if (!fs.existsSync(dir)) {
    throw new Error(`package directory not found: ${dir}`);
  }

  // 1. read and parse schema.json
  const schemaPath = path.join(dir, "schema.json");
  if (!fs.existsSync(schemaPath)) {
    throw new Error(`schema.json not found in ${dir}`);
  }
  const schemaJSON = JSON.parse(fs.readFileSync(schemaPath, "utf-8"));

  // 2. validate runtime
  const runtime = schemaJSON.runtime || "";
  if (runtime !== "js" && runtime !== "node") {
    throw new Error(
      `unsupported runtime: "${runtime}" — expected "js" (or "node" for legacy compat)`
    );
  }

  // 3. load handler module
  const handlerPath = path.join(dir, "handler.js");
  let handlerMap = {};

    if (fs.existsSync(handlerPath)) {
    // clear require cache for hot-reload support
    try {
      const resolved = require.resolve(handlerPath);
      if (require.cache[resolved]) delete require.cache[resolved];
    } catch (_) { /* not yet cached, first load */ }
    const handlerModule = require(handlerPath);

    if (handlerModule.directives && typeof handlerModule.directives === "object") {
      // declarative mode — handler.js exports {domainAlias, directives: {action: {handler, actionAliases}}}
      handlerMap = handlerModule;
    }
  }

  // 4. legacy fallback: scan instructions/ subdirectory
  const instructionsDir = path.join(dir, "instructions");
  if (!handlerMap.directives && fs.existsSync(instructionsDir)) {
    handlerMap = {};
    const files = fs.readdirSync(instructionsDir);
    for (const file of files) {
      if (file.endsWith(".js")) {
        const action = file.replace(/\.js$/, "");
        const modPath = path.join(instructionsDir, file);
        try {
          const resolved = require.resolve(modPath);
          if (require.cache[resolved]) delete require.cache[resolved];
        } catch (_) { /* not yet cached */ }
        const mod = require(modPath);
        // each instruction/<action>.js should export handler or be the handler itself
        handlerMap[action] = typeof mod === "function" ? mod : (mod.handler || mod.main);
      }
    }
  }

  // 5. delegate to core loader
  const result = loadPackage(schemaJSON, handlerMap);

  // 6. cache schema for discover()
  if (!_schemas) { _schemas = {}; }
  _schemas[schemaJSON.id || path.basename(dir)] = schemaJSON;

  return result;
}

// Schema cache for discover() — populated by loadPackageFromPath
let _schemas = {};

function getLoaderState() {
  return { _schemas };
}

module.exports = { loadPackageFromPath, getLoaderState };
