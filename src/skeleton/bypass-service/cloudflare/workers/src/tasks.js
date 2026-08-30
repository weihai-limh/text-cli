// tasks — 异步任务（D1 tasks 表五态，不花钱：无 Queues/DO）
//
// 五态：pending / running / done / error / cancelled（对齐 SPEC §1.2.6）。
// 重启残留：running → error + service_restarted。
// 推进：真实 Worker 用 fetch 自唤醒 / 事件触发调用 runNext；本地测试手动推进。

export async function startTask(db, domain, action, params) {
  const taskId = `task-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
  await db
    .prepare("INSERT INTO tasks (task_id, domain, action, params, status, result_json, created_at, updated_at) VALUES (?, ?, ?, ?, 'pending', NULL, ?, ?)")
    .bind(taskId, domain, action, JSON.stringify(params || []), Date.now(), Date.now())
    .run();
  return { taskId };
}

export async function pollTask(db, taskId) {
  const row = await db.prepare("SELECT * FROM tasks WHERE task_id = ?").bind(taskId).first();
  if (!row) return { state: "not_found" };
  return {
    task_id: row.task_id,
    domain: row.domain,
    action: row.action,
    state: row.status,
    result: row.result_json ? JSON.parse(row.result_json) : undefined,
    progress: row.status === "running" ? "running" : undefined,
  };
}

export async function cancelTask(db, taskId) {
  const row = await db.prepare("SELECT * FROM tasks WHERE task_id = ?").bind(taskId).first();
  if (!row || (row.status !== "pending" && row.status !== "running")) return false;
  await db.prepare("UPDATE tasks SET status = 'cancelled', updated_at = ? WHERE task_id = ?").bind(Date.now(), taskId).run();
  return true;
}

/** 重启对账：所有 running → error + service_restarted（终态） */
export async function reconcileAfterRestart(db) {
  await db.prepare("UPDATE tasks SET status = 'error', result_json = ?, updated_at = ? WHERE status = 'running'")
    .bind(JSON.stringify({ reason: "service_restarted" }), Date.now())
    .run();
}

/**
 * 推进一个 pending 任务：查 packages 表找到提供 domain;action 的 handler，受限执行，写结果。
 * @returns {boolean} 是否有任务被推进
 */
export async function runNext(db, { runHandler, register }, opts = {}) {
  const row = await db.prepare("SELECT * FROM tasks WHERE status = 'pending' ORDER BY created_at LIMIT 1").first();
  if (!row) return false;
  await db.prepare("UPDATE tasks SET status = 'running', updated_at = ? WHERE task_id = ?").bind(Date.now(), row.task_id).run();
  try {
    const result = await dispatchByDirective(db, row.domain, row.action, JSON.parse(row.params || "[]"), { runHandler, register });
    await db.prepare("UPDATE tasks SET status = 'done', result_json = ?, updated_at = ? WHERE task_id = ?")
      .bind(JSON.stringify(result), Date.now(), row.task_id)
      .run();
  } catch (e) {
    await db.prepare("UPDATE tasks SET status = 'error', result_json = ?, updated_at = ? WHERE task_id = ?")
      .bind(JSON.stringify({ reason: "ERR_EXECUTION", message: e && e.message }), Date.now(), row.task_id)
      .run();
  }
  return true;
}

/** 按 domain;action 在 D1 packages 里反查并受限执行（任务内部路径，跳过入口鉴权） */
async function dispatchByDirective(db, domain, action, params, { runHandler }) {
  const res = await db.prepare("SELECT * FROM packages").all();
  for (const p of res.results) {
    const schema = JSON.parse(p.schema_json);
    const hit = (schema.directives || []).find((d) => d.domain === domain && d.action === action);
    if (hit) {
      return runHandler(p.handler_js, schema, params, {}, {});
    }
  }
  throw new Error(`no matching directive: ${domain};${action}`);
}
