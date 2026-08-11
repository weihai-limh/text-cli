#!/usr/bin/env python3
"""
weather-query — text-cli online-API directive package (implementation side, text-cli-A9 runtime)

Data sources: Open-Meteo free weather API (primary) + wttr.in (fallback)
Both sources are free and require no API key, so this package has no credentials and
uses only the standard-library `urllib` (zero pip dependencies).

Registration contract (consistent with core/registry.py):
    @directive(domain, action, domain_alias=..., action_aliases={...})
    def handler(params: list[str]) -> dict:   # returns a protocol envelope dict

Internationalization (handler-side i18n — the endpoint is only a forward pipe,
translation lives in the package):
    - Input intent i18n is provided by the runtime alias mechanism (domain_alias /
      action_aliases): weather;query / 天气;查询 / mixed forms all route
      (service-side alias registration per SPEC §8).
    - Output language is controlled by params[2] = lang (default zh, also en / ja).
      Translation is fully data-driven: the I18N table is the single source of truth;
      adding a language means adding one subtree, zero logic changes.
    - The date argument also accepts multilingual input (今天/today/今日...), which is
      normalized to a canonical key before rendering.
"""

import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from core.registry import directive


class CityNotFound(Exception):
    """Raised when a city cannot be resolved by the geocoding source."""


# ── i18n resources (single source of truth) ──────────────────────────────
#
# Each language is a complete resource subtree: the sentence `template`, an
# `unknown` fallback word, a `table` mapping WMO weather codes to localized
# descriptions, and an `errors` subtree of user-facing error messages. Weather
# sources return only the WMO code; translation happens exactly once here. The
# output always renders the concrete date (YYYY-MM-DD), which is language-neutral.
# To add a language, add one subtree — no other code needs to change.

I18N = {
    "zh": {
        "template": "{date} {city}天气: {tmin}℃到{tmax}℃, {desc}, 日出{sunrise}, 日落{sunset}",
        "unknown": "未知",
        "table": {
            0: "晴", 1: "大致晴朗", 2: "局部多云", 3: "阴",
            45: "雾", 48: "雾凇",
            51: "小毛毛雨", 53: "毛毛雨", 55: "大毛毛雨",
            56: "冻毛毛雨", 57: "强冻毛毛雨",
            61: "小雨", 63: "中雨", 65: "大雨",
            66: "冻雨", 67: "强冻雨",
            71: "小雪", 73: "中雪", 75: "大雪", 77: "雪粒",
            80: "阵雨", 81: "强阵雨", 82: "暴雨",
            85: "阵雪", 86: "强阵雪",
            95: "雷雨", 96: "雷雨伴冰雹", 99: "强雷雨伴冰雹",
        },
        "errors": {
            "usage": "用法: weather;query,<城市>[,<日期>[,<语言>]]",
            "city_not_found": "找不到城市: {city}",
            "both_unavailable": "天气查询失败（双源均不可用）: {error}",
        },
    },
    "en": {
        "template": "Weather in {city} on {date}: {tmin}–{tmax}°C, {desc}, sunrise {sunrise}, sunset {sunset}",
        "unknown": "Unknown",
        "table": {
            0: "Clear", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
            45: "Fog", 48: "Rime fog",
            51: "Light drizzle", 53: "Drizzle", 55: "Dense drizzle",
            56: "Freezing drizzle", 57: "Heavy freezing drizzle",
            61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
            66: "Freezing rain", 67: "Heavy freezing rain",
            71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow", 77: "Snow grains",
            80: "Rain showers", 81: "Heavy rain showers", 82: "Violent rain showers",
            85: "Snow showers", 86: "Heavy snow showers",
            95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Severe thunderstorm with hail",
        },
        "errors": {
            "usage": "usage: weather;query,<city>[,<date>[,<lang>]]",
            "city_not_found": "city not found: {city}",
            "both_unavailable": "weather query failed (both sources unavailable): {error}",
        },
    },
    "ja": {
        "template": "{date} {city}の天気: {tmin}〜{tmax}℃, {desc}, 日の出{sunrise}, 日の入り{sunset}",
        "unknown": "不明",
        "table": {
            0: "晴れ", 1: "おおむね晴れ", 2: "一部曇り", 3: "曇り",
            45: "霧", 48: "霧氷",
            51: "弱い霧雨", 53: "霧雨", 55: "強い霧雨",
            56: "着氷性霧雨", 57: "強い着氷性霧雨",
            61: "弱い雨", 63: "雨", 65: "強い雨",
            66: "着氷性の雨", 67: "強い着氷性の雨",
            71: "弱い雪", 73: "雪", 75: "強い雪", 77: "雪粒",
            80: "にわか雨", 81: "強いにわか雨", 82: "激しいにわか雨",
            85: "雪のにわか降り", 86: "強い雪のにわか降り",
            95: "雷雨", 96: "ひょうを伴う雷雨", 99: "激しいひょうを伴う雷雨",
        },
        "errors": {
            "usage": "使い方: weather;query,<都市>[,<日付>[,<言語>]]",
            "city_not_found": "都市が見つかりません: {city}",
            "both_unavailable": "天気取得に失敗しました（両方のソースが利用不可）: {error}",
        },
    },
}

# Supported languages are derived from I18N keys (add a language = add a subtree,
# nothing gets missed).
LANGS = list(I18N.keys())          # ["zh", "en", "ja"]
DEFAULT_LANG = "zh"


# ── date input parsing (multilingual → canonical key) ────────────────────
#
# Input layer: map relative date words from any language to a canonical key
# (today / tomorrow / after_tomorrow), then convert to YYYY-MM-DD for the weather
# source. This is fully separated from output rendering.

_DATE_ALIASES = {
    "today": ["今天", "今日", "本日", "today"],
    "tomorrow": ["明天", "明日", "tomorrow"],
    "after_tomorrow": ["后天", "明後日", "day after tomorrow", "dayaftertomorrow"],
}
_DATE_OFFSET = {"today": 0, "tomorrow": 1, "after_tomorrow": 2}
_DATE_LOOKUP = {a.lower(): k for k, alist in _DATE_ALIASES.items() for a in alist}


def _normalize_date(raw):
    """Map any-language relative date word / YYYY-MM-DD → (YYYY-MM-DD, canonical_key|None).

    The canonical key is only used internally (day-index for the wttr.in fallback);
    the output layer always renders the concrete date string, never a friendly word.
    """
    key = (raw or "").strip().lower()
    if key in _DATE_LOOKUP:
        canon = _DATE_LOOKUP[key]
        target = (datetime.now() + timedelta(days=_DATE_OFFSET[canon])).strftime("%Y-%m-%d")
        return target, canon
    try:
        datetime.strptime(raw, "%Y-%m-%d")
        return raw, None
    except (ValueError, TypeError):
        return datetime.now().strftime("%Y-%m-%d"), "today"


def _http_get_json(url, params=None, timeout=10):
    full = url if not params else url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(full, headers={"User-Agent": "text-cli-weather/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ── primary source: Open-Meteo (returns WMO code, untranslated) ──────────

def _geocode(city):
    data = _http_get_json(
        "https://geocoding-api.open-meteo.com/v1/search",
        {"name": city, "count": 1, "language": "zh"},
    )
    results = data.get("results") or []
    if not results:
        raise CityNotFound(city)
    r = results[0]
    return r["latitude"], r["longitude"], r.get("timezone", "Asia/Shanghai")


def _open_meteo(city, date_str):
    lat, lon, tz = _geocode(city)
    data = _http_get_json(
        "https://api.open-meteo.com/v1/forecast",
        {
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_max,temperature_2m_min,weather_code,sunrise,sunset",
            "timezone": tz,
            "start_date": date_str,
            "end_date": date_str,
        },
    )
    d = data["daily"]
    return {
        "city": city,
        "date": date_str,
        "temp_min": d["temperature_2m_min"][0],
        "temp_max": d["temperature_2m_max"][0],
        "weather_code": int(d["weather_code"][0]),   # code only; translated via I18N
        "sunrise": d["sunrise"][0],
        "sunset": d["sunset"][0],
    }


# ── fallback source: wttr.in (also returns only the WMO code) ────────────

def _wttr_fallback(city, date_str):
    # The fallback also needs relative date → day index; reuse the normalizer.
    _, canon = _normalize_date(date_str)
    day_idx = _DATE_OFFSET.get(canon, 0)
    data = _http_get_json(
        "https://wttr.in/" + urllib.parse.quote(city),
        {"format": "j1"},
    )
    weather = data["weather"]
    if day_idx >= len(weather):
        day_idx = 0
    w = weather[day_idx]
    astro = w["astronomy"][0]
    code = int(w["hourly"][0]["weatherCode"])   # take the WMO code, translate uniformly
    return {
        "city": city,
        "date": w["date"],
        "temp_min": int(w["mintempC"]),
        "temp_max": int(w["maxtempC"]),
        "weather_code": code,
        "sunrise": astro["sunrise"],
        "sunset": astro["sunset"],
    }


# ── output rendering (pure data-driven i18n) ─────────────────────────────

def _render(data, lang):
    i18n = I18N.get(lang, I18N[DEFAULT_LANG])
    desc = i18n["table"].get(data["weather_code"], i18n["unknown"])
    return i18n["template"].format(
        date=data["date"],
        city=data["city"],
        tmin=data["temp_min"],
        tmax=data["temp_max"],
        desc=desc,
        sunrise=data["sunrise"],
        sunset=data["sunset"],
    )


def _err(key, lang, **kwargs):
    """Build a localized error envelope dict."""
    msg = I18N.get(lang, I18N[DEFAULT_LANG])["errors"][key].format(**kwargs)
    return {"status": "error", "reason": msg}


# ── register as a text-cli directive ─────────────────────────────────────

@directive("weather", "query", domain_alias="天气", action_aliases={"query": "查询"})
def query(params: list[str]) -> dict:
    """Weather query: weather;query,<city>[,<date>[,<lang>]]"""
    if not params:
        return _err("usage", DEFAULT_LANG)

    city = params[0].strip()
    raw_date = params[1].strip() if len(params) > 1 and params[1].strip() else ""
    lang = (params[2].strip().lower() if len(params) > 2 and params[2].strip() else DEFAULT_LANG)
    # Out-of-range language: gracefully degrade to the default (not ERR_NOT_FOUND,
    # which is the routing layer's responsibility).
    if lang not in I18N:
        lang = DEFAULT_LANG

    date_str, _ = _normalize_date(raw_date)

    # Primary source first, auto-fallback to wttr.in on failure.
    try:
        data = _open_meteo(city, date_str)
        source = "open-meteo"
    except CityNotFound:
        return _err("city_not_found", lang, city=city)
    except Exception:
        try:
            data = _wttr_fallback(city, date_str)
            source = "wttr.in"
        except Exception as e:
            return _err("both_unavailable", lang, error=str(e))

    text = _render(data, lang)
    return {
        "status": "ok",
        "result": text,
        "source": source,
        "lang": lang,
        "city": data["city"],
        "date": data["date"],
        "temp_min": data["temp_min"],
        "temp_max": data["temp_max"],
        "weather_code": data["weather_code"],
        "weather_desc": I18N[lang]["table"].get(data["weather_code"], I18N[lang]["unknown"]),
        "sunrise": data["sunrise"],
        "sunset": data["sunset"],
    }
