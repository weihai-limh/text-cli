//! In-memory registry: directive handlers registered under canonical keys.
//!
//! Design: registry is a plain hash map keyed by canonical `"domain\0action"`.
//! Handlers are plain functions (or closures that capture nothing).
//! Dispatch = parse -> alias resolve -> lookup -> call handler -> envelope.

use crate::alias::{self, AliasMap};
use crate::envelope::Envelope;
use crate::error::TcErr;
use crate::parse::parse;
use serde_json::Value;
use std::collections::HashMap;

/// Handler: receives positional params, returns a JSON object to place in
/// `rst_data`, or a protocol error.
pub type Handler = fn(params: &[&str]) -> Result<Value, TcErr>;

/// In-memory directive registry.
#[derive(Debug, Default)]
pub struct Registry {
    handlers: HashMap<String, Handler>,
    aliases: AliasMap,
}

impl Registry {
    /// Create an empty registry.
    pub fn new() -> Self {
        Self::default()
    }

    /// Register a handler under a canonical `(domain, action)`.
    pub fn register(&mut self, domain: &str, action: &str, handler: Handler) {
        self.handlers
            .insert(alias::join_key(domain, action), handler);
    }

    /// Add an alias (e.g. Chinese name) to a canonical key.
    pub fn add_alias(
        &mut self,
        alias_domain: &str,
        alias_action: &str,
        canon_domain: &str,
        canon_action: &str,
    ) {
        self.aliases
            .add(alias_domain, alias_action, canon_domain, canon_action);
    }

    /// Dispatch a prompt: parse -> alias resolve -> lookup -> handler ->
    /// envelope. Never panics on malformed input; parse/route errors are
    /// returned as error envelopes.
    pub fn dispatch(&self, prompt: &str) -> Envelope {
        let directive = match parse(prompt) {
            Ok(d) => d,
            Err(e) => {
                return Envelope::err(e, "invalid directive format");
            }
        };

        let canon_key = self.aliases.resolve(directive.domain, directive.action);
        match self.handlers.get(&canon_key) {
            None => Envelope::err(TcErr::NotFound, "no matching directive"),
            Some(handler) => match handler(&directive.params) {
                // Envelope::ok handles pray_rst_types promotion and stripping.
                Ok(data) => Envelope::ok(data, crate::envelope::RstType::Text),
                Err(code) => Envelope::err(code, "handler error"),
            },
        }
    }

    /// Number of registered handlers (debug/query support).
    pub fn len(&self) -> usize {
        self.handlers.len()
    }

    /// Whether the registry has no handlers.
    pub fn is_empty(&self) -> bool {
        self.handlers.is_empty()
    }
}

/// Convenience: register one handler.
pub fn register(registry: &mut Registry, domain: &str, action: &str, handler: Handler) {
    registry.register(domain, action, handler);
}

/// Convenience: dispatch one prompt.
pub fn dispatch(registry: &Registry, prompt: &str) -> Envelope {
    registry.dispatch(prompt)
}
