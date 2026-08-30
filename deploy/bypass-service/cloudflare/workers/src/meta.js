// meta — 指令包生命周期（D1 可执行包）+ 指令发现
//
// install：从包源读 schema + handler 源码字符串 → 写 D1 packages 表 →
//          注册 handler 到核心 registry（handler = 受限执行包装）。
// uninstall：删 D1 packages + 反注册（与 install 对称）。
// query/packages：从 D1 包声明生成 directives（SPEC §1.2.7 canonical）。

import fs from "node:fs";
import path from "node:path";
import { runHandler } from "./executor.js";

export async function installPackage({ packageId, sourceDir, db, register, executorDeps }) {
  const dir = path.join(sourceDir, packageId);
  const schemaPath = path.join(dir, "schema.json");
  const handlerPath = path.join(dir, "handler.js");
  if (!fs.existsSync(schemaPath)) {
    return { ok: false, error: `package not found in source: ${packageId}` };
  }
  const schema = JSON.parse(fs.readFileSync(schemaPath, "utf8"));
  const handlerJs = fs.readFileSync(handlerPath, "utf8");
  // 保留完整指令声明（含 domain_zh/action_zh 等，供别名注册与 query 发现）
  const directives = (schema.directives || []).map((d) => ({
    domain: d.domain,
    action: d.action,
    domain_zh: d.domain_zh,
    action_zh: d.action_zh,
    usage: d.usage,
    usage_zh: d.usage_zh,
    description: d.description,
    description_zh: d.description_zh,
    params: d.params,
    outputs: d.outputs,
  }));

  // D1 packages 表 upsert（可执行包：schema + handler 源码）
  await db
    .prepare(
      "INSERT INTO packages (package_id, schema_json, handler_js, domains, actions, installed_at) VALUES (?, ?, ?, ?, ?, ?) " +
        "ON CONFLICT(package_id) DO UPDATE SET schema_json = excluded.schema_json, handler_js = excluded.handler_js, " +
        "domains = excluded.domains, actions = excluded.actions, installed_at = excluded.installed_at",
    )
    .bind(packageId, JSON.stringify(schema), handlerJs, JSON.stringify(directives.map((d) => d.domain)), JSON.stringify(directives.map((d) => d.action)), Date.now())
    .run();

  // 注册到核心 registry：handler = 受限执行包装；别名（domain_zh/action_zh）进 alias 表（SPEC §1.1 别名路由）
  for (const d of directives) {
    const opts = {
      domainAlias: d.domain_zh || undefined,
      actionAliases: d.action_zh ? { [d.action]: d.action_zh } : undefined,
    };
    register(d.domain, d.action, async (params, context) =>
      runHandler(handlerJs, schema, params || [], context, executorDeps),
      opts,
    );
  }
  return { ok: true, installed: packageId, directives };
}

export async function uninstallPackage({ packageId, db, unregister }) {
  const row = await db.prepare("SELECT * FROM packages WHERE package_id = ?").bind(packageId).first();
  if (!row) return { ok: false, error: `package not installed: ${packageId}` };
  const directives = JSON.parse(row.domains).map((domain, i) => ({ domain, action: JSON.parse(row.actions)[i] }));
  for (const d of directives) unregister(d.domain, d.action);
  await db.prepare("DELETE FROM packages WHERE package_id = ?").bind(packageId).run();
  return { ok: true, uninstalled: packageId };
}

export async function listPackages(db) {
  const res = await db.prepare("SELECT * FROM packages ORDER BY installed_at").all();
  return res.results.map((r) => ({
    package_id: r.package_id,
    directives: JSON.parse(r.domains).map((domain, i) => ({ domain, action: JSON.parse(r.actions)[i] })),
    installed_at: r.installed_at,
  }));
}

/** 从 D1 包声明生成 directives（SPEC §1.2.7 canonical 投影） */
export async function buildDirectives(db) {
  const res = await db.prepare("SELECT * FROM packages").all();
  const out = [];
  for (const r of res.results) {
    const schema = JSON.parse(r.schema_json);
    const domains = JSON.parse(r.domains);
    const actions = JSON.parse(r.actions);
    (schema.directives || []).forEach((d, i) => {
      out.push({
        domain: d.domain,
        action: d.action,
        package: r.package_id,
        domain_zh: d.domain_zh,
        action_zh: d.action_zh,
        usage: d.usage,
        usage_zh: d.usage_zh,
        description: d.description,
        description_zh: d.description_zh,
        params: d.params,
        outputs: d.outputs,
      });
    });
    void domains;
    void actions;
  }
  return out;
}
