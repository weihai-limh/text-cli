# tideweather · 天气查询

天气预报查询，双源降级。

## 安装

```
AI:text-cli;install,tideweather
```

## 依赖

**运行时**：Node.js（v18+）。无需 npm 包——使用内置 `fetch`。

## 指令

| 指令 | 说明 |
|------|------|
| `tideweather;query,<日期>,<城市>` | 查询天气预报。中文别名：`天气;查询` |

## 示例

```
AI:tideweather;query,明天,威海
→ 2026-05-20 威海, 中国天气: 15℃到17℃, 中雨, 日出04:38, 日落18:57

AI:天气;查询,后天,东京
→ 2026-05-21 東京, Japan: 18-25°C, cloudy, sunrise 04:32, sunset 18:55
```

## 架构

```
A3 Service 扩展（node runtime）
  ├── tideweather.js  — subprocess 处理器（stdin JSON → stdout 文本）
  └── schema.json     — 指令声明

数据源：
  主：Open-Meteo API（地理编码 + 预报）
  降级：wttr.in
```
