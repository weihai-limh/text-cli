# examples/text-cli

指令市场——按需安装的 text-cli service 指令包。每个目录是一个独立的指令单元，自带 handler 代码和双语说明。

```
text-cli/
├── README.md                         ← 本文件
├── text-cli.json                     ← 21 条指令 Schema 聚合（机器消费）
│
├── ai_inference/                     ← AI 推理 + 视觉
│   ├── handler.py                    ← 实现（多模型回退链，时段感知路由）
│   ├── model_aliases.example.json    ← 配置模板
│   └── README.md                     ← 安装 + 使用指南
│
├── ai_generate/                      ← AI 图像/视频生成
│   ├── handler.py
│   ├── model_aliases.example.json
│   └── README.md
│
├── image/                            ← 图片处理（EXIF + 编码）
│   ├── handler.py
│   └── README.md
│
├── media/                            ← 媒体加载（URL 透传 + 本地白名单）
│   ├── handler.py
│   └── README.md
│
├── template/                         ← 提示模板引擎
│   ├── handler.py
│   ├── prompt_templates.json
│   └── README.md
│
├── key/                              ← 密钥管理（注册/撤销/列表）
│   ├── handler.py
│   └── README.md
│
└── embed/                            ← 语义嵌入（编码/相似/匹配）
    ├── handler.py
    └── README.md
```

---

## CN · 中文导航

### 智能服务
- [ai_inference](./ai_inference/) — AI辅助推理与视觉。多模型回退链，时段感知路由，零外部依赖。
- [ai_generate](./ai_generate/) — 图像与视频生成。CogView/CogVideoX 兼容 API。

### 媒体与模板
- [image](./image/) — 图片 EXIF 提取 + 编码缓存。Pillow 依赖。
- [media](./media/) — 媒体文件加载。公网 URL 透传，本地白名单校验。
- [template](./template/) — 确定性提示模板。零 AI token 消耗，防幻觉。

### 基础设施
- [key](./key/) — 密钥注册/撤销/列表。XOR 加密存储。
- [embed](./embed/) — 语义嵌入编码/相似/匹配。BGE-M3 兼容。

### Schema
- [text-cli.json](./text-cli.json) — 全部指令 Schema 定义（id/参数/响应/安全策略）。

---

## EN · English

### Intelligent Services
- [ai_inference](./ai_inference/) — Text reasoning & vision. Multi-model fallback chain, period-aware routing.
- [ai_generate](./ai_generate/) — Image & video generation. CogView/CogVideoX compatible API.

### Media & Templates
- [image](./image/) — EXIF extraction + image encoding with cache. Pillow dependency.
- [media](./media/) — Media file loading. Public URL pass-through, local whitelist validation.
- [template](./template/) — Deterministic prompt templates. Zero AI tokens, hallucination-proof.

### Infrastructure
- [key](./key/) — API key register/revoke/list. XOR encrypted storage.
- [embed](./embed/) — Semantic encode/similarity/match. BGE-M3 compatible.

### Schema
- [text-cli.json](./text-cli.json) — Full directive schema registry for Agent routing & Function Calling.
