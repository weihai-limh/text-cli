# text-cli-core-rust

Rust 薄协议核——text-cli 协议条款(解析 / 信封 / 注册 / 别名 / 分发)的直接投影。


## 状态

- M1(内核成型):parse + envelope + registry + alias + dispatch
- 依赖:仅 `serde_json` 一项。

## 使用

```rust
use text_cli_core_rust::Registry;

fn echo(params: &[&str]) -> Result<serde_json::Value, text_cli_core_rust::TcErr> {
    Ok(serde_json::json!({ "status": "ok", "n": params.len() }))
}

let mut reg = Registry::new();
reg.register("echo", "run", echo);
reg.add_alias("hui-xian", "zhi-xing", "echo", "run");

let env = reg.dispatch("AI:echo;run,a,b");
assert_eq!(env.rst_err, "");
assert_eq!(env.to_json(),
    "{\"rst_types\":\"text\",\"rst_data\":{\"n\":2,\"status\":\"ok\"},\"rst_err\":\"\"}");
```

## 命令

```bash
cargo test
cargo clippy --all-targets -- -D warnings
cargo fmt --check
```

