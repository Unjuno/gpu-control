import assert from "node:assert/strict";
import test from "node:test";
import worker from "./index.js";
import { cancelLocalRun } from "./local_run_cancellation.js";

const sourceSha = "b".repeat(40);
const imageDigest = `sha256:${"a".repeat(64)}`;

async function toolCall(env, user, name, args) {
  return worker.fetch(new Request("https://site.invalid/mcp", {
    method: "POST",
    headers: { "content-type": "application/json", "oai-authenticated-user-id": user },
    body: JSON.stringify({ jsonrpc: "2.0", id: 99, method: "tools/call", params: { name, arguments: args } }),
  }), env);
}

function cancellationEnvironment(initialState) {
  const run = { id: "c".repeat(32), owner_id: "test-owner", state: initialState,
    cancel_requested: 0, cleanup_state: "pending", lease_id: "d".repeat(32) };
  let updates = 0;
  const env = { GPU_CONTROL_ALLOWED_USER_IDS: "test-owner", DB: {} };
  env.DB.prepare = (sql) => ({
    bind(...values) {
      return {
        async first() {
          if (sql.includes("SELECT") && sql.includes("FROM runs") && sql.includes("owner_id")) {
            return values.includes("test-owner") && values.includes(run.id) ? { ...run } : null;
          }
          if (sql.includes("UPDATE runs SET state='cancelled'") && run.state === "queued") {
            updates++;
            run.state = "cancelled";
            run.failure_code = "caller_cancelled_before_start";
            run.cleanup_state = "confirmed";
            return { id: run.id, state: run.state, cleanup_state: run.cleanup_state };
          }
          if (sql.includes("UPDATE runs SET cancel_requested=1") && run.state === "running") {
            updates++;
            run.cancel_requested = 1;
            return { id: run.id, state: run.state, cancel_requested: 1 };
          }
          return null;
        },
      };
    },
  });
  return { env, run, updates: () => updates };
}

test("cancels a queued owned run without asking Runner to clean up a container", async () => {
  const { env, run, updates } = cancellationEnvironment("queued");
  const response = await toolCall(env, "test-owner", "experiment_cancel", { run_id: run.id });
  const rpc = await response.json();
  const result = JSON.parse(rpc.result.content[0].text);

  assert.equal(result.status, "ok");
  assert.equal(result.machine_state.state, "cancelled");
  assert.equal(result.machine_state.cleanup_state, "confirmed");
  assert.equal(updates(), 1);
});

test("requests cooperative cancellation for an owned running run", async () => {
  const { env, run, updates } = cancellationEnvironment("running");
  const response = await toolCall(env, "test-owner", "experiment_cancel", { run_id: run.id });
  const rpc = await response.json();
  const result = JSON.parse(rpc.result.content[0].text);

  assert.equal(result.status, "pending");
  assert.equal(result.machine_state.state, "running");
  assert.equal(result.machine_state.cancellation_requested, true);
  assert.equal(updates(), 1);
});

test("ambiguous RunPod cancellation stays pending and is retried after receipt recovery", async () => {
  const run = { id: "e".repeat(32), owner_id: "test-owner", state: "running",
    cancel_requested: 0, cleanup_state: "pending", provider_phase: "uncertain", provider_job_id: null };
  const env = { DB: { prepare(sql) { return { bind(...values) { return { async first() {
    if (sql.includes("FROM runs") && sql.includes("owner_id")) {
      return values.includes(run.id) ? { ...run } : null;
    }
    if (sql.includes("SELECT p.provider")) return { provider: "runpod_gpu" };
    if (sql.includes("UPDATE runs SET cancel_requested=1")) {
      run.cancel_requested = 1;
      return { id: run.id, state: run.state, cancel_requested: 1 };
    }
    return null;
  } }; } }; } } };
  let requestedCancel = false;
  const result = await cancelLocalRun(env, run.owner_id, run.id, { synchronizeRunpod: async (_env, _owner, id, options) => {
    assert.equal(id, run.id);
    requestedCancel = options.cancel;
    return { ...run };
  } });

  assert.equal(requestedCancel, true);
  assert.equal(run.cancel_requested, 1, "cancellation intent is durable while the submission receipt is missing");
  assert.equal(result.status, "pending");
  assert.equal(result.machine_state.state, "uncertain");
  assert.equal(result.machine_state.provider_resource_created, "unknown");
  assert.equal(result.machine_state.cleanup_state, "pending");
  assert.equal(result.machine_state.cancellation_requested, true);
  assert.deepEqual(result.next_allowed_actions, ["experiment_status"]);
  assert.match(result.human_summary, /not yet confirmed/);
});

test("does not let another Site user cancel an owned run", async () => {
  const { env, run, updates } = cancellationEnvironment("queued");
  env.GPU_CONTROL_ALLOWED_USER_IDS = "test-owner,other-owner";
  const response = await toolCall(env, "other-owner", "experiment_cancel", { run_id: run.id });
  const rpc = await response.json();

  assert.equal(rpc.result.isError, true);
  assert.deepEqual(JSON.parse(rpc.result.content[0].text), { error: "RUN_NOT_FOUND" });
  assert.equal(updates(), 0);
});

test("does not advertise cancellation for a terminal run", async () => {
  const runId = "d".repeat(32);
  const env = { GPU_CONTROL_ALLOWED_USER_IDS: "test-owner", DB: {} };
  env.DB.prepare = (sql) => ({ bind() { return { async first() {
    assert.match(sql, /owner_id = \?/);
    return { id: runId, state: "cancelled", created_at: 10, updated_at: 11, result_json: null,
      failure_code: "caller_cancelled", cleanup_state: "confirmed", cancel_requested: 0,
      result_artifact_id: null, result_artifact_sha256: null, result_artifact_size: null,
      workload: "tiny-stories-inference-v1", repository: "Unjuno/gpu-control", source_sha: sourceSha,
      image_digest: imageDigest, parameters_json: JSON.stringify({ prompt: "A", max_new_tokens: 1, seed: 1 }) };
  } }; } });
  const response = await toolCall(env, "test-owner", "experiment_status", { run_id: runId });
  const result = JSON.parse((await response.json()).result.content[0].text);
  assert.deepEqual(result.next_allowed_actions, ["experiment_status"]);
});





