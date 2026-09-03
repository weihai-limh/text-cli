exports.main = async (event, context) => {
  const prompt = event.prompt || "";
  const parts = prompt.split(";");
  if (parts.length < 2) {
    return { rst_types: "text", rst_data: { status: "error", reason: "invalid" }, rst_err: "ERR_EXECUTION" };
  }

  const actionPart = parts[1].split(",");
  const name = actionPart[1] ? actionPart[1].trim() : "World";
  return { rst_types: "text", rst_data: { status: "ok", result: `Hello, ${name}!` }, rst_err: "" };
};
