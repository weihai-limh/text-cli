/**
 * weather handler — text-cli instruction package (Node.js subprocess)
 *
 * Dual-source weather query: Open-Meteo (primary) → wttr.in (fallback).
 *
 * stdin:  {"domain":"tideweather","action":"query","params":["tomorrow","Beijing"]}
 * stdout: "2026-05-20 Beijing, China: 15-22°C, clear, sunrise 05:01, sunset 18:45"
 * exit:   0 = success, non-zero = error
 */

// ── Date keyword mapping ────────────────────────

const DAY_MAP = {
  '今天': 0, 'today': 0,
  '明天': 1, 'tomorrow': 1,
  '后天': 2, 'day after tomorrow': 2,
};

const WMO_CODES = {
  0: '晴', 1: '晴', 2: '多云', 3: '阴',
  45: '雾', 48: '雾凇',
  51: '小雨', 53: '中雨', 55: '大雨',
  61: '小雨', 63: '中雨', 65: '大雨',
  71: '小雪', 73: '中雪', 75: '大雪',
  80: '阵雨', 81: '中阵雨', 82: '大阵雨',
  85: '阵雪', 86: '大阵雪',
  95: '雷暴', 96: '雷暴+冰雹', 99: '强雷暴+冰雹',
};

// ── Utility functions ────────────────────────────

function parseDate(dateStr) {
  const key = dateStr.toLowerCase();
  if (DAY_MAP[key] !== undefined) return DAY_MAP[key];
  const match = key.match(/^(\d+)天$/i);
  if (match) return Math.min(parseInt(match[1]), 7);
  return 1;
}

function wmoToText(code) {
  return WMO_CODES[code] || '未知';
}

// ── Open-Meteo data source ──────────────────────

async function fetchOpenMeteo(city, dayOffset) {
  const geoUrl = `https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(city)}&count=1&language=zh`;
  const geoResp = await fetch(geoUrl);
  if (!geoResp.ok) throw new Error('Open-Meteo geocoding failed');
  const geoData = await geoResp.json();
  if (!geoData.results || geoData.results.length === 0) {
    throw new Error(`未找到城市: ${city}`);
  }

  const { latitude, longitude, name, country } = geoData.results[0];
  const displayName = country ? `${name}, ${country}` : name;

  const forecastDays = dayOffset + 2;
  const weatherUrl = `https://api.open-meteo.com/v1/forecast?latitude=${latitude}&longitude=${longitude}&daily=temperature_2m_max,temperature_2m_min,weathercode,sunrise,sunset&timezone=auto&forecast_days=${forecastDays}`;
  const weatherResp = await fetch(weatherUrl);
  if (!weatherResp.ok) throw new Error('Open-Meteo forecast failed');
  const weatherData = await weatherResp.json();

  const daily = weatherData.daily;
  const idx = Math.min(dayOffset, daily.time.length - 1);
  const date = daily.time[idx];
  const maxTemp = Math.round(daily.temperature_2m_max[idx]);
  const minTemp = Math.round(daily.temperature_2m_min[idx]);
  const weatherCode = daily.weathercode[idx];
  const weatherText = wmoToText(weatherCode);
  const sunrise = daily.sunrise ? daily.sunrise[idx].split('T')[1] : '--';
  const sunset = daily.sunset ? daily.sunset[idx].split('T')[1] : '--';

  return {
    source: 'Open-Meteo',
    text: `${date} ${displayName}天气: ${minTemp}℃到${maxTemp}℃, ${weatherText}, 日出${sunrise}, 日落${sunset}`,
  };
}

// ── wttr.in fallback ────────────────────────────

async function fetchWttrIn(city, dayOffset) {
  const url = `https://wttr.in/${encodeURIComponent(city)}?format=j1`;
  const resp = await fetch(url);
  if (!resp.ok) throw new Error('wttr.in request failed');
  const data = await resp.json();

  const weather = data.weather;
  if (!weather) throw new Error('wttr.in data format error');

  const dayIdx = Math.min(dayOffset, weather.length - 1);
  const day = weather[dayIdx];
  const date = day.date;
  const maxTemp = day.maxtempC;
  const minTemp = day.mintempC;
  const desc = day.hourly[4]?.weatherDesc?.[0]?.value || '未知';
  const astronomy = day.astronomy?.[0];
  const sunrise = astronomy?.sunrise || '--';
  const sunset = astronomy?.sunset || '--';

  return {
    source: 'wttr.in',
    text: `${date} ${city}天气: ${minTemp}℃到${maxTemp}℃, ${desc}, 日出${sunrise}, 日落${sunset}`,
  };
}

// ── Main handler ────────────────────────────────

async function handleWeather(date, city) {
  if (!date || !city) {
    return { error: '参数不足: 需要 <日期> 和 <城市>' };
  }

  const dayOffset = parseDate(date);

  try {
    return await fetchOpenMeteo(city, dayOffset);
  } catch (e1) {
    try {
      return await fetchWttrIn(city, dayOffset);
    } catch (e2) {
      return { error: `天气查询失败: Open-Meteo(${e1.message}), wttr.in(${e2.message})` };
    }
  }
}

// ── Subprocess entry ────────────────────────────

async function main() {
  const chunks = [];
  process.stdin.setEncoding('utf-8');
  for await (const chunk of process.stdin) {
    chunks.push(chunk);
  }

  let input;
  try {
    input = JSON.parse(chunks.join(''));
  } catch (e) {
    process.stderr.write(`tideweather: JSON parse error: ${e.message}`);
    process.exit(1);
  }

  const [date, city] = input.params || [];

  if (!date || !city) {
    process.stderr.write('tideweather: missing params (need <date>,<city>)');
    process.exit(1);
  }

  const result = await handleWeather(date, city);

  if (result.error) {
    process.stderr.write(`tideweather: ${result.error}`);
    process.exit(1);
  }

  process.stdout.write(result.text);
  process.exit(0);
}

main().catch((err) => {
  process.stderr.write(`tideweather: ${err.message}`);
  process.exit(1);
});
