//! text-cli-core-rust M1 unit tests.
//!
//! Mirrors the C core test_unit.c: parse baseline semantics, registry,
//! alias, envelope (pray promotion/strip), NOT_FOUND.
//! Non-ASCII data is expressed via \u escapes to keep source pure ASCII.

use text_cli_core_rust::envelope::Envelope;
use text_cli_core_rust::error::TcErr;
use text_cli_core_rust::parse::parse;
use text_cli_core_rust::Registry;

fn expect_parse_ok(prompt: &str, domain: &str, action: &str, params: &[&str]) {
    let d = parse(prompt).unwrap_or_else(|e| {
        panic!("parse({prompt:?}) failed: {e:?}");
    });
    assert_eq!(d.domain, domain, "domain mismatch for {prompt:?}");
    assert_eq!(d.action, action, "action mismatch for {prompt:?}");
    assert_eq!(d.params, params, "params mismatch for {prompt:?}");
}

fn expect_parse_err(prompt: &str) {
    assert!(
        parse(prompt).is_err(),
        "expected parse error for {prompt:?}"
    );
}

#[test]
fn parse_baseline() {
    expect_parse_ok("AI:tc-math;eval,2+3*4", "tc-math", "eval", &["2+3*4"]);
    expect_parse_ok("AI:a;b,c,d", "a", "b", &["c", "d"]);
    expect_parse_ok("AI:a;b", "a", "b", &[]);
    expect_parse_ok(
        "AI:weather;query,\u{5317}\u{4eac},\u{660e}\u{5929}",
        "weather",
        "query",
        &["\u{5317}\u{4eac}", "\u{660e}\u{5929}"],
    );
    expect_parse_ok("AI:a;b,c,,d", "a", "b", &["c", "d"]); // empty dropped
    expect_parse_ok("AI:a;b,c,", "a", "b", &["c"]); // trailing comma
    expect_parse_ok("AI:a;b, c , d ", "a", "b", &["c", "d"]); // trim
    expect_parse_ok("  AI:a;b,c  ", "a", "b", &["c"]); // outer pad

    // bracket depth
    expect_parse_ok("AI:a;b,c,{x:1,y:2}", "a", "b", &["c", "{x:1,y:2}"]);
    expect_parse_ok(
        "AI:a;b,{a:{b:1,c:[1,2]}},z",
        "a",
        "b",
        &["{a:{b:1,c:[1,2]}}", "z"],
    );
    expect_parse_ok("AI:a;b,{x:1},y", "a", "b", &["{x:1}", "y"]);
    expect_parse_ok("AI:a;b,{x:1,y:2", "a", "b", &["{x:1,y:2"]); // unbalanced
    expect_parse_ok(
        "AI:a;b,{x:1,[2,3]},tail",
        "a",
        "b",
        &["{x:1,[2,3]}", "tail"],
    );
    expect_parse_ok("AI:a;b,[1,2,3],z", "a", "b", &["[1,2,3]", "z"]);
    expect_parse_ok("AI:a;b,[{a:1},{a:2}],z", "a", "b", &["[{a:1},{a:2}]", "z"]);

    // double quote
    expect_parse_ok("AI:a;b,\"x,y\",z", "a", "b", &["\"x,y\"", "z"]);
    expect_parse_ok(
        "AI:a;b,{text: \"has, comma\"}",
        "a",
        "b",
        &["{text: \"has, comma\"}"],
    );

    // errors
    expect_parse_err("AI:;b,c");
    expect_parse_err("AI:a;,c");
    expect_parse_err("AI:abc");
    expect_parse_err("");
    expect_parse_err("AI:");
    expect_parse_err("\u{6307}\u{4ee4}:a;b,c"); // legacy prefix unsupported
}

fn echo_handler(params: &[&str]) -> Result<serde_json::Value, TcErr> {
    Ok(serde_json::json!({
        "status": "ok",
        "n": params.len(),
    }))
}

fn pray_pic_handler(_params: &[&str]) -> Result<serde_json::Value, TcErr> {
    Ok(serde_json::json!({
        "pray_rst_types": "picture",
        "url": "http://x/a.jpg",
    }))
}

fn pray_text_handler(_params: &[&str]) -> Result<serde_json::Value, TcErr> {
    Ok(serde_json::json!({
        "pray_rst_types": "text",
        "result": 1,
    }))
}

#[test]
fn dispatch_envelope() {
    let mut reg = Registry::new();
    reg.register("echo", "run", echo_handler);
    reg.register("pray", "pic", pray_pic_handler);
    reg.register("pray", "txt", pray_text_handler);
    reg.add_alias("hui-xian", "zhi-xing", "echo", "run");

    // echo
    let e = reg.dispatch("AI:echo;run,a,b");
    assert_eq!(e.rst_err, "", "echo should succeed");
    assert_eq!(
        e.to_json(),
        "{\"rst_types\":\"text\",\"rst_data\":{\"n\":2,\"status\":\"ok\"},\"rst_err\":\"\"}"
    );

    // alias
    let e2 = reg.dispatch("AI:hui-xian;zhi-xing,x");
    assert_eq!(e2.rst_err, "", "alias should succeed");

    // pray -> picture promote & strip
    let e3 = reg.dispatch("AI:pray;pic");
    assert_eq!(e3.rst_types.as_str(), "picture", "pray should promote");
    assert!(
        !e3.to_json().contains("pray_rst_types"),
        "pray key must be stripped"
    );

    // pray text -> strip but keep type text
    let e4 = reg.dispatch("AI:pray;txt");
    assert_eq!(e4.rst_types.as_str(), "text", "pray text keeps text");
    assert!(
        !e4.to_json().contains("pray_rst_types"),
        "pray text key stripped"
    );

    // not found
    let e5 = reg.dispatch("AI:nope;x");
    assert_eq!(e5.rst_err, "ERR_NOT_FOUND");
    assert_eq!(e5.rst_types.as_str(), "text");

    // manual envelope checks
    let ok_env = Envelope::ok(
        serde_json::json!({"status":"ok","result":14}),
        Default::default(),
    );
    assert_eq!(ok_env.rst_err, "");
}

#[test]
fn empty_registry_len() {
    let reg = Registry::new();
    assert!(reg.is_empty());
    assert_eq!(reg.len(), 0);
}
