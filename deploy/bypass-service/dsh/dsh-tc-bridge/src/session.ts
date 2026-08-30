// session 透写：Model-visible ⟺ logged（红线⑧）。
// 桥把每次调用（prompt + 返回）写进 dsh session 事件，使 tc 信封成为 session log 里一段普通 tool 结果。
// 通过依赖注入抽象（apply(ctx) 时接 dsh 的 message/event 机制；纯逻辑可 mock 单测）。
import type { ToolResult } from './types.js';

/** 一次桥调用的 session 记录（脱敏：不写 Service-token / Access-token 明文，红线⑦） */
export interface SessionRecord {
  tool: string;
  prompt: string;
  result?: ToolResult;
  error?: string;
  /** 是否成功（rst_err 为空且非异步） */
  ok: boolean;
  ts: number;
}

/** session 写入器抽象（宿主注入：dsh 的 message/event 机制；测试用内存实现） */
export interface SessionWriter {
  /** 写一条调用记录（Model-visible ⟺ logged） */
  write(record: SessionRecord): void;
}

/** 内存实现（单测 / 无 dsh 环境时使用）；不写任何持久层 */
export class MemorySessionWriter implements SessionWriter {
  private _records: SessionRecord[] = [];
  write(record: SessionRecord): void {
    this._records.push(record);
  }
  get records(): readonly SessionRecord[] {
    return this._records;
  }
  clear(): void {
    this._records = [];
  }
}

/** 组装 SessionRecord（统一入口，供各 tool 调用） */
export function makeSessionRecord(tool: string, prompt: string, result?: ToolResult, error?: string): SessionRecord {
  return {
    tool,
    prompt,
    result,
    error,
    ok: !!result?.ok && !error,
    ts: Date.now(),
  };
}
