// index — Worker 入口（真实部署：wrangler 构建后上传）
//
// 部署绑定：
//   DB = D1 binding（初始化 schema.sql）
//   AUTH_SECRET / KEY_ENC_SECRET = Worker Secrets
//   PACKAGE_SOURCE_DIR = 包源（wrangler 内联资源或 KV）
//
// 本地测试：直接用 runtime.createWorkerRuntime(env) 不经过本入口；
// 本入口只做 request → runtime 的粘合。

import { createWorkerRuntime } from "./runtime.js";

export default {
  async fetch(request, env) {
    const rt = createWorkerRuntime(env);
    return rt.handle(request);
  },
};
