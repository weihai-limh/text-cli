module.exports = {
  domainAlias: "你好",
  directives: {
    world: {
      handler: (params) => {
        const name = (params[0] || "").trim() || "World";
        return { status: "ok", result: `Hello, ${name}!` };
      },
      actionAliases: ["世界"],
    },
  },
};
