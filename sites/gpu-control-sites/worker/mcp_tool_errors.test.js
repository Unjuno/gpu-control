import assert from "node:assert/strict";
import test from "node:test";
import { mcpToolErrorCode } from "./mcp_tool_errors.js";

test("MCP tool errors expose only registered stable domain codes", () => {
  assert.equal(mcpToolErrorCode(new Error("GOOGLE_COLAB_CONNECTION_REQUIRED")), "GOOGLE_COLAB_CONNECTION_REQUIRED");
  assert.equal(mcpToolErrorCode(new Error("arbitrary provider response text")), "INTERNAL_ERROR");
});

test("RunPod details are exposed only for its typed bounded error contract", () => {
  assert.equal(mcpToolErrorCode({ name: "RunpodProviderError", code: "RUNPOD_NETWORK_ERROR" }), "RUNPOD_NETWORK_ERROR");
  assert.equal(mcpToolErrorCode({ name: "Error", code: "RUNPOD_NETWORK_ERROR" }), "INTERNAL_ERROR");
  assert.equal(mcpToolErrorCode({ name: "RunpodProviderError", code: "provider returned a secret" }), "INTERNAL_ERROR");
  assert.equal(mcpToolErrorCode(new Error("RUNPOD_ACCOUNT_LEASE_MISSING")), "RUNPOD_ACCOUNT_LEASE_MISSING");
  assert.equal(mcpToolErrorCode(new Error("RUNPOD_PROVIDER_JOB_RECOVERY_FAILED")), "RUNPOD_PROVIDER_JOB_RECOVERY_FAILED");
});

test("legacy adapter failures collapse to one public error code", () => {
  assert.equal(mcpToolErrorCode(new Error("GATEWAY_DELEGATION_TIMEOUT")), "GATEWAY_DELEGATION_FAILED");
});
