import { describe, it, expect } from "vitest";
import { QuotaStore, createMemoryStorage } from "../src/index.js";

/** 可控时钟 */
function clock(start: number) {
  let t = start;
  return {
    now: () => t,
    advance: (ms: number) => {
      t += ms;
    },
  };
}

const DAY = 86_400_000;

describe("runtime-quota 核心", () => {
  it("register + check 初始为 ok 且 remaining=limit", async () => {
    const store = new QuotaStore(createMemoryStorage(), () => 1_700_000_000_000);
    const r = await store.register("api", { period: "day", limit: 10 });
    expect(r.ok).toBe(true);
    const c = await store.check("api");
    expect(c.status).toBe("ok");
    expect(c.remaining).toBe(10);
    expect(c.used).toBe(0);
  });

  it("consume 原子扣减，达上限转 stop 且不超扣", async () => {
    const store = new QuotaStore(createMemoryStorage(), () => 1_700_000_000_000);
    await store.register("api", { period: "day", limit: 3 });
    expect((await store.consume("api")).status).toBe("ok");
    expect((await store.consume("api")).status).toBe("ok");
    const third = await store.consume("api");
    expect(third.status).toBe("ok");
    expect(third.used).toBe(3);
    const fourth = await store.consume("api");
    expect(fourth.status).toBe("stop");
    expect(fourth.used).toBe(3); // 不超扣
    expect(fourth.remaining).toBe(0);
  });

  it("consume n>1 批量扣减", async () => {
    const store = new QuotaStore(createMemoryStorage(), () => 1_700_000_000_000);
    await store.register("bulk", { period: "forever", limit: 10 });
    const r = await store.consume("bulk", 4);
    expect(r.status).toBe("ok");
    expect(r.used).toBe(4);
    expect(r.remaining).toBe(6);
  });

  it("day 周期跨天自动翻转清零", async () => {
    const c = clock(1_700_000_000_000); // 某天
    const store = new QuotaStore(createMemoryStorage(), c.now);
    await store.register("daily", { period: "day", limit: 1 });
    expect((await store.consume("daily")).status).toBe("ok");
    expect((await store.consume("daily")).status).toBe("stop");
    c.advance(DAY + 1000); // 跨到第二天
    const after = await store.check("daily");
    expect(after.status).toBe("ok");
    expect(after.used).toBe(0);
    expect(after.remaining).toBe(1);
  });

  it("month 周期跨月翻转", async () => {
    // 2023-01-31 23:59:59 UTC
    const c = clock(Date.UTC(2023, 0, 31, 23, 59, 59));
    const store = new QuotaStore(createMemoryStorage(), c.now);
    await store.register("mon", { period: "month", limit: 1 });
    await store.consume("mon");
    expect((await store.check("mon")).status).toBe("stop");
    c.advance(2000); // 进入 2023-02-01
    expect((await store.check("mon")).status).toBe("ok");
  });

  it("forever 周期不翻转", async () => {
    const c = clock(1_700_000_000_000);
    const store = new QuotaStore(createMemoryStorage(), c.now);
    await store.register("perm", { period: "forever", limit: 2 });
    await store.consume("perm");
    await store.consume("perm"); // used=2 → stop
    expect((await store.check("perm")).status).toBe("stop");
    c.advance(365 * DAY);
    expect((await store.check("perm")).status).toBe("stop"); // 不翻转，仍 stop
  });

  it("reset 清零 used；unregister 后 check 找不到", async () => {
    const store = new QuotaStore(createMemoryStorage(), () => 1_700_000_000_000);
    await store.register("r", { period: "day", limit: 1 });
    await store.consume("r");
    expect((await store.check("r")).status).toBe("stop");
    await store.reset("r");
    expect((await store.check("r")).status).toBe("ok");
    await store.unregister("r");
    expect((await store.check("r")).ok).toBe(false);
  });

  it("list 返回全部记录含 status", async () => {
    const store = new QuotaStore(createMemoryStorage(), () => 1_700_000_000_000);
    await store.register("a", { period: "day", limit: 1 });
    await store.register("b", { period: "day", limit: 5 });
    await store.consume("a");
    const l = await store.list();
    expect(l.ok).toBe(true);
    expect(l.records?.length).toBe(2);
    const a = l.records?.find((x) => x.id === "a");
    expect(a?.status).toBe("stop");
    const b = l.records?.find((x) => x.id === "b");
    expect(b?.status).toBe("ok");
  });

  it("重复 register 报错；未注册 consume 报错", async () => {
    const store = new QuotaStore(createMemoryStorage(), () => 1_700_000_000_000);
    await store.register("x", { period: "day", limit: 1 });
    expect((await store.register("x", { period: "day", limit: 1 })).ok).toBe(false);
    expect((await store.consume("nope")).ok).toBe(false);
    expect((await store.consume("x", 0)).ok).toBe(false); // n 非法
  });
});
