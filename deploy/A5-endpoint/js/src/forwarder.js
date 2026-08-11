const DEFAULT_TIMEOUT_MS = 30_000;
const DEFAULT_MAX_RETRIES = 1;

export async function forwardRequest({
  parsed,
  backendUrl,
  prompt,
  serviceToken,
  accessTokenPrefix,
  db,
  timeout,
  maxRetries,
}) {
  const requestTimeout = timeout || DEFAULT_TIMEOUT_MS;
  const retries = maxRetries ?? DEFAULT_MAX_RETRIES;

  const requestId = crypto.randomUUID();
  const headers = { 'Content-Type': 'application/json' };
  if (serviceToken) {
    headers['Service-token'] = serviceToken;
  }

  let lastError = null;
  let result = null;

  for (let attempt = 0; attempt <= retries; attempt++) {
    const start = Date.now();
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), requestTimeout);

      const resp = await fetch(backendUrl + '/text-cli/cli', {
        method: 'POST',
        headers,
        body: JSON.stringify({ prompt }),
        signal: controller.signal,
      });

      clearTimeout(timer);
      const elapsed = Date.now() - start;
      const body = await resp.text();

      result = {
        statusCode: resp.status,
        body,
        responseTimeMs: elapsed,
      };

      if (resp.status >= 500 && attempt < retries) {
        lastError = `5xx ${resp.status}`;
        continue;
      }

      break;
    } catch (err) {
      const elapsed = Date.now() - start;

      if (err.name === 'AbortError') {
        lastError = 'timeout';
        result = {
          statusCode: 408,
          body: '{"rst_types":"text","rst_data":{"text":"request to backend timed out"}}',
          responseTimeMs: elapsed,
          errorMessage: 'timeout',
        };
      } else {
        lastError = String(err);
        result = {
          statusCode: 502,
          body: '{"rst_types":"text","rst_data":{"text":"backend request failed"}}',
          responseTimeMs: elapsed,
          errorMessage: String(err),
        };
      }

      if (attempt < retries) continue;
      break;
    }
  }

  const serviceTokenPrefix = serviceToken && serviceToken.length > 8
    ? serviceToken.slice(0, 8) + '***'
    : '';

  await logCall(db, {
    requestId,
    directive: parsed.raw,
    domain: parsed.domain,
    action: parsed.action,
    backendUrl,
    serviceTokenPrefix,
    access_token_prefix: accessTokenPrefix || '',
    statusCode: result?.statusCode || 0,
    responseTimeMs: result?.responseTimeMs || 0,
    errorMessage: result?.errorMessage || lastError,
  });

  await updateDailyStats(db, {
    domain: parsed.domain,
    action: parsed.action,
    statusCode: result?.statusCode || 0,
    responseTimeMs: result?.responseTimeMs || 0,
  });

  return result;
}

async function logCall(db, data) {
  if (!db) return;
  try {
    await db
      .prepare(
        `INSERT INTO call_logs
         (request_id, directive, domain, action, backend_url,
          service_token_prefix, access_token_prefix,
          status_code, response_time_ms, error_message)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
      )
      .bind(
        data.requestId,
        data.directive,
        data.domain,
        data.action,
        data.backendUrl,
        data.serviceTokenPrefix,
        data.access_token_prefix,
        data.statusCode,
        data.responseTimeMs,
        data.errorMessage || null
      )
      .run();
  } catch {
    // ignore
  }
}

async function updateDailyStats(db, data) {
  if (!db) return;
  try {
    const today = new Date().toISOString().slice(0, 10);
    const isSuccess = data.statusCode === 200 ? 1 : 0;

    const existing = await db
      .prepare(
        'SELECT id, call_count, success_count, avg_response_ms FROM daily_stats WHERE date = ? AND domain = ? AND action = ?'
      )
      .bind(today, data.domain, data.action)
      .first();

    if (existing) {
      const newCount = existing.call_count + 1;
      const newSuccess = existing.success_count + isSuccess;
      const newAvg = Math.floor(
        (existing.avg_response_ms * existing.call_count + data.responseTimeMs) / newCount
      );
      await db
        .prepare(
          'UPDATE daily_stats SET call_count = ?, success_count = ?, avg_response_ms = ? WHERE id = ?'
        )
        .bind(newCount, newSuccess, newAvg, existing.id)
        .run();
    } else {
      await db
        .prepare(
          'INSERT INTO daily_stats (date, domain, action, call_count, success_count, avg_response_ms) VALUES (?, ?, ?, ?, ?, ?)'
        )
        .bind(today, data.domain, data.action, 1, isSuccess, data.responseTimeMs)
        .run();
    }
  } catch {
    // ignore
  }
}
