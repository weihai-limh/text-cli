#!/usr/bin/env node
// JavaScript reference parser runner (textcli-core).
//
// Contract: read prompts line by line from stdin (blank line = empty prompt),
// write one JSON line per prompt to stdout:
//   {"domain":..,"action":..,"params":[..]}  on success
//   {"error":"INVALID_PARAMS"}               on parse error
// Stop at EOF.
//
// Usage: run.js <path-to-parser.js>  (e.g. .../npm/textcli-core/parser.js)
"use strict";

const readline = require("readline");

if (process.argv.length < 3) {
  process.stderr.write("usage: run.js <path-to-parser.js>\n");
  process.exit(2);
}

const parserPath = process.argv[2];
const { parse } = require(parserPath);

const rl = readline.createInterface({ input: process.stdin });
rl.on("line", (line) => {
  const prompt = line.replace(/\r$/, "");
  const r = parse(prompt);
  let out;
  if (r.error) {
    out = { error: "INVALID_PARAMS" };
  } else {
    out = { domain: r.domain, action: r.action, params: r.params };
  }
  process.stdout.write(JSON.stringify(out) + "\n");
});
