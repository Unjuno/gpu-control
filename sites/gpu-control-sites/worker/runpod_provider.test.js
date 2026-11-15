import assert from "node:assert/strict";
import test from "node:test";
import { RunpodProviderError, RunpodV2Client, runpodConfigured, validateCreatedPod, validateExecResult } from "./runpod_provider.js";

const env = {
  RUNPOD_API_KEY: "secret-api-key-with-enough-bytes",
  RUNPOD_WORKLOAD_IMAGE: `ghcr.io/unjuno/gpu-control-runpod@sha256:${"a".repeat(64)}`,
  RUNPOD_GPU_ID: "NVIDIA RTX 2000 Ada Generation",
};

function jsonResponse(value, status = 200, headers = {}) {
  return new Response(JSON.stringify(value), { status, headers: { "content-type": "application/json", ...headers } });
}

test("configuration requires an immutable image and bounded secret", () => {
  assert.equal(runpodConfigured(env), true);
  assert.equal(runpodConfigured({ ...env, RUNPOD_WORKLOAD_IMAGE: "ghcr.io/unjuno/image:latest" }), false);
  assert.equal(runpodConfigured({ ...env, RUNPOD_API_KEY: "bad\nkey" }), false);
});

test("create emits one secure GPU with no ports, SSH, Jupyter, or global network", async () => {
  let request;
  const client = new RunpodV2Client(env, { fetchImpl: async (url, init) => {
    request = { url, init, body: JSON.parse(init.body) };
    return jsonResponse({ id: "pod_abc123", status: "PROVISIONING" }, 201);
  } });
  await client.createPod({ runId: "1".repeat(32), dataCenterId: "US-TX-3" });
  assert.equal(request.url, "https://api.runpod.io/v2/pods");
  assert.equal(request.init.redirect, "manual");
  assert.match(request.init.headers.authorization, /^Bearer /);
  assert.deepEqual(request.body.gpu, { id: env.RUNPOD_GPU_ID, count: 1 });
  assert.equal(request.body.cloud, "SECURE");
  assert.deepEqual(request.body.ports, []);
  assert.equal(request.body.startSsh, false);
  assert.equal(request.body.startJupyter, false);
  assert.equal(request.body.globalNetworking, false);
  assert.deepEqual(request.body.dataCenterIds, ["US-TX-3"]);
});

test("registered execution cannot become an arbitrary shell", async () => {
  let body;
  const client = new RunpodV2Client(env, { fetchImpl: async (_url, init) => {
    body = JSON.parse(init.body);
    return jsonResponse({ stdout: "ok", stderr: "", exitCode: 0, timedOut: false, truncated: false, durationMs: 10 });
  } });
  await client.runRegisteredWorkload("pod_abc123", {
    planFingerprint: "b".repeat(64), nonce: "c".repeat(64), steps: 1, seed: 7,
  });
  assert.equal(body.command[0], "/opt/gpu-control/run-registered-workload");
  assert.equal(body.command.includes("sh"), false);
  assert.equal(body.command.includes("-c"), false);
  assert.equal(body.timeoutSeconds, 25);
});

test("HTTP failures are stable codes and never return provider text", async () => {
  const client = new RunpodV2Client(env, { fetchImpl: async () => jsonResponse({ detail: "add money now" }, 402) });
  await assert.rejects(client.createPod({ runId: "1".repeat(32) }), (error) => {
    assert.equal(error.code, "RUNPOD_INSUFFICIENT_BALANCE");
    assert.equal(error.message.includes("add money"), false);
    return true;
  });
});

test("unrequested queued create is rejected instead of becoming an unmanaged resource", async () => {
  const client = new RunpodV2Client(env, { fetchImpl: async () => jsonResponse({ id: "queue_abc123" }, 202) });
  await assert.rejects(client.createPod({ runId: "1".repeat(32) }), (error) => {
    assert.equal(error.code, "RUNPOD_UNEXPECTED_SUCCESS_STATUS");
    assert.equal(error.status, 202);
    return true;
  });
});

test("redirects are rejected and termination requires exact pod id", async () => {
  const client = new RunpodV2Client(env, { fetchImpl: async () => new Response(null, { status: 302, headers: { location: "https://evil.invalid" } }) });
  await assert.rejects(client.listPods(), (error) => error.code === "RUNPOD_REDIRECT_REJECTED");
  await assert.rejects(client.terminatePod("../../account"), (error) => error.code === "RUNPOD_INVALID_POD_ID");
});

test("create and exec receipts are strictly validated", () => {
  assert.deepEqual(validateCreatedPod({ id: "pod_abc123", name: "gpu-control-111111111111", image: env.RUNPOD_WORKLOAD_IMAGE,
    cloud: "SECURE", gpu: { id: env.RUNPOD_GPU_ID, count: 1 }, ports: [], status: "RUNNING", cost: 0.24,
    dataCenterId: "US-TX-3", globalNetworking: { enabled: false } }, {
    name: "gpu-control-111111111111", image: env.RUNPOD_WORKLOAD_IMAGE, gpuId: env.RUNPOD_GPU_ID,
  }), { id: "pod_abc123", status: "RUNNING", cost: 0.24, dataCenterId: "US-TX-3" });
  assert.throws(() => validateCreatedPod({ id: "pod_abc123", ports: ["22/tcp"] }, {}), RunpodProviderError);
  assert.equal(validateExecResult({ stdout: "ok", stderr: "", exitCode: 0, timedOut: false, truncated: false, durationMs: 4 }).stdout, "ok");
  assert.throws(() => validateExecResult({ stdout: "", stderr: "", exitCode: null, timedOut: true, truncated: false, durationMs: 25000 }), /RUNPOD_EXEC_WAIT_TIMED_OUT/);
});
