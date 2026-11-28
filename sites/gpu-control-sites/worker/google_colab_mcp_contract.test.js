import assert from "node:assert/strict";
import test from "node:test";
import { validGoogleColabExecution, validGoogleColabRuntime, validGoogleColabSession,
  validGoogleColabToolCall } from "./google_colab_mcp_contract.js";

const runtime = { name: "runtimes/gpu-control-test", runtimeSpec: {
  variant: "VARIANT_GPU", accelerator: "T4", shape: "SHAPE_STANDARD",
}, connectionInfo: { token: "opaque-private-runtime-token", expireTime: "2026-11-28T12:00:00Z",
  url: "https://runtime.googleusercontent.com" } };

test("Colab calls accept only the documented bounded lifecycle contract", () => {
  assert.equal(validGoogleColabToolCall("list_runtime_specs", {}), true);
  assert.equal(validGoogleColabToolCall("create_runtime", { runtime: { runtimeSpec: runtime.runtimeSpec },
    requestId: "7b21ceba-679e-4fd9-b1e7-cd53202b87f0" }), true);
  assert.equal(validGoogleColabToolCall("create_runtime", { runtime: { runtimeSpec: runtime.runtimeSpec },
    requestId: "retry-stable-id" }), false);
  assert.equal(validGoogleColabToolCall("execute_code", { code: "print('ok')",
    executionId: "7b21ceba-679e-4fd9-b1e7-cd53202b87f0",
    session: "runtimes/gpu-control-test/sessions/run-1" }), true);
  assert.equal(validGoogleColabToolCall("execute_code", { code: "print('ok')",
    runtime: "runtimes/gpu-control-test", executionId: "7b21ceba-679e-4fd9-b1e7-cd53202b87f0" }), false);
  assert.equal(validGoogleColabToolCall("execute_code", { code: "x".repeat(256 * 1024 + 1),
    executionId: "7b21ceba-679e-4fd9-b1e7-cd53202b87f0",
    session: "runtimes/gpu-control-test/sessions/run-1" }), false);
  assert.equal(validGoogleColabToolCall("delete_runtime", { name: runtime.name }), false);
  assert.equal(validGoogleColabToolCall("execute_code", { code: "print('ok')", executionId: "id",
    session: "runtimes/gpu-control-test/sessions/run-1", extra: true }), false);
});

test("Colab runtime, session, and execution responses are bound to expected identities", () => {
  assert.equal(validGoogleColabRuntime(runtime), true);
  assert.equal(validGoogleColabRuntime({ ...runtime, connectionInfo: { ...runtime.connectionInfo,
    url: "http://runtime.googleusercontent.com" } }), false);
  assert.equal(validGoogleColabSession({ name: "runtimes/gpu-control-test/sessions/run-1" }, runtime.name), true);
  assert.equal(validGoogleColabSession({ name: "runtimes/other/sessions/run-1" }, runtime.name), false);
  assert.equal(validGoogleColabExecution({ session: "runtimes/gpu-control-test/sessions/run-1",
    executionId: "7b21ceba-679e-4fd9-b1e7-cd53202b87f0", executionCount: 1,
    stdout: "ok", stderr: "", result: "", outputTruncated: false },
  "runtimes/gpu-control-test/sessions/run-1", "7b21ceba-679e-4fd9-b1e7-cd53202b87f0"), true);
  assert.equal(validGoogleColabExecution({ session: "runtimes/gpu-control-test/sessions/run-1",
    executionId: "other", executionCount: 1, stdout: "ok", stderr: "", result: "", outputTruncated: false },
  "runtimes/gpu-control-test/sessions/run-1", "7b21ceba-679e-4fd9-b1e7-cd53202b87f0"), false);
});
