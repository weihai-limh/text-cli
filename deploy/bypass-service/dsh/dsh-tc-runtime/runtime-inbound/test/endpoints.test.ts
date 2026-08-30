import { describe, expect, it } from "vitest";
import { handleHealth, handleSkills, handleTaskQuery, MECHANISMS } from "../src/endpoints.js";
import { buildDirectives, type ToolSchema } from "@dsh-tc/runtime-mapper";

const schemas: ToolSchema[] = [
  {
    name: "tc__tc-math__eval",
    description: "Evaluate arithmetic expression",
    tc: { domain: "tc-math", action: "eval", package: "tc-math", runtime: "js", domain_zh: "数学工具", action_zh: "计算" },
  },
  {
    name: "tc__weather__query",
    description: "Query weather",
    tc: { domain: "weather", action: "query", package: "weather", runtime: "js" },
  },
];
const directives = buildDirectives(schemas);

describe("协议端点处理器", () => {
  it("health：status/version/spec_version/mechanism 9 词表", () => {
    const env = handleHealth({ version: "0.1.1", spec_version: "1.3.2" });
    const data = env.rst_data as Record<string, unknown>;
    expect(data.status).toBe("ok");
    expect(data.spec_version).toBe("1.3.2");
    expect(data.mechanism).toEqual([...MECHANISMS]);
    expect(data.mechanism).toHaveLength(9);
  });

  it("skills：白名单为空 → 全部暴露", () => {
    const env = handleSkills(directives, []);
    expect(env.rst_data).toEqual({ skills: [{ domain: "tc-math", action: "eval" }, { domain: "weather", action: "query" }] });
  });

  it("skills：白名单有内容 → 只暴露列出条目", () => {
    const env = handleSkills(directives, ["weather;query"]);
    expect(env.rst_data).toEqual({ skills: [{ domain: "weather", action: "query" }] });
  });

  it("tasks：存在 → {status:ok, task} 五态信封", async () => {
    const env = await handleTaskQuery("asr-0001", {
      readTask: async () => ({
        task_id: "asr-0001",
        domain: "asr",
        action: "transcribe",
        state: "running",
        progress: "步骤 3/8",
      }),
    });
    expect(env).not.toBeNull();
    expect(env!.rst_err).toBe("");
    expect(env!.rst_data).toMatchObject({ status: "ok", task: { task_id: "asr-0001", state: "running" } });
  });

  it("tasks：不存在 → null（HTTP 层映射 404 + not_found）", async () => {
    const env = await handleTaskQuery("nope", { readTask: async () => null });
    expect(env).toBeNull();
  });
});
