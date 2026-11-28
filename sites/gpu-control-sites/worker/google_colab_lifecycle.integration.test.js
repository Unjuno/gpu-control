import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";
import test from "node:test";
import { canonicalJson } from "./canonical_json.js";
import { createGoogleColabOperation, readGoogleColabOperation } from "./google_colab_operation_store.js";
import { googleColabRunTool } from "./google_colab_lifecycle.js";

const owner = "colab-lifecycle-owner";
const runId = "a".repeat(32);
const fingerprint = "b".repeat(64);
const runtimeRequestId = "12345678-1234-4234-8234-123456789abc";
const runtimeName = `runtimes/gpu-control-${runId.slice(0, 24)}`;
const sessionName = `${runtimeName}/sessions/gpu-control-${runId.slice(0, 24)}`;
const manifest = { schema_version: 1, task: "train", entrypoint: "train.py", python_version: "3.11",
  dependencies_lock: "requirements.lock", gpu_profiles: ["T4"], outputs: ["metrics.json", "checkpoints/final.pt"] };
const plan = { schema_version: 2, workload: "owner-selected-colab-training-v1", provider: "google_colab",
  repository: "owner/model", source_sha: "c".repeat(40), manifest_path: ".gpu-control/experiment.json",
  manifest_sha256: "d".repeat(64), manifest, dependencies_lock_sha256: "e".repeat(64), runtime_seconds: 60,
  runtime_spec: { variant: "VARIANT_GPU", accelerator: "T4", shape: "SHAPE_STANDARD" },
  cost_classification: "QUOTA_UNKNOWN", known_cost_usd: null, max_cost_usd: null,
  positive_compute_units_attestation_required: true, positive_compute_units_verified: false,
  paid_fallback_allowed: false, automatic_top_up_allowed: false, network_egress: "unrestricted",
  private_data_allowed: false, provider_credentials_allowed: false, runtime_deletion_authorized_by_submit: true };

function base64url(bytes) {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/g, "");
}

async function encryptedRefreshToken(keyBytes) {
  const key = await crypto.subtle.importKey("raw", keyBytes, { name: "AES-GCM" }, false, ["encrypt"]);
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const ciphertext = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key,
    new TextEncoder().encode("refresh-token-for-test-only"));
  return { refresh_token_ciphertext: base64url(new Uint8Array(ciphertext)), refresh_token_iv: base64url(iv) };
}

function database() {
  const sqlite = new DatabaseSync(":memory:");
  sqlite.exec(`PRAGMA foreign_keys=ON;
    CREATE TABLE gateway_delegated_plans (
      id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, fingerprint TEXT NOT NULL,
      workload TEXT NOT NULL, approved_plan_json TEXT NOT NULL, state TEXT NOT NULL,
      expires_at INTEGER NOT NULL, cancelled_at INTEGER, submit_attempted_at INTEGER,
      provider_state TEXT, provider_response_json TEXT, terminal_at INTEGER, updated_at INTEGER,
      UNIQUE(owner_id,id,fingerprint)
    );
    CREATE TABLE google_colab_accounts (
      owner_id TEXT PRIMARY KEY, google_subject_id TEXT NOT NULL, account_email TEXT NOT NULL,
      refresh_token_ciphertext TEXT NOT NULL, refresh_token_iv TEXT NOT NULL,
      connected_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
    );`);
  for (const migration of ["0037_colab_run_operations.sql", "0038_colab_run_artifacts.sql"]) {
    sqlite.exec(readFileSync(new URL(`../drizzle/${migration}`, import.meta.url), "utf8"));
  }
  const db = {
    prepare(sql) {
      return { bind(...values) {
        const statement = sqlite.prepare(sql);
        return {
          async first() { return statement.get(...values) || null; },
          async run() { const result = statement.run(...values); return { meta: { changes: result.changes } }; },
          async all() { return { results: statement.all(...values) }; },
        };
      } };
    },
  };
  return { db, sqlite };
}

function mcpResponse(id, structuredContent) {
  return Response.json({ jsonrpc: "2.0", id, result: { structuredContent } });
}

test("Colab recovers create and cleanup response loss without rerunning or confirming early", async () => {
  const { db, sqlite } = database();
  try {
    await sqlite.prepare(`INSERT INTO gateway_delegated_plans
      (id,owner_id,fingerprint,workload,approved_plan_json,state,expires_at,provider_state)
      VALUES (?,?,?,?,?,'prepared',5000,'running')`)
      .run(runId, owner, fingerprint, plan.workload, canonicalJson(plan));
    const encryptionKey = crypto.getRandomValues(new Uint8Array(32));
    const sealedToken = await encryptedRefreshToken(encryptionKey);
    await sqlite.prepare(`INSERT INTO google_colab_accounts
      (owner_id,google_subject_id,account_email,refresh_token_ciphertext,refresh_token_iv,connected_at,updated_at)
      VALUES (?,?,?,?,?,1,1)`)
      .run(owner, "google-subject", "owner@example.com", sealedToken.refresh_token_ciphertext,
        sealedToken.refresh_token_iv);
    const env = { DB: db,
      GOOGLE_COLAB_OAUTH_CLIENT_ID: "client-id-for-test",
      GOOGLE_COLAB_OAUTH_CLIENT_SECRET: "client-secret-for-test-only",
      GOOGLE_COLAB_OAUTH_CALLBACK_URL: "https://gpu-control-sites.unjuno.chatgpt.site/google/oauth/callback",
      GOOGLE_COLAB_TOKEN_ENCRYPTION_KEY: base64url(encryptionKey),
      BUCKET: { async put() {}, async get() {} } };
    await createGoogleColabOperation(db, { owner, runId, fingerprint, runtimeRequestId, now: 100 });
    await sqlite.prepare("UPDATE gateway_delegated_plans SET state='submitted' WHERE owner_id=? AND id=?")
      .run(owner, runId);

    const runtimeRequests = [];
    const providerResources = new Map();
    let createCalls = 0;
    let executionCalls = 0;
    let deleteCalls = 0;
    const fetchImpl = async (url, init = {}) => {
      if (new URL(url).hostname === "oauth2.googleapis.com") {
        return Response.json({ access_token: "access-token-for-test", expires_in: 3600 });
      }
      const request = JSON.parse(init.body);
      const { name, arguments: args } = request.params;
      if (name === "create_runtime") {
        createCalls += 1;
        runtimeRequests.push(args.requestId);
        let runtime = providerResources.get(args.requestId);
        if (!runtime) {
          runtime = { name: runtimeName, runtimeSpec: plan.runtime_spec,
            connectionInfo: { token: "runtime-token-for-test", expireTime: "2099-01-01T00:00:00Z",
              url: "https://colab.googleusercontent.com/runtime" } };
          providerResources.set(args.requestId, runtime);
        }
        if (createCalls === 1) throw new TypeError("provider created runtime but response was lost");
        return mcpResponse(request.id, { runtime });
      }
      if (name === "create_session") return mcpResponse(request.id, {
        session: { name: sessionName },
      });
      if (name === "execute_code") {
        executionCalls += 1;
        const receipt = { run_id: runId, repository: plan.repository, commit: plan.source_sha,
          state: "failed", elapsed_seconds: 1, artifacts: [], metrics: null, gpu: null,
          exit_code: 1, error_code: "COLAB_EXECUTION_FAILED" };
        return mcpResponse(request.id, { session: args.session, executionId: args.executionId,
          executionCount: 1, stdout: `GPU_CONTROL_RECEIPT:${JSON.stringify(receipt)}`,
          stderr: "", result: "", outputTruncated: false });
      }
      if (name === "delete_runtime") {
        deleteCalls += 1;
        return mcpResponse(request.id, deleteCalls === 1 ? { deleted: false } : {});
      }
      throw new Error(`unexpected Colab tool: ${name}`);
    };

    const first = await googleColabRunTool(env, owner, "experiment_status", runId,
      { fetchImpl, now: 101 });
    assert.equal(first.machine_state.state, "uncertain");
    assert.equal(first.machine_state.operation_state, "runtime_create_pending");
    assert.equal((await readGoogleColabOperation(db, owner, runId, fingerprint)).state,
      "runtime_create_pending");

    const recovered = await googleColabRunTool(env, owner, "experiment_status", runId,
      { fetchImpl, now: 102 });
    assert.equal(recovered.machine_state.state, "uncertain");
    assert.equal(recovered.machine_state.cleanup_state, "unknown");
    assert.equal(recovered.machine_state.operation_state, "cleanup_pending");
    assert.equal((await readGoogleColabOperation(db, owner, runId, fingerprint)).state, "cleanup_pending");
    assert.equal(executionCalls, 1, "execution is not replayed while cleanup is pending");

    const cleaned = await googleColabRunTool(env, owner, "experiment_status", runId,
      { fetchImpl, now: 103 });
    assert.equal(cleaned.machine_state.state, "failed");
    assert.equal(cleaned.machine_state.cleanup_state, "confirmed");
    assert.equal(cleaned.machine_state.runtime_deleted, true);
    assert.equal(createCalls, 2, "the exact runtime create operation is retried after a lost response");
    assert.deepEqual(runtimeRequests, [runtimeRequestId, runtimeRequestId]);
    assert.equal(providerResources.size, 1, "the same provider request identity resolves one runtime");
    assert.equal(executionCalls, 1);
    assert.equal(deleteCalls, 2, "cleanup retries until Google's empty success response is observed");
    assert.equal((await readGoogleColabOperation(db, owner, runId, fingerprint)).state, "terminal");
  } finally {
    sqlite.close();
  }
});
