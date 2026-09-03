# conformance — 协议一致性套件(漂移互照)

> 用途:把同一批向量喂给**多个独立实现**(Py/JS 真源 + C/Rust 内核),任何不一致立即可见。
> 目标不是「证明实现正确」,而是**把静默漂移照出来**——漂移是 conformance 的产出,不是缺陷。

## 目录

```
conformance/
├── vectors/
│   ├── parse.jsonl       # 解析向量(22 baseline + 5 observe)
│   └── envelope.jsonl    # 信封向量(待接入 runner)
├── runners/
│   ├── py/run.py         # Python 真源 runner(textcli-loader)
│   ├── js/run.js         # JavaScript 真源 runner(textcli-core)
│   ├── c/run.c           # C 内核 runner(text_cli_core.c)
│   └── rust/             # Rust 内核 runner crate(依赖 text-cli-core-rust)
│       ├── Cargo.toml
│       └── src/main.rs
├── tools/
│   └── gen-parse-vectors.py   # 双真源交叉验证生成器(制向量时用)
├── run_drift.py          # 漂移互照驱动(唯一入口)
└── README_zh.md
```

## 用法

```bash
# 全量互照(自动构建 C/rust runner,首次需 cargo/gcc)
python conformance/run_drift.py

# 跳过某实现(如只照 C vs Rust)
python conformance/run_drift.py --skip py,js
```

退出码:baseline 有 FAIL → 1;全绿 → 0。observe 行不判生死,仅记录。

## Runner 契约

每个 runner 是独立可执行,stdin 逐行读 prompt(空行 = 空 prompt),stdout 逐行输出 JSON:

```
{"domain":..,"action":..,"params":[..]}    # 成功
{"error":"INVALID_PARAMS"}                  # 解析错误
```

驱动按行对齐 prompt 与输出,做**语义比较**(JSON 对象,键序无关)。

## 向量字段

| 字段 | 含义 |
|---|---|
| `id` | 向量唯一标识(供 runner exclude 引用) |
| `in` | prompt 输入 |
| `expect` | baseline 的期望输出(所有实现必须一致) |
| `mode` | `baseline`(必须绿)/ `observe`(只记录,不判) |
| `py`/`js`/`c`/`rust` | observe 行中各实现的参考输出(记录漂移) |
| `note` | 裁决说明 |

## 当前漂移清单(observe,2026-09-02 实测)

| id | 分歧 | 状态 |
|---|---|---|
| `parse.boundary.toomany` | 55 参数:Py/JS 上限 50 报错;C/Rust 上限 16 截断 | 实现常量,待统一或保持 |
| `parse.prefix.legacy` | `指令:` 前缀:Py/JS 支持;C/Rust 仅 `AI:`(按 SPEC 附录 B §1.1 可弃) | C/Rust 遵循 plan 裁决 |
| `parse.drift.quote.single` | 单引号:JS 当字符串;Py/C/Rust 不当 | 语义裁决偏向 Py/C/Rust |
| `parse.drift.escape.comma` | 反斜杠:Py/C/Rust 保留;JS 吞 | 同上 |
| `parse.drift.escape.bs` | 反斜杠:同上 | 同上 |

> **C 与 Rust 内核在全部 observe 项行为一致**——两核遵循同一语义裁决(Python 语义 + AI:-only),互为参照无漂移。真正分叉在 JS 与参数上限常量。

## envelope 向量

`vectors/envelope.jsonl` 已就位(ok/err/pray 提升剥离),runner 接入待后续——envelope 是"装配"而非"解析",runner 需模拟 handler 返回,契约与 parse runner 不同,独立设计。
