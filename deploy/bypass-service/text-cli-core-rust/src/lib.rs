//! text-cli-core-rust -- text-cli protocol core (Rust thin core).
//!
//! Direct projection of SPEC clauses S1.1 / S1.2.2 / S1.2.8.
//! Red lines: no IO / no network / no dynamic loading / no boundary
//! validation / not a full 9-mechanism runtime.
//! Prefix: "AI:" only (legacy "directive:" NOT supported).
//!
//! Design decisions (see docs/LIMITS_zh.md; mirror conformance observe items):
//!  - double quote toggles a string; single quote does NOT (Python-aligned);
//!  - backslash escapes the next char, backslash itself is KEPT (Python-aligned);
//!  - empty params after trim are dropped;
//!  - `pray_rst_types` promotes (non-"text") and is stripped (SPEC S1.2.2).
#![forbid(unsafe_code)]
#![deny(missing_docs)]

pub mod alias;
pub mod envelope;
pub mod error;
pub mod parse;
pub mod registry;

/// Max params before the tail is merged.
pub const MAX_PARAMS: usize = 16;
/// Max prompt length.
pub const MAX_PROMPT: usize = 2048;
/// Max brace nesting depth.
pub const MAX_DEPTH: usize = 32;

pub use alias::{join_key, AliasMap};
pub use envelope::{promote_pray, Envelope, RstType};
pub use error::{TcErr, ERR_CODES};
pub use parse::{parse, Directive};
pub use registry::{dispatch, register, Handler, Registry};
