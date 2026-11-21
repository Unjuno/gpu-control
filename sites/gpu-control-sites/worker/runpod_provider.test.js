import assert from "node:assert/strict";
import test from "node:test";
import { RunpodProviderError, RunpodV2Client, parseLogSnapshot, runpodConfigured, validateCreatedPod } from "./runpod_provider.js";

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
  await client.createPod({ runId: "1".repeat(32), planFingerprint: "b".repeat(64),
    nonce: "c".repeat(64), completionKeyB64: Buffer.alloc(32, 7).toString("base64"),
    completionKeyId: "d".repeat(32), sourceSha: "e".repeat(40), dataCenterId: "US-TX-3" });
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
  assert.deepEqual(request.body.entrypoint.slice(0, 2),
    ["/opt/gpu-control/run-registered-workload", "--plan-fingerprint"]);
  assert.equal(request.body.entrypoint.includes("sh"), false);
  assert.equal(request.body.entrypoint.includes("-c"), false);
  assert.match(request.body.env.GPU_CONTROL_COMPLETION_KEY_B64, /^[A-Za-z0-9+/]{43}=$/);
});

test("HTTP failures are stable codes and never return provider text", async () => {
  const client = new RunpodV2Client(env, { fetchImpl: async () => jsonResponse({ detail: "add money now" }, 402) });
  await assert.rejects(client.listPods(), (error) => {
    assert.equal(error.code, "RUNPOD_INSUFFICIENT_BALANCE");
    assert.equal(error.message.includes("add money"), false);
    return true;
  });
});

test("unrequested queued create is rejected instead of becoming an unmanaged resource", async () => {
  const client = new RunpodV2Client(env, { fetchImpl: async () => jsonResponse({ id: "queue_abc123" }, 202) });
  const binding = { runId: "1".repeat(32), planFingerprint: "b".repeat(64), nonce: "c".repeat(64),
    completionKeyB64: Buffer.alloc(32, 7).toString("base64"), completionKeyId: "d".repeat(32), sourceSha: "e".repeat(40) };
  await assert.rejects(client.createPod(binding), (error) => {
    assert.equal(error.code, "RUNPOD_UNEXPECTED_SUCCESS_STATUS");
    assert.equal(error.status, 202);
    return true;
  });
});

test("pod log snapshots parse only bounded container SSE frames", async () => {
  const stream = 'id: 1\ndata: {"source":"system","line":"ignored","ts":"2026-01-01T00:00:00Z"}\n\n' +
    'id: 2\ndata: {"source":"container","line":"GPU_CONTROL_RESULT_JSON_V1:abc","ts":"2026-01-01T00:00:01Z"}\n\n';
  assert.deepEqual(parseLogSnapshot(stream), ["GPU_CONTROL_RESULT_JSON_V1:abc"]);
  assert.throws(() => parseLogSnapshot('data: {"source":"container","line":7}\n\n'),
    /RUNPOD_INVALID_LOG_RESPONSE/);
});

test("catalog offer requires one positive secure price and HIGH exact-datacenter capacity", async () => {
  const client = new RunpodV2Client(env, { fetchImpl: async (url) => {
    assert.equal(url, "https://api.runpod.io/v2/catalog/gpus?include=AVAILABILITY&product=POD&count=1&cloud=SECURE");
    return jsonResponse({ gpus: [{ id: env.RUNPOD_GPU_ID, secure: true, price: { secure: 0.24 },
      maxCount: { secure: 2 }, availability: "HIGH", dataCenters: [
        { id: "US-TX-3", availability: "HIGH" }, { id: "EU-RO-1", availability: "HIGH" },
      ] }] });
  } });
  const offer = await client.getVerifiedOffer();
  assert.deepEqual({ ...offer, checkedAt: 0 }, { gpuId: env.RUNPOD_GPU_ID, cloud: "SECURE", gpuCount: 1,
    hourlyPriceUsd: 0.24, availability: "HIGH", dataCenterId: "EU-RO-1", checkedAt: 0,
    validForSeconds: 300, source: "runpod-rest-v2-catalog" });
});

test("catalog refuses zero price, non-HIGH stock, and duplicate exact GPU rows", async () => {
  for (const gpus of [
    [{ id: env.RUNPOD_GPU_ID, secure: true, price: { secure: 0 }, maxCount: { secure: 1 }, availability: "HIGH", dataCenters: [{ id: "US-TX-3", availability: "HIGH" }] }],
    [{ id: env.RUNPOD_GPU_ID, secure: true, price: { secure: 0.24 }, maxCount: { secure: 1 }, availability: "LOW", dataCenters: [{ id: "US-TX-3", availability: "LOW" }] }],
    [{ id: env.RUNPOD_GPU_ID }, { id: env.RUNPOD_GPU_ID }],
  ]) {
    const client = new RunpodV2Client(env, { fetchImpl: async () => jsonResponse({ gpus }) });
    await assert.rejects(client.getVerifiedOffer(), RunpodProviderError);
  }
});

test("redirects are rejected and termination requires exact pod id", async () => {
  const client = new RunpodV2Client(env, { fetchImpl: async () => new Response(null, { status: 302, headers: { location: "https://evil.invalid" } }) });
  await assert.rejects(client.listPods(), (error) => error.code === "RUNPOD_REDIRECT_REJECTED");
  await assert.rejects(client.terminatePod("../../account"), (error) => error.code === "RUNPOD_INVALID_POD_ID");
});

test("create receipts are strictly validated", () => {
  assert.deepEqual(validateCreatedPod({ id: "pod_abc123", name: "gpu-control-111111111111", image: env.RUNPOD_WORKLOAD_IMAGE,
    cloud: "SECURE", gpu: { id: env.RUNPOD_GPU_ID, count: 1 }, ports: [], status: "RUNNING", cost: 0.24,
    dataCenterId: "US-TX-3", globalNetworking: false }, {
    name: "gpu-control-111111111111", image: env.RUNPOD_WORKLOAD_IMAGE, gpuId: env.RUNPOD_GPU_ID,
  }), { id: "pod_abc123", status: "RUNNING", cost: 0.24, dataCenterId: "US-TX-3" });
  assert.throws(() => validateCreatedPod({ id: "pod_abc123", ports: ["22/tcp"] }, {}), RunpodProviderError);
});
