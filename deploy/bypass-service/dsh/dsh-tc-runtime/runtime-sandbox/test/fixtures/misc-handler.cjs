// 测试夹具：函数式 handler（exports[action] 形态）+ 睡眠（超时验证）
"use strict";

module.exports = {
  sleep: (params) =>
    new Promise((resolve) => {
      const ms = Number(params[0] ?? 1000);
      setTimeout(() => resolve({ status: "ok", result: `slept ${ms}ms` }), ms);
    }),
  boom: () => {
    throw new Error("fixture boom");
  },
};
