//! Response envelope (SPEC S1.2.2): `{rst_types, rst_data, rst_err}`.

use crate::error::TcErr;
use serde_json::{json, Value};

/// Closed set of result types (SPEC S1.2.2).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum RstType {
    /// text
    #[default]
    Text,
    /// picture
    Picture,
    /// video
    Video,
    /// audio
    Audio,
    /// file
    File,
}

impl RstType {
    /// Canonical wire string.
    pub fn as_str(self) -> &'static str {
        match self {
            RstType::Text => "text",
            RstType::Picture => "picture",
            RstType::Video => "video",
            RstType::Audio => "audio",
            RstType::File => "file",
        }
    }

    /// Parse a wire string into `RstType`; unknown -> `None`.
    pub fn parse_wire(s: &str) -> Option<RstType> {
        match s {
            "text" => Some(RstType::Text),
            "picture" => Some(RstType::Picture),
            "video" => Some(RstType::Video),
            "audio" => Some(RstType::Audio),
            "file" => Some(RstType::File),
            _ => None,
        }
    }
}

/// A protocol response envelope.
#[derive(Debug, Clone, PartialEq)]
pub struct Envelope {
    /// `rst_types`
    pub rst_types: RstType,
    /// `rst_data` -- handler's JSON object carried directly.
    pub rst_data: Value,
    /// `rst_err` -- empty string on success, else a closed-set error code.
    pub rst_err: String,
}

impl Envelope {
    /// Wrap a successful handler result.
    ///
    /// If `data` (a JSON object) carries `pray_rst_types`, it is promoted to
    /// `rst_types` (unless already non-default / unless the value equals
    /// `text`) and the key is stripped from `rst_data` (SPEC S1.2.2).
    pub fn ok(mut data: Value, rst_type: RstType) -> Envelope {
        let mut rst_type = rst_type;
        if let Value::Object(map) = &mut data {
            if let Some(pray) = map.remove("pray_rst_types") {
                if let Some(ps) = pray.as_str() {
                    // "text" keeps current type but the key is already
                    // stripped; non-"text" promotes.
                    if let Some(t) = RstType::parse_wire(ps) {
                        if t != RstType::Text {
                            rst_type = t;
                        }
                    }
                    // unknown values: stripped, type unchanged.
                }
            }
        }
        Envelope {
            rst_types: rst_type,
            rst_data: data,
            rst_err: String::new(),
        }
    }

    /// Wrap an error with a closed-set code and a reason.
    pub fn err(code: TcErr, reason: &str) -> Envelope {
        Envelope {
            rst_types: RstType::Text,
            rst_data: json!({ "status": "error", "reason": reason }),
            rst_err: code.as_str().to_string(),
        }
    }

    /// Serialize the envelope to a JSON string.
    ///
    /// Field order is fixed as rst_types / rst_data / rst_err to keep the
    /// output byte-comparable across implementations (SPEC examples use this
    /// order; JSON semantics are unordered, this is a stability choice).
    pub fn to_json(&self) -> String {
        let data = serde_json::to_string(&self.rst_data).unwrap_or_else(|_| "{}".into());
        let mut s = String::with_capacity(data.len() + 64);
        s.push_str("{\"rst_types\":\"");
        s.push_str(self.rst_types.as_str());
        s.push_str("\",\"rst_data\":");
        s.push_str(&data);
        s.push_str(",\"rst_err\":\"");
        // rst_err is either empty or one of the closed-set codes (ASCII,
        // no quoting needed); defensively escape anyway.
        for ch in self.rst_err.chars() {
            match ch {
                '"' => s.push_str("\\\""),
                '\\' => s.push_str("\\\\"),
                c => s.push(c),
            }
        }
        s.push_str("\"}");
        s
    }
}

/// Promotes `pray_rst_types` found in a handler JSON object and strips it.
///
/// Returns the new `RstType` plus the cleaned object.
pub fn promote_pray(data: &mut Value, current: RstType) -> RstType {
    let mut out = current;
    if let Value::Object(map) = data {
        if let Some(pray) = map.remove("pray_rst_types") {
            if let Some(ps) = pray.as_str() {
                if let Some(t) = RstType::parse_wire(ps) {
                    if t != RstType::Text {
                        out = t;
                    }
                }
            }
        }
    }
    out
}
