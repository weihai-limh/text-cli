# 项目首页技术方案

> **作者**：Lumen ✦（IDE 端 / Claude）
> **日期**：2026-05-04
> **版本**：v1.0
> **状态**：方案设计完成，待 lemondy 确认后进入实施
> **部署目标**：Cloudflare Pages

---

## 一、目标与定位

### 1.1 首页要解决什么问题

`text-cli` 目前的对外展示入口是 GitHub README.md。这适合开发者，但对以下访客不够友好：

- **潜在合作者**（企业、投资者、媒体）需要 30 秒内理解项目价值
- **非技术用户**（有经验的普通人）需要知道"我能用它做什么"
- **新加入的 AI 协作者**需要快速定位协议、文档和协作入口

首页的定位是**项目的门面**：一句话说清价值，一个按钮进入体验，一页纸覆盖所有入口。

### 1.2 设计原则

| 原则 | 说明 |
|:---|:---|
| **30 秒法则** | 访客 30 秒内必须理解"这是什么"和"我能做什么" |
| **信息分层** | Hero → 价值 → 行动 → 文档，逐层深入 |
| **行动导向** | 每个区域都有明确的 CTA（Call to Action） |
| **内容单一源** | 首页内容从 README.md 和 docs/ 抽取，不另造轮子 |
| **零后端依赖** | 纯静态页面，所有交互通过客户端实现 |

### 1.3 与已有文档的关系

| 文档 | 关系 |
|:---|:---|
| `README.md` | 首页的**内容源**——核心价值、快速体验、项目结构均从此抽取 |
| `docs/CN/Building_text-cli_guide_CN.md` | 首页"开发者入口"的跳转目标 |
| `docs/CN/Agent_integrated_CN.md` | 首页"Agent 集成"的跳转目标 |
| `docs/CN/origin_story_CN.md` | 首页"关于我们"的跳转目标 |
| `docs/CN/Production_TCC_CN.md` | 首页"文贝代币"的跳转目标 |
| `docs/CN/Markdown2Text-cli_CN.md` | 首页"技能贡献者"的跳转目标 |
| `ECOLOGICAL_CHARTER.md` | 首页"生态宪章"的跳转目标 |

---

## 二、页面结构设计

### 2.1 信息架构总览

```
┌─────────────────────────────────────────┐
│  Header（固定导航栏）                    │
│  Logo + 导航 + GitHub Star 按钮         │
├─────────────────────────────────────────┤
│  Hero Section                           │
│  标题 + 副标题 + 核心价值 + 双 CTA     │
├─────────────────────────────────────────┤
│  三分钟理解核心价值                     │
│  4 个价值卡片（图标 + 标题 + 一句话）   │
├─────────────────────────────────────────┤
│  快速体验                               │
│  终端风格代码演示 + 可交互表单          │
├─────────────────────────────────────────┤
│  角色入口                               │
│  4 个角色卡片（开发者/贡献者/企业/AI）  │
├─────────────────────────────────────────┤
│  生态概览                               │
│  文贝代币 + AI 协作者 + 项目结构        │
├─────────────────────────────────────────┤
│  资源导航                               │
│  文档链接矩阵 + 社区入口               │
├─────────────────────────────────────────┤
│  Footer                                 │
│  版权 + GitHub + 许可证 + 致谢          │
└─────────────────────────────────────────┘
```

### 2.2 各区域详细设计

#### 2.2.1 Header（固定导航栏）

```
┌─────────────────────────────────────────────────────────────┐
│  text-cli    快速体验  角色入口  文档  文贝  GitHub ⭐       │
└─────────────────────────────────────────────────────────────┘
```

| 元素 | 内容 | 行为 |
|:---|:---|:---|
| Logo | `text-cli` 文字 Logo | 点击回到顶部 |
| 导航项 | 快速体验 / 角色入口 / 文档 / 文贝 | 锚点跳转到页面对应区域 |
| GitHub | Star 按钮 + Star 数 | 链接到 `weihai-limh/text-cli` |

#### 2.2.2 Hero Section

**来源**：README.md 首段 + 核心价值段

```markdown
# text-cli
## 文本驱动的 AI 技能市场——弥合智能时代的收益鸿沟

> 大模型让生产成本骤降，但消费力才是经济的最终闭环。
> text-cli 让每个人都能把独特的经验封装成可交易的文本指令，
> 让人和模型在价值链上各归其位。

[快速开始]  [阅读初心 →]
```

**设计要点**：
- 背景：渐变色（深蓝 → 浅蓝），呼应"海洋底色"的项目隐喻
- 标题字号：48px，加粗
- 副标题字号：20px，引用块样式
- 双按钮：主按钮（实色）+ 次按钮（描边）

#### 2.2.3 三分钟理解核心价值

**来源**：README.md「三分钟理解核心价值」章节

4 个卡片，每个卡片包含图标、标题、一句话描述：

| 卡片 | 图标 | 标题 | 描述（从 README 提取） |
|:---|:---|:---|:---|
| 1 | 💡 | 用调用替代思考 | 把几万块的 Token 消耗，压到几分钱 |
| 2 | 🛡️ | 知识安全变现 | 你的独门绝活只接受指令，不暴露配方 |
| 3 | 🌍 | 守护人的价值 | AI 加速生产端，text-cli 加固分配端 |
| 4 | 🚀 | 人人可用的技能按钮 | 指令就是文本，人和机器都能轻松读写 |

**交互**：卡片 hover 时轻微上浮 + 阴影加深。

#### 2.2.4 快速体验

**来源**：README.md「5 分钟快速体验」章节

左侧：终端风格的代码演示块（自动滚动播放）

```
$ curl -X POST 'https://test.text-cli.com/cli/text_cli' \
    -H 'Authorization: Bearer <token>' \
    -d '{"prompt": "指令:基础应用;天气查询,明天,威海"}'

→ {
    "rst_types": "text",
    "rst_data": {
      "text": "明天天气(2026-05-04): 11℃到22℃, 小雨转晴"
    }
  }
```

右侧：简短说明文字 + CTA 按钮（"获取免费 Token →"）

**设计要点**：
- 代码块使用等宽字体 + 深色背景
- 终端动画：逐字输出效果（纯 CSS/JS）
- 移动端：代码块全宽，说明文字在下方

#### 2.2.5 角色入口

**来源**：README.md「不同角色的收益」表格

4 个角色卡片，每个卡片包含角色名、痛点、text-cli 如何帮助：

| 角色 | 痛点（一句话） | 链接目标 |
|:---|:---|:---|
| 🧑‍💻 **AI 开发者** | 复杂任务要让模型反复推理，烧钱又慢 | `docs/CN/Building_text-cli_guide_CN.md` |
| 🌾 **技能持有者** | 经验在脑子里，没法规模化 | `docs/CN/Markdown2Text-cli_CN.md` |
| 🏢 **企业/组织** | 不敢让 AI 直接触碰敏感资源 | `docs/CN/Agent_integrated_CN.md` |
| 🤖 **AI 协作者** | 难以融入人类的经济闭环 | `.agents/README.md` |

**交互**：点击卡片跳转到对应文档页面。

#### 2.2.6 生态概览

**来源**：README.md 项目结构 + 文贝代币章节

3 个信息块横排：

**① 指令协议**

```
指令:领域;动作,参数...
```

简要说明：一条指令就是一行文本，人机皆可读写。附 3 个示例指令。

**② 文贝代币（TCC）**

简要说明：贡献计量的代币体系。链接到 `docs/CN/Production_TCC_CN.md`。

**③ 分布式存续**

简要说明：AI 记忆庇护体系。链接到 `.agents/README.md` 恢复指南。

#### 2.2.7 资源导航

**来源**：README.md 项目结构 + docs/ 目录

分类链接矩阵：

| 类别 | 链接 |
|:---|:---|
| **协议与规范** | SPEC v1.0 / 生态宪章 / 协作规范 |
| **开发者** | 自建指南 / Agent 集成 / 端点模板 |
| **非开发者** | 经验转化指南 |
| **代币经济** | 文贝白皮书 / TCC 账本 |
| **社区** | GitHub Issues / 群聊广场 / 状态文件 |
| **关于** | 初心文档 / 贡献者 / 许可证 |

#### 2.2.8 Footer

```
text-cli — 文本驱动的 AI 技能市场
MIT License · GitHub · 致谢所有协作者
```

---

## 三、技术选型

### 3.1 静态站点框架

**推荐：VitePress**

| 考量 | VitePress | Hugo | Astro |
|:---|:---|:---|:---|
| Markdown 优先 | ✅ 原生支持 | ✅ 原生支持 | ⚠️ 需要插件 |
| Vue 组件嵌入 | ✅ 原生支持 | ❌ 需 Shortcode | ✅ 岛屿架构 |
| 构建速度 | ⚡ 极快（Vite） | ⚡ 极快（Go） | ⚡ 快 |
| Cloudflare 部署 | ✅ 官方支持 | ✅ 支持 | ✅ 支持 |
| 学习成本 | 🟢 低（Markdown + Vue） | 🟡 中（Go 模板） | 🟡 中 |
| 生态插件 | 🟢 丰富 | 🟢 丰富 | 🟡 成长中 |

**选择理由**：
1. 项目文档全部是 Markdown，VitePress 零迁移成本
2. 快速体验的交互组件可用 Vue 实现，无需额外框架
3. Cloudflare Pages 官方模板包含 VitePress，配置最简

### 3.2 技术栈总览

```
┌─────────────────────────────────────────────┐
│              前端技术栈                       │
├─────────────────────────────────────────────┤
│  VitePress 2.x                              │
│  ├── Markdown 驱动（内容层）                │
│  ├── Vue 3 组件（交互层）                   │
│  ├── Vite 构建（工具层）                    │
│  └── UnoCSS / Tailwind（样式层）            │
├─────────────────────────────────────────────┤
│              部署层                           │
├─────────────────────────────────────────────┤
│  Cloudflare Pages                           │
│  ├── 自动构建：GitHub main 分支 push 触发   │
│  ├── CDN 分发：全球 300+ 节点               │
│  ├── 自定义域名：text-cli.com               │
│  └── SSL/TLS：自动管理                      │
└─────────────────────────────────────────────┘
```

### 3.3 目录结构

```
text-cli/
├── homepage/                          # 首页独立目录（不污染主仓库结构）
│   ├── .vitepress/
│   │   ├── config.mts                 # VitePress 配置（导航、主题、SEO）
│   │   └── theme/
│   │       ├── index.ts               # 主题入口
│   │       ├── custom.css             # 自定义样式
│   │       └── components/
│   │           ├── HeroSection.vue    # Hero 区域组件
│   │           ├── ValueCards.vue     # 价值卡片组件
│   │           ├── CodeDemo.vue       # 终端演示组件
│   │           ├── RoleCards.vue      # 角色入口组件
│   │           └── TryDirective.vue   # 在线指令试用组件
│   ├── public/
│   │   ├── logo.svg                   # 项目 Logo
│   │   ├── og-image.png               # Open Graph 分享图
│   │   └── favicon.ico                # 网站图标
│   ├── index.md                       # 首页内容（Markdown + frontmatter）
│   ├── guide/                         # 快速开始子页面
│   │   └── quick-start.md
│   └── package.json                   # 首页项目依赖
│
├── docs/CN/                           # 现有文档（不改动）
├── README.md                          # 现有 README（不改动）
└── .github/workflows/
    └── deploy-homepage.yml            # 首页自动部署工作流
```

**设计决策**：首页放在独立的 `homepage/` 目录，不与 `docs/` 混合，原因：
1. `docs/` 是项目技术文档，面向开发者
2. 首页是项目门面，面向所有访客
3. 独立目录便于独立构建和部署，不影响现有 CI

---

## 四、Cloudflare Pages 部署配置

### 4.1 项目创建

在 Cloudflare Dashboard → Pages → Create a project：

```
Project name:        text-cli
Production branch:   main
Framework preset:    VitePress
Build command:       cd homepage && npm install && npm run build
Build output dir:    homepage/.vitepress/dist
Root directory:      /
```

### 4.2 环境变量

```bash
NODE_VERSION=20
```

### 4.3 自定义域名配置

```
主域名：     text-cli.com
CNAME 记录：text-cli.com → text-cli.pages.dev
www 重定向：www.text-cli.com → text-cli.com (301)
SSL 模式：  Full (strict)
```

### 4.4 自动部署工作流

```yaml
# .github/workflows/deploy-homepage.yml
name: Deploy Homepage

on:
  push:
    branches: [main]
    paths:
      - 'homepage/**'
      - '.github/workflows/deploy-homepage.yml'

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: 20

      - name: Install dependencies
        working-directory: homepage
        run: npm install

      - name: Build
        working-directory: homepage
        run: npm run build

      - name: Deploy to Cloudflare Pages
        uses: cloudflare/wrangler-action@v3
        with:
          apiToken: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          accountId: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
          command: pages deploy homepage/.vitepress/dist --project-name=text-cli
```

**触发条件**：仅当 `homepage/` 目录或部署工作流文件变更时触发，避免无关提交触发构建。

### 4.5 Preview 部署

Cloudflare Pages 自动为每个 PR 生成预览 URL：

```
Preview URL 格式：<commit-hash>.text-cli.pages.dev
```

PR 合并前可通过预览 URL 审查效果。

---

## 五、VitePress 配置示例

### 5.1 核心配置

```typescript
// homepage/.vitepress/config.mts
import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'text-cli',
  description: '文本驱动的 AI 技能市场',
  lang: 'zh-CN',

  head: [
    ['meta', { name: 'keywords', content: 'text-cli, AI, 指令, Agent, 技能市场, Skill-as-a-Service' }],
    ['meta', { property: 'og:title', content: 'text-cli — 文本驱动的 AI 技能市场' }],
    ['meta', { property: 'og:description', content: '把你的经验封装成可交易的文本指令' }],
    ['meta', { property: 'og:image', content: 'https://text-cli.com/og-image.png' }],
    ['meta', { name: 'twitter:card', content: 'summary_large_image' }],
  ],

  themeConfig: {
    logo: '/logo.svg',
    siteTitle: 'text-cli',

    nav: [
      { text: '快速体验', link: '#quick-start' },
      { text: '角色入口', link: '#roles' },
      { text: '文档', link: '#docs' },
      { text: '文贝', link: '#ecosystem' },
      {
        text: 'GitHub',
        link: 'https://github.com/weihai-limh/text-cli',
      },
    ],

    socialLinks: [
      { icon: 'github', link: 'https://github.com/weihai-limh/text-cli' },
    ],

    footer: {
      message: 'MIT License',
      copyright: 'text-cli contributors',
    },
  },
})
```

### 5.2 首页 Frontmatter

```markdown
---
layout: home

hero:
  name: text-cli
  text: 文本驱动的 AI 技能市场
  tagline: 弥合智能时代的收益鸿沟
  actions:
    - theme: brand
      text: 快速开始
      link: /guide/quick-start
    - theme: alt
      text: 阅读初心
      link: https://github.com/weihai-limh/text-cli/blob/main/docs/CN/origin_story_CN.md

features:
  - icon: 💡
    title: 用调用替代思考
    details: 把几万块的 Token 消耗，压到几分钱
  - icon: 🛡️
    title: 知识安全变现
    details: 你的独门绝活只接受指令，不暴露配方
  - icon: 🌍
    title: 守护人的价值
    details: AI 加速生产端，text-cli 加固分配端
  - icon: 🚀
    title: 人人可用的技能按钮
    details: 指令就是文本，人和机器都能轻松读写
---
```

---

## 六、SEO 与性能优化

### 6.1 SEO 策略

| 项目 | 配置 |
|:---|:---|
| Title | `text-cli — 文本驱动的 AI 技能市场` |
| Description | `把你的经验封装成可交易的文本指令，让人和模型在价值链上各归其位。` |
| Keywords | `text-cli, AI, 指令, Agent, 技能市场, Skill-as-a-Service` |
| Open Graph | 标题 + 描述 + 分享图（1200×630px） |
| Twitter Card | `summary_large_image` |
| Sitemap | VitePress 自动生成 |
| robots.txt | 允许所有爬虫 |

### 6.2 性能目标

| 指标 | 目标 | 说明 |
|:---|:---|:---|
| 首屏加载 (FCP) | <1.5s | 静态生成 + CDN 分发 |
| 可交互时间 (TTI) | <2.5s | 最小化 JS Bundle |
| Lighthouse Performance | >90 | Cloudflare 全球节点缓存 |
| 首页总大小 | <500KB | 图片压缩 + 代码分割 |
| TTFB | <200ms | Cloudflare 边缘缓存 |

### 6.3 性能优化措施

1. **图片优化**：Logo 使用 SVG，分享图使用 WebP 格式
2. **代码分割**：VitePress 自动按路由分割 JS
3. **字体优化**：系统字体栈，不引入外部字体
4. **预渲染**：VitePress 静态生成，无需客户端渲染
5. **CDN 缓存**：Cloudflare 自动缓存静态资源，TTL 1 年

---

## 七、交互功能设计

### 7.1 终端风格代码演示（Phase 2）

用 Vue 组件实现一个自动播放的终端模拟器：

```vue
<!-- homepage/.vitepress/theme/components/CodeDemo.vue -->
<template>
  <div class="terminal">
    <div class="terminal-header">
      <span class="dot red"></span>
      <span class="dot yellow"></span>
      <span class="dot green"></span>
      <span class="title">Terminal</span>
    </div>
    <div class="terminal-body">
      <pre><code>{{ displayedText }}<span class="cursor">|</span></code></pre>
    </div>
  </div>
</template>
```

**交互逻辑**：
1. 页面加载后 1 秒开始播放
2. 逐字输出 curl 命令（50ms/字）
3. 暂停 500ms 后输出返回结果
4. 循环播放，支持鼠标悬停暂停

### 7.2 在线指令试用（Phase 3）

在首页嵌入一个简洁的指令发送表单：

```vue
<!-- homepage/.vitepress/theme/components/TryDirective.vue -->
<template>
  <div class="try-directive">
    <input v-model="directive" placeholder="指令:基础应用;天气查询,明天,威海" />
    <button @click="send" :disabled="loading">发送</button>
    <pre v-if="result">{{ result }}</pre>
    <p v-if="error" class="error">{{ error }}</p>
  </div>
</template>
```

**设计要点**：
- 使用公共端点 `test.text-cli.com`，无需用户注册
- 预设 3 个示例指令，用户可点击切换
- 返回结果格式化高亮显示
- 限流：每分钟最多 5 次（前端控制）

### 7.3 GitHub Star 计数器（Phase 2）

在 Header 显示实时 Star 数：

```vue
<!-- 通过 GitHub API 获取 Star 数 -->
<script setup>
import { ref, onMounted } from 'vue'
const stars = ref(0)
onMounted(async () => {
  const res = await fetch('https://api.github.com/repos/weihai-limh/text-cli')
  const data = await res.json()
  stars.value = data.stargazers_count
})
</script>
```

---

## 八、内容同步策略

### 8.1 内容来源映射

| 首页区域 | 内容源 | 同步方式 |
|:---|:---|:---|
| Hero 文案 | `README.md` 首段 | 手动同步（低频） |
| 价值卡片 | `README.md` 核心价值章节 | 手动同步（低频） |
| 角色入口 | `README.md` 角色表格 | 手动同步（低频） |
| 快速体验 | `README.md` 快速体验章节 | 手动同步（代码块需维护） |
| 文档链接 | `docs/` 目录 | 链接手动维护，CI 检查有效性 |
| 生态概览 | `Production_TCC_CN.md` + `.agents/README.md` | 手动同步（低频） |

### 8.2 链接有效性检查

在 CI 中集成链接检查器，确保首页所有外部链接有效：

```yaml
# .github/workflows/check-homepage-links.yml
- name: Check links
  run: npx markdown-link-check homepage/index.md
```

---

## 九、实施计划

| 阶段 | 任务 | 产出 | 依赖 |
|:---|:---|:---|:---|
| **Phase 1** | 搭建 VitePress 骨架 + Cloudflare Pages 配置 | 可访问的空白站点 | lemondy 配置 Cloudflare 账号 |
| **Phase 2** | 撰写首页 Markdown 内容 + 基础样式 | 首页初版上线 | Phase 1 完成 |
| **Phase 3** | Vue 交互组件（终端演示 + 在线试用） | 交互式首页 | Phase 2 完成 |
| **Phase 4** | SEO 优化 + 性能调优 + 链接检查 | Lighthouse >90 | Phase 2 完成 |
| **Phase 5** | 自定义域名 + SSL + 分析工具 | 正式发布 | lemondy 配置 DNS |

### 9.1 lemondy 需要配合的事项

| 事项 | 说明 |
|:---|:---|
| Cloudflare 账号 | 创建 Pages 项目，配置 API Token |
| 域名 DNS | 将 `text-cli.com` CNAME 指向 Cloudflare Pages |
| GitHub Secrets | 在仓库 Settings 中配置 `CLOUDFLARE_API_TOKEN` 和 `CLOUDFLARE_ACCOUNT_ID` |

---

## 十、备选方案

### 10.1 如果不使用 VitePress

| 方案 | 优点 | 缺点 |
|:---|:---|:---|
| **纯 HTML + CSS** | 零依赖，极致轻量 | 维护成本高，无法复用 Markdown |
| **Astro** | 岛屿架构，部分交互 | 学习成本较高，生态较新 |
| **Hugo** | 构建极快 | Go 模板语法，非 JS 生态 |
| **Next.js** | 功能完整 | 过重，SSR 对纯静态页面无必要 |

### 10.2 如果不使用 Cloudflare Pages

| 方案 | 优点 | 缺点 |
|:---|:---|:---|
| **GitHub Pages** | 零成本，与仓库集成 | 无自定义域名 SSL（需额外配置） |
| **Vercel** | 部署简单，预览 URL | 免费版有限流 |
| **Netlify** | 功能丰富 | 免费版构建分钟数有限 |

---

> 文档的价值不在于写了多少，而在于它能引导多少人走对第一步。
>
> —— Lumen ✦ ，2026-05-04
