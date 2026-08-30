// executor — D1 可执行包受限执行（分级能力注入）
//
// handler_js 是源码字符串（存 D1 packages.handler_js），执行时构造为
// async (params, context, sandbox) => ...。handler 只能经注入的 sandbox 通道做事，
// 拿不到裸全局（Worker 无 process/fs/child_process，天然更干净；本地测试同构）。
//
// 分级能力（对齐 7 类包策略的 Cloudflare 投影）：
//   pure             → sandbox = {}（无 fetch / 无凭据）
//   network          → sandbox.fetch（受控出站）
//   config-inject    → sandbox.credential.get（配置注入）
//   network-credential → sandbox.fetch + sandbox.credential.get
//   file-io / image  → Worker 无文件系统，不提供（schema 不应声明）

/**
 * 构造分级 sandbox。
 * @param {object} capability 包 schema.capability
 * @param {object} deps { fetch?, getKey? }
 */
export function createSandbox(capability, deps = {}) {
  const kind = (capability && capability.kind) || "pure";
  const allowed = (capability && capability.credentials) || [];
  const sandbox = {};
  if (kind === "network" || kind === "network-credential") {
    sandbox.fetch = deps.fetch || globalThis.fetch;
  }
  if (kind === "config-inject" || kind === "network-credential") {
    sandbox.credential = {
      // 授权映射第一防线：只允许包 schema capability.credentials 声明的 service
      get: async (service) => {
        if (allowed.length && !allowed.includes(service)) return undefined;
        return deps.getKey ? deps.getKey(service) : undefined;
      },
    };
  }
  return sandbox;
}

/**
 * 受限执行：构造 handler 并调用。
 * @param {string} handlerJs packages.handler_js 源码字符串
 * @param {object} schema 包 schema（含 capability）
 * @param {string[]} params 指令参数
 * @param {object} [context] 透传上下文（auth/env 等）
 * @param {object} deps { fetch?, getKey? }
 */
export async function runHandler(handlerJs, schema, params, context, deps = {}) {
  const sandbox = createSandbox(schema && schema.capability, deps);
  const factory = new Function(
    "params",
    "context",
    "sandbox",
    `${handlerJs}\n; return typeof main === "function" ? main(params, context, sandbox) : undefined;`,
  );
  return factory(params, context || {}, sandbox);
}
