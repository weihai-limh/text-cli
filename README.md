# text-cli

**text-cli 是以'文本驱动'的'分布式'的'渐进式'技能交付服务。**
> 调用者（人或 AI）通过 curl 向部署了 text-cli 服务的终端发起请求后，目标终端即根据"声明"向调用方返回"经过技能加工后"的"响应结果"。
> 无论你是开发者、行业专家，还是只想把经验变成服务的非开发者，都可以在这里把你的知识打包成"一键指令"——一种全新的 **Skill-as-a-Service** 模式。

**text-cli is a text-driven, distributed, progressive skill delivery service.**
> A caller (human or AI) sends a curl request to a terminal running text-cli. The terminal returns a skill-processed result based on the declaration. Anyone can package knowledge as a one-line directive — a new **Skill-as-a-Service** model.

[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Version](https://img.shields.io/badge/version-v0.1.0-orange)]()

---

🌐 **中文** | [English](README.md) (coming in v1.0)

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
| **多台机器各自暴露能力** | 换 IP 就是换能力源，`AI:text-cli;query` 返回不同清单 |

---

## 🚀 快速开始 / Quick Start

| 你是 / You are | 去这里 / Go here |
|:---|:---|
| 我想了解项目是什么、能做什么 | [README_zh.md](README_zh.md) — 完整中文文档 |
| 我想了解完整指令格式 | [docs/SPEC_v1_3_1_zh.md](docs/SPEC_v1_3_1_zh.md) |
| 我想看渐进式部署全景 | [deploy/INDEX_zh.md](deploy/INDEX_zh.md) |
| 我想部署本地 copilot | [deploy/A2-copilot/](deploy/A2-copilot/) |
| 我想部署平台服务 | [deploy/A3-service/](deploy/A3-service/) |
| 我想了解生态规则 | [docs/ecosystem/charter_zh.md](docs/ecosystem/charter_zh.md) |

---

## 📜 许可证 / License

MIT License

---

## 📮 联系 / Contact

建议、合作、指令提交：`limh@10000.world`
项目仓库：[https://github.com/weihai-limh/text-cli](https://github.com/weihai-limh/text-cli)
