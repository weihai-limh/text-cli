// textcli-core parser — Protocol directive parser (SPEC §1.1)
// Zero-dependency, isomorphic with Python textcli-loader parser.py.
//
// Input:  "AI:domain;action,param1,param2"
// Output: {domain, action, params[]} or {error, reason}
//
// Supports:
//   - AI: and 指令: prefixes (equivalent)
//   - JSON objects/arrays in params (bracket-depth tracking)
//   - String quotes inside params (commas inside quotes not split)
//   - Escape sequences in string params
//   - Free-text trailing param (may contain commas)

"use strict";

const _MAX_LENGTH = 2048;
const _MAX_PARAMS = 50;
const _DIRECTIVE_PATTERN = /^\s*(?:AI|指令)[：:]([^;]+);([^,]+)(?:,(.+))?\s*$/;

// ─── Private ─────────────────────────────────────────

/**
 * Split params by comma, respecting JSON brackets and string quotes.
 * Isomorphic with Python textcli-loader _split_params().
 */
function _splitParams(raw) {
  const result = [];
  let buf = "";
  let depth = 0;        // { } and [ ] nesting
  let inString = false;
  let strCh = "";
  let escape = false;

  for (let i = 0; i < raw.length; i++) {
    const ch = raw[i];

    if (escape) {
      buf += ch;
      escape = false;
      continue;
    }

    if (ch === "\\") {
      escape = true;
      continue;
    }

    if ((ch === '"' || ch === "'") && depth === 0) {
      inString = !inString;
      strCh = inString ? ch : "";
      buf += ch;
      continue;
    }

    if (inString) {
      buf += ch;
      continue;
    }

    if (ch === "{" || ch === "[") {
      depth++;
      buf += ch;
      continue;
    }

    if (ch === "}" || ch === "]") {
      depth = Math.max(0, depth - 1);
      buf += ch;
      continue;
    }

    if (ch === "," && depth === 0) {
      const val = buf.trim();
      if (val.length > 0) result.push(val);
      buf = "";
      continue;
    }

    buf += ch;
  }

  const val = buf.trim();
  if (val.length > 0) result.push(val);
  return result;
}

// ─── Public ──────────────────────────────────────────

/**
 * Parse a text-cli directive string.
 *
 * @param {string} prompt - e.g. "AI:weather;query,Beijing"
 * @returns {{domain:string, action:string, params:string[]} | {error:string, reason:string}}
 */
function parse(prompt) {
  if (!prompt || typeof prompt !== "string" || !prompt.trim()) {
    return { error: "INVALID_PARAMS", reason: "prompt is required" };
  }

  prompt = prompt.trim();

  if (prompt.length > _MAX_LENGTH) {
    return { error: "INVALID_PARAMS", reason: `directive exceeds max length (${_MAX_LENGTH})` };
  }

  const match = prompt.match(_DIRECTIVE_PATTERN);
  if (!match) {
    return { error: "INVALID_PARAMS", reason: `invalid directive format: ${prompt}` };
  }

  const domain = match[1].trim();
  const action = match[2].trim();
  const rawParams = match[3] || "";

  const params = rawParams ? _splitParams(rawParams) : [];

  if (params.length > _MAX_PARAMS) {
    return { error: "INVALID_PARAMS", reason: `too many parameters (${params.length}), max ${_MAX_PARAMS}` };
  }

  if (!domain) {
    return { error: "INVALID_PARAMS", reason: "domain is empty" };
  }
  if (!action) {
    return { error: "INVALID_PARAMS", reason: "action is empty" };
  }

  return { domain, action, params };
}

module.exports = { parse };
