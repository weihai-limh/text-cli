//! Protocol error codes (SPEC S1.2.8 closed set).

use std::fmt;

/// Closed set of protocol error codes (SPEC S1.2.8).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TcErr {
    /// ERR_NOT_FOUND -- capability does not exist.
    NotFound,
    /// ERR_EXECUTION -- execution failure.
    Execution,
    /// ERR_ROUTING -- routing/network failure.
    Routing,
    /// INVALID_PARAMS -- invalid parameters / malformed directive.
    InvalidParams,
    /// ACCESS_DENIED -- access token invalid / denied.
    AccessDenied,
    /// SERVICE_DENIED -- service token invalid / provider refused.
    ServiceDenied,
}

/// All six protocol error codes (closed set).
pub const ERR_CODES: [TcErr; 6] = [
    TcErr::NotFound,
    TcErr::Execution,
    TcErr::Routing,
    TcErr::InvalidParams,
    TcErr::AccessDenied,
    TcErr::ServiceDenied,
];

impl TcErr {
    /// Canonical wire code string.
    pub fn as_str(self) -> &'static str {
        match self {
            TcErr::NotFound => "ERR_NOT_FOUND",
            TcErr::Execution => "ERR_EXECUTION",
            TcErr::Routing => "ERR_ROUTING",
            TcErr::InvalidParams => "INVALID_PARAMS",
            TcErr::AccessDenied => "ACCESS_DENIED",
            TcErr::ServiceDenied => "SERVICE_DENIED",
        }
    }

    /// Parse a wire code string into a `TcErr`, or `None` if not in the set.
    pub fn parse_wire(s: &str) -> Option<TcErr> {
        ERR_CODES.iter().copied().find(|e| e.as_str() == s)
    }
}

impl fmt::Display for TcErr {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_str())
    }
}

impl std::error::Error for TcErr {}
