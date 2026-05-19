# open_text_cli

text-cli 标准指令包目录。每个子目录是一个可安装的指令包。

## 快速开始

查看所有可用指令：[INDEX_CN.md](./INDEX_CN.md)

安装包：

```
AI:text-cli;install,<包名>
```

## 包目录结构

```
<包名>/
├── schema.json      — 指令声明
├── handler.py(.js)  — 指令实现
├── README.md        — 英文文档
└── README_CN.md     — 中文文档
```

cmd 运行时包用 `whitelist.json` 替代 handler。

## 运行时

| 类型 | 说明 |
|------|------|
| python | Python handler，`@directive` 注册 |
| node | Node.js handler，stdin JSON → stdout |
| cmd | Shell 命令，copilot 白名单执行 |

## 贡献新包

参考《标准指令包发布指南》（`/root/tide/package-publishing-guide.md`）。
