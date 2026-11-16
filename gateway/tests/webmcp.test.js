import test from "node:test";
import assert from "node:assert/strict";
import { registerWebMCP } from "../gpu_gateway/static/webmcp.js";

test("unsupported browsers keep the Web UI usable", async () => {
  assert.equal(await registerWebMCP({ context: undefined, definitions: [] }), false);
});
test("WebMCP invokes the common API and never registers approval", async () => {
  const registered = [], invoked = [], controller = new AbortController();
  const context = { registerTool: async (tool, options) => registered.push({tool, options}) };
  assert.equal(await registerWebMCP({context, signal: controller.signal,
    definitions: [{name:"experiments_get", description:"Read", inputSchema:{type:"object"}, annotations:{readOnlyHint:true}}, {name:"approve_experiment"}],
    invoke: async (...args) => { invoked.push(args); return {state:"running"}; }
  }), true);
  assert.equal(registered.length, 1);
  assert.equal(registered[0].options.signal, controller.signal);
  assert.equal(registered[0].tool.annotations.untrustedContentHint, true);
  assert.equal(await registered[0].tool.execute({run_id:"a"}), '{"state":"running"}');
  assert.deepEqual(invoked, [["experiments_get", {run_id:"a"}]]);
});
test("registration failures are visible, not silently claimed as support", async () => {
  await assert.rejects(registerWebMCP({ context: {registerTool: async () => {throw new Error("denied");}}, definitions: [{name:"x"}] }), /denied/);
});
