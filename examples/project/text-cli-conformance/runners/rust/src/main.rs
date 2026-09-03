//! Rust core parser runner for the conformance drift mirror.
//!
//! Contract: read prompts line by line from stdin (blank line = empty prompt),
//! write one JSON line per prompt to stdout:
//!   {"domain":..,"action":..,"params":[..]}  on success
//!   {"error":"INVALID_PARAMS"}               on parse error
//! Stop at EOF.
//!
//! Build from conformance/ (or let run_drift.py build it):
//!   cargo build --manifest-path runners/rust/Cargo.toml

use std::io::{self, BufRead, Write};

use serde_json::json;
use text_cli_core_rust::parse;

fn main() {
    let stdin = io::stdin();
    let stdout = io::stdout();
    let mut out = stdout.lock();
    for line in stdin.lock().lines() {
        let line = match line {
            Ok(l) => l,
            Err(_) => break,
        };
        let prompt = line.trim_end_matches('\r');
        let result = match parse(prompt) {
            Ok(d) => json!({
                "domain": d.domain,
                "action": d.action,
                "params": d.params,
            }),
            Err(_) => json!({ "error": "INVALID_PARAMS" }),
        };
        let _ = writeln!(out, "{result}");
        let _ = out.flush();
    }
}
