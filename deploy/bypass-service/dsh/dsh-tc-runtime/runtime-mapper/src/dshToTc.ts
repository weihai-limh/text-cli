/**
 * dshToTc——dsh 工具 schema → tc 指令发现契约（功能设计 §3.3，SPEC §1.2.7）
 *
 * 输入 = 工具 schema 列表（抽象接口；ubuntu 联调时从 `ctx.tools.schemas()` 映射），
 * 输出 = `directives[]`（domain/action 强制 + 可选增强字段；`_package` 剥离 → 顶层提升）。
 *
 * 纯函数，平台数据源注入（R17）——不依赖 dsh ctx。
 */

/** 工具 schema 抽象形状（dsh `ctx.tools.schemas()` 的 tc 投影；ubuntu 联调时映射） */
export interface ToolSchema {
  /** 工具名：tc__<domain>__<action>（tc 包）或 mcp__<server>__<tool>（MCP 桥） */
  name: string;
  description?: string;
  /** tc 注册元数据（install 时随工具注册，见 Phase 7）；无 tc 元数据的工具不进入发现契约 */
  tc?: {
    domain: string;
    action: string;
    /** 包标识（schema.id 扁平提升） */
    package?: string;
    /** 运行时标识（schema.runtime） */
    runtime?: string;
    domain_zh?: string;
    action_zh?: string;
    usage?: string;
    usage_zh?: string;
    description_zh?: string;
    /** 原样透传（SPEC §1.2.7 params） */
    params?: string[];
  };
}

/** SPEC §1.2.7 canonical 指令条目（强制基线 domain+action + 可选增强） */
export interface DirectiveEntry {
  domain: string;
  action: string;
  usage?: string;
  package?: string;
  runtime?: string;
  domain_zh?: string;
  action_zh?: string;
  usage_zh?: string;
  description?: string;
  description_zh?: string;
  params?: string[];
}

/**
 * 工具 schema → 指令条目。
 * 仅输出带 tc 元数据的工具（tc 包注册的）；MCP 桥工具（mcp__*）在 Phase 11
 * 协议桥转化链中映射，不在此处推断（避免错误契约）。
 */
export function toolSchemaToDirective(schema: ToolSchema): DirectiveEntry | null {
  if (!schema.tc) return null;
  const t = schema.tc;
  const entry: DirectiveEntry = { domain: t.domain, action: t.action };
  if (t.usage !== undefined) entry.usage = t.usage;
  if (t.package !== undefined) entry.package = t.package;
  if (t.runtime !== undefined) entry.runtime = t.runtime;
  if (t.domain_zh !== undefined) entry.domain_zh = t.domain_zh;
  if (t.action_zh !== undefined) entry.action_zh = t.action_zh;
  if (t.usage_zh !== undefined) entry.usage_zh = t.usage_zh;
  if (schema.description !== undefined) entry.description = schema.description;
  if (t.description_zh !== undefined) entry.description_zh = t.description_zh;
  if (t.params !== undefined) entry.params = t.params;
  return entry;
}

/** 全量映射：schemas → directives[]（按包分组排序，`_package` 剥离语义由 tc 元数据承担） */
export function buildDirectives(schemas: ToolSchema[]): DirectiveEntry[] {
  const entries: DirectiveEntry[] = [];
  for (const s of schemas) {
    const entry = toolSchemaToDirective(s);
    if (entry) entries.push(entry);
  }
  entries.sort((a, b) =>
    (a.package ?? a.domain).localeCompare(b.package ?? b.domain) ||
    a.domain.localeCompare(b.domain) ||
    a.action.localeCompare(b.action),
  );
  return entries;
}

/** 关键词模糊搜索（domain/action/description） */
export function searchDirectives(entries: DirectiveEntry[], keyword: string): DirectiveEntry[] {
  const k = keyword.toLowerCase();
  return entries.filter(
    (e) =>
      e.domain.toLowerCase().includes(k) ||
      e.action.toLowerCase().includes(k) ||
      (e.description ?? "").toLowerCase().includes(k) ||
      (e.domain_zh ?? "").includes(keyword) ||
      (e.action_zh ?? "").includes(keyword),
  );
}

export type QueryMode = "text" | "json" | "compact" | "keyword";
export type QueryLang = "zh" | "en" | undefined;

export interface QueryOptions {
  mode: QueryMode;
  keyword?: string;
  lang?: QueryLang;
}

/**
 * 发现契约格式化（SPEC §1.2.7 触发形式 + 本地化策略）：
 * - json：返回全部 locale 变体（canonical + _zh），服务端不做单语选择
 * - text/compact：按尾参 lang 选单一语言（回退 canonical）
 * - keyword：模糊搜索
 * - usage 前缀约定：不含 `AI:` 前缀（SPEC §1.2.7 引用块）
 */
export function formatQuery(entries: DirectiveEntry[], opts: QueryOptions): unknown {
  const { mode, keyword, lang } = opts;

  let base = entries;
  if (mode === "keyword" && keyword) {
    base = searchDirectives(entries, keyword);
  }

  switch (mode) {
    case "json": {
      // canonical 全量（含 locale 变体）
      const directives = base.map((e) => {
        const out: Record<string, unknown> = { domain: e.domain, action: e.action };
        for (const key of [
          "usage", "package", "runtime", "domain_zh", "action_zh", "usage_zh",
          "description", "description_zh", "params",
        ] as const) {
          if (e[key] !== undefined) out[key] = e[key];
        }
        return out;
      });
      return { directives };
    }
    case "compact":
      // 每行一条 domain;action（按语言选别名）
      return base
        .map((e) => {
          const d = lang === "zh" && e.domain_zh ? e.domain_zh : e.domain;
          const a = lang === "zh" && e.action_zh ? e.action_zh : e.action;
          return `${d};${a}`;
        })
        .join("\n");
    case "text":
    default: {
      // 全量纯文本，按包分组
      const byPackage = new Map<string, DirectiveEntry[]>();
      for (const e of base) {
        const key = e.package ?? e.domain;
        const list = byPackage.get(key) ?? [];
        list.push(e);
        byPackage.set(key, list);
      }
      const lines: string[] = [];
      for (const [pkg, list] of byPackage) {
        lines.push(`# ${pkg}`);
        for (const e of list) {
          const d = lang === "zh" && e.domain_zh ? e.domain_zh : e.domain;
          const a = lang === "zh" && e.action_zh ? e.action_zh : e.action;
          const desc = lang === "zh" && e.description_zh ? e.description_zh : e.description;
          lines.push(`  ${d};${a}${desc ? ` — ${desc}` : ""}`);
        }
      }
      return lines.join("\n");
    }
  }
}
