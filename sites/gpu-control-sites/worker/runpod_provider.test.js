import assert from "node:assert/strict";
import test from "node:test";
import { RunpodProviderError, RunpodV2Client, runpodConfigured, validateJobStatus, validateSubmittedJob } from "./runpod_provider.js";

const env = { RUNPOD_API_KEY: "secret-api-key-with-enough-bytes",
  RUNPOD_WORKLOAD_IMAGE: `ghcr.io/unjuno/gpu-control-runpod@sha256:${"a".repeat(64)}`,
  RUNPOD_GPU_ID: "NVIDIA RTX 2000 Ada Generation", RUNPOD_SERVERLESS_ENDPOINT_ID: "endpoint_abc123",
  RUNPOD_SERVERLESS_HOURLY_PRICE_USD: "0.240000", RUNPOD_SERVERLESS_GPU_POOL_ID: "ADA_24",
  RUNPOD_WORKLOAD_SOURCE_SHA: "b".repeat(40) };
function jsonResponse(value, status = 200) { return new Response(JSON.stringify(value), { status, headers: { "content-type": "application/json" } }); }
function endpoint() { return { id: env.RUNPOD_SERVERLESS_ENDPOINT_ID, type: "QUEUE", image: env.RUNPOD_WORKLOAD_IMAGE,
  gpu: { count: 1, pools: [env.RUNPOD_SERVERLESS_GPU_POOL_ID] }, workers: { min: 0, max: 1, idleTimeout: 5 }, timeout: 30000,
  ports: [], networkVolumes: [], mounts: { network: [], global: [] }, args: "", env: {
    GPU_CONTROL_SOURCE_SHA: env.RUNPOD_WORKLOAD_SOURCE_SHA,
    GPU_CONTROL_IMAGE_DIGEST: env.RUNPOD_WORKLOAD_IMAGE.split("@")[1],
  } }; }
function catalog(price = 0.24, pool = env.RUNPOD_SERVERLESS_GPU_POOL_ID) {
  return { gpus: [{ id: env.RUNPOD_GPU_ID, pool, price: { serverless: price } }] };
}

test("configuration requires an immutable image, endpoint, price, and bounded secret", () => {
  assert.equal(runpodConfigured(env), true);
  assert.equal(runpodConfigured({ ...env, RUNPOD_WORKLOAD_IMAGE: "image:latest" }), false);
  assert.equal(runpodConfigured({ ...env, RUNPOD_SERVERLESS_ENDPOINT_ID: ".." }), false);
  assert.equal(runpodConfigured({ ...env, RUNPOD_SERVERLESS_HOURLY_PRICE_USD: "free" }), false);
});

test("submit sends an asynchronous bounded serverless job", async () => {
  let request;
  const client = new RunpodV2Client(env, { fetchImpl: async (url, init) => {
    request = { url, init, body: JSON.parse(init.body) }; return jsonResponse({ id: "job_abc123", status: "IN_QUEUE" });
  } });
  const result = validateSubmittedJob(await client.submitJob({ runId: "1".repeat(32), planFingerprint: "b".repeat(64),
    nonce: "c".repeat(64), completionKeyB64: Buffer.alloc(32, 7).toString("base64"),
    completionKeyId: "d".repeat(32), sourceSha: "e".repeat(40) }));
  assert.deepEqual(result, { id: "job_abc123", status: "IN_QUEUE" });
  assert.equal(request.url, "https://api.runpod.ai/v2/endpoint_abc123/run");
  assert.deepEqual(request.body.policy, { executionTimeout: 30000, ttl: 300000 });
  assert.equal(request.body.input.execution_name, "gpu-control-111111111111");
});

test("job relay is pinned to the authenticated provider adapter origin", async () => {
  const relayed = { ...env,
    PROVIDER_ADAPTER_URL: "https://unjuno--gpu-control-provider-adapter-provider-adapter-api.us-east.modal.run",
    PROVIDER_ADAPTER_KEY_ID: "adapter-key", PROVIDER_ADAPTER_HMAC_KEY_B64: Buffer.alloc(32, 5).toString("base64"),
    PROVIDER_ADAPTER_PROXY_TOKEN_ID: "wk-proxy-id", PROVIDER_ADAPTER_PROXY_TOKEN_SECRET: "ws-proxy-secret",
    RUNPOD_USE_PROVIDER_ADAPTER: "true",
  };
  let request;
  const client = new RunpodV2Client(relayed, { owner: "owner-1", fetchImpl: async (url, init) => {
    request = { url, init, envelope: JSON.parse(init.body) };
    return jsonResponse({ status: 200, body: { id: "job_abc123", status: "IN_QUEUE" } });
  } });
  await client.submitJob({ runId: "1".repeat(32), planFingerprint: "b".repeat(64), nonce: "c".repeat(64),
    completionKeyB64: Buffer.alloc(32, 7).toString("base64"), completionKeyId: "d".repeat(32), sourceSha: "e".repeat(40) });
  assert.equal(request.url, "https://unjuno--gpu-control-provider-adapter-provider-adapter-api.us-east.modal.run/internal/sites/v1/tools/runpod_queue_request");
  assert.equal(request.init.headers.authorization, "Bearer wk-proxy-id.ws-proxy-secret");
  assert.equal(request.envelope.owner, "owner-1");
  assert.equal(request.envelope.tool, "runpod_queue_request");
  assert.equal(request.envelope.arguments.operation, "run");
  assert.equal(request.envelope.arguments.run_id, "1".repeat(32));
  assert.equal(request.envelope.arguments.plan_fingerprint, "b".repeat(64));
  assert.match(request.init.headers["x-gpu-control-sites-signature"], /^[0-9a-f]{64}$/);
  assert.equal(request.init.body.includes(env.RUNPOD_API_KEY), false);
  assert.equal(runpodConfigured({ ...relayed, RUNPOD_API_KEY: undefined }), true);
  assert.equal(runpodConfigured({ ...relayed, RUNPOD_API_KEY: undefined, PROVIDER_ADAPTER_HMAC_KEY_B64: "short" }), false);
  assert.equal(runpodConfigured({ ...relayed, RUNPOD_API_KEY: undefined, PROVIDER_ADAPTER_PROXY_TOKEN_SECRET: "invalid" }), false);
  assert.throws(() => new RunpodV2Client({ ...relayed, PROVIDER_ADAPTER_URL: "https://evil.invalid" }, { owner: "owner-1" }),
    (error) => error.code === "RUNPOD_RELAY_INVALID");
  assert.equal(runpodConfigured({ ...relayed, RUNPOD_API_KEY: undefined, PROVIDER_ADAPTER_URL: "https://evil.invalid" }), false);
  assert.throws(() => new RunpodV2Client(relayed),
    (error) => error.code === "RUNPOD_RELAY_OWNER_REQUIRED");
});

test("relay receipt recovers only the exact signed run and plan binding", async () => {
  const relayed = { ...env,
    PROVIDER_ADAPTER_URL: "https://unjuno--gpu-control-provider-adapter-provider-adapter-api.us-east.modal.run",
    PROVIDER_ADAPTER_KEY_ID: "adapter-key", PROVIDER_ADAPTER_HMAC_KEY_B64: Buffer.alloc(32, 5).toString("base64"),
    PROVIDER_ADAPTER_PROXY_TOKEN_ID: "wk-proxy-id", PROVIDER_ADAPTER_PROXY_TOKEN_SECRET: "ws-proxy-secret",
    RUNPOD_USE_PROVIDER_ADAPTER: "true",
  };
  let request;
  const client = new RunpodV2Client(relayed, { owner: "owner-1", fetchImpl: async (_url, init) => {
    request = JSON.parse(init.body);
    return jsonResponse({ status: 200, body: { state: "completed",
      response: { id: "job_abc123", status: "IN_QUEUE" } } });
  } });
  const value = await client.getSubmissionReceipt({ runId: "1".repeat(32), planFingerprint: "b".repeat(64) });
  assert.deepEqual(value, { id: "job_abc123", status: "IN_QUEUE" });
  assert.deepEqual(request.arguments, { operation: "receipt", run_id: "1".repeat(32), plan_fingerprint: "b".repeat(64) });
});

test("offer is accepted only from the exact bounded endpoint configuration", async () => {
  const client = new RunpodV2Client(env, { fetchImpl: async (url) => {
    if (url.endsWith("/v2/serverless/endpoint_abc123")) return jsonResponse(endpoint());
    assert.equal(url, "https://api.runpod.io/v2/catalog/gpus"); return jsonResponse(catalog());
  } });
  const offer = await client.getVerifiedOffer();
  assert.equal(offer.cloud, "SERVERLESS");
  assert.equal(offer.hourlyPriceUsd, 0.24);
  assert.equal(offer.source, "runpod-rest-v2-catalog");
  const unsafe = new RunpodV2Client(env, { fetchImpl: async () => jsonResponse({ ...endpoint(), workers: { min: 1, max: 1, idleTimeout: 5 } }) });
  await assert.rejects(unsafe.getVerifiedOffer(), (error) => error.code === "RUNPOD_ENDPOINT_CONFIGURATION_MISMATCH");
  const costlyIdle = new RunpodV2Client(env, { fetchImpl: async () => jsonResponse({ ...endpoint(), workers: { min: 0, max: 1, idleTimeout: 3600 } }) });
  await assert.rejects(costlyIdle.getVerifiedOffer(), (error) => error.code === "RUNPOD_ENDPOINT_CONFIGURATION_MISMATCH");
});

test("offer uses fresh catalog price and rejects a price above the configured maximum", async () => {
  const fetchImpl = async (url) => jsonResponse(url.endsWith("/v2/catalog/gpus") ? catalog(0.25) : endpoint());
  await assert.rejects(new RunpodV2Client(env, { fetchImpl }).getVerifiedOffer(),
    (error) => error.code === "RUNPOD_CATALOG_PRICE_INVALID_OR_ABOVE_MAXIMUM");
  const safeMaximum = { ...env, RUNPOD_SERVERLESS_HOURLY_PRICE_USD: "0.580000" };
  assert.equal((await new RunpodV2Client(safeMaximum, { fetchImpl }).getVerifiedOffer()).hourlyPriceUsd, 0.25);
});

test("timeout remains active while reading a stalled response body", async () => {
  const body = new ReadableStream({ start(controller) { controller.enqueue(new TextEncoder().encode("{")); } });
  const client = new RunpodV2Client(env, { timeoutMs: 100, fetchImpl: async () => new Response(body, { status: 200 }) });
  const started = Date.now();
  await assert.rejects(client.getJob("job_abc123"), (error) => error.code === "RUNPOD_PROVIDER_TIMEOUT");
  assert.ok(Date.now() - started < 500);
});

test("status and cancellation are endpoint-scoped and validate job ids", async () => {
  const urls = [];
  const client = new RunpodV2Client(env, { fetchImpl: async (url) => { urls.push(url); return jsonResponse({ id: "job_abc123", status: "CANCELLED" }); } });
  validateJobStatus(await client.getJob("job_abc123"), "job_abc123");
  await client.cancelJob("job_abc123");
  assert.deepEqual(urls, ["https://api.runpod.ai/v2/endpoint_abc123/status/job_abc123", "https://api.runpod.ai/v2/endpoint_abc123/cancel/job_abc123"]);
  assert.throws(() => client.getJob("../../account"), RunpodProviderError);
});

test("cancellation requires the exact terminal receipt", async () => {
  const client = new RunpodV2Client(env, { fetchImpl: async () => jsonResponse({ id: "job_abc123", status: "IN_PROGRESS" }) });
  await assert.rejects(client.cancelJob("job_abc123"), (error) => error.code === "RUNPOD_CANCELLATION_NOT_TERMINAL");
});

test("provider errors do not expose response text and redirects are rejected", async () => {
  const payment = new RunpodV2Client(env, { fetchImpl: async () => jsonResponse({ detail: "add money now" }, 402) });
  await assert.rejects(payment.getJob("job_abc123"), (error) => error.code === "RUNPOD_INSUFFICIENT_BALANCE" && !error.message.includes("add money"));
  const redirect = new RunpodV2Client(env, { fetchImpl: async () => new Response(null, { status: 302, headers: { location: "https://evil.invalid" } }) });
  await assert.rejects(redirect.getJob("job_abc123"), (error) => error.code === "RUNPOD_REDIRECT_REJECTED");
});

test("receipts and status require exact safe shapes", () => {
  assert.throws(() => validateSubmittedJob({ id: "job_abc123", status: "COMPLETED" }), RunpodProviderError);
  assert.throws(() => validateJobStatus({ id: "other_job", status: "COMPLETED" }, "job_abc123"), RunpodProviderError);
});
