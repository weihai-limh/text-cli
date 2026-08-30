/**
 * meta.ts——text-cli;* 保留域元指令表面（功能设计 §7，SPEC §6.2.1 八元指令）
 *
 * 直接拦截处理，不落 ctx.tools 指令表（红线⑤）。八元指令：
 * install / uninstall / export / export-all / packages / query / path / pro
 */
import tc from "textcli-core";
import { handleQuery, type DirectiveEntry } from "@dsh-tc/runtime-mapper";
import { installPackage, uninstallPackage, exportPackage, exportAllPackages, listPackages, type InstallSchema } from "./installer.js";
import { PackageRegistry } from "./registry.js";

export type MetaAction =
  | "install"
  | "uninstall"
  | "export"
  | "export-all"
  | "packages"
  | "query"
  | "path"
  | "pro";

export const META_ACTIONS: MetaAction[] = [
  "install",
  "uninstall",
  "export",
  "export-all",
  "packages",
  "query",
  "path",
  "pro",
];

export interface MetaDeps {
  registry: PackageRegistry;
  /** 发现数据源（query 元指令；ubuntu 联调接 ctx.tools.schemas() → buildDirectives） */
  directives: DirectiveEntry[];
  /** 包安装输入（install 元指令；参数 = 包 JSON schema + handlerPath，ubuntu 联调接包仓库） */
  resolveInstallInput?: (param: string) => Promise<{ schema: InstallSchema; handlerPath: string } | null>;
  /** path 执行器（path 元指令；由调用方注入，内部接 runPath + dispatch 桥接）。
   *  依赖注入避免 runtime-meta → runtime-path 循环依赖；未注入 → path 未实现（fail-closed） */
  runPath?: (pathName: string, params: string[]) => Promise<ReturnType<typeof tc.ok>>;
}

export async function handleMeta(
  action: string,
  params: string[],
  deps: MetaDeps,
): Promise<ReturnType<typeof tc.ok>> {
  switch (action as MetaAction) {
    case "query":
      return handleQuery(params, { directives: deps.directives });

    case "install": {
      const param = params[0];
      if (!param || !deps.resolveInstallInput) {
        return tc.err("INVALID_PARAMS", "install 需要包参数且需配置包源（ubuntu 联调接入）");
      }
      const input = await deps.resolveInstallInput(param);
      if (!input) return tc.err("ERR_NOT_FOUND", `package source not found: ${param}`);
      const r = installPackage(deps.registry, input);
      if (!r.ok) return tc.err("ERR_EXECUTION", r.error);
      return tc.ok({ status: "ok", installed: r.installed.id });
    }

    case "uninstall": {
      const id = params[0];
      if (!id) return tc.err("INVALID_PARAMS", "uninstall 需要包名");
      const r = uninstallPackage(deps.registry, id);
      if (!r.ok) return tc.err("ERR_NOT_FOUND", r.error ?? "uninstall failed");
      return tc.ok({ status: "ok", uninstalled: id });
    }

    case "export": {
      const id = params[0];
      if (!id) return tc.err("INVALID_PARAMS", "export 需要包名");
      return exportPackage(deps.registry, id);
    }

    case "export-all":
      return exportAllPackages(deps.registry);

    case "packages":
      return listPackages(deps.registry);

    case "path": {
      // P0 接线点 B：调注入的 runPath 执行器（依赖注入，避免循环依赖）；未注入 → fail-closed
      const pathName = params[0];
      if (!pathName) return tc.err("INVALID_PARAMS", "path 需要路径名");
      if (!deps.runPath) return tc.err("ERR_NOT_FOUND", "path 执行器未注入（P0 接线）");
      const inputParams = params.slice(1);
      const env = await deps.runPath(pathName, inputParams);
      return env;
    }

    case "pro":
      // Phase 11 实现（门面注册表）
      return tc.err("ERR_NOT_FOUND", "pro 元指令未实现（Phase 11）");

    default:
      return tc.err("ERR_NOT_FOUND", `unknown meta action: ${action}`);
  }
}
