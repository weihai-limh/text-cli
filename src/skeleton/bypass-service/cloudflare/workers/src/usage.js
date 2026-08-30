// usage — 请求方调用计次（挂 Service-token requester_id）
//
// 复用 quota 的"周期翻转 + 原子 check+consume"语义，维度从 target 加 requester_id：
// usage 表 (requester_id, target, usage_date) 复合主键；limit 存 requester_id='default' 模板行。
// Cloudflare 红利：D1 跨节点统一计次。
// 协议红线：配额耗尽 → {status:"stop"} 降级信号（非错误），绝不出 SERVICE_DENIED。

const today = () => new Date().toISOString().slice(0, 10);
const DEFAULT = "default";

export async function registerUsage(db, params) {
  // quota;register,<target>,<limit>[,<cycle>]
  const target = params[0];
  const limit = Number(params[1]);
  const cycle = params[2] || "day";
  if (!target || !Number.isInteger(limit) || limit < 0) return { ok: false, error: "usage: quota;register,<target>,<limit>[,<cycle>]" };
  await db
    .prepare(
      "INSERT INTO usage (requester_id, target, cycle, limit, used, usage_date) VALUES (?, ?, ?, ?, 0, ?) " +
        "ON CONFLICT(requester_id, target, usage_date) DO UPDATE SET limit = excluded.limit, cycle = excluded.cycle",
    )
    .bind(DEFAULT, target, cycle, limit, today())
    .run();
  return { ok: true, target, limit, cycle };
}

async function getLimit(db, target) {
  const row = await db.prepare("SELECT limit FROM usage WHERE requester_id = ? AND target = ? AND usage_date = ?")
    .bind(DEFAULT, target, today())
    .first();
  return row ? row.limit : null;
}

/** 原子 check+consume：耗尽 → stop（不扣减）；否则 used+1 */
export async function checkAndConsume(db, requesterId, target) {
  const limit = await getLimit(db, target);
  if (limit === null) return { status: "ok" }; // 未注册配额 → 放行
  const date = today();
  const row = await db.prepare("SELECT used FROM usage WHERE requester_id = ? AND target = ? AND usage_date = ?")
    .bind(requesterId, target, date)
    .first();
  const used = row ? row.used : 0;
  if (used >= limit) return { status: "stop", used, limit };
  const next = used + 1;
  await db
    .prepare(
      "INSERT INTO usage (requester_id, target, cycle, limit, used, usage_date) VALUES (?, ?, ?, ?, ?, ?) " +
        "ON CONFLICT(requester_id, target, usage_date) DO UPDATE SET used = excluded.used",
    )
    .bind(requesterId, target, "day", limit, next, date)
    .run();
  return { status: "ok", used: next, limit };
}

/**
 * withUsage 中间件：context.auth（Service-token 校验后注入）存在时按 requester_id 计次。
 * 耗尽 → stop 信封（降级信号，由下游聚合消费）。
 */
export function withUsage({ db, keyFor }) {
  const kf = keyFor || ((domain, action) => `${domain};${action}`);
  return (next) => async (domain, action, params, context) => {
    const requester = context && context.auth && context.auth.sub;
    if (!requester) return next(domain, action, params, context);
    const q = await checkAndConsume(db, requester, kf(domain, action));
    if (q.status === "stop") {
      return { rst_types: "text", rst_err: "", rst_data: { status: "stop", reason: "quota_exhausted", requester, target: kf(domain, action) } };
    }
    return next(domain, action, params, context);
  };
}
