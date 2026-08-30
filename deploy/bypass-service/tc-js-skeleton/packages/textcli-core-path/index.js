// textcli-core-path — path 声明层解释器（对齐协议 SPEC §4 + 原版 A4-paths 形态）
//
// 步骤形态（协议 §4.2 / A4 path_executor）：
//   { "id": "start", "instruction": "map;geocode,{input.address}", "output_as": "start" }
//   { "id": "route", "instruction": "map;route,{start.lat},{start.lon}", "output_as": "route",
//     "if": {"step": "start", "field": "status", "equals": "ok"} }
//   { "id": "backup", "instruction": "...", "degradation": [{"instruction": "..."}] }
//   { "id": "remote", "instruction": "tc-ffmpeg;info,{video.path}", "source": "http://host/text-cli/cli", "timeout": 30000 }
//   { "id": "para", "mode": "parallel", "strategy": "first_ok", "steps": [...] }
//   { "id": "loop", "mode": "map", "items": "list", "steps": [...], "as": "item",
//     "collect_as": "collected", "on_error": "continue", "concurrency": "serial" }
//
// 变量模型：{input.key} 用户输入 JSON；{output_as.field} 命名变量深路径；
//   两阶段插值：resolveVar（{var} 未定义→空串+WARNING）→ interpolateParams（{var.field} 深路径，取不到保留原样）。
// 执行语义：ok / error（dispatch error、handler status:error、降级链耗尽）/
//   delegated（指令未注册，非错误，继续）/ BRANCH_NO_MATCH（if 跳过导致后续引用悬空）。
// 响应：{ status, code, path_id, total_steps, completed_steps, failed_step?, reason?,
//         delegated?, output, warnings } —— rst_data 直接承载。
//
// 环检测：withPath 对注册命中的 path 推 `path:<id>` 键（与 guard/aggregate 共享 ancestorChain）。

import { ancestorChain as defaultChain, cycleKey } from "../textcli-core-guard/index.js";
import parser from "../textcli-core/parser.js";

export class PathError extends Error {
  constructor(code, reason) {
    super(code);
    this.name = "PathError";
    this.code = code;
    this.reason = reason;
  }
}

// ─── 常量 ─────────────────────────────────────────────
export const MAP_HARD_CAP = 1000;
export const MAX_DEPTH = 2;
const ACCEPTED_TYPES = new Set(["skill", "pipeline"]);
const ACCEPTED_MODES = new Set(["toolchain", "parallel"]);

const VAR_RE = /\{(\w+)\}/g;
const INLINE_RE = /\{(\w+)((?:\.\w+|\.\d+)*)\}/g;

// ─── 信封/结果判定 ─────────────────────────────────────
function isEnvelope(r) {
  return r && typeof r === "object" && !Array.isArray(r) && "rst_err" in r && "rst_data" in r;
}

/**
 * 统一 dispatch 结果归一化。
 * @returns {{kind:"ok"|"error"|"delegated", data?:any, reason?:string}}
 */
function classifyResult(r) {
  if (r === null || r === undefined) return { kind: "delegated" };
  if (isEnvelope(r)) {
    if (r.rst_err) {
      const reason = r.rst_data && r.rst_data.reason ? `${r.rst_err}: ${r.rst_data.reason}` : r.rst_err;
      return { kind: "error", reason };
    }
    return { kind: "ok", data: r.rst_data };
  }
  if (typeof r === "object") {
    if (r.status === "error") return { kind: "error", reason: r.reason || "handler error" };
    return { kind: "ok", data: r };
  }
  if (typeof r === "string") {
    try {
      const o = JSON.parse(r);
      if (o && typeof o === "object") return classifyResult(o);
    } catch { /* 非 JSON 文本当 ok */ }
    return { kind: "ok", data: r };
  }
  return { kind: "ok", data: r };
}

// ─── 插值（两阶段，对齐 A4 path_executor）──────────────
/** {var} 简单替换；未定义 → 空串 + WARNING（SPEC §4.2 未定义变量行为） */
function resolveVar(text, variables, warnings) {
  return text.replace(VAR_RE, (m, name) => {
    if (name in variables) return variables[name];
    warnings.push(`undefined variable: ${name}`);
    return "";
  });
}

/** {var.field[.0.path]} 深路径 JSON 插值；取不到/非 JSON → 保留原样 */
function interpolateParams(params, variables, warnings) {
  if (!params) return params;
  return params.map((p) =>
    p.replace(INLINE_RE, (m, varName, tail) => {
      const raw = variables[varName];
      if (!raw) return m;
      let obj;
      try {
        obj = JSON.parse(raw);
      } catch {
        return m;
      }
      let cur = obj;
      if (!tail) return raw;
      const segments = tail.replace(/^\./, "").split(".");
      for (const seg of segments) {
        if (cur && typeof cur === "object" && seg in cur) cur = cur[seg];
        else return m;
        if (cur === null || cur === undefined) return m;
      }
      if (typeof cur === "boolean") return String(cur).toLowerCase();
      if (typeof cur === "number") return String(cur);
      if (typeof cur === "string") return cur;
      if (Array.isArray(cur)) return cur.join(",");
      return JSON.stringify(cur);
    }),
  );
}

// ─── 条件求值（对齐 A4 evaluate_if / check_condition）────
function compare(actual, op, expected) {
  let a, e, numeric = true;
  try {
    a = parseFloat(actual) ?? 0;
    e = parseFloat(expected);
    if (Number.isNaN(e)) throw new Error("nan");
  } catch {
    a = String(actual ?? "");
    e = String(expected);
    numeric = false;
  }
  switch (op) {
    case "eq": return numeric ? a === e : String(a) === String(e);
    case "gt": return numeric ? a > e : String(a) > String(e);
    case "lt": return numeric ? a < e : String(a) < String(e);
    case "gte": return numeric ? a >= e : String(a) >= String(e);
    case "lte": return numeric ? a <= e : String(a) <= String(e);
    case "ne": return numeric ? a !== e : String(a) !== String(e);
    default: return false;
  }
}

function computeCount(raw) {
  if (!raw) return 0;
  try {
    const obj = JSON.parse(raw);
    if (Array.isArray(obj)) return obj.length;
    if (obj && typeof obj === "object") {
      if (Array.isArray(obj.result)) return obj.result.length;
      for (const v of Object.values(obj)) if (Array.isArray(v)) return v.length;
      return Object.keys(obj).length;
    }
  } catch { /* fallthrough */ }
  return 0;
}

function checkCondition(cond, variables) {
  const stepName = cond.step || "";
  const field = cond.field || "";
  let raw = variables[stepName] || "";
  let obj = {};
  try {
    obj = JSON.parse(raw);
  } catch { obj = {}; }
  if (!obj || typeof obj !== "object" || Array.isArray(obj)) obj = {};
  const val = obj[field];

  if ("op" in cond && "value" in cond) {
    const op = cond.op;
    const expected = cond.value;
    let funcVal;
    if (field === "count") funcVal = computeCount(raw);
    else if (field === "size") funcVal = raw ? raw.length : 0;
    else if (field === "exists") funcVal = raw && raw.trim() ? 1 : 0;
    else return compare(val ?? 0, op, expected);
    return compare(funcVal, op, expected);
  }
  if ("equals" in cond) return String(val ?? "") === String(cond.equals);
  if ("contains" in cond) return String(val ?? "").includes(String(cond.contains));
  if ("matches" in cond) {
    try { return new RegExp(cond.matches).test(String(val ?? "")); }
    catch { return false; }
  }
  if ("exists" in cond) return val !== undefined && val !== null && val !== "";
  return false;
}

function evaluateIf(ifDef, variables, warnings) {
  if (ifDef === null || ifDef === undefined) return true;
  if (typeof ifDef === "string") {
    // 字符串式：{step.field} == 'V' / != ；否则真值
    const interpolated = resolveVar(ifDef, variables, warnings).trim();
    const m = interpolated.match(/^\s*(.+?)\s*(==|!=)\s*(.+?)\s*$/);
    if (m) {
      const left = m[1].trim();
      const right = m[3].trim().replace(/^['"]|['"]$/g, "");
      return m[2] === "==" ? left === right : left !== right;
    }
    return interpolated.trim() !== "";
  }
  if (typeof ifDef === "object") {
    if ("step" in ifDef) return checkCondition(ifDef, variables);
    if ("all" in ifDef) return (ifDef.all || []).every((c) => checkCondition(c, variables));
    if ("any" in ifDef) return (ifDef.any || []).some((c) => checkCondition(c, variables));
    // 兼容旧 {type:"equals", left, right} 形态
    if (ifDef.type === "equals") return resolveVar(String(ifDef.left ?? ""), variables, warnings) === resolveVar(String(ifDef.right ?? ""), variables, warnings);
    if (ifDef.type === "contains") return resolveVar(String(ifDef.left ?? ""), variables, warnings).includes(resolveVar(String(ifDef.right ?? ""), variables, warnings));
    if (ifDef.type === "exists") {
      const k = resolveVar(String(ifDef.key ?? ""), variables, warnings);
      return k in variables && variables[k] !== "";
    }
    if (ifDef.type === "matches") {
      const l = resolveVar(String(ifDef.left ?? ""), variables, warnings);
      const expr = resolveVar(String(ifDef.expr ?? ""), variables, warnings);
      try { return new RegExp(expr).test(l); } catch { return false; }
    }
  }
  return false;
}

// ─── 指令解析（instruction 字符串 → domain/action/params）──
function parseDirective(raw) {
  const resolved = raw.trim();
  const withPrefix = /^(AI|指令)[：:]/.test(resolved) ? resolved : `AI:${resolved}`;
  const parsed = parser.parse(withPrefix);
  if (parsed.error) throw new PathError("PARSE_FAILED", parsed.reason);
  return { domain: parsed.domain, action: parsed.action, params: parsed.params };
}

// ─── 步骤执行 ─────────────────────────────────────────
function referencesSkipped(directive, skippedOutputs) {
  for (const name of skippedOutputs) {
    if (directive.includes(`{${name}.`) || directive.includes(`{${name}}`)) return true;
  }
  return false;
}

/**
 * 单步执行（toolchain：普通 instruction 步骤）。
 * @returns {{status:"ok"|"error"|"delegated", result:string, outputAs:string, reason?:string}}
 */
async function executeStep(step, variables, stepIndex, deps, defaultSource, warnings) {
  const rawDirective = step.instruction || step.directive || ""; // directive 为旧名，告警兼容
  if (step.directive && !step.instruction) warnings.push(`DEPRECATED: step uses 'directive' instead of 'instruction'`);
  if (!rawDirective) {
    return { status: "error", result: "", outputAs: step.output_as || `_step${stepIndex}`, reason: `step ${stepIndex}: no instruction` };
  }

  const resolved = resolveVar(rawDirective, variables, warnings);
  let domain, action, params;
  try {
    ({ domain, action, params } = parseDirective(resolved));
  } catch (e) {
    return { status: "error", result: "", outputAs: step.output_as || `_step${stepIndex}`, reason: e.reason || e.message };
  }
  [domain] = interpolateParams([domain], variables, warnings);
  [action] = interpolateParams([action], variables, warnings);
  params = interpolateParams(params, variables, warnings);
  if (!domain) return { status: "error", result: "", outputAs: step.output_as || `_step${stepIndex}`, reason: `step ${stepIndex}: empty domain` };

  const outputAs = step.output_as || `_step${stepIndex}`;
  const source = step.source || defaultSource;
  const timeoutMs = step.timeout;

  let result;
  if (source) {
    // 跨节点：注入的 httpDispatch 必须可用
    if (typeof deps.httpDispatch !== "function") {
      return { status: "error", result: "", outputAs, reason: `step ${stepIndex}: source requires httpDispatch (not injected)` };
    }
    try {
      const raw = await withTimeout(deps.httpDispatch(source, domain, action, params), timeoutMs ?? 30000);
      result = extractRstData(raw);
    } catch (e) {
      return { status: "error", result: "", outputAs, reason: `step ${stepIndex}: remote dispatch failed: ${e.message}` };
    }
  } else {
    try {
      const r = await withTimeout(deps.dispatch(domain, action, params), timeoutMs);
      const cls = classifyResult(r);
      if (cls.kind === "delegated") return { status: "delegated", result: `${domain};${action}`, outputAs };
      if (cls.kind === "error") return { status: "error", result: "", outputAs, reason: cls.reason };
      result = cls.data;
    } catch (e) {
      return { status: "error", result: "", outputAs, reason: `step ${stepIndex}: ${e.message}` };
    }
  }

  // handler status:error 检测（result 可能是对象/字符串）
  const cls = classifyResult(result);
  if (cls.kind === "error") return { status: "error", result: "", outputAs, reason: cls.reason };
  return { status: "ok", result: typeof result === "string" ? result : JSON.stringify(result), outputAs };
}

function extractRstData(raw) {
  if (raw && typeof raw === "object" && "rst_data" in raw) {
    const rd = raw.rst_data;
    if (rd && typeof rd === "object" && !Array.isArray(rd) && Object.keys(rd).length === 1 && "text" in rd) {
      return rd.text;
    }
    return rd;
  }
  return raw;
}

function withTimeout(promise, ms) {
  if (!ms) return promise;
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`timeout after ${ms}ms`)), ms);
    Promise.resolve(promise).then(
      (v) => { clearTimeout(timer); resolve(v); },
      (e) => { clearTimeout(timer); reject(e); },
    );
  });
}

// ─── parallel / map ────────────────────────────────────
async function executeParallel(step, variables, stepIndex, deps, defaultSource, depth, state) {
  const pSteps = step.steps || [];
  if (!pSteps.length) return { status: "error", result: "", outputAs: step.output_as || `_step${stepIndex}`, reason: "parallel group: no steps" };
  const strategy = step.strategy || "first_ok";
  const outputAs = step.output_as || `_step${stepIndex}`;
  const childDepth = depth + 1;
  if (childDepth > MAX_DEPTH) return { status: "error", result: "", outputAs, reason: "NESTING_EXCEEDED" };

  if (strategy === "first_ok") {
    const results = await Promise.allSettled(
      pSteps.map((ps) => dispatchStep(ps, variables, stepIndex, deps, defaultSource, childDepth, state)),
    );
    const winner = results.find((r) => r.status === "fulfilled" && r.value.status === "ok");
    if (winner) return { status: "ok", result: winner.value.result, outputAs };
    return { status: "error", result: "", outputAs, reason: "all parallel steps failed" };
  }

  // all：全部执行收集（delegated 单独记录）
  const results = await Promise.allSettled(
    pSteps.map((ps, pi) => dispatchStep(ps, variables, stepIndex, deps, defaultSource, childDepth, state)),
  );
  const collected = [];
  results.forEach((r, i) => {
    if (r.status === "fulfilled") {
      const v = r.value;
      if (v.status === "ok") {
        variables[v.outputAs] = v.result;
        collected.push(v.result);
      } else if (v.status === "delegated") {
        state.delegated.push({ step: `${stepIndex}.${pSteps[i].id || `p${i}`}`, directive: v.result, output_as: v.outputAs });
      } else {
        state.warnings.push(`parallel branch failed: ${v.reason}`);
      }
    }
  });
  return { status: "ok", result: JSON.stringify(collected), outputAs };
}

async function executeMap(step, variables, stepIndex, deps, defaultSource, depth, state) {
  const outputAs = step.output_as || `_step${stepIndex}`;
  if (!deps.mapEnabled) {
    return { status: "error", result: "", outputAs, reason: "map_disabled" };
  }
  if (depth >= MAX_DEPTH) {
    return { status: "error", result: "", outputAs, reason: "nested map not allowed (depth limit 2)" };
  }
  const itemsVar = step.items || "";
  if (!itemsVar) return { status: "error", result: "", outputAs, reason: "mode:map requires 'items' field" };
  const raw = variables[itemsVar] || "";
  const collectAs = step.collect_as || outputAs;
  if (!raw) {
    variables[collectAs] = "[]";
    return { status: "ok", result: "[]", outputAs };
  }
  let items;
  try {
    items = JSON.parse(raw);
  } catch {
    return { status: "error", result: "", outputAs, reason: `items '${itemsVar}' is not valid JSON` };
  }
  if (!Array.isArray(items)) return { status: "error", result: "", outputAs, reason: `items '${itemsVar}' is not a list` };
  if (items.length > MAP_HARD_CAP) return { status: "error", result: "", outputAs, reason: `LOOP_LIMIT: ${items.length} > ${MAP_HARD_CAP}` };

  const elementAs = step.as || "item";
  const bodySteps = step.steps || [];
  const onError = step.on_error || "break";
  const concurrency = step.concurrency || "serial";
  const childDepth = depth + 1;
  const collected = [];
  let skipped = 0;

  const runElement = async (idx, element) => {
    const v = { ...variables };
    v[elementAs] = typeof element === "string" ? element : JSON.stringify(element);
    let lastVal = "";
    let lastOut = "";
    for (const bs of bodySteps) {
      const r = await dispatchStep(bs, v, idx, deps, defaultSource, childDepth, state);
      if (r.status === "ok") {
        v[r.outputAs] = r.result;
        lastVal = r.result;
        lastOut = r.outputAs;
      } else if (r.status === "error") {
        if (onError === "break") throw new Error(r.reason);
        return { status: "error" };
      } else {
        // delegated：跳过此元素
        return { status: "error" };
      }
    }
    return { status: "ok", value: lastVal };
  };

  if (concurrency === "parallel") {
    const settled = await Promise.allSettled(items.map((el, i) => runElement(i + 1, el)));
    for (const s of settled) {
      if (s.status === "fulfilled" && s.value.status === "ok") collected.push(s.value.value);
      else {
        skipped++;
        if (onError === "break") return { status: "error", result: "", outputAs, reason: `element failed (skipped=${skipped})` };
      }
    }
  } else {
    for (let i = 0; i < items.length; i++) {
      try {
        const r = await runElement(i + 1, items[i]);
        if (r.status === "ok") collected.push(r.value);
      } catch (e) {
        if (onError === "break") return { status: "error", result: "", outputAs, reason: `element ${i + 1} failed: ${e.message}` };
        skipped++;
      }
    }
  }

  variables[collectAs] = JSON.stringify(collected);
  return { status: "ok", result: JSON.stringify({ count: collected.length, skipped, collect_as: collectAs }), outputAs };
}

// ─── 统一步分发 ────────────────────────────────────────
async function dispatchStep(step, variables, stepIndex, deps, defaultSource, depth, state) {
  if (!step) return { status: "error", result: "", outputAs: "", reason: "empty step" };
  const mode = step.mode || "toolchain";
  if (mode === "parallel") {
    return executeParallel(step, variables, stepIndex, deps, defaultSource, depth, state);
  }
  if (mode === "map") {
    return executeMap(step, variables, stepIndex, deps, defaultSource, depth, state);
  }
  return executeStep(step, variables, stepIndex, deps, defaultSource, state.warnings);
}

function getFinalOutput(variables, steps) {
  for (let i = steps.length - 1; i >= 0; i--) {
    const key = steps[i].output_as || "";
    if (key && key in variables && variables[key]) return variables[key];
  }
  return "";
}

/** 最终输出友好化：JSON 对象含 result 字段 → 提取 result（协议 rst_data 直接承载） */
function friendlyOutput(raw) {
  if (typeof raw !== "string") return raw;
  try {
    const o = JSON.parse(raw);
    if (o && typeof o === "object" && !Array.isArray(o) && "result" in o) return String(o.result);
  } catch { /* 非 JSON 文本 */ }
  return raw;
}

// ─── path 声明校验 ─────────────────────────────────────
export function validateDeclaration(pathDef) {
  const missing = ["id", "name", "version", "type", "steps"].filter((f) => !(f in pathDef));
  if (missing.length) return { ok: false, error: `missing fields: ${missing.join(", ")} (expected: id, name, version, type, steps)` };
  if (!ACCEPTED_TYPES.has(pathDef.type)) return { ok: false, error: `unsupported type: ${pathDef.type}` };
  const mode = pathDef.mode || "toolchain";
  if (!ACCEPTED_MODES.has(mode)) return { ok: false, error: `unsupported mode: ${mode}` };
  if (!Array.isArray(pathDef.steps) || pathDef.steps.length === 0) return { ok: false, error: "steps must be a non-empty array" };
  return { ok: true };
}

// ─── PathRegistry（注册 + 发现 + schema 化）─────────────
export class PathRegistry {
  constructor() {
    this.paths = new Map();
  }
  register(id, def) {
    const v = validateDeclaration(def);
    if (!v.ok) throw new PathError("INVALID_DECLARATION", v.error);
    this.paths.set(id, { ...def, id });
    return { ok: true, id };
  }
  resolve(name) {
    if (this.paths.has(name)) return this.paths.get(name);
    for (const def of this.paths.values()) {
      if (def.name === name || def.name_zh === name) return def;
    }
    return undefined;
  }
  has(id) {
    return this.paths.has(id);
  }
  unregister(id) {
    return this.paths.delete(id);
  }
  list() {
    return [...this.paths.entries()].map(([id, def]) => ({ id, def }));
  }
  /** 注册 path 的扁平 directives（供 query 发现合并，对齐 SPEC §1.2.7 canonical / A4 register_path） */
  schemaEntries() {
    return [...this.paths.values()].map((def) => ({
      domain: "text-cli",
      domain_zh: "文本指令",
      action: "path",
      action_zh: "路径",
      usage: `text-cli;path,${def.id},<input>`,
      usage_zh: `文本指令;路径,${def.id},<input>`,
      description: `Execute path: ${def.name}`,
      description_zh: `执行路径: ${def.name}`,
      package: def.id,
      runtime: "path",
      params: def.input_schema && def.input_schema.properties ? Object.keys(def.input_schema.properties) : [],
      outputs: [def.output_schema && def.output_schema.type ? def.output_schema.type : "text"],
    }));
  }
}

// ─── 顶层执行 ──────────────────────────────────────────
/**
 * 执行一个 path 定义。
 * @param {object} pathDef
 * @param {string} initialInput 用户输入（可为 JSON 字符串）
 * @param {object} deps { dispatch, httpDispatch?, mapEnabled?=false, now? }
 */
export async function runPath(pathDef, initialInput, deps = {}) {
  const variables = { input: initialInput };
  const defaultSource = pathDef.default_source;
  const state = { delegated: [], warnings: [], skippedOutputs: new Set() };
  const steps = pathDef.steps || [];
  const pathId = pathDef.id || "unnamed";
  let completed = 0;

  for (let i = 0; i < steps.length; i++) {
    const step = steps[i];
    const idx = i + 1;
    // L1: if 条件
    if ("if" in step) {
      const ok = evaluateIf(step.if, variables, state.warnings);
      if (!ok) {
        const outputAs = step.output_as || `_step${idx}`;
        state.skippedOutputs.add(outputAs);
        state.warnings.push(`step ${idx} skipped: ${step.instruction || step.directive || "?"}`);
        // 后续步骤引用被跳过输出 → BRANCH_NO_MATCH
        for (const later of steps.slice(idx)) {
          const ld = later.instruction || later.directive || "";
          if (referencesSkipped(ld, state.skippedOutputs)) {
            return {
              status: "error", code: "BRANCH_NO_MATCH",
              path_id: pathId, total_steps: steps.length, completed_steps: i,
              failed_step: idx, failed_step_id: step.id || "",
              reason: "no executable branch", warnings: state.warnings,
            };
          }
        }
        continue;
      }
    }

    // L2: 统一分发（toolchain / parallel / map）
    const r = await dispatchStep(step, variables, idx, deps, defaultSource, 0, state);
    if (r.status === "ok") {
      variables[r.outputAs] = r.result;
      completed = idx;
    } else if (r.status === "delegated") {
      state.delegated.push({ step: idx, directive: r.result, output_as: r.outputAs });
      completed = idx;
    } else {
      // error → degradation 链 / 熔断
      const recovered = await tryDegradation(step, variables, idx, deps, defaultSource, state, r);
      if (recovered) {
        completed = idx;
        continue;
      }
      const code = step.degradation ? "DEGRADE_EXHAUSTED" : "CIRCUIT_BREAK";
      return {
        status: "error", code,
        path_id: pathId, total_steps: steps.length, completed_steps: i,
        failed_step: idx, failed_step_id: step.id || "",
        reason: r.reason || "step failed", warnings: state.warnings,
      };
    }
  }

  const output = friendlyOutput(getFinalOutput(variables, steps));
  if (state.delegated.length) {
    return {
      status: "partial", code: "PARTIAL",
      path_id: pathId, total_steps: steps.length, completed_steps: completed,
      delegated: state.delegated, output, warnings: state.warnings,
    };
  }
  return {
    status: "ok", code: "OK",
    path_id: pathId, total_steps: steps.length, completed_steps: completed,
    output, warnings: state.warnings,
  };
}

/** 降级链：逐个尝试 degrade_steps（禁止嵌套 degradation），任一成功即恢复 */
async function tryDegradation(step, variables, stepIndex, deps, defaultSource, state, failure) {
  const degradeSteps = step.degradation || [];
  const outputAs = step.output_as || `_step${stepIndex}`;
  for (const ds of degradeSteps) {
    if ("degradation" in ds) {
      state.warnings.push(`nested degradation rejected for step ${ds.id || "degrade"}`);
      continue;
    }
    try {
      const r = await dispatchStep(ds, variables, stepIndex, deps, defaultSource, 0, state);
      if (r.status === "ok") {
        variables[outputAs] = r.result;
        state.warnings.push(`degraded to ${ds.id || "?"}`);
        return true;
      }
    } catch { /* 继续尝试 */ }
  }
  return false;
}

// ─── withPath 中间件（五入口）──────────────────────────
/**
 * path 中间件：拦截 `text-cli;path,...`（其余 fallthrough）。
 * 入口：text-cli;path,<inline-json|file|name>[,<input>][,--register][,--json]
 * @param {PathRegistry} registry
 * @param {object} [opts] { ancestorChain, httpDispatch, mapEnabled, now, readFile }
 */
export function withPath(registry, opts = {}) {
  const ancestor = opts.ancestorChain || defaultChain;
  const readFile = opts.readFile; // 宿主注入（CF 无文件系统时由调用方预加载）
  const mapEnabled = opts.mapEnabled ?? false;

  return (next) => async (domain, action, params, context) => {
    if (domain !== "text-cli" || action !== "path") return next(domain, action, params, context);
    if (!params || !params[0]) {
      return { rst_types: "text", rst_err: "INVALID_PARAMS", rst_data: { reason: "usage: text-cli;path,<pathId|file|inline-json>[,<input>][,--register][,--json]" } };
    }

    const first = String(params[0]).trim();
    let registerMode = false;
    let jsonMode = false;
    let initialInput = "";
    for (const p of params.slice(1)) {
      const ps = String(p).trim();
      if (ps === "--register") registerMode = true;
      else if (ps === "--json") jsonMode = true;
      else initialInput = ps;
    }

    // 1. 加载 path 定义：inline JSON / registry name / 文件
    let pathDef = null;
    let byName = false;
    if (first.startsWith("{")) {
      try {
        pathDef = JSON.parse(first);
      } catch (e) {
        return { rst_types: "text", rst_err: "INVALID_PARAMS", rst_data: { reason: `inline JSON parse failed: ${e.message}` } };
      }
    } else {
      const named = registry.resolve(first);
      if (named) {
        pathDef = named;
        byName = true;
      } else if (readFile) {
        try {
          pathDef = JSON.parse(readFile(first));
        } catch (e) {
          return { rst_types: "text", rst_err: "ERR_NOT_FOUND", rst_data: { reason: `path not found: ${first} (${e.message})` } };
        }
      } else {
        return { rst_types: "text", rst_err: "ERR_NOT_FOUND", rst_data: { reason: `path not found: ${first}` } };
      }
    }

    // 2. --register：校验 + 注册（schema 化）
    if (registerMode) {
      try {
        registry.register(pathDef.id, pathDef);
      } catch (e) {
        return { rst_types: "text", rst_err: "INVALID_PARAMS", rst_data: { reason: e.reason || e.message } };
      }
      if (!initialInput) {
        return { rst_types: "text", rst_data: { status: "ok", code: "REGISTERED", path_id: pathDef.id, type: pathDef.type, version: pathDef.version, requires: pathDef.requires || [] }, rst_err: "" };
      }
    }

    // 3. 环检测（仅按 name 注册命中的 path 推键；inline 每次新执行）
    const key = byName ? cycleKey.path(pathDef.id) : null;
    if (key && ancestor.contains(key)) {
      return { rst_types: "text", rst_err: "ERR_EXECUTION", rst_data: { reason: "CYCLE_DETECTED" } };
    }

    const deps = {
      dispatch: next,
      httpDispatch: opts.httpDispatch,
      mapEnabled,
      now: opts.now,
    };

    const exec = () => runPath(pathDef, initialInput, deps);
    let result;
    if (key) {
      ancestor.push(key);
      try {
        result = await exec();
      } finally {
        ancestor.pop(key);
      }
    } else {
      result = await exec();
    }

    // 4. 信封化（rst_data 直接承载 path 结果）
    return { rst_types: "text", rst_data: result, rst_err: "" };
  };
}

export { interpolateParams as _interpolateParams, resolveVar as _resolveVar, evaluateIf as _evaluateIf };
