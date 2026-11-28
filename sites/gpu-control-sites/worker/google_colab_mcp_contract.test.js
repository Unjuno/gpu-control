import assert from "node:assert/strict";
import test from "node:test";
import { validGoogleColabExecution, validGoogleColabRuntime, validGoogleColabSession,
  validGoogleColabToolCall, validGoogleColabRuntimeDeletion, isGoogleColabRuntimeProxyUrl } from "./google_colab_mcp_contract.js";

const runtime = { name: "runtimes/gpu-control-test", runtimeSpec: {
  variant: "VARIANT_GPU", accelerator: "T4", shape: "SHAPE_STANDARD",
}, connectionInfo: { token: "opaque-private-runtime-token", expireTime: "2026-11-28T12:00:00Z",
  url: "https://colab.googleusercontent.com/runtime" } };

test("Colab calls accept only the documented bounded lifecycle contract", () => {
  assert.equal(validGoogleColabToolCall("list_runtime_specs", {}), true);
  const sessionId = "run-1";
  const sessionName = runtime.name + "/sessions/" + sessionId;
  assert.equal(validGoogleColabToolCall("create_session", { parent: runtime.name, sessionId }), false);
  assert.equal(validGoogleColabToolCall("create_session", { parent: runtime.name, sessionId }, {
    expectedRuntimeName: runtime.name, expectedSessionId: sessionId,
  }), true);
  assert.equal(validGoogleColabToolCall("create_session", { parent: "runtimes/other", sessionId }, {
    expectedRuntimeName: runtime.name, expectedSessionId: sessionId,
  }), false);
  assert.equal(validGoogleColabToolCall("list_sessions", { parent: runtime.name }), false);
  assert.equal(validGoogleColabToolCall("list_sessions", { parent: runtime.name }, {
    expectedRuntimeName: runtime.name,
  }), true);
  assert.equal(validGoogleColabToolCall("list_sessions", { parent: "runtimes/other" }, {
    expectedRuntimeName: runtime.name,
  }), false);
  assert.equal(validGoogleColabToolCall("list_sessions", { parent: runtime.name, recursive: true }, {
    expectedRuntimeName: runtime.name,
  }), false);
  assert.equal(validGoogleColabToolCall("create_runtime", { runtime: { runtimeSpec: runtime.runtimeSpec },
    requestId: "7b21ceba-679e-4fd9-b1e7-cd53202b87f0" }), true);
  assert.equal(validGoogleColabToolCall("create_runtime", { runtime: { runtimeSpec: runtime.runtimeSpec },
    requestId: "retry-stable-id" }), false);
  assert.equal(validGoogleColabToolCall("execute_code", { code: "print('ok')",
    executionId: "7b21ceba-679e-4fd9-b1e7-cd53202b87f0",
    session: sessionName }, { expectedSessionName: sessionName,
    expectedExecutionId: "7b21ceba-679e-4fd9-b1e7-cd53202b87f0" }), true);
  assert.equal(validGoogleColabToolCall("execute_code", { code: "print('ok')",
    runtime: "runtimes/gpu-control-test", executionId: "7b21ceba-679e-4fd9-b1e7-cd53202b87f0" }), false);
  assert.equal(validGoogleColabToolCall("execute_code", { code: "x".repeat(256 * 1024 + 1),
    executionId: "7b21ceba-679e-4fd9-b1e7-cd53202b87f0",
    session: sessionName }, { expectedSessionName: sessionName,
    expectedExecutionId: "7b21ceba-679e-4fd9-b1e7-cd53202b87f0" }), false);
  assert.equal(validGoogleColabToolCall("execute_code", { code: "print('ok')",
    executionId: "7b21ceba-679e-4fd9-b1e7-cd53202b87f0", session: sessionName }), false);
  assert.equal(validGoogleColabToolCall("get_runtime", { name: runtime.name }), false);
  assert.equal(validGoogleColabToolCall("get_runtime", { name: runtime.name }, {
    expectedRuntimeName: runtime.name,
  }), true);
  assert.equal(validGoogleColabToolCall("delete_runtime", { name: runtime.name }), false);
  assert.equal(validGoogleColabToolCall("delete_runtime", { name: runtime.name }, {
    expectedRuntimeName: runtime.name,
  }), true);
  assert.equal(validGoogleColabToolCall("delete_runtime", { name: runtime.name, allowMissing: true }, {
    expectedRuntimeName: runtime.name,
  }), true);
  assert.equal(validGoogleColabToolCall("delete_runtime", { name: runtime.name, allowMissing: false }, {
    expectedRuntimeName: runtime.name,
  }), false);
  assert.equal(validGoogleColabToolCall("delete_runtime", { name: "runtimes/other-owner-runtime" }, {
    expectedRuntimeName: runtime.name,
  }), false);
  assert.equal(validGoogleColabToolCall("delete_runtime", { name: "https://attacker.example/runtime" }, {
    expectedRuntimeName: runtime.name,
  }), false);
  assert.equal(validGoogleColabToolCall("delete_runtime", { name: runtime.name, force: true }, {
    expectedRuntimeName: runtime.name,
  }), false);
  const ownedSession = sessionName;
  assert.equal(validGoogleColabToolCall("delete_session", { name: ownedSession }), false);
  assert.equal(validGoogleColabToolCall("delete_session", { name: ownedSession }, {
    expectedSessionName: ownedSession,
  }), true);
  assert.equal(validGoogleColabToolCall("delete_session", { name: runtime.name + "/sessions/user-notebook" }, {
    expectedSessionName: ownedSession,
  }), false);
  assert.equal(validGoogleColabToolCall("delete_session", { name: ownedSession, force: true }, {
    expectedSessionName: ownedSession,
  }), false);
  assert.equal(validGoogleColabToolCall("execute_code", { code: "print('ok')", executionId: "id",
    session: "runtimes/gpu-control-test/sessions/run-1", extra: true }), false);
});

test("Colab runtime, session, and execution responses are bound to expected identities", () => {
  assert.equal(validGoogleColabRuntime(runtime), true);
  assert.equal(validGoogleColabRuntime({ ...runtime, connectionInfo: { ...runtime.connectionInfo,
    url: "http://runtime.googleusercontent.com" } }), false);
  for (const url of ["https://attacker.example", "https://colab.googleusercontent.com.attacker.example",
    "https://user:pass@colab.googleusercontent.com", "https://colab.googleusercontent.com:444",
    "https://colab.googleusercontent.com/?redirect=attacker", "https://colab.googleusercontent.com/#fragment"]) {
    assert.equal(isGoogleColabRuntimeProxyUrl(url), false, url);
    assert.equal(validGoogleColabRuntime({ ...runtime, connectionInfo: { ...runtime.connectionInfo, url } }), false, url);
  }
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

test("Colab runtime deletion accepts only Google's empty success response", () => {
  assert.equal(validGoogleColabRuntimeDeletion({}), true);
  assert.equal(validGoogleColabRuntimeDeletion({ deleted: false }), false);
  assert.equal(validGoogleColabRuntimeDeletion({ deleted: true }), false);
  assert.equal(validGoogleColabRuntimeDeletion(null), false);
  assert.equal(validGoogleColabRuntimeDeletion([]), false);
});
