import { describe, expect, it } from "vitest";
import { ancestorChain, MAX_CHAIN, type AncestorKey } from "../src/ancestor-chain.js";
import { guardDispatch, CycleDetectedError, cycleKey } from "../src/guard.js";

/** 在链上下文内执行并返回结果 */
async function inChain<T>(keys: AncestorKey[], fn: () => Promise<T>): Promise<T> {
  return ancestorChain.run(keys, () => fn());
}

describe("ancestorChain：祖先链基础", () => {
  it("run 内 push/pop/contains 正常", () => {
    ancestorChain.run(["path:a"], () => {
      expect(ancestorChain.contains("path:a")).toBe(true);
      expect(ancestorChain.push("path:b")).toBe(true);
      expect(ancestorChain.current()).toEqual(["path:a", "path:b"]);
      ancestorChain.pop("path:b");
      expect(ancestorChain.current()).toEqual(["path:a"]);
    });
  });

  it("run 外（无上下文）→ push 不检测、contains false", () => {
    expect(ancestorChain.contains("path:a")).toBe(false);
    expect(ancestorChain.push("path:a")).toBe(true); // 无链上下文透传
  });

  it("链长上限 32：超限拒绝", () => {
    ancestorChain.run([], () => {
      const keys: AncestorKey[] = [];
      for (let i = 0; i < MAX_CHAIN; i++) {
        const k = `path:k${i}` as AncestorKey;
        expect(ancestorChain.push(k)).toBe(true);
        keys.push(k);
      }
      expect(ancestorChain.push("path:overflow" as AncestorKey)).toBe(false);
      for (const k of keys) ancestorChain.pop(k);
    });
  });
});

describe("guardDispatch：dispatchFn 单守卫（功能设计 §4.4.3）", () => {
  it("四类环之一：path 自环——同键重入 → CycleDetectedError", async () => {
    const guarded = guardDispatch(
      async (id: string) => {
        // 模拟 path 内部再次 dispatch 同 path
        try {
          await guarded(id);
          return "inner";
        } catch (e) {
          if (e instanceof CycleDetectedError) return "cycle-blocked";
          throw e;
        }
      },
      (id) => cycleKey.path(id),
    );
    const result = await inChain([], () => guarded("outer"));
    expect(result).toBe("cycle-blocked");
  });

  it("四类环之二：聚合自环——agg:web 嵌套 agg:web → 拒绝", async () => {
    const guarded = guardDispatch(async () => "ok", () => cycleKey.agg("web"));
    let cycleBlocked = false;
    const inner = guardDispatch(
      async () => {
        try {
          await guarded();
        } catch (e) {
          if (e instanceof CycleDetectedError) cycleBlocked = true;
          else throw e;
        }
        return "inner";
      },
      () => cycleKey.agg("web"),
    );
    await inChain([], () => inner());
    expect(cycleBlocked).toBe(true);
  });

  it("四类环之三：跨类型互环——agg:web → path:a → path:a 重入 → 拒绝", async () => {
    let pathReentered = false;
    // path:a 内部再调 path:a（同键重入）
    const pathGuard = guardDispatch(
      async (id: string) => {
        try {
          await pathGuard(id);
          return "inner";
        } catch (e) {
          if (e instanceof CycleDetectedError) pathReentered = true;
          else throw e;
          return "blocked";
        }
      },
      (id) => cycleKey.path(id),
    );
    // agg:web 的 provider 是 path:a
    const aggGuard = guardDispatch(
      async () => {
        await pathGuard("a");
        return "agg-ok";
      },
      () => cycleKey.agg("web"),
    );
    await inChain([], () => aggGuard());
    expect(pathReentered).toBe(true);
  });

  it("四类环之四：native 重入——同 domain;action 两次 → 拒绝", async () => {
    const guarded = guardDispatch(async () => "ok", (d: string, a: string) => cycleKey.native(d, a));
    let blocked = false;
    const inner = guardDispatch(
      async () => {
        try {
          await guarded("d", "a");
        } catch (e) {
          if (e instanceof CycleDetectedError) blocked = true;
          else throw e;
        }
        return "inner";
      },
      (d: string, a: string) => cycleKey.native(d, a),
    );
    await inChain([], () => inner("d", "a"));
    expect(blocked).toBe(true);
  });

  it("正常调用：push → execute → finally pop（链恢复原状）", async () => {
    const guarded = guardDispatch(async () => "ok", () => cycleKey.native("d", "a"));
    await inChain(["path:x"], async () => {
      expect(ancestorChain.current()).toEqual(["path:x"]);
      await guarded();
      expect(ancestorChain.current()).toEqual(["path:x"]); // pop 后恢复
    });
  });

  it("执行抛错也 pop（finally 语义）", async () => {
    const guarded = guardDispatch(
      async () => {
        throw new Error("boom");
      },
      () => cycleKey.native("d", "a"),
    );
    await inChain(["path:x"], async () => {
      await expect(guarded()).rejects.toThrow("boom");
      expect(ancestorChain.current()).toEqual(["path:x"]);
    });
  });
});

describe("断点 A：jobs 恢复快照（功能设计 §4.4.3）", () => {
  it("snapshot 捕获 → restore（enterWith）重建链", async () => {
    let snapshot: AncestorKey[] = [];
    await ancestorChain.run(["path:outer"], async () => {
      snapshot = ancestorChain.snapshot(); // 任务启动时捕获
    });
    expect(snapshot).toEqual(["path:outer"]);

    // 模拟任务恢复（新 async 上下文，链已断）
    await new Promise<void>((resolve) => {
      ancestorChain.restore(snapshot); // enterWith 重建
      expect(ancestorChain.current()).toEqual(["path:outer"]);
      resolve();
    });
  });
});
