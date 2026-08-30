/**
 * query 元指令处理器（SPEC §1.2.7 / 功能设计 §3.3）
 *
 * `text-cli;query[,json|compact|<关键词>][,zh|en]`——发现契约。
 * 数据源（directives 列表）注入：ubuntu 联调接入 `ctx.tools.schemas()` → buildDirectives。
 * 纯逻辑，可外溢复用。
 */
import tc from "textcli-core";
import { formatQuery, type DirectiveEntry, type QueryMode, type QueryLang } from "./dshToTc.js";

export interface QueryDeps {
  directives: DirectiveEntry[];
}

/** 解析 query 参数：`query` / `query,json` / `query,compact` / `query,<关键词>` / 尾参 `,zh|,en` */
export function parseQueryArgs(params: string[]): { mode: QueryMode; keyword?: string; lang?: QueryLang } {
  const args = params.map((p) => p.trim());
  let mode: QueryMode = "text";
  let keyword: string | undefined;
  let lang: QueryLang;

  for (const arg of args) {
    if (arg === "json") mode = "json";
    else if (arg === "compact") mode = "compact";
    else if (arg === "zh") lang = "zh";
    else if (arg === "en") lang = "en";
    else if (arg === "python" || arg === "js" || arg === "mcp" || arg === "cloudbase") {
      // runtime 过滤——可选能力（SPEC §1.2.7 引用块），0.1.0 暂不支持（忽略，不报错）
    } else if (arg.startsWith("category")) {
      // 分类过滤——可选能力，0.1.0 暂不支持
    } else if (arg !== "") {
      // 关键词搜索
      mode = "keyword";
      keyword = arg;
    }
  }
  return { mode, keyword, lang };
}

export function handleQuery(params: string[], deps: QueryDeps): ReturnType<typeof tc.ok> {
  const { mode, keyword, lang } = parseQueryArgs(params);
  const data = formatQuery(deps.directives, { mode, keyword, lang });
  return tc.ok(data);
}
