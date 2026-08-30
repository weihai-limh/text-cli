// 测试夹具：声明式 handler（对齐 tc 包形态 module.exports = {domainAlias, directives}）
"use strict";

module.exports = {
  domainAlias: "tc-math",
  directives: {
    eval: {
      handler(params) {
        const expr = (params[0] ?? "0").trim();
        if (!/^[0-9+\-*/().\s]+$/.test(expr)) {
          return { status: "error", reason: "unsafe expression" };
        }
        const value = Function(`"use strict"; return (${expr});`)();
        if (typeof value !== "number" || Number.isNaN(value)) {
          return { status: "error", reason: `non-numeric result: ${expr}` };
        }
        return { status: "ok", result: value };
      },
    },
    version: {
      handler() {
        return { status: "ok", result: "0.1.0" };
      },
    },
  },
};
