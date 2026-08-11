# weather-query 天气查询

按城市与日期查询天气预报。主数据源为 Open-Meteo（免费、无需密钥），失败自动降级到 wttr.in。零依赖，仅用 Python 标准库 `urllib`。翻译在包内完成（handler 侧 i18n），端点只做转发，因此输出支持中文 / 英文 / 日文。

## 安装

```
AI:text-cli;install,weather-query
```

## 支持指令

| 指令 | 说明 |
|------|------|
| `weather;query,<城市>[,<日期>[,<语言>]]` | 按城市与日期查询天气预报（温度区间、天气状况、日出日落） |
| `天气;查询,<城市>[,<日期>[,<语言>]]` | 中文别名，行为一致，由运行时别名机制路由 |

## 参数

- `city` — 城市名，中文或英文，如 威海 / Weihai / London
- `date` — `今天` / `明天` / `后天`，或 `YYYY-MM-DD`（默认：今天）。支持多语言输入（今天 / 明日 / today …），渲染前会归一化
- `lang` — 输出语言：`zh`（默认）| `en` | `ja`。越界值优雅降级为 `zh`（这是输出层职责，不是路由层的 `ERR_NOT_FOUND`）

## 示例

```
AI:weather;query,威海,明天
→ {"status":"ok","result":"2026-07-30 威海天气: 25.0℃到33.4℃, 雷雨, 日出2026-07-30T04:53, 日落2026-07-30T19:02","source":"open-meteo","lang":"zh",...}

AI:weather;query,Weihai,tomorrow,en
→ {"status":"ok","result":"Weather in Weihai on 2026-07-30: 25.0–33.4°C, Thunderstorm, sunrise 2026-07-30T04:53, sunset 2026-07-30T19:02","source":"open-meteo","lang":"en",...}

AI:weather;query,Weihai,2026-07-30,ja
→ {"status":"ok","result":"2026-07-30 Weihaiの天気: 25.0〜33.4℃, 雷雨, 日の出2026-07-30T04:53, 日の入り2026-07-30T19:02","source":"open-meteo","lang":"ja",...}

AI:天气;查询,北京,今天
→ 经中文别名路由，返回结构相同。

AI:weather;query,不存在的城市XYZ,今天
→ {"status":"error","reason":"找不到城市: 不存在的城市XYZ"}
```

## 错误信封（重要）

业务级错误使用 **`reason`** 字段（遵循 `package-dev-guide` §2.4 与 SPEC 内层信封），
例如 `{"status":"error","reason":"找不到城市: …"}`。请勿改名为 `message`——部分旧指南示例
用的是 `message`，但运行时解析的是 `reason`。外层传输级错误字段是 `rst_err`，属另一回事，
业务错误时它保持为空。

## 架构

```
weather-query/
├── schema.json   — 包声明（指令、locales、参数）
└── handler.py    — @directive("weather","query", domain_alias="天气", action_aliases={"query":"查询"})
                    → urllib → Open-Meteo / wttr.in → I18N.render
```

两个数据源都只返回 WMO 天气码，翻译只在 `I18N` 表里发生一次。`I18N` 表是所有本地化文案（句子模板、WMO 天气码描述、错误文案）的唯一真相源。新增语言只需加一棵子树，handler 逻辑零改动。
