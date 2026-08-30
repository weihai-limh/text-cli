/**
 * pathBridge.ts——P0 接线器（接线点 A/B/C 组装）
 *
 * 把 path 引擎 + inbound dispatchFn + meta 元指令组装起来：
 * - 接线点 C：path 引擎的 `dispatch(domain,action,params)` → inbound `DispatchFn(ToolExecutionInput)` 桥接
 * - 接线点 B：meta 的 `path` 分支 → `runPath(def, pathDeps)`
 * - 接线点 A：组装好的 meta 可注入 `HandlerDeps.meta`（text-cli 保留域）
 *
 * 纯组装，不持有状态；path 注册表与执行依赖由调用方注入（保持 handler 纯逻辑，红线①）。
 */
import tc from "textcli-core";
import { runPath, type PathDef, type PathDeps } from "@dsh-tc/runtime-path";
import { normalizeName } from "@dsh-tc/runtime-mapper";
import { handleMeta, type MetaDeps } from "@dsh-tc/runtime-meta";
import type { DispatchFn } from "./handler.js";

/** path 接线所需的注入项 */
export interface PathBridgeDeps {
  /** inbound 执行派发（path 每步指令的落地通道） */
  dispatch: DispatchFn;
  /** path 定义注册表：name → PathDef（调用方持有） */
  pathDefs: ReadonlyMap<string, PathDef>;
  /** path 引擎附加注入（maxDepth/mapHardCap/initialVars/httpDispatch 等，dispatch 由本桥接覆盖） */
  pathDeps?: Omit<PathDeps, "dispatch">;
  /** meta 元指令其余依赖（registry/directives/resolveInstallInput） */
  metaDeps: Omit<MetaDeps, "runPath">;
}

/** 组装 PathDeps：把 path 引擎三参 → inbound ToolExecutionInput */
export function buildPathDeps(bridge: PathBridgeDeps): PathDeps {
  const { dispatch, pathDeps } = bridge;
  return {
    ...pathDeps,
    dispatch: async (domain, action, params) => {
      const input = {
        callId: `path-${Date.now()}-${Math.floor(Math.random() * 1_000_000)}`,
        name: `tc__${normalizeName(domain)}__${normalizeName(action)}`,
        arguments: { params },
      };
      return dispatch(input);
    },
  };
}

/** 组装含 path 分支的 meta 元指令处理器（注入到 HandlerDeps.meta） */
export function createMetaWithPath(bridge: PathBridgeDeps): (action: string, params: string[]) => Promise<ReturnType<typeof tc.ok>> {
  const pathDeps = buildPathDeps(bridge);
  const metaDeps: MetaDeps = {
    ...bridge.metaDeps,
    runPath: async (pathName, params) => {
      const def = bridge.pathDefs.get(pathName);
      if (!def) return tc.err("ERR_NOT_FOUND", `path not found: ${pathName}`);
      // path 输入参数经 initialVars 注入（steps 可用 {params.0} 引用）
      const result = await runPath(def, { ...pathDeps, initialVars: { params } });
      if (!result.ok) {
        return tc.err("ERR_EXECUTION", result.error ?? "path execution failed");
      }
      return tc.ok({
        status: "ok",
        output: result.output,
        vars: result.vars,
        steps: result.steps,
        warnings: result.warnings,
      });
    },
  };
  return (action, params) => handleMeta(action, params, metaDeps);
}
