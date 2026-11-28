import assert from "node:assert/strict";
import test from "node:test";
import worker from "./index.js";

const sourceSha = "b".repeat(40);
const imageDigest = `sha256:${"a".repeat(64)}`;

function readModelEnvironment() {
  return {
    GPU_CONTROL_ALLOWED_USER_IDS: "test-owner,different-owner",
    DB: { prepare() { throw new Error("each read-model case must declare its query result"); } },
  };
}

async function toolCall(env, user, name, args) {
  return worker.fetch(new Request("https://site.invalid/mcp", {
    method: "POST",
    headers: { "content-type": "application/json", "oai-authenticated-user-id": user },
    body: JSON.stringify({ jsonrpc: "2.0", id: 99, method: "tools/call", params: { name, arguments: args } }),
  }), env);
}

test("another Site user cannot read an owned run status or result", async () => {
  const runId = "8".repeat(32);
  const privateMarker = "owner-private-result-marker";
  const row = {
    id: runId, state: "succeeded", created_at: 1, updated_at: 2,
    result_json: JSON.stringify({ output: privateMarker }), failure_code: null,
    cleanup_state: "confirmed", cancel_requested: 0, result_artifact_id: null,
    result_artifact_sha256: null, result_artifact_size: null,
    workload: "tiny-stories-inference-v1", repository: "Unjuno/gpu-control",
    source_sha: sourceSha, image_digest: imageDigest,
    parameters_json: JSON.stringify({ prompt: "private", max_new_tokens: 1, seed: 1 }),
  };
  const env = readModelEnvironment();
  env.GPU_CONTROL_ALLOWED_USER_IDS = "test-owner,different-owner";
  env.DB.prepare = (sql) => ({ bind(run, owner) { return { async first() {
    assert.match(sql, /r\.owner_id = \?/);
    assert.equal(run, runId);
    return owner === "test-owner" ? row : null;
  } }; } });

  for (const name of ["experiment_status", "experiment_result"]) {
    const response = await toolCall(env, "different-owner", name, { run_id: runId });
    const rpc = await response.json();
    assert.equal(rpc.result.isError, true);
    assert.deepEqual(JSON.parse(rpc.result.content[0].text), { error: "RUN_NOT_FOUND" });
    assert.equal(JSON.stringify(rpc).includes(privateMarker), false);
  }
});

test("experiment_list returns no other owner's run metadata", async () => {
  const env = readModelEnvironment();
  env.GPU_CONTROL_ALLOWED_USER_IDS = "test-owner,different-owner";
  env.DB.prepare = (sql) => ({ bind(owner) { return { async all() {
    assert.match(sql, /WHERE/);
    assert.equal(owner, "different-owner");
    return { results: [] };
  } }; } });

  const response = await toolCall(env, "different-owner", "experiment_list", {});
  const rpc = await response.json();
  assert.equal(rpc.result.isError, false);
  assert.deepEqual(JSON.parse(rpc.result.content[0].text).machine_state.experiments, []);
});

test("experiment_list labels historical Runner records separately from Modal and unknown provenance", async () => {
  const env = readModelEnvironment();
  const localRunId = "1".repeat(32);
  const modalRunId = "2".repeat(32);
  const results = [
    { run_id: localRunId, state: "succeeded", created_at: 1, updated_at: 2, workload: "tiny-stories-inference-v1",
      repository: "Unjuno/gpu-control", source_sha: sourceSha, image_digest: imageDigest, lease_id: null,
      cleanup_receipt_json: JSON.stringify({ absent: true, container_id: "a".repeat(64),
        container_name: `gpu-control-${localRunId}`, image_digest: imageDigest, lease_id: "b".repeat(32), run_id: localRunId }) },
    { run_id: modalRunId, state: "failed", created_at: 3, updated_at: 4, workload: "tiny-stories-inference-v1",
      repository: "Unjuno/gpu-control", source_sha: sourceSha, image_digest: imageDigest,
      lease_id: "sb-01ABCDEF", cleanup_receipt_json: null },
    { run_id: "3".repeat(32), state: "succeeded", created_at: 5, updated_at: 6, workload: "tiny-stories-inference-v1",
      repository: "Unjuno/gpu-control", source_sha: sourceSha, image_digest: imageDigest,
      lease_id: null, cleanup_receipt_json: null },
  ];
  env.DB.prepare = (sql) => ({ bind(owner) { return { async all() {
    assert.equal(owner, "test-owner");
    return { results: sql.includes("FROM runs r") ? results.map((row) => ({ ...row,
      provider: row.run_id === modalRunId ? "modal_cpu" : "unknown", result_json: null,
      result_artifact_id: null, cleanup_state: row.run_id === modalRunId ? "confirmed" : "unknown" })) : [] };
  } }; } });

  const response = await toolCall(env, "test-owner", "experiment_list", {});
  const rpc = await response.json();
  const runs = JSON.parse(rpc.result.content[0].text).machine_state.experiments;
  assert.deepEqual(runs.map((run) => [run.run_id, run.execution_origin]), [
    ["3".repeat(32), "unknown"], [modalRunId, "modal_sandbox"], [localRunId, "retired_local_runner"],
  ]);
  assert.equal(JSON.stringify(runs).includes("container_id"), false, "raw cleanup receipts stay private");
  assert.equal(runs.find((run) => run.run_id === modalRunId).cleanup_state, "confirmed");
});

test("experiment_list includes owner-bound delegated provider runs from D1", async () => {
  const env = readModelEnvironment();
  env.PROVIDER_ADAPTER_URL = "https://unjuno--gpu-control-provider-adapter-provider-adapter-api.us-east.modal.run";
  env.PROVIDER_ADAPTER_KEY_ID = "sites-v1";
  env.PROVIDER_ADAPTER_HMAC_KEY_B64 = Buffer.alloc(32, 7).toString("base64");
  env.PROVIDER_ADAPTER_PROXY_TOKEN_ID = "wk-adaptertest123";
  env.PROVIDER_ADAPTER_PROXY_TOKEN_SECRET = "ws-adaptertestsecret123";
  const plan = {
    schema_version: 2, workload: "orbitune-kaggle-100-step-v1", provider: "kaggle",
    repository: "Unjuno/orbitune", source_sha: "44a1b806160ab5bc721a370d034a6dfcb28f27a8",
    parameters: {}, runtime_seconds: 300, max_cost_usd: "0", known_cost_usd: "0",
    cost_classification: "FREE_QUOTA", paid_fallback_allowed: false,
    image_digest: "sha256:09742cdf89ec6646e0a227bfd88252aed7b7a44a854899d8bd3eea8da6a9f8bd",
  };
  env.DB.prepare = (sql) => ({ bind(owner) { return { async all() {
    assert.equal(owner, "test-owner");
    if (sql.includes("FROM runs r")) return { results: [] };
    if (sql.includes("FROM gateway_delegated_plans")) return { results: [{
      run_id: "7".repeat(32), plan_state: "submitted", provider_state: "succeeded",
      created_at: 20, updated_at: 30, workload: "orbitune-kaggle-100-step-v1",
      terminal_at: 25,
      provider_response_json: JSON.stringify({ machine_state: { state: "succeeded", cleanup_state: "confirmed", result: { steps: 100 } } }),
      approved_plan_json: JSON.stringify(plan),
    }] };
    throw new Error(`unexpected list query: ${sql}`);
  } }; } });

  const response = await toolCall(env, "test-owner", "experiment_list", {});
  const value = JSON.parse((await response.json()).result.content[0].text);
  assert.equal(value.machine_state.experiments.length, 1);
  assert.deepEqual(value.machine_state.experiments[0], {
    run_id: "7".repeat(32), state: "succeeded", created_at: 20, updated_at: 30,
    workload: "orbitune-kaggle-100-step-v1", repository: "Unjuno/orbitune",
    source_sha: "44a1b806160ab5bc721a370d034a6dfcb28f27a8",
    image_digest: "sha256:09742cdf89ec6646e0a227bfd88252aed7b7a44a854899d8bd3eea8da6a9f8bd",
    provider: "kaggle", execution_origin: "kaggle", finished_at: 25,
    result_available: true, cleanup_state: "confirmed",
  });
});

test("experiment_list reports pre-submit cancellation cleanup and terminal time", async () => {
  const env = readModelEnvironment();
  const plan = {
    schema_version: 2, workload: "orbitune-kaggle-100-step-v1", provider: "kaggle",
    repository: "Unjuno/orbitune", source_sha: "44a1b806160ab5bc721a370d034a6dfcb28f27a8",
    parameters: {}, runtime_seconds: 1800, max_cost_usd: "0", known_cost_usd: "0",
    cost_classification: "FREE_QUOTA", paid_fallback_allowed: false,
    image_digest: "sha256:09742cdf89ec6646e0a227bfd88252aed7b7a44a854899d8bd3eea8da6a9f8bd",
  };
  env.DB.prepare = (sql) => ({ bind(owner) { return { async all() {
    assert.equal(owner, "test-owner");
    if (sql.includes("FROM runs r")) return { results: [] };
    if (sql.includes("FROM gateway_delegated_plans")) return { results: [{
      run_id: "9".repeat(32), plan_state: "prepared", cancelled_at: 120,
      submit_attempted_at: null, provider_state: null, provider_response_json: null,
      terminal_at: null, created_at: 100, updated_at: 120, workload: plan.workload,
      source_run_id: null, approved_plan_json: JSON.stringify(plan), expires_at: 400,
    }] };
    throw new Error(`unexpected list query: ${sql}`);
  } }; } });

  const response = await toolCall(env, "test-owner", "experiment_list", {});
  const value = JSON.parse((await response.json()).result.content[0].text);
  assert.deepEqual(value.machine_state.experiments[0], {
    run_id: "9".repeat(32), state: "cancelled", created_at: 100, updated_at: 120,
    workload: "orbitune-kaggle-100-step-v1", repository: "Unjuno/orbitune",
    source_sha: plan.source_sha, image_digest: plan.image_digest, provider: "kaggle",
    execution_origin: "kaggle", finished_at: 120, result_available: false,
    cleanup_state: "confirmed",
  });
});

test("experiment_list filters before returning a bounded cursor page", async () => {
  const env = readModelEnvironment();
  const rows = [
    { run_id: "8".repeat(32), state: "succeeded", created_at: 20, updated_at: 99, completed_at: 21,
      cleanup_state: "confirmed", result_json: JSON.stringify({ loss: 1 }), result_artifact_id: null,
      provider: "kaggle", workload: "orbitune-kaggle-100-step-v1", repository: "Unjuno/orbitune",
      source_sha: "44a1b806160ab5bc721a370d034a6dfcb28f27a8", image_digest: "sha256:" + "a".repeat(64),
      lease_id: null, cleanup_receipt_json: null },
    { run_id: "7".repeat(32), state: "succeeded", created_at: 10, updated_at: 100, completed_at: 11,
      cleanup_state: "confirmed", result_json: null, result_artifact_id: "artifact-1",
      provider: "kaggle", workload: "orbitune-kaggle-100-step-v1", repository: "Unjuno/orbitune",
      source_sha: "44a1b806160ab5bc721a370d034a6dfcb28f27a8", image_digest: "sha256:" + "a".repeat(64),
      lease_id: null, cleanup_receipt_json: null },
  ];
  env.DB.prepare = (sql) => ({ bind(...values) { return { async all() {
    assert.ok(values.includes("orbitune-kaggle-100-step-v1"));
    assert.ok(values.includes("kaggle"));
    assert.ok(values.includes("succeeded"));
    return { results: sql.includes("FROM runs r") ? rows : [] };
  } }; } });
  const response = await toolCall(env, "test-owner", "experiment_list", {
    workload: "orbitune-kaggle-100-step-v1", provider: "kaggle", state: "succeeded", limit: 1,
  });
  const value = JSON.parse((await response.json()).result.content[0].text).machine_state;
  assert.equal(value.experiments.length, 1);
  assert.equal(value.experiments[0].run_id, "8".repeat(32));
  assert.equal(value.experiments[0].finished_at, 21, "polling time does not replace the terminal timestamp");
  assert.equal(value.experiments[0].result_available, true);
  assert.equal(value.experiments[0].cleanup_state, "confirmed");
  assert.deepEqual(value.page, { limit: 1, has_more: true, next_cursor: `20:${"8".repeat(32)}` });
});

test("experiment_status identifies a historical local Runner result from its cleanup receipt", async () => {
  const env = readModelEnvironment();
  const runId = "4".repeat(32);
  const row = { id: runId, state: "succeeded", created_at: 1, updated_at: 2, result_json: null,
    failure_code: null, cleanup_state: "confirmed", cancel_requested: 0, result_artifact_id: null,
    result_artifact_sha256: null, result_artifact_size: null, lease_id: null, workload: "tiny-stories-inference-v1",
    repository: "Unjuno/gpu-control", source_sha: sourceSha, image_digest: imageDigest,
    parameters_json: JSON.stringify({ prompt: "A", max_new_tokens: 1, seed: 1 }), fingerprint: "c".repeat(64),
    runtime_seconds: 1, idempotency_key: "legacy-run", provider: "modal_cpu", cleanup_receipt_json: JSON.stringify({ absent: true,
      container_id: "d".repeat(64), container_name: `gpu-control-${runId}`, image_digest: imageDigest,
      lease_id: "e".repeat(32), run_id: runId }) };
  env.DB.prepare = (sql) => ({ bind() { return { async first() {
    assert.match(sql, /r\.cleanup_receipt_json/);
    return row;
  } }; } });
  const response = await toolCall(env, "test-owner", "experiment_status", { run_id: runId });
  const rpc = await response.json();
  assert.equal(JSON.parse(rpc.result.content[0].text).machine_state.execution_origin, "retired_local_runner");
});
