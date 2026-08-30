/**
 * tcToDsh——tc 指令 → dsh 工具调用映射（功能设计 §3.3 工具命名 + §5.1 六段管道①）
 *
 * 复用 textcli-core `parser.js`（零改动），解析结果映射为 dsh `ctx.tools.execute`
 * 的输入形状。工具名 = `tc__<domain>__<action>`（对齐 mcp-client 双下划线模式）。
 *
 * 纯函数，不依赖 dsh ctx——可外溢复用（R17）。
 */
import tc from "textcli-core";

/** dsh `ctx.tools.execute` 输入形状（tools.md 实证字段子集） */
export interface ToolExecutionInput {
  callId: string;
  /** 工具名：tc__<domain>__<action> */
  name: string;
  arguments: Record<string, unknown>;
  signal?: AbortSignal;
}

export interface MappedOk {
  ok: true;
  domain: string;
  action: string;
  params: string[];
  input: ToolExecutionInput;
}

export interface MappedErr {
  ok: false;
  /** 已组装的协议错误信封（闭集码） */
  envelope: ReturnType<typeof tc.err>;
}

export type TcMapResult = MappedOk | MappedErr;

/** domain/action → 小写连字符规范名（对齐工具命名契约） */
export function normalizeName(s: string): string {
  return s.trim().toLowerCase().replace(/\s+/g, "-");
}

export function tcToDsh(
  prompt: string,
  opts?: { callId?: string },
): TcMapResult {
  const parsed = tc.parse(prompt);
  if (parsed.error) {
    return { ok: false, envelope: tc.err(parsed.error, parsed.reason) };
  }
  const toolName = `tc__${normalizeName(parsed.domain)}__${normalizeName(parsed.action)}`;
  return {
    ok: true,
    domain: parsed.domain,
    action: parsed.action,
    params: parsed.params,
    input: {
      callId:
        opts?.callId ??
        `tc-${Date.now()}-${Math.floor(Math.random() * 1_000_000)}`,
      name: toolName,
      arguments: { params: parsed.params },
    },
  };
}
