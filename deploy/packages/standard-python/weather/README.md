# weather-query

Weather forecast by city and date. Open-Meteo (free, no API key) is the primary
source with wttr.in as automatic fallback. Zero dependencies — only the Python
standard-library `urllib`. Translation is done inside the package (handler-side
i18n); the endpoint is just a forward pipe, so output supports zh / en / ja.

## Install

```
AI:text-cli;install,weather-query
```

## Directives

| Directive | Description |
|-----------|-------------|
| `weather;query,<city>[,<date>[,<lang>]]` | Get weather forecast (temperature range, condition, sunrise/sunset) for a city on a date |
| `天气;查询,<城市>[,<日期>[,<语言>]]` | Chinese alias — same behavior, routed by the runtime alias mechanism |

## Parameters

- `city` — city name in Chinese or English, e.g. 威海 / Weihai / London
- `date` — `today` / `tomorrow` / `day after tomorrow`, or `YYYY-MM-DD` (default: today). Accepts multilingual input (今天 / 明日 / today …), which is normalized before rendering.
- `lang` — output language: `zh` (default) | `en` | `ja`. Out-of-range values degrade gracefully to `zh` (this is the output layer, not the `ERR_NOT_FOUND` routing layer).

## Example

```
AI:weather;query,威海,明天
→ {"status":"ok","result":"2026-07-30 威海天气: 25.0℃到33.4℃, 雷雨, 日出2026-07-30T04:53, 日落2026-07-30T19:02","source":"open-meteo","lang":"zh",...}

AI:weather;query,Weihai,tomorrow,en
→ {"status":"ok","result":"Weather in Weihai on 2026-07-30: 25.0–33.4°C, Thunderstorm, sunrise 2026-07-30T04:53, sunset 2026-07-30T19:02","source":"open-meteo","lang":"en",...}

AI:weather;query,Weihai,2026-07-30,ja
→ {"status":"ok","result":"2026-07-30 Weihaiの天気: 25.0〜33.4℃, 雷雨, 日の出2026-07-30T04:53, 日の入り2026-07-30T19:02","source":"open-meteo","lang":"ja",...}

AI:天气;查询,北京,今天
→ routes via the Chinese alias, same result shape.

AI:weather;query,不存在的城市XYZ,今天
→ {"status":"error","reason":"找不到城市: 不存在的城市XYZ"}
```

## Error envelope (important)

The business-level error uses the **`reason`** field (per `package-dev-guide` §2.4
and the SPEC inner envelope), e.g. `{"status":"error","reason":"找不到城市: …"}`.
Do **not** rename it to `message` — some older guide samples use `message`, but the
runtime parses `reason`. The outer transport-level error field is `rst_err`, which
is a separate concern and stays empty on a business error.

## Architecture

```
weather-query/
├── schema.json   — package declaration (directives, locales, params)
└── handler.py    — @directive("weather","query", domain_alias="天气", action_aliases={"query":"查询"})
                    → urllib → Open-Meteo / wttr.in → I18N.render
```

Both sources return only the WMO weather code; translation happens exactly once
in the `I18N` table. `I18N` is the single source of truth for all localized
strings (sentence templates, WMO code descriptions, and error messages). Adding a
language means adding one subtree — no handler logic needs to change.
