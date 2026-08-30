/**
 * workflowCompiler.ts——tc path → dsh workflow 翻译（P9）
 *
 * 翻译形态：tc path JSON → dsh workflow JS 脚本（生成 agent()/pipeline()/parallel() hooks）。
 * 语义同构处无损翻译；语义差异处显式标注 `// LOSSY:`（翻译纪律，不得静默翻译）。
 *
 * 注意：dsh workflow 是"模型写的 JS 脚本"（node:vm 执行，暴露 agent/pipeline/parallel 等 hooks）。
 * 本编译器生成结构清晰的脚本，dsh hooks 的确切签名在联调阶段校准（见验证标准）。
 */
import type { PathDef, PathStep } from "./types.js";

export interface CompileResult {
  /** 生成的 dsh workflow 脚本 */
  script: string;
  /** 有损标注清单（翻译纪律：显式记录哪些步骤有损） */
  losses: Array<{ step: string; reason: string }>;
}

const STEP_ID = (() => { let i = 0; return () => `s${++i}`; })();

function compileStep(step: PathStep, depth: number, losses: CompileResult["losses"]): string {
  const ind = "  ".repeat(depth + 1);
  if (step.type === "call" || step.type === undefined) {
    const c = step as { domain: string; action: string; params?: string[]; name?: string };
    const id = c.name ?? STEP_ID();
    const params = c.params ? JSON.stringify(c.params) : "[]";
    return `${ind}// step ${id}: ${c.domain};${c.action} ${params}\n${ind}await run("${c.domain}", "${c.action}", ${params});`;
  }
  if (step.type === "sequence") {
    const s = step as { steps: PathStep[] };
    return `${ind}await pipeline([...], [\n${s.steps.map(x => compileStep(x, depth + 1, losses)).join(",\n")}\n${ind}]);`;
  }
  if (step.type === "parallel") {
    const p = step as { strategy: string; branches: PathStep[] };
    const thunks = p.branches.map((b, i) => `${ind}  () => {\n${compileStep(b, depth + 1, losses)}\n${ind}  }`);
    return `${ind}await parallel([\n${thunks.join(",\n")}\n${ind}], { strategy: "${p.strategy}" });`;
  }
  if (step.type === "if") {
    const i = step as { cond: unknown; then: PathStep; else?: PathStep };
    losses.push({ step: `if:${JSON.stringify(i.cond)}`, reason: "cond 需联调映射为 dsh 原生条件" });
    const elseBranch = i.else ? `else {\n${compileStep(i.else, depth + 1, losses)}\n}` : "";
    return `${ind}if (await evalCondition(${JSON.stringify(i.cond)})) {\n${compileStep(i.then, depth + 1, losses)}\n${ind}} ${elseBranch}`;
  }
  if (step.type === "map") {
    const m = step as { over: string; as: string; step: PathStep };
    losses.push({ step: `map:${m.over}`, reason: "dsh 无一等 map hook，用 JS for 循环 + 并发近似（需联调确认并发语义）" });
    return `${ind}for (const ${m.as} of vars[${JSON.stringify(m.over)}] ?? []) {\n${compileStep(m.step, depth + 1, losses)}\n${ind}}`;
  }
  if (step.type === "http_dispatch") {
    const h = step as { node: string; domain: string; action: string };
    losses.push({ step: `http_dispatch:${h.node}`, reason: "LOSSY：dsh workflow 无直接对等物，需本地回退或 dsh 跨节点机制" });
    return `${ind}// LOSSY http_dispatch to ${h.node}\n${ind}await run("${h.domain}", "${h.action}", []);`;
  }
  if (step.type === "delegated") {
    const d = step as { domain: string; action: string };
    losses.push({ step: `delegated:${d.domain};${d.action}`, reason: "LOSSY：委托语义 dsh 需经 subagent/ralph 映射" });
    return `${ind}// LOSSY delegated\n${ind}await run("${d.domain}", "${d.action}", []);`;
  }
  losses.push({ step: JSON.stringify(step), reason: "LOSSY：未知 step 类型" });
  return `${ind}// LOSSY unknown step`;
}

/** 编译 PathDef → dsh workflow 脚本 */
export function compileToWorkflow(def: PathDef): CompileResult {
  STEP_ID(); // reset
  const losses: CompileResult["losses"] = [];
  const body = def.steps.map(s => compileStep(s, 0, losses)).join("\n");
  const script = [
    `// dsh workflow 编译产物（来源：tc path "${def.name}"）`,
    `// 依赖 hooks：run / agent / pipeline / parallel / evalCondition / vars`,
    `export default async function main({ run, agent, pipeline, parallel, evalCondition, vars }) {`,
    body,
    `  return vars;`,
    `}`,
  ].join("\n");
  return { script, losses };
}
