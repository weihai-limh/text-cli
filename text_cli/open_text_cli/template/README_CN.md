# template · 模板

提示词模板库，支持占位符替换。

## 安装

```
AI:text-cli;install,template
```

## 依赖

**数据文件**（随包分发）：
- `prompt_templates.json` — 模板定义（ID、文本、描述）

**运行时依赖**：`handlers.image`（输出缓存）。

## 指令

| 指令 | 说明 |
|------|------|
| `template;list` | 列出所有可用模板 |
| `template;use,<ID>[,键=值,...]` | 渲染模板并替换占位符，输出缓存 |

## 示例

```
AI:模板;列表
→ 默认: 通用场景分析
   风景: 侧重自然景观
   城市: 侧重城市环境

AI:模板;使用,默认,地点=威海,时间=清晨,设备=手机
→ cache:a1b2c3d4e5f6
  请描述这张手机于清晨在威海拍摄的照片。描述场景、主体、光线、色彩和地貌特征。
```

## 架构

```
Python 包（含数据文件）
  ├── handler.py              — @directive 注册 + 模板渲染
  ├── prompt_templates.json   — 模板定义（随包分发）
  └── schema.json             — 指令声明
```
