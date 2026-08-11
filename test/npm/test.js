// textcli-core test chain — Protocol compliance and package execution
// Analogous to test/pypi/test.py (pure function calls, no HTTP).
//
// Requires: textcli-core available at ../../.dev/textcli-core/

"use strict";

const path = require("path");
const fs = require("fs");
const os = require("os");

const { loadPackageFromPath, execute, parse, ok, err, health, discover } = require(
  path.join(__dirname, "..", "..", "src", "skeleton", "bypass-service", "npm", "textcli-core", "index.js")
);
const { getRegistered } = require(
  path.join(__dirname, "..", "..", "src", "skeleton", "bypass-service", "npm", "textcli-core", "registry.js")
);

let PASS = 0;
let FAIL = 0;

function check(label, condition) {
  if (condition) { PASS++; }
  else { console.log(`  FAIL: ${label}`); FAIL++; }
}

function checkContains(label, haystack, needle) {
  if (typeof haystack === "string" && haystack.includes(needle)) { PASS++; }
  else if (typeof haystack === "object") {
    const s = JSON.stringify(haystack);
    if (s.includes(needle)) { PASS++; }
    else { console.log(`  FAIL: ${label} (expected "${needle}" in ${s.substring(0, 200)})`); FAIL++; }
  }
  else { console.log(`  FAIL: ${label}`); FAIL++; }
}

async function main() {
  // ─── Setup: create temp declarative-style package ───
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "textcli-test-"));

  const schema = {
    id: "date-calc",
    type: "native",
    runtime: "js",
    version: "0.1.0",
    trust: "community",
    category: "utils",
    directives: [{
      domain: "date-calc",
      domain_zh: "\u65e5\u671f\u8ba1\u7b97",
      action: "add-days",
      action_zh: "\u52a0\u5929",
      usage: "date-calc;add-days,<date>,<days>",
      params: ["date", "days"],
      outputs: ["result"],
    }],
  };
  fs.writeFileSync(path.join(tmpDir, "schema.json"), JSON.stringify(schema));

  fs.writeFileSync(path.join(tmpDir, "handler.js"), `
    module.exports = {
      domainAlias: '\u65e5\u671f\u8ba1\u7b97',
      directives: {
        'add-days': {
          handler: (params) => {
            const d = new Date(params[0]);
            d.setDate(d.getDate() + Number(params[1]));
            return { status: 'ok', result: d.toISOString().split('T')[0] };
          },
          actionAliases: ['\u52a0\u5929'],
        },
      },
    };
  `);

  // ─── 1. loadPackageFromPath ───
  console.log("1. loadPackageFromPath (declarative)");
  const meta = loadPackageFromPath(tmpDir);
  check("1a id", meta.id === "date-calc");
  check("1b registered", meta.registered === 1);

  // ─── 2. execute (English) ───
  console.log("2. execute (en)");
  let result = await execute("AI:date-calc;add-days,2025-01-01,10");
  check("2a rst_err empty", result.rst_err === "");
  check("2b result", result.rst_data.result === "2025-01-11");

  // ─── 3. execute (Chinese alias) ───
  console.log("3. execute (zh)");
  result = await execute("AI:\u65e5\u671f\u8ba1\u7b97;\u52a0\u5929,2025-01-01,5");
  check("3a rst_err empty", result.rst_err === "");
  check("3b result", result.rst_data.result === "2025-01-06");

  // ─── 4. execute (mix Chinese/English) ───
  console.log("4. execute (mix)");
  result = await execute("AI:date-calc;\u52a0\u5929,2025-01-01,3");
  check("4a rst_err empty", result.rst_err === "");
  check("4b result", result.rst_data.result === "2025-01-04");

  // ─── 5. getRegistered ───
  console.log("5. getRegistered");
  const reg = getRegistered();
  check("5a count >= 1", reg.length >= 1);

  // ─── 6. unknown directive ───
  console.log("6. unknown directive");
  result = await execute("AI:unknown;test");
  check("6a rst_err", result.rst_err === "ERR_NOT_FOUND");

  // ─── 7. parse only ───
  console.log("7. parse");
  const parsed = parse("AI:weather;query,Beijing,tomorrow");
  check("7a domain", parsed.domain === "weather");
  check("7b action", parsed.action === "query");
  check("7c params[0]", parsed.params[0] === "Beijing");

  // ─── 8. envelope ───
  console.log("8. envelope");
  const envOk = ok({ status: "ok", result: 14 });
  check("8a rst_types", envOk.rst_types === "text");
  check("8b rst_err", envOk.rst_err === "");
  const envErr = err("ERR_NOT_FOUND", "test");
  check("8c err code", envErr.rst_err === "ERR_NOT_FOUND");

  // ─── 9. health ───
  console.log("9. health");
  const h = health();
  check("9a status", h.status === "ok");
  check("9b body", h.body === "textcli-core");
  check("9c version", h.version === "0.1.0");
  check("9d spec_version", h.spec_version === "1.3.2");
  check("9e runtime", h.runtime === "node");

  // ─── 10. discover ───
  console.log("10. discover");
  const dirs = discover();
  check("10a directives array", Array.isArray(dirs.directives));
  const found = dirs.directives.filter(d => d.package === "date-calc");
  check("10b found date-calc", found.length >= 1);
  check("10c domain", found[0].domain === "date-calc");
  check("10d action", found[0].action === "add-days");
  check("10e domain_zh", found[0].domain_zh === "日期计算");
  check("10f action_zh", found[0].action_zh === "加天");

  // ─── 11. cleanup ───
  console.log("11. cleanup");
  fs.rmSync(tmpDir, { recursive: true, force: true });
  check("11a cleaned", !fs.existsSync(tmpDir));

  // ─── 12. loadPackageFromPath (legacy instructions/ compat) ───
  console.log("12. legacy instructions/ format");
  const legacyDir = fs.mkdtempSync(path.join(os.tmpdir(), "textcli-legacy-"));
  const legacySchema = {
    id: "legacy-pkg",
    type: "native",
    runtime: "js",
    version: "0.1.0",
    trust: "community",
    directives: [{
      domain: "legacy",
      action: "greet",
      params: ["name"],
    }],
  };
  fs.writeFileSync(path.join(legacyDir, "schema.json"), JSON.stringify(legacySchema));
  fs.mkdirSync(path.join(legacyDir, "instructions"));
  fs.writeFileSync(path.join(legacyDir, "instructions", "greet.js"),
    "module.exports = (params) => 'Hello ' + params[0];"
  );
  const legacyMeta = loadPackageFromPath(legacyDir);
  check("10a id", legacyMeta.id === "legacy-pkg");
  check("10b registered", legacyMeta.registered === 1);
  const legacyResult = await execute("AI:legacy;greet,World");
  check("12c result", legacyResult.rst_data.result === "Hello World");
  fs.rmSync(legacyDir, { recursive: true, force: true });
  check("12d cleaned", !fs.existsSync(legacyDir));

  console.log(`\n=== textcli-core: ${PASS} passed, ${FAIL} failed ===`);
  process.exit(FAIL > 0 ? 1 : 0);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
