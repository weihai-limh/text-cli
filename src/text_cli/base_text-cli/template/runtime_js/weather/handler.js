// weather JS — Dual-source weather query with i18n
// Zero external dependencies. Uses fetch (Node 18+ built-in).
// Open-Meteo (primary) -> wttr.in (fallback).
// i18n: zh / en / ja.

"use strict";

// ─── i18n ────────────────────────────────────────────

const I18N = {
  zh: {
    city_not_found: "未找到城市：{city}",
    both_unavailable: "天气服务暂不可用",
    sunrise: "日出",
    sunset: "日落",
    temp_range: "温度范围",
    source_open_meteo: "Open-Meteo",
    source_wttr: "wttr.in",
    today: "今天",
  },
  en: {
    city_not_found: "City not found: {city}",
    both_unavailable: "Weather service unavailable",
    sunrise: "Sunrise",
    sunset: "Sunset",
    temp_range: "Temperature range",
    source_open_meteo: "Open-Meteo",
    source_wttr: "wttr.in",
    today: "today",
  },
  ja: {
    city_not_found: "\u90fd\u5e02\u304c\u898b\u3064\u304b\u308a\u307e\u305b\u3093\uff1a{city}",
    both_unavailable: "\u5929\u6c17\u30b5\u30fc\u30d3\u30b9\u306f\u5229\u7528\u3067\u304d\u307e\u305b\u3093",
    sunrise: "\u65e5\u306e\u51fa",
    sunset: "\u65e5\u6ca1",
    temp_range: "\u6c17\u6e29\u7bc4\u56f2",
    source_open_meteo: "Open-Meteo",
    source_wttr: "wttr.in",
    today: "\u4eca\u65e5",
  },
};

const LANGS = Object.keys(I18N);
const DEFAULT_LANG = "zh";

// date aliases for multi-language input
const DATE_ALIASES = {
  "\u4eca\u5929": "today",
  "\u4eca\u65e5": "today",
  "today": "today",
};

// ─── Helpers ─────────────────────────────────────────

async function httpGetJSON(url) {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.json();
}

function normalizeDate(dateStr) {
  if (!dateStr) return new Date().toISOString().split("T")[0];
  const key = DATE_ALIASES[dateStr.toLowerCase()] || dateStr;
  if (key === "today") return new Date().toISOString().split("T")[0];
  // pass through — assume ISO format or let API reject
  return dateStr;
}

// ─── Geocoding (Open-Meteo) ──────────────────────────

async function geocode(city) {
  const url = `https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(city)}&count=1&language=en&format=json`;
  const data = await httpGetJSON(url);
  if (!data.results || data.results.length === 0) {
    throw new Error("CITY_NOT_FOUND");
  }
  const r = data.results[0];
  return { lat: r.latitude, lon: r.longitude, name: r.name, country: r.country || "" };
}

// ─── Open-Meteo ──────────────────────────────────────

async function openMeteo(lat, lon, dateStr) {
  const url = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&daily=temperature_2m_max,temperature_2m_min,sunrise,sunset,weather_code&timezone=auto&start_date=${dateStr}&end_date=${dateStr}`;
  const data = await httpGetJSON(url);
  if (!data.daily) throw new Error("no daily data");
  const d = data.daily;
  return {
    temp_min: d.temperature_2m_min[0],
    temp_max: d.temperature_2m_max[0],
    sunrise: d.sunrise[0],
    sunset: d.sunset[0],
    weather_code: d.weather_code[0],
    date: dateStr,
  };
}

// ─── wttr.in fallback ────────────────────────────────

async function wttrFallback(city, dateStr, lang) {
  const l = lang === "zh" ? "zh" : (lang === "ja" ? "ja" : "en");
  const url = `https://wttr.in/${encodeURIComponent(city)}?format=j1&lang=${l}`;
  const data = await httpGetJSON(url);
  const day = dateStr || new Date().toISOString().split("T")[0];
  const weather = data.weather || [];
  let entry = null;
  for (const w of weather) {
    if (w.date === day) { entry = w; break; }
  }
  if (!entry) entry = weather[0] || {};
  return {
    temp_min: parseInt(entry.mintempC) || 0,
    temp_max: parseInt(entry.maxtempC) || 0,
    sunrise: entry.astronomy ? entry.astronomy[0].sunrise : "N/A",
    sunset: entry.astronomy ? entry.astronomy[0].sunset : "N/A",
    weather_code: 0,
    date: day,
  };
}

// ─── Render ──────────────────────────────────────────

function render(data, lang) {
  const t = I18N[lang] || I18N[DEFAULT_LANG];
  const sourceLabel = data.source === "open-meteo" ? t.source_open_meteo : t.source_wttr;
  return [
    `${data.city}, ${data.date}`,
    `${t.temp_range}: ${data.temp_min}\u00b0C ~ ${data.temp_max}\u00b0C`,
    `${data.weather_desc || ""}`,
    `${t.sunrise}: ${data.sunrise}  ${t.sunset}: ${data.sunset}`,
    `(${sourceLabel})`,
  ].filter(Boolean).join("\n");
}

// ─── Handler ─────────────────────────────────────────

async function handler(params) {
  const city = params[0];
  if (!city) return { status: "error", reason: "city is required" };

  const dateStr = normalizeDate(params[1] || "");
  let lang = (params[2] || DEFAULT_LANG).toLowerCase();
  if (!LANGS.includes(lang)) lang = DEFAULT_LANG;

  let geo;
  try {
    geo = await geocode(city);
  } catch (e) {
    if (e.message === "CITY_NOT_FOUND") {
      const t = I18N[lang] || I18N[DEFAULT_LANG];
      return { status: "error", reason: t.city_not_found.replace("{city}", city) };
    }
    return { status: "error", reason: e.message };
  }

  let data, source;
  try {
    data = await openMeteo(geo.lat, geo.lon, dateStr);
    source = "open-meteo";
  } catch (e) {
    try {
      data = await wttrFallback(city, dateStr, lang);
      source = "wttr.in";
    } catch (e2) {
      const t = I18N[lang] || I18N[DEFAULT_LANG];
      return { status: "error", reason: t.both_unavailable };
    }
  }

  return {
    status: "ok",
    result: render({ ...data, city: geo.name, source }, lang),
    source,
    lang,
    city: geo.name,
    date: data.date,
    temp_min: data.temp_min,
    temp_max: data.temp_max,
    weather_code: data.weather_code || 0,
    weather_desc: data.weather_desc || "",
    sunrise: data.sunrise,
    sunset: data.sunset,
  };
}

module.exports = {
  domainAlias: "\u5929\u6c14",
  directives: {
    query: {
      handler,
      actionAliases: ["\u67e5\u8be2"],
    },
  },
};
