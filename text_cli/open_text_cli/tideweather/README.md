# tideweather

Weather forecast query with dual-source fallback.

## Install

```
AI:text-cli;install,tideweather
```

## Dependencies

**Runtime**: Node.js (v18+). No npm packages required — uses built-in `fetch`.

## Directives

| Directive | Description |
|-----------|-------------|
| `tideweather;query,<date>,<city>` | Query weather forecast. Date: `today`/`tomorrow`/`day after tomorrow`. City: name in Chinese or English. Chinese alias: `天气;查询` |

## Example

```
AI:tideweather;query,tomorrow,Beijing
→ 2026-05-20 Beijing, China: 22-30°C, clear, sunrise 04:54, sunset 19:27

AI:天气;查询,后天,东京
→ 2026-05-21 東京, Japan: 18-25°C, cloudy, sunrise 04:32, sunset 18:55
```

## Architecture

```
A3 Service extension (node runtime)
  ├── tideweather.js  — subprocess handler (stdin JSON → stdout text)
  └── schema.json   — directive declaration

Data sources:
  Primary: Open-Meteo API (geocoding + forecast)
  Fallback: wttr.in
```
