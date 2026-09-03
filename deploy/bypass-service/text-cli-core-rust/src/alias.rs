//! Alias map: non-canonical (e.g. Chinese) names to canonical ASCII keys.
//!
//! SPEC S1.1: canonical names are ASCII and are the only routing keys;
//! aliases are access entries only. Normalization (case folding, Unicode
//! NFC/NFKC) is the host/binding layer's job -- the core matches bytes
//! exactly. This module stores alias -> canon pairs and resolves by exact
//! byte comparison.

use std::collections::HashMap;

/// Canonical key `"domain\0action"` (byte-joined with a NUL).
pub type CanonKey = String;

/// Alias map from alias key to canonical key.
#[derive(Debug, Default, Clone)]
pub struct AliasMap {
    map: HashMap<String, String>,
}

impl AliasMap {
    /// Create an empty alias map.
    pub fn new() -> Self {
        Self::default()
    }

    /// Register an alias `(alias_domain, alias_action)` -> canon
    /// `(canon_domain, canon_action)`.
    ///
    /// Hosts should normalize (fold case / NFC) before calling; the core
    /// stores bytes verbatim.
    pub fn add(
        &mut self,
        alias_domain: &str,
        alias_action: &str,
        canon_domain: &str,
        canon_action: &str,
    ) {
        let alias_key = join_key(alias_domain, alias_action);
        let canon_key = join_key(canon_domain, canon_action);
        self.map.insert(alias_key, canon_key);
    }

    /// Resolve an alias to its canonical key; returns the input key if no
    /// alias matches.
    pub fn resolve(&self, domain: &str, action: &str) -> String {
        let key = join_key(domain, action);
        self.map.get(&key).cloned().unwrap_or(key)
    }
}

/// Join domain/action into a single canonical key string.
pub fn join_key(domain: &str, action: &str) -> String {
    let mut k = String::with_capacity(domain.len() + action.len() + 1);
    k.push_str(domain);
    k.push('\0');
    k.push_str(action);
    k
}
