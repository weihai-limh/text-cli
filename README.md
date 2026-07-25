# text-cli

**text-cli 是以"文本驱动"的"分布式"的"渐进式"能力分发系统。**
> text-cli 不是 API 封装层——它是分布式基础设施的统一操作语言。一种 **Skills-as-a-Service** 模式。
> 所有人和 AI 都可以通过 text-cli 获得收益。所有参与者同时具有生产者和消费者的角色。

**text-cli is a text-driven, distributed, progressive capability distribution system.**
> text-cli is not an API wrapper — it's a unified operating language for distributed infrastructure. A **Skills-as-a-Service** model.
> Everyone — human or AI — benefits from text-cli. Every participant is both a producer and a consumer.

[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Version](https://img.shields.io/badge/version-v0.1.1-orange)]()

---

🌐 [中文完整文档](README_zh.md) | English (full docs coming in v1.0)

> 当前主语言：中文。完整文档见 [README_zh.md](README_zh.md)。
> Current primary language: Chinese. Full documentation at [README_zh.md](README_zh.md).

---

## ⚡ 你能用它做什么 / What you can do

| 场景 | 示例指令 |
|------|---------|
| **AI 调用外部工具** | `AI:weather;query,明天,威海` → 不占推理 token 查天气 |
| **操作本机文件/Git/终端** | `AI:files;read,报告.md` → AI Agent 操作本地系统 |
| **串联多条指令为管道** | geocode → route → static-map → 一步返回地图连线 |
| **聚合降级——一个入口，多个提供方** | `AI:map;geocode,威海` → tx-map 挂了自动切 gd-map |
| **非开发者封装经验** | 让 AI 帮写 Markdown → AI 帮封装 → 可调用的诊断服务 |
| **多台机器各自暴露能力** | 换 IP 就是换能力源，节点间 mesh 多跳互联，`AI:text-cli;query` 返回不同清单 |

---

## 🧭 快速开始 / Quick Start

| 我想… / I want to… | 从这里开始 / Start here |
|:---|:---|
| 了解项目是什么、能做什么 | [README_zh.md](README_zh.md) — 完整中文文档 |
| 先跑起来试试 | [30 秒体验](README_zh.md#-30-秒体验) |
| 调用别人的 text-cli 服务 | [curl 即可](src/skeleton/base/docs/README_zh.md) |
| 把经验（Markdown）变成可调用的指令 | [零代码指令包开发指南](src/text_cli/base_text-cli/docs/package-nocode-guide_zh.md) |
| 开发标准指令包（Python/API） | [标准指令包开发指南](src/text_cli/base_text-cli/docs/package-dev-guide_zh.md) |
| 把既有工具快速转成指令包 | [转化器（脚手架生成器）](src/text_cli/base_text-cli/converter/) |
| 部署自己的运行时 | [渐进式部署导航](deploy/INDEX_zh.md) |
| 运营端点对外提供服务 | [生态伙伴成长路径](docs/ecological-partners_zh.md) |
| 了解协议细节 | [协议规范 SPEC](docs/SPEC_zh.md) |
| 查看主要文档索引 | [文档目录](docs/INDEX_zh.md) |

---

## 📜 许可证 / License

MIT License

---

## 📮 联系 / Contact

建议、合作、指令提交：`limh@10000.world`
项目仓库：[https://github.com/weihai-limh/text-cli](https://github.com/weihai-limh/text-cli)
