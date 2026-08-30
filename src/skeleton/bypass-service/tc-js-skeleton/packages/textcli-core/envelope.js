// textcli-core envelope — Protocol response envelope (SPEC §1.2.2)
// Zero-dependency, isomorphic with Python textcli-loader envelope.py.
//
// ok(data)    → {rst_types, rst_data, rst_err: ""}
// err(code)   → {rst_types, rst_data, rst_err: code}
//
// Protocol closed-set error codes (SPEC §1.2.8):
//   ERR_NOT_FOUND  ERR_EXECUTION  ERR_ROUTING
//   INVALID_PARAMS ACCESS_DENIED  SERVICE_DENIED

"use strict";

const _ERROR_CODES = new Set([
  "ERR_NOT_FOUND", "ERR_EXECUTION", "ERR_ROUTING",
  "INVALID_PARAMS", "ACCESS_DENIED", "SERVICE_DENIED",
]);

/**
 * Wrap a successful result in text-cli envelope format.
 *
 * If data contains pray_rst_types, it is promoted to rst_types
 * and stripped from rst_data (SPEC §1.2.2).
 *
 * @param {object} data - handler's return dict
 * @param {string} [rstType="text"] - "text" | "picture" | "video" | "audio" | "file"
 * @returns {{rst_types:string, rst_data:object, rst_err:string}}
 */
function ok(data, rstType) {
  rstType = rstType || "text";
  // pray_rst_types promotion — strip from data, promote to rst_types
  let pray = null;
  if (data && typeof data === "object" && !Array.isArray(data)) {
    if ("pray_rst_types" in data) {
      pray = data.pray_rst_types;
      delete data.pray_rst_types;
    }
  }
  if (pray && rstType === "text") {
    rstType = pray;
  }
  return { rst_types: rstType, rst_data: data, rst_err: "" };
}

/**
 * Wrap an error in text-cli envelope format.
 *
 * code must be one of the protocol's closed-set error codes.
 * Defaults to ERR_EXECUTION.
 *
 * @param {string} code - protocol error code
 * @param {string} [reason] - human-readable reason
 * @returns {{rst_types:string, rst_data:object, rst_err:string}}
 */
function err(code, reason) {
  if (!_ERROR_CODES.has(code)) {
    console.warn(`[textcli-core] unknown error code "${code}", falling back to ERR_EXECUTION`);
    code = "ERR_EXECUTION";
  }
  return {
    rst_types: "text",
    rst_data: { status: "error", reason: reason || code },
    rst_err: code,
  };
}

module.exports = { ok, err };
