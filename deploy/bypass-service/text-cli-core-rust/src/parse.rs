//! Directive parser (SPEC S1.1).
//!
//! Semantics aligned with the Python textcli-loader parser.py and the C core:
//!  - "AI:" prefix only (leading whitespace allowed before it);
//!  - domain: up to the first `;`;
//!  - action: up to the first `,` or end of input;
//!  - params: comma-split at bracket depth 0, double-quote strings honored,
//!    backslash escapes the next char (backslash kept), empty segments dropped;
//!  - single quote is NOT a string quote (Python-aligned).
//!
//! All slices are zero-copy borrows of the input `&str`. Cutting only happens
//! at ASCII delimiters/whitespace, so every boundary is a UTF-8 char boundary.

use crate::error::TcErr;
use crate::{MAX_DEPTH, MAX_PARAMS, MAX_PROMPT};

/// Parsed directive: zero-copy slices into the original prompt.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Directive<'a> {
    /// Canonical (or as-written) domain.
    pub domain: &'a str,
    /// Action.
    pub action: &'a str,
    /// Positional params (trimmed, empty segments dropped).
    pub params: Vec<&'a str>,
    /// True if more than `MAX_PARAMS` segments were seen.
    pub truncated: bool,
}

/// Parse a directive prompt into its parts.
pub fn parse(prompt: &str) -> Result<Directive<'_>, TcErr> {
    if prompt.is_empty() || prompt.len() > MAX_PROMPT {
        return Err(TcErr::InvalidParams);
    }
    let b = prompt.as_bytes();

    // Leading whitespace before the "AI:" prefix.
    let mut i = 0usize;
    while i < b.len() && is_ws(b[i]) {
        i += 1;
    }
    // Prefix "AI:".
    if b.len() - i < 3 || &prompt[i..i + 3] != "AI:" {
        return Err(TcErr::InvalidParams);
    }
    i += 3;
    // Whitespace between prefix and domain.
    while i < b.len() && is_ws(b[i]) {
        i += 1;
    }

    // domain: up to first ';'.
    let dom_start = i;
    while i < b.len() && b[i] != b';' {
        i += 1;
    }
    if i >= b.len() {
        return Err(TcErr::InvalidParams); // no ';'
    }
    let dom_end = i;
    i += 1; // skip ';'

    // action: up to first ',' or end.
    let act_start = i;
    while i < b.len() && b[i] != b',' {
        i += 1;
    }
    let act_end = i;

    let domain = trim(&prompt[dom_start..dom_end]);
    if domain.is_empty() {
        return Err(TcErr::InvalidParams);
    }
    let action = trim(&prompt[act_start..act_end]);
    if action.is_empty() {
        return Err(TcErr::InvalidParams);
    }

    let mut params: Vec<&str> = Vec::new();
    let mut truncated = false;

    if i < b.len() {
        // There is a ',' -> params region is [i+1, tail trimmed).
        i += 1; // skip ','
        let tail_end = {
            let mut e = b.len();
            while e > i && is_ws(b[e - 1]) {
                e -= 1;
            }
            e
        };

        let mut depth: i32 = 0;
        let mut in_str = false;
        let mut esc = false;
        let mut seg_start = i;

        let mut j = i;
        while j <= tail_end {
            let at_end = j == tail_end;
            let mut flush = at_end;
            if !at_end {
                let c = b[j];
                if esc {
                    esc = false;
                } else if c == b'\\' {
                    esc = true;
                } else if c == b'"' && depth == 0 {
                    in_str = !in_str;
                } else if in_str {
                    // inside string, keep as-is
                } else if c == b'{' || c == b'[' {
                    depth += 1;
                    if depth > MAX_DEPTH as i32 {
                        return Err(TcErr::InvalidParams);
                    }
                } else if c == b'}' || c == b']' {
                    if depth > 0 {
                        depth -= 1;
                    }
                } else if c == b',' && depth == 0 {
                    flush = true;
                }
            }

            if flush {
                let seg = trim(&prompt[seg_start..if at_end { tail_end } else { j }]);
                if !seg.is_empty() {
                    if params.len() < MAX_PARAMS {
                        params.push(seg);
                    } else {
                        truncated = true;
                    }
                }
                if !at_end {
                    seg_start = j + 1;
                }
            }
            j += 1;
        }
    }

    Ok(Directive {
        domain,
        action,
        params,
        truncated,
    })
}

/// Trim ASCII whitespace from both ends.
fn trim(s: &str) -> &str {
    let b = s.as_bytes();
    let mut start = 0usize;
    let mut end = b.len();
    while start < end && is_ws(b[start]) {
        start += 1;
    }
    while end > start && is_ws(b[end - 1]) {
        end -= 1;
    }
    &s[start..end]
}

#[inline]
fn is_ws(c: u8) -> bool {
    c == b' ' || c == b'\t' || c == b'\r' || c == b'\n'
}
