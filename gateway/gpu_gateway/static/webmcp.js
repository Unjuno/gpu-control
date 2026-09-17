/** W3C WebMCP draft surface, feature-detected. Not a Remote MCP polyfill. */
export async function registerWebMCP({ context, definitions, invoke, signal }) {
  if (!context || typeof context.registerTool !== "function") return false;
  for (const tool of definitions) {
    // Approval is deliberately absent from the public tool list.
    if (tool.name === "authorize_experiment" || tool.name.includes("approve")) continue;
    await context.registerTool({
      name: tool.name,
      description: tool.description,
      inputSchema: tool.inputSchema,
      annotations: {
        readOnlyHint: Boolean(tool.annotations?.readOnlyHint),
        consequentialHint: ["experiments_submit", "experiments_cancel"].includes(tool.name),
        untrustedContentHint: ["experiments_get", "experiments_list"].includes(tool.name),
      },
      execute: async (input) => JSON.stringify(await invoke(tool.name, input)),
    }, { signal });
  }
  return true;
}
