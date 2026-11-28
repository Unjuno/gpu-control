import { readFileSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";
import { trainingControlPlaneConfigured, trainingRuntimeProfileConfigured,
  trainingRuntimeProfileFingerprint } from "./training_contract.js";
import assert from "node:assert/strict";
import test from "node:test";
import { createHash } from "node:crypto";
import worker, { modalGpuProviderEvidence } from "./index.js";
import { maybeDelegateRunTool, reserveModalGpuLease } from "./delegated_experiment_lifecycle.js";

const imageDigest = `sha256:${"a".repeat(64)}`;
const sourceSha = "b".repeat(40);
const modalApiUrl = "https://unjuno--gpu-control-sites-control-api.us-east.modal.run";
const siteOrigin = "https://gpu-control-sites.unjuno.chatgpt.site";

function approvedPlan(overrides = {}) {
  return { workload: "tiny-stories-inference-v1", repository: "Unjuno/gpu-control", commit: sourceSha,
    prompt: "A", max_new_tokens: 1, seed: 1, runtime_seconds: 10, estimated_sandbox_cost_usd: "0.0005",
    max_cost_usd: "0.01", cpu_limit_physical_cores: 1, memory_limit_mib: 512, gpu_allowed: false,
    control_function_cost_included: false, ...overrides };
}

function submitArgs(runId, fingerprint, plan = approvedPlan()) {
  return { run_id: runId, plan_fingerprint: fingerprint, approved_plan: plan };
}

function storedPlan(runId, fingerprint, plan = approvedPlan(), overrides = {}) {
  return { id: runId, owner_id: "test-owner", fingerprint, workload: plan.workload,
    repository: plan.repository, source_sha: plan.commit,
    parameters_json: JSON.stringify({ prompt: plan.prompt, max_new_tokens: plan.max_new_tokens, seed: plan.seed }),
    runtime_seconds: plan.runtime_seconds, max_cost_usd: plan.max_cost_usd, image_digest: imageDigest,
    state: "prepared", expires_at: Math.floor(Date.now() / 1000) + 300, ...overrides };
}

function environment({ heartbeatAt, admission = "false", heartbeatDigest = imageDigest, heartbeatSha = sourceSha, cancellationProtocol = 1 } = {}) {
  const healthLimit = new Map();
  const modalReservations = new Map();
  const heartbeat = heartbeatAt === undefined ? null : {
    last_seen_at: heartbeatAt,
    image_digest: heartbeatDigest,
    source_sha: heartbeatSha,
    cancellation_protocol: cancellationProtocol,
  };
  return {
    CPU_WORKLOAD_ADMISSION_ENABLED: admission,
    GPU_CONTROL_ALLOWED_USER_IDS: "test-owner,other-owner",
    CPU_WORKLOAD_REPOSITORY: "Unjuno/gpu-control",
    CPU_WORKLOAD_SOURCE_SHA: sourceSha,
    CPU_WORKLOAD_IMAGE_DIGEST: imageDigest,
    DB: {
      prepare(sql) {
        const policyRows = sql.includes("FROM provider_budget_policies") ? [
          { provider: "runpod_gpu", monthly_limit_microusd: null, per_run_limit_microusd: 1_000_000 },
        ] : sql.includes("FROM provider_free_policies") ? [
          { provider: "kaggle", max_cost_microusd: 0, paid_fallback_allowed: 0 },
          { provider: "huggingface_space", max_cost_microusd: 0, paid_fallback_allowed: 0 },
        ] : null;
        const row = sql.includes("sqlite_master") ? { name: "human_authorizations" }
          : sql.includes("FROM provider_budget_policies") ? policyRows[0]
          : sql.includes("FROM modal_compute_budget_policy") ? {
            monthly_limit_microusd: 30_000_000, per_run_limit_microusd: 1_000_000,
          } : sql.includes("FROM modal_gpu_admission_policy") ? { admission_enabled: 0 }
          : sql.includes("FROM modal_compute_budget_reservations") ? {
            monthly_reserved_microusd: [...modalReservations.values()]
              .filter((item) => item.period_key === new Date().toISOString().slice(0, 7))
              .reduce((sum, item) => sum + item.reserved_microusd, 0),
          }
          : heartbeat;
        return {
          first: async (...values) => sql.includes("FROM modal_compute_budget_reservations WHERE run_id=?")
            ? modalReservations.get(values[0]) || null : row,
          all: async () => ({ results: policyRows || [] }),
          bind(...values) {
            return {
              first: async () => sql.includes("FROM modal_compute_budget_reservations WHERE run_id=?")
                ? modalReservations.get(values[0]) || null : row,
              run: async () => {
                if (sql.includes("INSERT OR IGNORE INTO modal_compute_budget_reservations")) {
                  const [runId, source, fingerprint, periodKey, reservedMicrousd, createdAt] = values;
                  const existing = modalReservations.get(runId);
                  if (existing) return { meta: { changes: 0 } };
                  const used = [...modalReservations.values()].filter((item) => item.period_key === periodKey)
                    .reduce((sum, item) => sum + item.reserved_microusd, 0);
                  if (reservedMicrousd > 1_000_000 || used + reservedMicrousd > 30_000_000) {
                    return { meta: { changes: 0 } };
                  }
                  modalReservations.set(runId, { source, plan_fingerprint: fingerprint,
                    period_key: periodKey, reserved_microusd: reservedMicrousd, created_at: createdAt });
                  return { meta: { changes: 1 } };
                }
                if (!sql.includes("modal_health_check_limits")) return { meta: { changes: 1 } };
                const [now, threshold] = values;
                const prior = healthLimit.get("workspace");
                if (prior !== undefined && prior > threshold) return { meta: { changes: 0 } };
                healthLimit.set("workspace", now);
                return { meta: { changes: 1 } };
              },
            };
          },
          run: async () => ({ meta: { changes: 1 } }),
        };
      },
    },
  };
}

function canonicalJson(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

async function capabilities(env) {
  const request = new Request("https://site.invalid/mcp", {
    method: "POST",
    headers: { "content-type": "application/json", "oai-authenticated-user-id": "test-owner" },
    body: JSON.stringify({
      jsonrpc: "2.0",
      id: 1,
      method: "tools/call",
      params: { name: "experiment_capabilities", arguments: {} },
    }),
  });
  const response = await worker.fetch(request, env);
  assert.equal(response.status, 200);
  const envelope = JSON.parse((await response.json()).result.content[0].text);
  return envelope;
}

async function toolCall(env, user, name, args) {
  return worker.fetch(new Request("https://site.invalid/mcp", {
    method: "POST",
    headers: { "content-type": "application/json", "oai-authenticated-user-id": user },
    body: JSON.stringify({ jsonrpc: "2.0", id: 99, method: "tools/call", params: { name, arguments: args } }),
  }), env);
}

test("GitHub App connection tools are owner-scoped and fail closed until configured", async () => {
  const db = new DatabaseSync(":memory:");
  try {
    db.exec(readFileSync(new URL("../drizzle/0030_github_app_connections.sql", import.meta.url), "utf8"));
    const env = { ...environment(), GPU_CONTROL_ALLOWED_USER_IDS: "test-owner", DB: {
      prepare(sql) {
        return { bind(...values) {
          const statement = db.prepare(sql);
          return { run: async () => statement.run(...values), first: async () => statement.get(...values),
            all: async () => ({ results: statement.all(...values) }) };
        } };
      },
      async batch(statements) {
        db.exec("BEGIN");
        try {
          const result = statements.map(({ sql, values }) => {
            const statement = db.prepare(sql);
            if (sql.includes("RETURNING")) return { results: statement.all(...values) };
            return { meta: { changes: Number(statement.run(...values).changes) } };
          });
          db.exec("COMMIT");
          return result;
        } catch (error) { db.exec("ROLLBACK"); throw error; }
      },
    } };
    const call = async (user, name) => {
      const response = await toolCall(env, user, name, {});
      return JSON.parse((await response.json()).result.content[0].text);
    };
    assert.equal((await toolCall(env, "unauthorized", "github_connection_status", {})).status, 403);
    assert.equal((await call("test-owner", "github_connection_start")).blocking_reason, "GITHUB_APP_NOT_CONFIGURED");
    assert.deepEqual((await call("test-owner", "github_connection_status")).machine_state,
      { configured: false, connected: false });
    const repos = await call("test-owner", "github_repositories");
    assert.equal(repos.blocking_reason, "GITHUB_APP_NOT_CONFIGURED");
    assert.deepEqual(repos.machine_state.repositories, []);
    assert.equal((await call("test-owner", "github_connection_disconnect")).machine_state.disconnected, true);

    const listed = await worker.fetch(new Request("https://site.invalid/mcp", { method: "POST",
      headers: { "content-type": "application/json", "oai-authenticated-user-id": "test-owner" },
      body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "tools/list", params: {} }) }), env);
    const body = await listed.json();
    const byName = new Map(body.result.tools.map((tool) => [tool.name, tool]));
    assert.ok(byName.has("github_connection_start"));
    assert.equal(byName.get("github_repositories").annotations.readOnlyHint, true);
    assert.equal(byName.get("github_connection_disconnect").annotations.destructiveHint, true);
    assert.match(byName.get("experiment_capabilities").description, /colab_capabilities/);
    assert.match(byName.get("experiment_capabilities").description, /Google Colab readiness reports owner OAuth connection/);
  } finally { db.close(); }
});

test("root page is a public status surface without granting execution authority", async () => {
  const response = await worker.fetch(new Request("https://gpu-control.example/"), {});
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type"), /^text\/html/);
  const body = await response.text();
  assert.match(body, /Viewing this page does not grant execution authority/);
  assert.doesNotMatch(body, /token|secret|credential/i);
});

test("Modal status polling fails closed when the shared provider-call budget is exhausted", async () => {
  const runId = "8".repeat(32);
  const row = { id: runId, state: "running", created_at: 1, updated_at: 2,
    result_json: null, failure_code: null, cleanup_state: "pending", cleanup_receipt_json: null,
    cancel_requested: 0, result_artifact_id: null, result_artifact_sha256: null,
    result_artifact_size: null, lease_id: "sb-123", workload: "tiny-stories-inference-v1",
    repository: "Unjuno/gpu-control", source_sha: "b".repeat(40), image_digest: imageDigest,
    parameters_json: JSON.stringify({ prompt: "Once", max_new_tokens: 1, seed: 1 }),
    fingerprint: "c".repeat(64), runtime_seconds: 10, idempotency_key: "budget-test", provider: "modal_cpu" };
  const env = environment({ admission: "true" });
  env.MODAL_API_URL = modalApiUrl;
  env.MODAL_PROXY_TOKEN_ID = "wk-12345678";
  env.MODAL_PROXY_TOKEN_SECRET = "ws-12345678";
  env.MODAL_WORKLOAD_IMAGE_FINGERPRINT = "d".repeat(64);
  env.BUCKET = { put: async () => {} };
  env.DB.prepare = (sql) => ({ bind() { return {
    first: async () => sql.includes("FROM runs r JOIN plans p") ? { ...row } : null,
    run: async () => sql.includes("modal_status_check_limits") ? { meta: { changes: 0 } } : { meta: { changes: 1 } },
  }; } });
  let providerCalls = 0;
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => { providerCalls++; throw new Error("budgeted status call must not reach Modal"); };
  try {
    const response = await toolCall(env, "test-owner", "experiment_status", { run_id: runId });
    const result = JSON.parse((await response.json()).result.content[0].text);
    assert.equal(result.machine_state.state, "running");
    assert.equal(result.machine_state.provider_sync_skipped, "MODAL_STATUS_CHECK_RATE_LIMITED");
    assert.equal(providerCalls, 0);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("authenticated users outside the configured owner allowlist cannot touch D1", async () => {
  const env = environment();
  let databaseReads = 0;
  env.DB.prepare = () => {
    databaseReads++;
    throw new Error("unauthorized Site user reached D1");
  };
  const response = await toolCall(env, "another-chatgpt-user", "experiment_list", {});
  assert.equal(response.status, 403);
  assert.equal(databaseReads, 0);
});

test("read-only capabilities do not call Modal", async () => {
  const env = environment({ admission: "true" });
  env.MODAL_PROVIDER_ADMISSION_ENABLED = "true";
  env.MODAL_API_URL = modalApiUrl;
  env.MODAL_PROXY_TOKEN_ID = "wk-" + "t".repeat(16);
  env.MODAL_PROXY_TOKEN_SECRET = "ws-" + "s".repeat(16);
  env.MODAL_WORKLOAD_IMAGE_FINGERPRINT = "f".repeat(64);
  env.BUCKET = { put: async () => {} };
  const originalFetch = globalThis.fetch;
  let providerCalls = 0;
  try {
    globalThis.fetch = async () => { providerCalls++; throw new Error("read-only capabilities must not call Modal"); };
    const result = await capabilities(env);
    assert.equal(result.machine_state.provider_ready, null);
    assert.equal(result.machine_state.provider_configured, true);
    assert.deepEqual(result.machine_state.provider_health_checks, { configured: true, deferred_until_authorized_submit: true });
    assert.equal(result.machine_state.available, true);
    assert.deepEqual(result.machine_state.owner_selected_training, {
      execution_kind: "owner_selected_python",
      compute_provider: "modal_gpu",
      repository_access: "authenticated_owner_selected_github_repositories",
      requires_manifest: ".gpu-control/experiment.json",
      requires_hash_locked_dependencies: true,
      registration_id_is_internal: true,
      ask_user_for_registration_id: false,
      github_app_configured: false,
      github_connected: false,
      adapter_configured: false,
      site_profile_configured: false,
      site_control_plane_configured: false,
      admission_enabled: false,
      provider_budget_policy_ready: true,
      provider_budget_admission_enabled: false,
      budget_policy: { state: "unavailable", provider: "modal", scope: "modal_compute_shared_across_routes" },
      adapter_readiness_available: false,
      adapter_profile_configured: false,
      adapter_control_plane_configured: false,
      adapter_admission_enabled: false,
      adapter_profile_matches: false,
      ready_to_prepare: false,
      paid_fallback_allowed: false,
      next_actions: ["github_connection_status"],
      blocker: "GITHUB_APP_NOT_CONFIGURED",
    });
    assert.deepEqual(result.providers.map((provider) => provider.id),
      ["modal_cpu", "modal_gpu", "runpod_gpu", "kaggle", "huggingface_space", "google_colab"]);
    assert.equal(result.providers[1].enabled, false);
    assert.equal(result.providers[1].configured, false);
    assert.equal(result.provider_budgets[0].provider, "modal");
    assert.deepEqual(result.provider_budgets[0].routes, ["modal_cpu", "modal_gpu"]);
    assert.equal(result.provider_budgets[0].monthly_limit_usd, "30.00");
    assert.equal(result.provider_budgets[0].per_run_limit_usd, "1.00");
    assert.deepEqual(result.workloads.map((workload) => workload.id),
      ["tiny-stories-inference-v1", "runpod-gpu-canary-v1", "modal-gpu-vector-add-v1",
        "orbitune-kaggle-100-step-v1", "orbitune-zero-gpu-eval-v1"]);
    assert.deepEqual(result.provider_budgets.slice(2), [
      { provider: "kaggle", policy_available: true, scope: "registered_free_workload_policy",
        monthly_limit_usd: "0.00", per_run_limit_usd: "0.00",
        paid_fallback_allowed: false },
      { provider: "huggingface_space", policy_available: true, scope: "registered_free_workload_policy",
        monthly_limit_usd: "0.00", per_run_limit_usd: "0.00",
        paid_fallback_allowed: false },
    ]);
    assert.equal(providerCalls, 0);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("owner runtime profile validation and fingerprint match the shared cross-runtime contract", async () => {
  const contract = JSON.parse(readFileSync(new URL("../contracts/owner-training-profile-cases.json", import.meta.url), "utf8"));
  assert.equal(contract.schema_version, 1);
  for (const item of contract.cases) {
    assert.equal(trainingRuntimeProfileConfigured(item.config, contract.now), item.profile_configured, item.name);
  }
  assert.equal(await trainingRuntimeProfileFingerprint(contract.cases[0].config, contract.now),
    contract.expected_fingerprint);
  assert.equal(trainingControlPlaneConfigured("1".repeat(40)), true);
  assert.equal(trainingControlPlaneConfigured("bad"), false);
});

test("capabilities exposes all provider routes and enables only configured routes", async () => {
  const env = environment();
  env.PROVIDER_ADAPTER_URL = "https://unjuno--gpu-control-provider-adapter-provider-adapter-api.us-east.modal.run";
  env.PROVIDER_ADAPTER_KEY_ID = "sites-v1";
  env.PROVIDER_ADAPTER_HMAC_KEY_B64 = Buffer.alloc(32, 7).toString("base64");
  env.PROVIDER_ADAPTER_PROXY_TOKEN_ID = "wk-adaptertest123";
  env.PROVIDER_ADAPTER_PROXY_TOKEN_SECRET = "ws-adaptertestsecret123";
  const originalFetch = globalThis.fetch;
  try {
    globalThis.fetch = async () => new Response(JSON.stringify({
      schema_version: 2, status: "ok", human_summary: "Configured.",
      next_allowed_actions: ["experiment_prepare"], blocking_reason: null,
      machine_state: { owner_selected_training: { profile_configured: true, control_plane_configured: true,
        admission_enabled: false,
        profile_fingerprint: "9".repeat(64),
        ready: false, blocker: "OWNER_TRAINING_ADMISSION_DISABLED" }, providers: [
        { id: "kaggle", configured: true, paid_fallback: false },
        { id: "huggingface_space", configured: false, paid_fallback: false },
        { id: "modal_gpu", configured: true, paid_fallback: false },
      ], workloads: ["orbitune-kaggle-100-step-v1", "orbitune-zero-gpu-eval-v1", "modal-gpu-vector-add-v1"] },
    }), { status: 200, headers: { "content-type": "application/json" } });
    const result = await capabilities(env);
    assert.deepEqual(result.providers.map((provider) => provider.id),
      ["modal_cpu", "modal_gpu", "runpod_gpu", "kaggle", "huggingface_space", "google_colab"]);
    assert.equal(result.providers[1].configured, true);
    assert.equal(result.providers[1].enabled, false);
    assert.equal(result.providers[1].blocker, "MODAL_GPU_WORKLOAD_ADMISSION_DISABLED");
    assert.equal(result.providers[3].enabled, true);
    assert.equal(result.providers[3].blocker, null);
    assert.equal(result.providers[4].enabled, false);
    assert.equal(result.providers[4].blocker, "FREE_PROVIDER_NOT_CONFIGURED");
    assert.equal(result.machine_state.owner_selected_training.adapter_configured, true);
    assert.equal(result.machine_state.owner_selected_training.site_profile_configured, false);
    assert.equal(result.machine_state.owner_selected_training.site_control_plane_configured, false);
    assert.equal(result.machine_state.owner_selected_training.adapter_profile_configured, true);
    assert.equal(result.machine_state.owner_selected_training.adapter_control_plane_configured, true);
    assert.equal(result.machine_state.owner_selected_training.adapter_readiness_available, true);
    assert.equal(result.machine_state.owner_selected_training.admission_enabled, false);
    assert.equal(result.machine_state.owner_selected_training.ready_to_prepare, false);
    assert.equal(result.machine_state.owner_selected_training.blocker, "GITHUB_APP_NOT_CONFIGURED");
    assert.equal(JSON.stringify(result).includes("9".repeat(64)), false);
    assert.equal(result.workloads.find((item) => item.id === "orbitune-kaggle-100-step-v1").enabled, true);
    assert.equal(result.workloads.find((item) => item.id === "orbitune-zero-gpu-eval-v1").enabled, false);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("Modal GPU account evidence is exact, short-lived, and leaves one cent of headroom", async () => {
  const body = { schema_version: 1, workspace: "unjuno", environment: "main",
    usage_limit_usd: "30.00", credits_used_usd: "0.15", charges_usd: "0.00",
    gpu: "T4", hourly_price_usd: "0.000164", price_source: "https://modal.com/pricing",
    verified_at: 900, expires_at: 1200 };
  const evidence = { ...body, evidence_id: createHash("sha256").update(canonicalJson(body)).digest("hex") };
  assert.deepEqual(await modalGpuProviderEvidence({ MODAL_GPU_ACCOUNT_EVIDENCE_JSON: JSON.stringify(evidence) }, 1000), evidence);
  assert.equal(await modalGpuProviderEvidence({ MODAL_GPU_ACCOUNT_EVIDENCE_JSON: JSON.stringify(evidence) }, 1201), null);
  const projectUsageAboveInternalLimit = { ...body, credits_used_usd: "1.00" };
  projectUsageAboveInternalLimit.evidence_id = createHash("sha256")
    .update(canonicalJson(projectUsageAboveInternalLimit)).digest("hex");
  assert.deepEqual(await modalGpuProviderEvidence({ MODAL_GPU_ACCOUNT_EVIDENCE_JSON:
    JSON.stringify(projectUsageAboveInternalLimit) }, 1000), projectUsageAboveInternalLimit);
  const exhausted = { ...body, credits_used_usd: "30.00" };
  exhausted.evidence_id = createHash("sha256").update(canonicalJson(exhausted)).digest("hex");
  assert.equal(await modalGpuProviderEvidence({ MODAL_GPU_ACCOUNT_EVIDENCE_JSON: JSON.stringify(exhausted) }, 1000), null);
  assert.equal(await modalGpuProviderEvidence({ MODAL_GPU_ACCOUNT_EVIDENCE_JSON: JSON.stringify({ ...evidence,
    hourly_price_usd: "0.000165" }) }, 1000), null);
});

test("Modal GPU active lease serializes distinct plans and permits exact retry", async () => {
  let lease = null;
  const env = { DB: { prepare(sql) { return {
    bind(...values) { return { async run() {
      if (sql.includes("INSERT OR IGNORE INTO modal_gpu_active_lease")) {
        if (lease) return { meta: { changes: 0 } };
        lease = { run_id: values[0], plan_fingerprint: values[1], state: "submitting" };
        return { meta: { changes: 1 } };
      }
      throw new Error("unexpected lease write");
    } }; },
    async first() { return lease; },
  }; } } };
  assert.equal(await reserveModalGpuLease(env, { runId: "a".repeat(32), fingerprint: "b".repeat(64), now: 1000 }), true);
  assert.equal(await reserveModalGpuLease(env, { runId: "a".repeat(32), fingerprint: "b".repeat(64), now: 1001 }), true);
  assert.equal(await reserveModalGpuLease(env, { runId: "c".repeat(32), fingerprint: "d".repeat(64), now: 1002 }), false);
});

test("authorized submission still bounds and cancels oversized Modal health responses", async () => {
  const env = environment({ admission: "true" });
  env.MODAL_PROVIDER_ADMISSION_ENABLED = "true";
  env.MODAL_API_URL = modalApiUrl;
  env.MODAL_PROXY_TOKEN_ID = `wk-${"t".repeat(16)}`;
  env.MODAL_PROXY_TOKEN_SECRET = `ws-${"s".repeat(16)}`;
  env.MODAL_WORKLOAD_IMAGE_FINGERPRINT = "f".repeat(64);
  env.BUCKET = { put: async () => {} };
  const fingerprint = "e".repeat(64);
  const runId = "c".repeat(32);
  const plan = storedPlan(runId, fingerprint);
  let healthBudgetUsed = false;
  let planHealthUsed = false;
  env.DB.prepare = (sql) => ({ bind() { return {
    first: async () => {
    if (sql.startsWith("SELECT id, state, created_at FROM runs WHERE owner_id=?")) return null;
    if (sql.includes("FROM plans WHERE id=?")) return plan;
    if (sql.includes("FROM human_authorizations")) return { id: "a".repeat(32), fingerprint,
      expires_at: Math.floor(Date.now() / 1000) + 300, consumed_at: null };
    return null;
    },
    async run() {
      if (sql.includes("modal_health_check_limits")) {
        if (healthBudgetUsed) return { meta: { changes: 0 } };
        healthBudgetUsed = true;
        return { meta: { changes: 1 } };
      }
      if (sql.includes("modal_authorized_health_checks")) {
        if (planHealthUsed) return { meta: { changes: 0 } };
        planHealthUsed = true;
        return { meta: { changes: 1 } };
      }
      return { meta: { changes: 1 } };
    },
  }; } });
  let batchCalls = 0;
  env.DB.batch = async () => { batchCalls++; throw new Error("unhealthy provider must not reserve a run"); };
  const originalFetch = globalThis.fetch;
  let cancelCalls = 0;
  let healthCalls = 0;
  try {
    globalThis.fetch = async () => { healthCalls++; return new Response(new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode("x".repeat(4096)));
        controller.enqueue(new TextEncoder().encode("y".repeat(4097)));
      },
      cancel() { cancelCalls++; },
    })); };
    const response = await toolCall(env, "test-owner", "experiment_submit", submitArgs(runId, fingerprint));
    const rpc = await response.json();
    const result = JSON.parse(rpc.result.content[0].text);
    assert.equal(rpc.result.isError, false);
    assert.equal(result.status, "blocked");
    assert.equal(cancelCalls, 1);
    assert.equal(healthCalls, 1);
    assert.equal(batchCalls, 0);
    const retryResponse = await toolCall(env, "test-owner", "experiment_submit", submitArgs(runId, fingerprint));
    const retry = JSON.parse((await retryResponse.json()).result.content[0].text);
    assert.equal(retry.blocking_reason, "MODAL_HEALTH_CHECK_RATE_LIMITED");
    assert.equal(healthCalls, 1, "a failed health response cannot be retried within the workspace budget");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("parallel submits for one confirmed plan reserve at most one billable health call", async () => {
  const env = environment({ admission: "true" });
  env.MODAL_API_URL = modalApiUrl;
  env.MODAL_PROXY_TOKEN_ID = `wk-${"t".repeat(16)}`;
  env.MODAL_PROXY_TOKEN_SECRET = `ws-${"s".repeat(16)}`;
  env.MODAL_WORKLOAD_IMAGE_FINGERPRINT = "f".repeat(64);
  env.BUCKET = { put: async () => {} };
  const fingerprint = "e".repeat(64);
  const runId = "c".repeat(32);
  const plan = storedPlan(runId, fingerprint);
  let workspaceReserved = false;
  let planReserved = false;
  let providerBudgetReserved = false;
  let batchCalls = 0;
  let healthCalls = 0;
  env.DB.prepare = (sql) => ({ bind() { return {
    async first() {
      if (sql.startsWith("SELECT id, state, created_at FROM runs WHERE owner_id=?")) return null;
      if (sql.includes("SELECT ready FROM modal_authorized_health_checks")) return null;
      if (sql.includes("FROM plans WHERE id=?")) return plan;
      if (sql.includes("FROM human_authorizations")) return { id: "a".repeat(32), fingerprint,
        expires_at: Math.floor(Date.now() / 1000) + 300, consumed_at: null };
      if (sql.includes("FROM provider_budget_reservations WHERE run_id=?")) return providerBudgetReserved
        ? { provider: "modal_cpu", period_key: new Date().toISOString().slice(0, 7), reserved_microusd: 10000 }
        : null;
      return null;
    },
    async run() {
      if (sql.includes("modal_health_check_limits")) {
        if (workspaceReserved) return { meta: { changes: 0 } };
        workspaceReserved = true;
        return { meta: { changes: 1 } };
      }
      if (sql.includes("INSERT INTO modal_authorized_health_checks")) {
        if (planReserved) return { meta: { changes: 0 } };
        planReserved = true;
        return { meta: { changes: 1 } };
      }
      if (sql.includes("UPDATE modal_authorized_health_checks")) return { meta: { changes: 1 } };
      if (sql.includes("INSERT INTO provider_budget_reservations")) {
        if (providerBudgetReserved) return { meta: { changes: 0 } };
        providerBudgetReserved = true;
        return { meta: { changes: 1 } };
      }
      throw new Error(`unexpected D1 write query: ${sql}`);
    },
  }; } });
  env.DB.batch = async () => { batchCalls++; throw new Error("failed health must not reserve a run"); };

  const originalFetch = globalThis.fetch;
  try {
    globalThis.fetch = async () => {
      healthCalls++;
      return new Response("unavailable", { status: 503 });
    };
    const responses = await Promise.all([
      toolCall(env, "test-owner", "experiment_submit", submitArgs(runId, fingerprint)),
      toolCall(env, "test-owner", "experiment_submit", submitArgs(runId, fingerprint)),
    ]);
    const outcomes = await Promise.all(responses.map(async (response) => {
      const rpc = await response.json();
      return JSON.parse(rpc.result.content[0].text);
    }));
    assert.equal(healthCalls, 1, "the shared workspace reservation allows only one provider health call");
    assert.equal(batchCalls, 0, "failed health checks must not consume authorization or reserve a run");
    assert.deepEqual(outcomes.map((outcome) => outcome.blocking_reason).sort(), [
      "MODAL_HEALTH_CHECK_RATE_LIMITED",
      "MODAL_PROVIDER_HEALTH_FAILED",
    ]);
    const failed = outcomes.find((outcome) => outcome.blocking_reason === "MODAL_PROVIDER_HEALTH_FAILED");
    assert.deepEqual(failed.machine_state.provider_health_checks, {
      configured: true,
      request_succeeded: false,
      error_code: "MODAL_PROVIDER_HTTP_5XX",
    });
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("capabilities reports configured Modal without a health probe while admission remains disabled", async () => {
  const env = environment();
  env.MODAL_API_URL = modalApiUrl;
  env.MODAL_PROXY_TOKEN_ID = "wk-" + "t".repeat(16);
  env.MODAL_PROXY_TOKEN_SECRET = "ws-" + "s".repeat(16);
  env.MODAL_WORKLOAD_IMAGE_FINGERPRINT = "f".repeat(64);
  env.BUCKET = { put: async () => {} };
  const originalFetch = globalThis.fetch;
  try {
    globalThis.fetch = async () => { throw new Error("capabilities must defer provider health"); };
    const result = await capabilities(env);
    assert.equal(result.machine_state.provider_ready, null);
    assert.equal(result.machine_state.provider_configured, true);
    assert.deepEqual(result.machine_state.provider_health_checks, { configured: true, deferred_until_authorized_submit: true });
    assert.equal(result.machine_state.admission_enabled, false);
    assert.equal(result.machine_state.available, false);
    assert.equal(result.machine_state.free, false);
    assert.equal(result.machine_state.paid, true);
    assert.equal(result.machine_state.credit_eligible, true);
    assert.equal(result.machine_state.estimated_max_sandbox_cost_usd, "0.0013");
    assert.deepEqual(result.machine_state.sandbox_resources, {
      cpu_request_physical_cores: 1, cpu_limit_physical_cores: 1,
      memory_request_mib: 512, memory_limit_mib: 512,
    });
    assert.equal(result.providers[0].paid, true);
    assert.equal(result.providers[0].credit_eligible, true);
    assert.equal(result.provider_budgets[0].monthly_limit_usd, "30.00");
    assert.equal(result.provider_budgets[0].per_run_limit_usd, "1.00");
    assert.equal(result.blocking_reason, "CPU_WORKLOAD_ADMISSION_DISABLED");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("capabilities avoids Modal cold starts", async () => {
  const env = environment();
  env.MODAL_API_URL = modalApiUrl;
  env.MODAL_PROXY_TOKEN_ID = `wk-${"t".repeat(16)}`;
  env.MODAL_PROXY_TOKEN_SECRET = `ws-${"s".repeat(16)}`;
  env.MODAL_WORKLOAD_IMAGE_FINGERPRINT = "f".repeat(64);
  env.BUCKET = { put: async () => {} };

  const originalFetch = globalThis.fetch;
  try {
    let providerCalls = 0;
    globalThis.fetch = async () => { providerCalls++; throw new Error("capabilities must not contact Modal"); };
    const result = await capabilities(env);
    assert.equal(result.machine_state.provider_ready, null);
    assert.equal(providerCalls, 0);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("stores a bounded Modal exit-code diagnostic without exposing provider stderr", async () => {
  const runId = "f".repeat(32);
  const current = { id: runId, state: "running", created_at: 10, updated_at: 11,
    result_json: null, failure_code: null, cleanup_state: "pending", cancel_requested: 0,
    result_artifact_id: null, result_artifact_sha256: null, result_artifact_size: null,
    lease_id: null, workload: "tiny-stories-inference-v1", repository: "Unjuno/gpu-control",
    source_sha: "b".repeat(40), image_digest: `sha256:${"a".repeat(64)}`,
    parameters_json: JSON.stringify({ prompt: "Once", max_new_tokens: 1, seed: 1 }),
    fingerprint: "c".repeat(64), runtime_seconds: 10, idempotency_key: "diagnostic-test", provider: "modal_cpu" };
  const env = environment();
  env.MODAL_API_URL = modalApiUrl;
  env.MODAL_PROXY_TOKEN_ID = `wk-${"t".repeat(16)}`;
  env.MODAL_PROXY_TOKEN_SECRET = `ws-${"s".repeat(16)}`;
  env.MODAL_WORKLOAD_IMAGE_FINGERPRINT = "d".repeat(64);
  env.BUCKET = { put: async () => {} };
  env.DB.prepare = (sql) => ({ bind(...values) { return {
    async first() {
      if (sql.includes("FROM runs r JOIN plans p")) return { ...current };
      throw new Error(`unexpected D1 first query: ${sql}`);
    },
    async run() {
      if (sql.includes("modal_status_check_limits")) return { meta: { changes: 1 } };
      if (sql.startsWith("UPDATE runs SET lease_id=")) {
        current.lease_id = values[0];
        return { success: true };
      }
      if (sql.includes("SET state='failed', failure_code=?")) {
        [current.failure_code, current.updated_at] = values;
        current.state = "failed";
        current.cleanup_state = "confirmed";
        return { success: true };
      }
      throw new Error(`unexpected D1 write query: ${sql}`);
    },
  }; } });

  let diagnosticCode = "PREFLIGHT_RETURN_LINE_76";
  const originalFetch = globalThis.fetch;
  try {
    globalThis.fetch = async () => Response.json({ state: "failed", exit_code: 2,
      diagnostic_code: diagnosticCode,
      stderr: "private-provider-diagnostic-must-not-leak", sandbox_id: "sb-failed",
      cleanup_state: "confirmed" });
    const response = await toolCall(env, "test-owner", "experiment_status", { run_id: runId });
    const rpc = await response.json();
    const result = JSON.parse(rpc.result.content[0].text);
    assert.equal(result.machine_state.state, "failed");
    assert.equal(result.machine_state.failure_code, "MODAL_WORKLOAD_EXIT_2_PREFLIGHT_RETURN_LINE_76");
    assert.equal(result.machine_state.cleanup_state, "confirmed");
    assert.doesNotMatch(JSON.stringify(result), /private-provider-diagnostic-must-not-leak/);

    current.state = "running";
    current.failure_code = null;
    diagnosticCode = "PREFLIGHT_SYSTEM_EXIT_2";
    const fallbackResponse = await toolCall(env, "test-owner", "experiment_status", { run_id: runId });
    const fallbackRpc = await fallbackResponse.json();
    const fallbackResult = JSON.parse(fallbackRpc.result.content[0].text);
    assert.equal(fallbackResult.machine_state.failure_code, "MODAL_WORKLOAD_EXIT_2_PREFLIGHT_SYSTEM_EXIT_2");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("does not persist a successful result from a different Modal image fingerprint", async () => {
  const runId = "7".repeat(32);
  const expectedFingerprint = "d".repeat(64);
  const row = { id: runId, state: "running", created_at: 10, updated_at: 11,
    result_json: null, failure_code: null, cleanup_state: "pending", cancel_requested: 0,
    result_artifact_id: null, result_artifact_sha256: null, result_artifact_size: null,
    lease_id: null, workload: "tiny-stories-inference-v1", repository: "Unjuno/gpu-control",
    source_sha: sourceSha, image_digest: imageDigest,
    parameters_json: JSON.stringify({ prompt: "Once", max_new_tokens: 1, seed: 1 }),
    fingerprint: "c".repeat(64), runtime_seconds: 10, idempotency_key: "fingerprint-mismatch", provider: "modal_cpu" };
  const env = environment({ admission: "true" });
  env.MODAL_API_URL = modalApiUrl;
  env.MODAL_PROXY_TOKEN_ID = `wk-${"t".repeat(16)}`;
  env.MODAL_PROXY_TOKEN_SECRET = `ws-${"s".repeat(16)}`;
  env.MODAL_WORKLOAD_IMAGE_FINGERPRINT = expectedFingerprint;
  let artifactWrites = 0;
  env.BUCKET = { put: async () => { artifactWrites++; } };
  env.DB.prepare = (sql) => ({ bind(...values) { return {
    async first() {
      if (sql.includes("FROM runs r JOIN plans p")) return { ...row };
      throw new Error(`unexpected D1 first query: ${sql}`);
    },
    async run() {
      if (sql.includes("modal_status_check_limits")) return { meta: { changes: 1 } };
      if (sql.startsWith("UPDATE runs SET lease_id=")) return { meta: { changes: 1 } };
      if (sql.includes("MODAL_IMAGE_FINGERPRINT_MISMATCH")) {
        row.state = "failed";
        row.failure_code = "MODAL_IMAGE_FINGERPRINT_MISMATCH";
        row.cleanup_state = "confirmed";
        return { meta: { changes: 1 } };
      }
      throw new Error(`unexpected D1 write query: ${sql}`);
    },
  }; } });

  const originalFetch = globalThis.fetch;
  try {
    globalThis.fetch = async () => Response.json({ state: "succeeded", cleanup_state: "confirmed",
      sandbox_id: "sb-mismatched-image", image_fingerprint: "e".repeat(64), result: { status: "passed" } });
    const response = await toolCall(env, "test-owner", "experiment_status", { run_id: runId });
    const result = JSON.parse((await response.json()).result.content[0].text);
    assert.equal(result.machine_state.state, "failed");
    assert.equal(result.machine_state.failure_code, "MODAL_IMAGE_FINGERPRINT_MISMATCH");
    assert.equal(result.machine_state.cleanup_state, "confirmed");
    assert.equal(artifactWrites, 0);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("lost Modal submit response is reconciled without creating a duplicate Sandbox", async () => {
  const runId = "9".repeat(32);
  const plan = { id: runId, owner_id: "test-owner", state: "prepared", expires_at: Math.floor(Date.now() / 1000) + 300,
    fingerprint: "c".repeat(64), image_digest: imageDigest, workload: "tiny-stories-inference-v1",
    repository: "Unjuno/gpu-control", source_sha: sourceSha, provider: "modal_cpu",
    parameters_json: JSON.stringify({ prompt: "Once", max_new_tokens: 1, seed: 1 }), runtime_seconds: 10, max_cost_usd: "0.01" };
  let current = null;
  const authorization = { id: "d".repeat(32), fingerprint: plan.fingerprint,
    expires_at: Math.floor(Date.now() / 1000) + 300, consumed_at: null };
  let healthBudgetUsed = false;
  let planHealthUsed = false;
  let providerBudgetReserved = false;
  const env = environment({ admission: "true" });
  env.MODAL_API_URL = modalApiUrl;
  env.MODAL_PROXY_TOKEN_ID = `wk-${"t".repeat(16)}`;
  env.MODAL_PROXY_TOKEN_SECRET = `ws-${"s".repeat(16)}`;
  env.MODAL_WORKLOAD_IMAGE_FINGERPRINT = "d".repeat(64);
  env.BUCKET = { put: async () => {} };
  env.DB.batch = async () => {
    assert.equal(plan.state, "prepared");
    assert.equal(authorization.consumed_at, null);
    authorization.consumed_at = Math.floor(Date.now() / 1000);
    plan.state = "queued";
    current = { id: runId, state: "queued", cancel_requested: 0, cleanup_state: "pending", lease_id: null,
      created_at: Math.floor(Date.now() / 1000), updated_at: Math.floor(Date.now() / 1000) };
  };
  env.DB.prepare = (sql) => ({ bind(...values) { return {
    async first() {
      if (sql.startsWith("SELECT id, state, created_at FROM runs WHERE owner_id=?")) return current ? { id: current.id, state: current.state, created_at: current.created_at } : null;
      if (sql.includes("SELECT ready FROM modal_authorized_health_checks")) return { ready: 1 };
      if (sql.includes("FROM plans WHERE id=?")) return plan;
      if (sql.includes("FROM human_authorizations")) return { ...authorization };
      if (sql.includes("FROM provider_budget_reservations WHERE run_id=?")) return providerBudgetReserved
        ? { provider: "modal_cpu", period_key: new Date().toISOString().slice(0, 7), reserved_microusd: 10000 }
        : null;
      if (sql.includes("FROM runs r JOIN plans p")) return current ? { ...plan, ...current } : null;
      if (sql.startsWith("SELECT state, created_at, updated_at, cleanup_state, failure_code FROM runs")) return current;
      throw new Error(`unexpected D1 first query: ${sql}`);
    },
    async run() {
      if (sql.includes("modal_status_check_limits")) return { meta: { changes: 1 } };
      if (sql.includes("UPDATE modal_authorized_health_checks")) return { meta: { changes: 1 } };
      if (sql.includes("modal_health_check_limits")) {
        if (healthBudgetUsed) return { meta: { changes: 0 } };
        healthBudgetUsed = true;
        return { meta: { changes: 1 } };
      }
      if (sql.includes("modal_authorized_health_checks")) {
        if (planHealthUsed) return { meta: { changes: 0 } };
        planHealthUsed = true;
        return { meta: { changes: 1 } };
      }
      if (sql.includes("INSERT INTO provider_budget_reservations")) {
        providerBudgetReserved = true;
        return { meta: { changes: 1 } };
      }
      if (sql.startsWith("UPDATE runs SET state='running'")) {
        current.state = "running";
        current.updated_at = values[1];
        return { success: true };
      }
      if (sql.startsWith("UPDATE runs SET lease_id=")) {
        current.lease_id = values[0];
        return { success: true };
      }
      throw new Error(`unexpected D1 write query: ${sql}`);
    },
  }; } });

  const originalFetch = globalThis.fetch;
  let statusChecks = 0;
  let submitCalls = 0;
  let healthChecks = 0;
  try {
    globalThis.fetch = async (url) => {
      const requestUrl = String(url);
      if (requestUrl.endsWith("/v1/health")) {
        healthChecks++;
        return Response.json({ ready: true, provider: "modal_cpu", workload: "tiny-stories-inference-v1",
          source_sha: sourceSha, registered_image_digest: imageDigest,
          image_fingerprint: env.MODAL_WORKLOAD_IMAGE_FINGERPRINT, max_runtime_seconds: 30 });
      }
      if (requestUrl.endsWith(`/v1/runs/${runId}/submit`)) {
        submitCalls++;
        throw new TypeError("response lost after provider accepted the request");
      }
      if (requestUrl.endsWith(`/v1/runs/${runId}/status`)) {
        statusChecks++;
        if (statusChecks === 1) return Response.json({ detail: "Sandbox not found" }, { status: 404 });
        return Response.json({ state: "running", sandbox_id: "sb-existing", cleanup_state: "pending" });
      }
      throw new Error(`unexpected provider request: ${requestUrl}`);
    };

    const submitResponse = await toolCall(env, "test-owner", "experiment_submit", {
      ...submitArgs(runId, plan.fingerprint, approvedPlan({ prompt: "Once" })),
    });
    const submitRpc = await submitResponse.json();
    assert.equal(submitRpc.result.isError, true, "the lost provider response is reported as an error");
    assert.equal(current.state, "running", "the durable run reservation survives the lost response");

    const originalNow = Date.now;
    for (let attempt = 0; attempt < 2; attempt++) {
      Date.now = attempt === 0 ? originalNow : () => originalNow() + 4000;
      const response = await toolCall(env, "test-owner", "experiment_status", { run_id: runId });
      const rpc = await response.json();
      const result = JSON.parse(rpc.result.content[0].text);
      assert.equal(rpc.result.isError, false, rpc.result.content[0].text);
      assert.equal(result.machine_state.state, "running");
    }
    Date.now = originalNow;
  } finally {
    globalThis.fetch = originalFetch;
  }
  assert.equal(statusChecks, 2, "repeated status checks reconcile the same reserved run");
  assert.equal(submitCalls, 1, "a lost submit response is never blindly retried");
  assert.equal(healthChecks, 0, "submit reuses a successful one-use health result instead of billing a duplicate check");
  assert.equal(current.state, "running", "the reconciled Sandbox retains the occupied slot");
  assert.equal(current.lease_id, "sb-existing", "the later provider lookup reconnects the original Sandbox");
});

test("Modal status timeout preserves the recoverable running state without claiming cleanup", async () => {
  const runId = "6".repeat(32);
  const current = { id: runId, state: "running", created_at: 10, updated_at: 11,
    lease_expires_at: 1000, result_json: null, failure_code: null, cleanup_state: "pending",
    cleanup_receipt_json: null, cancel_requested: 0, result_artifact_id: null,
    result_artifact_sha256: null, result_artifact_size: null, lease_id: "sb-existing",
    workload: "tiny-stories-inference-v1", repository: "Unjuno/gpu-control", source_sha: sourceSha,
    image_digest: imageDigest, parameters_json: JSON.stringify({ prompt: "Once", max_new_tokens: 1, seed: 1 }),
    fingerprint: "c".repeat(64), runtime_seconds: 30, provider: "modal_cpu" };
  const env = environment();
  env.MODAL_API_URL = modalApiUrl;
  env.MODAL_PROXY_TOKEN_ID = `wk-${"t".repeat(16)}`;
  env.MODAL_PROXY_TOKEN_SECRET = `ws-${"s".repeat(16)}`;
  env.MODAL_WORKLOAD_IMAGE_FINGERPRINT = "d".repeat(64);
  env.BUCKET = { put: async () => {} };
  let stateWrites = 0;
  env.DB.prepare = (sql) => ({ bind() { return {
    async first() {
      if (sql.includes("FROM runs r JOIN plans p")) return { ...current };
      throw new Error(`unexpected D1 first query: ${sql}`);
    },
    async run() {
      if (sql.includes("modal_status_check_limits")) return { meta: { changes: 1 } };
      stateWrites++;
      throw new Error(`unexpected D1 state write after provider timeout: ${sql}`);
    },
  }; } });

  const originalFetch = globalThis.fetch;
  try {
    globalThis.fetch = async () => { throw new DOMException("request timed out", "AbortError"); };
    const response = await toolCall(env, "test-owner", "experiment_status", { run_id: runId });
    const rpc = await response.json();
    assert.equal(rpc.result.isError, true);
    assert.deepEqual(JSON.parse(rpc.result.content[0].text), { error: "INTERNAL_ERROR" },
      "provider timeout details must not escape through the public tool response");
    assert.equal(current.state, "running");
    assert.equal(current.cleanup_state, "pending");
    assert.equal(current.failure_code, null);
    assert.equal(stateWrites, 0, "an observation timeout must not invent a terminal state or cleanup receipt");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("persistent Modal not-found releases a stale run slot only after the recovery horizon", async () => {
  const runId = "8".repeat(32);
  const leaseExpiresAt = 1000;
  const current = { id: runId, state: "running", created_at: 900, updated_at: 901,
    lease_expires_at: leaseExpiresAt, result_json: null, failure_code: null, cleanup_state: "pending",
    cleanup_receipt_json: null, cancel_requested: 0, result_artifact_id: null,
    result_artifact_sha256: null, result_artifact_size: null, lease_id: null,
    workload: "tiny-stories-inference-v1", repository: "Unjuno/gpu-control", source_sha: sourceSha,
    image_digest: imageDigest, parameters_json: JSON.stringify({ prompt: "Once", max_new_tokens: 1, seed: 1 }),
    fingerprint: "c".repeat(64), runtime_seconds: 30, provider: "modal_cpu" };
  const env = environment();
  env.MODAL_API_URL = modalApiUrl;
  env.MODAL_PROXY_TOKEN_ID = `wk-${"t".repeat(16)}`;
  env.MODAL_PROXY_TOKEN_SECRET = `ws-${"s".repeat(16)}`;
  env.MODAL_WORKLOAD_IMAGE_FINGERPRINT = "d".repeat(64);
  env.BUCKET = { put: async () => {} };
  env.DB.prepare = (sql) => ({ bind(...values) { return {
    async first() {
      if (sql.includes("FROM runs r JOIN plans p")) return { ...current };
      if (sql.startsWith("SELECT state, created_at, updated_at, cleanup_state, failure_code FROM runs")) return { ...current };
      throw new Error(`unexpected D1 first query: ${sql}`);
    },
    async run() {
      if (sql.includes("modal_status_check_limits")) return { meta: { changes: 1 } };
      if (sql.includes("MODAL_SANDBOX_ABSENT_AFTER_RECOVERY_GRACE")) {
        assert.equal(values[4], leaseExpiresAt, "the update is fenced to the observed lease generation");
        current.state = "failed";
        current.failure_code = "MODAL_SANDBOX_ABSENT_AFTER_RECOVERY_GRACE";
        current.cleanup_state = "confirmed";
        current.cleanup_receipt_json = values[0];
        current.updated_at = values[1];
        return { meta: { changes: 1 } };
      }
      throw new Error(`unexpected D1 write query: ${sql}`);
    },
  }; } });

  const originalFetch = globalThis.fetch;
  const originalNow = Date.now;
  try {
    globalThis.fetch = async () => Response.json({ state: "not_found", cleanup_state: "unknown" }, { status: 404 });
    Date.now = () => (leaseExpiresAt + 300 - 1) * 1000;
    const earlyResponse = await toolCall(env, "test-owner", "experiment_status", { run_id: runId });
    const early = JSON.parse((await earlyResponse.json()).result.content[0].text);
    assert.equal(early.machine_state.state, "running");
    assert.equal(early.machine_state.cleanup_state, "pending");

    Date.now = () => (leaseExpiresAt + 300) * 1000;
    const recoveredResponse = await toolCall(env, "test-owner", "experiment_status", { run_id: runId });
    const recovered = JSON.parse((await recoveredResponse.json()).result.content[0].text);
    assert.equal(recovered.machine_state.state, "failed");
    assert.equal(recovered.machine_state.failure_code, "MODAL_SANDBOX_ABSENT_AFTER_RECOVERY_GRACE");
    assert.equal(recovered.machine_state.cleanup_state, "confirmed");
    assert.equal(JSON.parse(current.cleanup_receipt_json).evidence, "modal_named_sandbox_absent_after_bounded_lifetime");
  } finally {
    globalThis.fetch = originalFetch;
    Date.now = originalNow;
  }
});

test("retries Modal result persistence after an R2 or D1 write failure", async () => {
  const runId = "e".repeat(32);
  const fingerprint = "f".repeat(64);
  const parameters = { prompt: "Once", max_new_tokens: 1, seed: 1 };
  const checks = ["source_identity_present", "parameter_bounds", "model_digest_verified", "inference_completed",
    "non_root", "no_secret_environment", "no_docker_socket", "read_only_rootfs", "network_disabled"];
  const metrics = { model_id: "karpathy/tinyllamas@0bd21da7698eaf29a0d7de3992de8a46ef624add/stories15M.bin",
    model_sha256: "cd590644d963867a2b6e5a1107f51fad663c41d79c149fbecbbb1f95fa81f49a",
    max_new_tokens: 1, seed: 1, generated_text: "A", generated_tokens: 1, prompt_sha256: "1".repeat(64) };
  const resultCore = { schema_version: 1, run_id: runId, source_sha: sourceSha, plan_fingerprint: fingerprint,
    check: "tiny-stories-inference-v1", status: "passed", gpu_used: false, checks, metrics };
  const result = { ...resultCore,
    checksum: createHash("sha256").update(canonicalJson({ run_id: runId, source_sha: sourceSha,
      plan_fingerprint: fingerprint, metrics })).digest("hex") };
  const joined = { id: runId, state: "running", cancel_requested: 0, workload: "tiny-stories-inference-v1",
    repository: "Unjuno/gpu-control", source_sha: sourceSha, image_digest: imageDigest, fingerprint,
    parameters_json: JSON.stringify(parameters), runtime_seconds: 10, lease_id: null, provider: "modal_cpu" };

  for (const fault of ["r2", "d1", "cancel-race"]) {
    const env = environment({ admission: "true" });
    env.MODAL_API_URL = modalApiUrl;
    env.MODAL_PROXY_TOKEN_ID = `wk-${"t".repeat(16)}`;
    env.MODAL_PROXY_TOKEN_SECRET = `ws-${"s".repeat(16)}`;
    env.MODAL_WORKLOAD_IMAGE_FINGERPRINT = "a".repeat(64);
    let bucketWrites = 0;
    let bucketDeletes = 0;
    env.BUCKET = { put: async () => {
      if (fault === "r2" && bucketWrites++ === 0) throw new Error("injected R2 write failure");
      if (fault === "d1" || fault === "cancel-race") bucketWrites++;
      if (fault === "cancel-race") current.cancel_requested = 1;
      return {};
    }, delete: async () => { bucketDeletes++; } };
    let finalizeWrites = 0;
    const current = { ...joined };
    env.DB.prepare = (sql) => ({ bind(...values) {
      return {
        async first() {
          if (sql.includes("FROM runs r JOIN plans p")) return { ...current };
          if (sql.startsWith("SELECT state, cancel_requested FROM runs")) return { ...current };
          throw new Error(`unexpected D1 first query: ${sql}`);
        },
        async run() {
          if (sql.includes("modal_status_check_limits")) return { meta: { changes: 1 } };
          if (sql.startsWith("UPDATE runs SET lease_id=")) {
            current.lease_id = values[0];
            return { success: true };
          }
          if (sql.startsWith("UPDATE runs SET state='succeeded'")) {
            if (fault === "d1" && finalizeWrites++ === 0) throw new Error("injected D1 finalize failure");
            if (fault === "cancel-race") return { success: true, meta: { changes: 0 } };
            current.state = "succeeded";
            current.result_json = values[0];
            current.result_artifact_id = values[1];
            current.result_artifact_sha256 = values[2];
            current.result_artifact_size = values[3];
            current.cleanup_state = "confirmed";
            return { success: true, meta: { changes: 1 } };
          }
          throw new Error(`unexpected D1 write query: ${sql}`);
        },
      };
    } });

    const originalFetch = globalThis.fetch;
    let providerReads = 0;
    try {
      globalThis.fetch = async (url, init) => {
        assert.match(String(url), new RegExp(`/v1/runs/${runId}/status$`));
        assert.equal(new Headers(init.headers).get("authorization"),
          `Bearer ${env.MODAL_PROXY_TOKEN_ID}.${env.MODAL_PROXY_TOKEN_SECRET}`);
        assert.equal(new Headers(init.headers).get("modal-key"), null);
        assert.equal(new Headers(init.headers).get("modal-secret"), null);
        providerReads++;
        return Response.json({ state: "succeeded", cleanup_state: "confirmed", sandbox_id: "sb-terminal",
          image_fingerprint: env.MODAL_WORKLOAD_IMAGE_FINGERPRINT, result });
      };
      const firstResponse = await toolCall(env, "test-owner", "experiment_status", { run_id: runId });
      const firstRpc = await firstResponse.json();
      if (fault === "cancel-race") {
        assert.equal(firstRpc.result.isError, false);
        const state = JSON.parse(firstRpc.result.content[0].text);
        assert.equal(state.machine_state.state, "running");
        assert.equal(state.machine_state.cancellation_requested, true);
        assert.equal(current.state, "running", "a concurrent cancellation must prevent success finalization");
        assert.equal(bucketWrites, 1);
        assert.equal(bucketDeletes, 1, "the uncommitted run artifact must be removed after cancellation wins");
        assert.equal(providerReads, 1);
        continue;
      }
      assert.equal(firstRpc.result.isError, true, `${fault} failure must remain visible: ${JSON.stringify(firstRpc.result)}`);
      assert.equal(current.state, "running", `${fault} failure must not mark an unpersisted result successful`);

      const retryResponse = await toolCall(env, "test-owner", "experiment_status", { run_id: runId });
      const retryRpc = await retryResponse.json();
      assert.equal(retryRpc.result.isError, false);
      assert.equal(JSON.parse(retryRpc.result.content[0].text).machine_state.state, "succeeded");
      assert.equal(current.state, "succeeded");
      assert.equal(providerReads, 2, "retry must reconcile the same deterministic Modal run");
      assert.equal(bucketWrites, 2);
    } finally {
      globalThis.fetch = originalFetch;
    }
  }
});

test("rejects legacy checksum parameters from the inference tool", async () => {
  const request = new Request("https://site.invalid/mcp", {
    method: "POST",
    headers: { "content-type": "application/json", "oai-authenticated-user-id": "test-owner" },
    body: JSON.stringify({
      jsonrpc: "2.0", id: 9, method: "tools/call",
      params: { name: "experiment_prepare", arguments: {
        repository: "Unjuno/gpu-control", commit: sourceSha, workload: "cpu-smoke-v1",
        parameters: { iterations: 1000, seed: 61112 }, runtime_seconds: 30,
        max_cost_usd: "0.01", idempotency_key: "legacy-smoke-key",
      } },
    }),
  });
  const response = await worker.fetch(request, environment());
  const rpc = await response.json();
  assert.equal(rpc.result.isError, true);
  assert.deepEqual(JSON.parse(rpc.result.content[0].text), { error: "INVALID_ARGUMENTS" });
});

test("rejects a zero-dollar cost ceiling for usage-billed Modal Sandbox compute", async () => {
  const env = environment();
  env.DB.prepare = () => { throw new Error("invalid cost ceiling must fail before D1"); };
  const response = await toolCall(env, "test-owner", "experiment_prepare", {
    repository: "Unjuno/gpu-control", commit: sourceSha, workload: "tiny-stories-inference-v1",
    parameters: { prompt: "Once", max_new_tokens: 1, seed: 1 }, runtime_seconds: 30,
    max_cost_usd: "0.00", idempotency_key: "zero-cost-denied",
  });
  const rpc = await response.json();
  assert.equal(rpc.result.isError, true);
  assert.deepEqual(JSON.parse(rpc.result.content[0].text), { error: "INVALID_ARGUMENTS" });
});

test("registered workload ID resolves fixed CPU defaults without provider calls", async () => {
  const env = environment();
  const writes = [];
  let fingerprint;
  env.DB.prepare = (sql) => ({ bind(...values) { return {
    async run() { writes.push({ sql, values }); if (sql.includes("INSERT OR IGNORE INTO plans")) fingerprint = values[3]; return { meta: { changes: 1 } }; },
    async first() { return { id: "d".repeat(32), fingerprint, image_digest: imageDigest,
      state: "prepared", expires_at: Math.floor(Date.now() / 1000) + 600 }; },
  }; } });

  const response = await toolCall(env, "test-owner", "experiment_prepare", {
    workload_id: "tiny-stories-inference-v1",
  });
  const result = JSON.parse((await response.json()).result.content[0].text);
  assert.equal(result.status, "ok");
  assert.equal(result.machine_state.provider, "modal_cpu");
  assert.deepEqual(result.machine_state.approved_plan, approvedPlan({ prompt: "Once", max_new_tokens: 1,
    seed: 61112, runtime_seconds: 30, estimated_sandbox_cost_usd: "0.0013" }));
  assert.equal(writes.length, 1);
  assert.match(writes[0].sql, /INSERT OR IGNORE INTO plans/);
});

test("registered RunPod workload ID resolves its fixed plan without allocating a job", async () => {
  const env = environment();
  Object.assign(env, {
    RUNPOD_API_KEY: "safe-runpod-key-with-enough-bytes",
    RUNPOD_WORKLOAD_IMAGE: `ghcr.io/unjuno/gpu-control-runpod-canary@sha256:${"a".repeat(64)}`,
    RUNPOD_GPU_ID: "NVIDIA RTX 2000 Ada Generation", RUNPOD_SERVERLESS_ENDPOINT_ID: "endpoint_test_123",
    RUNPOD_SERVERLESS_HOURLY_PRICE_USD: "0.580000", RUNPOD_SERVERLESS_GPU_POOL_ID: "ADA_16",
    RUNPOD_WORKLOAD_SOURCE_SHA: sourceSha, RUNPOD_WORKLOAD_ADMISSION_ENABLED: "true",
    RUNPOD_LIVE_COMPLETION_TRANSPORT_VERIFIED: "true",
  });
  let inserted = false;
  let plan;
  let fingerprint;
  let persistedPlanJson;
  env.DB.prepare = (sql) => ({ bind(...values) { return {
    async run() { if (sql.includes("INSERT OR IGNORE INTO plans")) { inserted = true; fingerprint = values[3]; persistedPlanJson = values.at(-2); plan = JSON.parse(persistedPlanJson); } return { meta: { changes: 1 } }; },
    async first() { return inserted ? { id: "f".repeat(32), fingerprint, provider_plan_json: persistedPlanJson,
      state: "prepared", expires_at: Math.floor(Date.now() / 1000) + 600 } : null; },
  }; } });
  env.fetch = async () => { throw new Error("prepare must not call RunPod"); };

  const response = await toolCall(env, "test-owner", "experiment_prepare", { workload_id: "runpod-gpu-canary-v1" });
  const result = JSON.parse((await response.json()).result.content[0].text);
  assert.equal(result.status, "ok");
  assert.equal(result.provider_approved_plan.source_sha, sourceSha);
  assert.equal(result.provider_approved_plan.max_cost_usd, "1.00");
  assert.equal(inserted, true);
});

test("registered ZeroGPU workload resolves only an owned completed Kaggle artifact", async () => {
  const sourceRun = "1".repeat(32);
  // Artifact repository commits are created per run and are distinct from
  // the fixed Hugging Face Space source revision in the workload registry.
  const revision = "8".repeat(40);
  const artifactSha = "3".repeat(64);
  const env = environment();
  env.PROVIDER_ADAPTER_URL = "https://unjuno--gpu-control-provider-adapter-provider-adapter-api.us-east.modal.run";
  env.PROVIDER_ADAPTER_KEY_ID = "sites-v1";
  env.PROVIDER_ADAPTER_HMAC_KEY_B64 = Buffer.alloc(32, 7).toString("base64");
  env.PROVIDER_ADAPTER_PROXY_TOKEN_ID = "wk-adaptertest123";
  env.PROVIDER_ADAPTER_PROXY_TOKEN_SECRET = "ws-adaptertestsecret123";
  let persistedApprovedPlan;
  env.DB.prepare = (sql) => ({ bind(...values) { return {
    async all() {
      if (sql.includes("gateway_delegated_plans")) return { results: [{ source_run_id: sourceRun,
        approved_plan_json: JSON.stringify({ source_sha: sourceSha }),
        provider_response_json: JSON.stringify({ cleanup_confirmed: true, result: { external_artifacts: [{
          service: "huggingface_hub", private: true, repo_type: "model", repo_id: "Unjuno/gpu-control-orbitune-artifacts",
          revision, path_in_repo: `runs/${sourceRun}/orbitune-output.zip`, sha256: artifactSha,
          run_id: sourceRun, source_sha: sourceSha,
        }] } }) }] };
      return { results: [] };
    },
    async first() {
      if (sql.includes("FROM runs r JOIN plans p")) return null;
      if (sql.includes("gateway_delegated_plans") && sql.includes("WHERE owner_id=? AND id=?")) return {
        source_run_id: sourceRun, approved_plan_json: JSON.stringify({ source_sha: sourceSha }),
        provider_response_json: JSON.stringify({ cleanup_confirmed: true, result: { external_artifacts: [{
          service: "huggingface_hub", private: true, repo_type: "model", repo_id: "Unjuno/gpu-control-orbitune-artifacts",
          revision, path_in_repo: `runs/${sourceRun}/orbitune-output.zip`, sha256: artifactSha,
          run_id: sourceRun, source_sha: sourceSha,
        }] } }),
      };
      return { id: "4".repeat(32), fingerprint: "5".repeat(64), workload: "orbitune-zero-gpu-eval-v1",
        approved_plan_json: persistedApprovedPlan, state: "prepared", expires_at: Math.floor(Date.now() / 1000) + 600 };
    },
    async run() { if (sql.includes("INSERT OR IGNORE INTO gateway_delegated_plans")) persistedApprovedPlan = values[5]; return { meta: { changes: 1 } }; },
  }; } });
  let delegated;
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (_url, init) => {
    delegated = JSON.parse(init.body).arguments;
    return new Response(JSON.stringify({ schema_version: 2, status: "ok", human_summary: "prepared",
      machine_state: { run_id: "4".repeat(32), plan_fingerprint: "5".repeat(64), state: "prepared" },
      approved_plan: { schema_version: 2, workload: "orbitune-zero-gpu-eval-v1", repository: "Unjuno/orbitune",
        source_sha: "44a1b806160ab5bc721a370d034a6dfcb28f27a8", provider: "huggingface_space", max_cost_usd: "0", paid_fallback_allowed: false } }));
  };

  try {
    const response = await toolCall(env, "test-owner", "experiment_prepare", {
      workload_id: "orbitune-zero-gpu-eval-v1", source_run_id: sourceRun,
    });
    const result = JSON.parse((await response.json()).result.content[0].text);
    assert.equal(result.status, "ok", JSON.stringify(result));
    assert.equal(result.machine_state.source_run_id, sourceRun);
    assert.equal(delegated.repository, "Unjuno/orbitune");
    assert.equal(delegated.commit, "44a1b806160ab5bc721a370d034a6dfcb28f27a8");
    assert.equal(delegated.parameters.artifact_revision, revision);
    assert.equal(delegated.parameters.artifact_sha256, artifactSha);
    assert.equal(delegated.max_cost_usd, "0");
  } finally { globalThis.fetch = originalFetch; }
});

test("Runpod prepare fails closed before provider access when completion transport is unverified", async () => {
  const env = environment();
  Object.assign(env, {
    RUNPOD_API_KEY: "safe-runpod-key-with-enough-bytes",
    RUNPOD_WORKLOAD_IMAGE: `ghcr.io/unjuno/gpu-control-runpod-canary@sha256:${"a".repeat(64)}`,
    RUNPOD_GPU_ID: "NVIDIA RTX 2000 Ada Generation",
    RUNPOD_SERVERLESS_ENDPOINT_ID: "endpoint_test_123",
    RUNPOD_SERVERLESS_HOURLY_PRICE_USD: "0.580000",
    RUNPOD_SERVERLESS_GPU_POOL_ID: "ADA_16",
    RUNPOD_WORKLOAD_SOURCE_SHA: sourceSha,
    RUNPOD_WORKLOAD_ADMISSION_ENABLED: "true",
    RUNPOD_LIVE_COMPLETION_TRANSPORT_VERIFIED: "false",
  });
  env.DB.prepare = () => { throw new Error("unverified transport must fail before D1 or provider access"); };
  const response = await toolCall(env, "test-owner", "experiment_prepare", {
    repository: "Unjuno/gpu-control", commit: sourceSha, workload: "runpod-gpu-canary-v1",
    parameters: {}, runtime_seconds: 30, max_cost_usd: "1.00", idempotency_key: "runpod-unverified",
  });
  const result = JSON.parse((await response.json()).result.content[0].text);
  assert.equal(result.status, "blocked");
  assert.equal(result.blocking_reason, "RUNPOD_LIVE_COMPLETION_TRANSPORT_UNVERIFIED");
  assert.equal(result.machine_state.job_submitted, false);
});

test("rejects a malformed UTF-16 prompt before writing a plan", async () => {
  const request = new Request("https://site.invalid/mcp", {
    method: "POST",
    headers: { "content-type": "application/json", "oai-authenticated-user-id": "test-owner" },
    body: JSON.stringify({
      jsonrpc: "2.0", id: 10, method: "tools/call",
      params: { name: "experiment_prepare", arguments: {
        repository: "Unjuno/gpu-control", commit: sourceSha, workload: "tiny-stories-inference-v1",
        parameters: { prompt: "\ud800", max_new_tokens: 8, seed: 1 }, runtime_seconds: 30,
        max_cost_usd: "0.01", idempotency_key: "invalid-unicode-key",
      } },
    }),
  });
  const response = await worker.fetch(request, environment());
  const rpc = await response.json();
  assert.deepEqual(JSON.parse(rpc.result.content[0].text), { error: "INVALID_ARGUMENTS" });
});

test("prepare idempotency keys are isolated by Site owner", async () => {
  const plans = new Map();
  const env = environment();
  env.GPU_CONTROL_ALLOWED_USER_IDS = "test-owner,different-owner";
  env.DB.prepare = (sql) => ({ bind(...values) {
    if (sql.includes("INSERT OR IGNORE INTO plans")) {
      assert.match(sql, /owner_id/);
      return { async run() {
        const [id, owner, key, fingerprint, , , , digest] = values;
        const mapKey = `${owner}:${key}`;
        if (!plans.has(mapKey)) plans.set(mapKey, { id, fingerprint, image_digest: digest,
          state: "prepared", expires_at: Math.floor(Date.now() / 1000) + 300 });
      } };
    }
    assert.match(sql, /WHERE owner_id = \? AND idempotency_key = \?/);
    return { async first() { return plans.get(`${values[0]}:${values[1]}`) || null; } };
  } });

  const args = { repository: "Unjuno/gpu-control", commit: sourceSha,
    workload: "tiny-stories-inference-v1",
    parameters: { prompt: "A", max_new_tokens: 1, seed: 1 },
    runtime_seconds: 10, max_cost_usd: "0.01", idempotency_key: "same-key-0001" };
  const firstResult = JSON.parse((await (await toolCall(env, "test-owner", "experiment_prepare", args)).json()).result.content[0].text);
  const secondResult = JSON.parse((await (await toolCall(env, "different-owner", "experiment_prepare", args)).json()).result.content[0].text);
  const first = firstResult.machine_state;
  const second = secondResult.machine_state;

  assert.equal(first.state, "prepared");
  assert.equal(first.approval_required, true);
  assert.equal(first.authorization_surface, "mcp_destructive_write_action");
  assert.equal(first.approved_plan.prompt, "A");
  assert.equal(first.approved_plan.max_cost_usd, "0.01");
  assert.equal(first.approved_plan.estimated_sandbox_cost_usd, "0.0005");
  assert.equal(first.approved_plan.gpu_allowed, false);
  assert.equal(first.approved_plan.control_function_cost_included, false);
  assert.equal(first.authorization_url, undefined);
  assert.equal(second.state, "prepared");
  assert.equal(first.estimated_sandbox_cost_usd, "0.0005");
  assert.equal(first.max_sandbox_cost_usd, "0.01");
  assert.deepEqual(first.sandbox_resources, {
    cpu_request_physical_cores: 1, cpu_limit_physical_cores: 1,
    memory_request_mib: 512, memory_limit_mib: 512,
  });
  assert.equal(first.control_function_cost_included, false);
  assert.equal(first.cost_is_estimate, true);
  assert.equal(first.credit_eligible, true);
  assert.notEqual(first.run_id, second.run_id);
  assert.equal(plans.size, 2);
});



test("keeps Modal submission blocked until the provider is configured", async () => {
  const env = environment();
  const plan = storedPlan("f".repeat(32), "a".repeat(64));
  env.DB.prepare = (sql) => ({ bind() { return { first: async () => {
    if (sql.startsWith("SELECT id, state, created_at FROM runs WHERE owner_id=?")) return null;
    if (sql.includes("FROM plans WHERE id=?")) return plan;
    if (sql.includes("FROM human_authorizations")) return { id: "a".repeat(32), fingerprint: "a".repeat(64), expires_at: Math.floor(Date.now() / 1000) + 300, consumed_at: null };
    return null;
  } }; } });
  let writes = 0;
  env.DB.batch = async () => { writes++; throw new Error("blocked submission must not write"); };
  const response = await toolCall(env, "test-owner", "experiment_submit", {
    ...submitArgs("f".repeat(32), "a".repeat(64)),
  });
  const rpc = await response.json();
  assert.equal(rpc.result.isError, false);
  const result = JSON.parse(rpc.result.content[0].text);
  assert.equal(result.status, "blocked");
  assert.equal(result.blocking_reason, "MODAL_PROVIDER_NOT_CONFIGURED");
  assert.equal(writes, 0);
});

test("confirmed ChatGPT submit records an exact one-use authorization without a browser session", async () => {
  const runId = "8".repeat(32);
  const fingerprint = "9".repeat(64);
  const plan = storedPlan(runId, fingerprint);
  const env = environment();
  let authorization = null;
  let authorizationInsert = null;
  let batches = 0;
  env.DB.prepare = (sql) => ({ bind(...values) { return {
    async first() {
      if (sql.startsWith("SELECT id, state, created_at FROM runs WHERE owner_id=?")) return null;
      if (sql.includes("FROM plans WHERE id=?")) return plan;
      if (sql.includes("FROM human_authorizations")) return authorization;
      throw new Error(`unexpected ChatGPT authorization query: ${sql}`);
    },
    async run() {
      assert.match(sql, /chatgpt_mcp_write_confirmation/);
      assert.match(sql, /json_extract\(p\.parameters_json/);
      authorizationInsert = { source: "chatgpt_mcp_write_confirmation", owner_id: values[5], plan_id: values[4],
        fingerprint: values[6], authorized_at: values[2], expires_at: Math.min(values[3], plan.expires_at), consumed_at: null };
      authorization = { id: values[0], fingerprint: values[6], expires_at: authorizationInsert.expires_at, consumed_at: null };
      return { meta: { changes: 1 } };
    },
  }; } });
  env.DB.batch = async () => { batches++; throw new Error("provider-disabled submit must not reserve a run"); };

  const response = await toolCall(env, "test-owner", "experiment_submit", submitArgs(runId, fingerprint));
  const rpc = await response.json();
  const result = JSON.parse(rpc.result.content[0].text);
  assert.equal(rpc.result.isError, false);
  assert.equal(result.blocking_reason, "MODAL_PROVIDER_NOT_CONFIGURED");
  assert.equal(authorizationInsert.owner_id, "test-owner");
  assert.equal(authorizationInsert.plan_id, runId);
  assert.equal(authorizationInsert.fingerprint, fingerprint);
  assert.equal(authorizationInsert.source, "chatgpt_mcp_write_confirmation");
  assert.ok(authorizationInsert.expires_at <= plan.expires_at);
  assert.equal(authorization.consumed_at, null);
  assert.equal(batches, 0);
});

test("ChatGPT submit rejects plan review values that do not match the exact owner-bound plan", async () => {
  const env = environment({ admission: "true" });
  const plan = storedPlan("c".repeat(32), "e".repeat(64));
  let providerRequests = 0;
  let dbWrites = 0;
  let authorization = null;
  env.MODAL_API_URL = modalApiUrl;
  env.MODAL_PROXY_TOKEN_ID = `wk-${"t".repeat(16)}`;
  env.MODAL_PROXY_TOKEN_SECRET = `ws-${"s".repeat(16)}`;
  env.MODAL_WORKLOAD_IMAGE_FINGERPRINT = "f".repeat(64);
  env.DB.prepare = (sql) => ({ bind() { return { first: async () => {
    if (sql.startsWith("SELECT id, state, created_at FROM runs WHERE owner_id=?")) return null;
    if (sql.includes("FROM plans WHERE id=?")) return plan;
    if (sql.includes("FROM human_authorizations")) return authorization;
    return null;
  }, async run() { dbWrites++; return { success: true }; } }; } });
  env.DB.batch = async () => { dbWrites++; throw new Error("unconfirmed plan reached D1 batch"); };
  const originalFetch = globalThis.fetch;
  try {
    globalThis.fetch = async () => { providerRequests++; throw new Error("unconfirmed plan reached Modal"); };
    const response = await toolCall(env, "test-owner", "experiment_submit",
      submitArgs("c".repeat(32), "e".repeat(64), approvedPlan({ prompt: "changed" })));
    const rpc = await response.json();
    const result = JSON.parse(rpc.result.content[0].text);
    assert.equal(rpc.result.isError, false);
    assert.equal(result.blocking_reason, "APPROVED_PLAN_MISMATCH_OR_EXPIRED");
    assert.equal(result.machine_state.authorization_required, true);
    assert.equal(providerRequests, 0);
    assert.equal(dbWrites, 0);

    plan.expires_at = Math.floor(Date.now() / 1000) - 1;
    const expiredResponse = await toolCall(env, "test-owner", "experiment_submit",
      submitArgs("c".repeat(32), "e".repeat(64)));
    const expiredRpc = await expiredResponse.json();
    const expired = JSON.parse(expiredRpc.result.content[0].text);
    assert.equal(expired.blocking_reason, "APPROVED_PLAN_MISMATCH_OR_EXPIRED");
    assert.equal(expired.authorization_url, undefined);
    assert.equal(providerRequests, 0);
    assert.equal(dbWrites, 0);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("retired Runner routes stay closed even when a legacy bearer is supplied", async () => {
  const env = environment();
  env.RUNNER_BEARER_TOKEN = "x".repeat(48);
  env.DB.prepare = () => { throw new Error("retired route reached D1"); };
  for (const path of ["/runner/heartbeat", "/runner/claim", "/runner/result"]) {
    const response = await worker.fetch(new Request(`https://site.invalid${path}`, {
      method: "POST", headers: { authorization: `Bearer ${env.RUNNER_BEARER_TOKEN}` }, body: "{}",
    }), env);
    assert.equal(response.status, 404, path);
    assert.deepEqual(await response.json(), { error: "NOT_FOUND" });
  }
});

test("prepared delegated plans answer lifecycle reads locally without contacting a provider", async () => {
  const runId = "8".repeat(32);
  const now = Math.floor(Date.now() / 1000);
  const plan = {
    id: runId, owner_id: "test-owner", fingerprint: "a".repeat(64),
    workload: "orbitune-kaggle-100-step-v1", approved_plan_json: "{}",
    state: "prepared", created_at: now, expires_at: now + 300,
    provider_handle_json: null, provider_state: null, provider_response_json: null,
    updated_at: null,
  };
  const env = environment();
  env.PROVIDER_ADAPTER_URL = "https://unjuno--gpu-control-provider-adapter-provider-adapter-api.us-east.modal.run";
  env.PROVIDER_ADAPTER_KEY_ID = "sites-v1";
  env.PROVIDER_ADAPTER_HMAC_KEY_B64 = Buffer.alloc(32, 7).toString("base64");
  env.PROVIDER_ADAPTER_PROXY_TOKEN_ID = "wk-adaptertest123";
  env.PROVIDER_ADAPTER_PROXY_TOKEN_SECRET = "ws-adaptertestsecret123";
  env.DB.prepare = (sql) => ({
    bind() {
      return {
        async first() {
          if (sql.includes("FROM gateway_delegated_plans")) return plan;
          return null;
        },
        async run() { throw new Error(`unexpected write: ${sql}`); },
        async all() { return { results: [] }; },
      };
    },
  });
  const originalFetch = globalThis.fetch;
  let providerCalls = 0;
  globalThis.fetch = async () => { providerCalls += 1; throw new Error("provider must not be called"); };
  try {
    const status = await toolCall(env, "test-owner", "experiment_status", { run_id: runId });
    const statusValue = JSON.parse((await status.json()).result.content[0].text);
    assert.equal(statusValue.status, "ok");
    assert.equal(statusValue.machine_state.state, "prepared");
    assert.equal(statusValue.machine_state.provider_resource_created, false);
    assert.deepEqual(statusValue.next_allowed_actions, ["experiment_submit", "experiment_cancel"]);

    const result = await toolCall(env, "test-owner", "experiment_result", { run_id: runId });
    const resultValue = JSON.parse((await result.json()).result.content[0].text);
    assert.equal(resultValue.status, "blocked");
    assert.equal(resultValue.blocking_reason, "RESULT_NOT_READY");
    assert.equal(providerCalls, 0);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("prepared delegated cancellation uses a durable marker compatible with the deployed state constraint", async () => {
  const runId = "6".repeat(32);
  const now = Math.floor(Date.now() / 1000);
  const plan = { id: runId, owner_id: "test-owner", fingerprint: "a".repeat(64),
    workload: "orbitune-kaggle-100-step-v1", approved_plan_json: "{}", state: "prepared",
    created_at: now, expires_at: now + 300, provider_handle_json: null, provider_state: null,
    provider_response_json: null, updated_at: null, cancelled_at: null, submit_attempted_at: null };
  const env = environment();
  env.DB.prepare = (sql) => ({ bind() { return {
    async first() {
      if (sql.includes("FROM gateway_delegated_plans")) return plan;
      if (sql.includes("p.provider='runpod_gpu'")) return null;
      if (sql.includes("UPDATE gateway_delegated_plans SET cancelled_at")) {
        plan.cancelled_at = now;
        return { id: runId, cancelled_at: now };
      }
      throw new Error(`unexpected first query: ${sql}`);
    },
  }; } });
  const first = await toolCall(env, "test-owner", "experiment_cancel", { run_id: runId });
  const cancelled = JSON.parse((await first.json()).result.content[0].text);
  assert.equal(cancelled.machine_state.state, "cancelled");
  assert.equal(plan.state, "prepared", "the persisted state stays within the deployed CHECK constraint");
  assert.equal(plan.cancelled_at, now);
  const status = await toolCall(env, "test-owner", "experiment_status", { run_id: runId });
  const observed = JSON.parse((await status.json()).result.content[0].text);
  assert.equal(observed.machine_state.state, "cancelled");
  assert.equal(observed.machine_state.provider_resource_created, false);
});

test("lost delegated submit response remains uncertain when the adapter has no recorded claim", async () => {
  const runId = "5".repeat(32);
  const approved = { schema_version: 2, workload: "orbitune-kaggle-100-step-v1", provider: "kaggle",
    repository: "Unjuno/orbitune", source_sha: "44a1b806160ab5bc721a370d034a6dfcb28f27a8",
    parameters: {}, runtime_seconds: 300, max_cost_usd: "0", known_cost_usd: "0",
    cost_classification: "FREE_QUOTA", paid_fallback_allowed: false,
    image_digest: "sha256:09742cdf89ec6646e0a227bfd88252aed7b7a44a854899d8bd3eea8da6a9f8bd" };
  const plan = { id: runId, owner_id: "test-owner", fingerprint: "a".repeat(64), workload: approved.workload,
    approved_plan_json: JSON.stringify(approved), state: "submitted", created_at: 1, expires_at: 9999999999,
    provider_handle_json: null, provider_state: null, provider_response_json: null, updated_at: 2,
    cancelled_at: null, terminal_at: null, source_run_id: null, submit_attempted_at: 2 };
  const env = environment();
  env.PROVIDER_ADAPTER_URL = "https://unjuno--gpu-control-provider-adapter-provider-adapter-api.us-east.modal.run";
  env.PROVIDER_ADAPTER_KEY_ID = "sites-v1";
  env.PROVIDER_ADAPTER_HMAC_KEY_B64 = Buffer.alloc(32, 7).toString("base64");
  env.PROVIDER_ADAPTER_PROXY_TOKEN_ID = "wk-adaptertest123";
  env.PROVIDER_ADAPTER_PROXY_TOKEN_SECRET = "ws-adaptertestsecret123";
  env.DB.prepare = (sql) => ({ bind() { return { async first() {
    if (sql.includes("FROM gateway_delegated_plans")) return plan;
    if (sql.includes("p.provider='runpod_gpu'")) return null;
    throw new Error(`unexpected first query: ${sql}`);
  } }; } });
  const originalFetch = globalThis.fetch;
  let observed;
  globalThis.fetch = async (_url, init) => {
    observed = JSON.parse(init.body);
    return Response.json({ code: "provider_handle_mismatch" }, { status: 409 });
  };
  try {
    const result = await maybeDelegateRunTool(env, "test-owner", "experiment_status", { run_id: runId });
    assert.equal(observed.tool, "experiment_status");
    assert.equal(observed.arguments.provider_handle.transport, "modal_spawn_v1");
    assert.equal(result.status, "pending");
    assert.equal(result.machine_state.state, "uncertain");
    assert.equal(result.machine_state.provider_resource_created, "unknown");
    assert.equal(result.machine_state.cleanup_state, "unknown");
    assert.equal(result.blocking_reason, "SUBMISSION_OUTCOME_UNCONFIRMED");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("native RunPod runs take precedence over stale delegated-plan shadows", async () => {
  const runId = "7".repeat(32);
  const env = environment();
  let delegatedPlanReads = 0;
  env.DB.prepare = (sql) => ({
    bind(...values) {
      return {
        async first() {
          if (sql.includes("gateway_delegated_plans")) return {
            id: runId, owner_id: "test-owner", state: "submitted",
            provider_handle_json: null,
          };
          if (sql.includes("FROM runs r") && sql.includes("p.provider='runpod_gpu'")) {
            assert.deepEqual(values, [runId, "test-owner"]);
            return { id: runId };
          }
          delegatedPlanReads += 1;
          return null;
        },
      };
    },
  });

  const delegated = await maybeDelegateRunTool(
    env, "test-owner", "experiment_status", { run_id: runId });
  assert.equal(delegated, null);
  assert.equal(delegatedPlanReads, 0);
});

test("delegated private artifact uses the exact persisted immutable reference", async () => {
  const runId = "8".repeat(32);
  const reference = {
    service: "huggingface_hub", repo_id: "Unjuno/gpu-control-orbitune-artifacts",
    repo_type: "model", path_in_repo: `runs/${runId}/orbitune-output.zip`,
    revision: "a".repeat(40), sha256: "b".repeat(64), size_bytes: 1737429,
    run_id: runId, source_sha: "c".repeat(40), private: true,
  };
  const plan = {
    id: runId, fingerprint: "d".repeat(64), workload: "orbitune-kaggle-100-step-v1",
    approved_plan_json: JSON.stringify({ runtime_seconds: 300 }), state: "submitted",
    provider_handle_json: JSON.stringify({ provider: "kaggle", run_id: runId }),
    provider_response_json: JSON.stringify({ result: { external_artifacts: [reference] } }),
  };
  const env = environment();
  let providerObservationWrites = 0;
  env.PROVIDER_ADAPTER_URL = "https://unjuno--gpu-control-provider-adapter-provider-adapter-api.us-east.modal.run";
  env.PROVIDER_ADAPTER_KEY_ID = "sites-v1";
  env.PROVIDER_ADAPTER_HMAC_KEY_B64 = Buffer.alloc(32, 7).toString("base64");
  env.PROVIDER_ADAPTER_PROXY_TOKEN_ID = "wk-adaptertest123";
  env.PROVIDER_ADAPTER_PROXY_TOKEN_SECRET = "ws-adaptertestsecret123";
  env.DB.prepare = (sql) => ({
    bind() {
      return {
        async first() {
          if (sql.includes("gateway_delegated_plans")) return plan;
          if (sql.includes("p.provider='runpod_gpu'")) return null;
          throw new Error(`unexpected read: ${sql}`);
        },
        async run() {
          if (sql.includes("UPDATE gateway_delegated_plans")) {
            providerObservationWrites++;
            return { meta: { changes: 1 } };
          }
          throw new Error(`unexpected write: ${sql}`);
        },
      };
    },
  });
  const originalFetch = globalThis.fetch;
  let delegatedBody;
  globalThis.fetch = async (_url, options) => {
    delegatedBody = JSON.parse(options.body);
    const offset = delegatedBody.arguments.offset;
    return Response.json({ schema_version: 2, status: "ok", human_summary: "verified",
      machine_state: { run_id: runId, state: "succeeded", artifact_id: "orbitune-output.zip",
        sha256: reference.sha256, size_bytes: reference.size_bytes, offset,
        next_offset: offset + 3, eof: false, encoding: "base64", data: "YWJj" },
      next_allowed_actions: [], blocking_reason: null });
  };
  try {
    const first = await maybeDelegateRunTool(env, "test-owner", "experiment_artifact", {
      run_id: runId, artifact_id: "orbitune-output.zip", offset: 0, max_bytes: 3,
    });
    assert.equal(first.status, "ok");
    assert.deepEqual(delegatedBody.arguments.external_artifact, reference);
    assert.equal(delegatedBody.arguments.length, 3);
    assert.equal(delegatedBody.arguments.provider_handle.run_id, runId);
    const second = await maybeDelegateRunTool(env, "test-owner", "experiment_artifact", {
      run_id: runId, artifact_id: "orbitune-output.zip", offset: 3, max_bytes: 3,
    });
    assert.equal(second.status, "ok");
    assert.equal(second.machine_state.offset, 3);
    assert.deepEqual(delegatedBody.arguments.external_artifact, reference);
    assert.equal(plan.provider_response_json,
      JSON.stringify({ result: { external_artifacts: [reference] } }));
    assert.equal(providerObservationWrites, 0,
      "artifact chunks must not replace terminal provider evidence or persist bytes");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("scheduled reconciliation advances one active delegated provider run", async () => {
  const runId = "6".repeat(32);
  const plan = {
    id: runId, owner_id: "test-owner", fingerprint: "a".repeat(64),
    workload: "orbitune-kaggle-100-step-v1",
    approved_plan_json: JSON.stringify({ runtime_seconds: 300 }), state: "submitted",
    provider_handle_json: JSON.stringify({ provider: "kaggle", run_id: runId,
      plan_fingerprint: "a".repeat(64), version: 7 }),
    provider_state: "running", provider_response_json: null,
  };
  const env = environment();
  env.PROVIDER_ADAPTER_URL = "https://unjuno--gpu-control-provider-adapter-provider-adapter-api.us-east.modal.run";
  env.PROVIDER_ADAPTER_KEY_ID = "sites-v1";
  env.PROVIDER_ADAPTER_HMAC_KEY_B64 = Buffer.alloc(32, 7).toString("base64");
  env.PROVIDER_ADAPTER_PROXY_TOKEN_ID = "wk-adaptertest123";
  env.PROVIDER_ADAPTER_PROXY_TOKEN_SECRET = "ws-adaptertestsecret123";
  env.DB.prepare = (sql) => ({
    bind(...values) {
      return {
        async first() {
          if (sql.includes("workload=? AND state='submitted'")) return null;
          if (sql.includes("WHERE owner_id=? AND state='submitted'")) {
            assert.deepEqual(values, ["test-owner", "orbitune-kaggle-100-step-v1",
              "orbitune-zero-gpu-eval-v1", "modal-gpu-vector-add-v1"]);
          }
          if (sql.includes("FROM gateway_delegated_plans")) return plan;
          if (sql.includes("LEFT JOIN provider_account_leases")) {
            assert.deepEqual(values, ["test-owner"]);
            return null;
          }
          if (sql.includes("p.provider='runpod_gpu'")) return null;
          throw new Error(`unexpected first query: ${sql}`);
        },
        async run() {
          if (sql.includes("UPDATE gateway_delegated_plans")) return { meta: { changes: 1 } };
          throw new Error(`unexpected write: ${sql}`);
        },
      };
    },
  });
  const originalFetch = globalThis.fetch;
  let request;
  globalThis.fetch = async (_url, options) => {
    request = JSON.parse(options.body);
    return new Response(JSON.stringify({ schema_version: 2, status: "pending",
      human_summary: "Provider remains active.", next_allowed_actions: ["experiment_status"],
      blocking_reason: null, machine_state: { run_id: runId, state: "running",
        provider: "kaggle", provider_handle: request.arguments.provider_handle } }),
    { status: 200, headers: { "content-type": "application/json" } });
  };
  try {
    const response = await toolCall(env, "test-owner", "experiment_reconcile", {});
    assert.equal(response.status, 200, await response.clone().text());
    const body = await response.json();
    assert.ok(body.result, JSON.stringify(body));
    const value = JSON.parse(body.result.content[0].text);
    assert.equal(value.status, "pending", JSON.stringify(value));
    assert.match(value.human_summary, /Scheduled provider reconciliation completed/);
    assert.equal(request.tool, "experiment_status");
    assert.equal(request.arguments.run_id, runId);
    assert.equal(request.arguments.runtime_seconds, 300);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("provider adapter submit retries reuse one owner-bound ChatGPT authorization", async () => {
  const plans = new Map();
  const authorizations = new Map();
  const freePolicyAuthorizations = new Map();
  const delegatedBodies = [];
  const runId = "9".repeat(32);
  const gatewayPlan = {
    schema_version: 2, workload: "orbitune-kaggle-100-step-v1", provider: "kaggle",
    repository: "Unjuno/orbitune", source_sha: "44a1b806160ab5bc721a370d034a6dfcb28f27a8",
    parameters: {}, runtime_seconds: 300, max_cost_usd: "0", known_cost_usd: "0",
    cost_classification: "FREE_QUOTA", paid_fallback_allowed: false,
  };
  const fingerprint = createHash("sha256").update(canonicalJson(gatewayPlan)).digest("hex");
  const env = environment();
  env.PROVIDER_ADAPTER_URL = "https://unjuno--gpu-control-provider-adapter-provider-adapter-api.us-east.modal.run";
  env.PROVIDER_ADAPTER_KEY_ID = "sites-v1";
  env.PROVIDER_ADAPTER_HMAC_KEY_B64 = Buffer.alloc(32, 7).toString("base64");
  env.PROVIDER_ADAPTER_PROXY_TOKEN_ID = "wk-adaptertest123";
  env.PROVIDER_ADAPTER_PROXY_TOKEN_SECRET = "ws-adaptertestsecret123";
  env.DB.prepare = (sql) => ({
    bind(...values) {
      return {
        async run() {
          if (sql.includes("INSERT OR IGNORE INTO gateway_delegated_plans")) {
            const [id, owner, idempotencyKey, storedFingerprint, workload, approvedPlanJson, createdAt, expiresAt] = values;
            if (![...plans.values()].some((row) => row.owner_id === owner && row.idempotency_key === idempotencyKey)) {
              plans.set(`${owner}:${id}`, { id, owner_id: owner, idempotency_key: idempotencyKey,
                fingerprint: storedFingerprint, workload, approved_plan_json: approvedPlanJson,
                state: "prepared", created_at: createdAt, expires_at: expiresAt });
            }
            return { meta: { changes: 1 } };
          }
          if (sql.includes("INSERT OR IGNORE INTO gateway_delegated_authorizations")) {
            const [authorizationId, authorizedAt, expiresAt, consumedAt, owner, id, storedFingerprint] = values;
            const key = `${owner}:${id}`;
            if (!authorizations.has(key)) authorizations.set(key, { authorization_id: authorizationId,
              authorization_source: "chatgpt_mcp_write_confirmation", authorized_at: authorizedAt,
              expires_at: expiresAt, consumed_at: consumedAt, fingerprint: storedFingerprint });
            return { meta: { changes: 1 } };
          }
          if (sql.includes("INSERT OR IGNORE INTO provider_free_run_authorizations")) {
            const [id, storedFingerprint, createdAt, provider] = values;
            if (!freePolicyAuthorizations.has(id)) freePolicyAuthorizations.set(id, {
              provider, plan_fingerprint: storedFingerprint, authorized_microusd: 0, created_at: createdAt,
            });
            return { meta: { changes: 1 } };
          }
          if (sql.includes("SET provider_handle_json=COALESCE")) {
            const [handleJson, providerState, responseJson, updatedAt, owner, id] = values;
            Object.assign(plans.get(`${owner}:${id}`), {
              provider_handle_json: handleJson,
              provider_state: providerState,
              provider_response_json: responseJson,
              updated_at: updatedAt,
            });
            return { meta: { changes: 1 } };
          }
          throw new Error(`unexpected run query: ${sql}`);
        },
        async first() {
          if (sql.includes("UPDATE gateway_delegated_plans") && sql.includes("RETURNING id")) {
            const [attemptAt, updatedAt, owner, id] = values;
            const row = plans.get(`${owner}:${id}`);
            if (!row || row.state !== "prepared" || row.cancelled_at) return null;
            row.state = "submitted";
            row.submit_attempted_at = attemptAt;
            row.updated_at = updatedAt;
            return { id };
          }
          if (sql.includes("gateway_delegated_plans") && sql.includes("idempotency_key=?")) {
            const [owner, idempotencyKey] = values;
            return [...plans.values()].find((row) => row.owner_id === owner && row.idempotency_key === idempotencyKey) || null;
          }
          if (sql.includes("gateway_delegated_plans")) return plans.get(`${values[0]}:${values[1]}`) || null;
          if (sql.includes("gateway_delegated_authorizations")) return authorizations.get(`${values[0]}:${values[1]}`) || null;
          if (sql.includes("provider_free_run_authorizations")) return freePolicyAuthorizations.get(values[0]) || null;
          return null;
        },
        async all() {
          if (sql.includes("FROM gateway_delegated_plans")) {
            const owner = values[0];
            return { results: [...plans.values()].filter((row) => row.owner_id === owner).map((row) => ({
              run_id: row.id, plan_state: row.state, provider_state: row.provider_state,
              created_at: row.created_at, updated_at: row.updated_at || row.created_at,
              workload: row.workload, approved_plan_json: row.approved_plan_json,
            })) };
          }
          return { results: [] };
        },
      };
    },
  });
  const originalFetch = globalThis.fetch;
  let submitCalls = 0;
  globalThis.fetch = async (_url, options) => {
    const body = JSON.parse(options.body);
    delegatedBodies.push(body);
    if (body.tool === "experiment_prepare") return new Response(JSON.stringify({ schema_version: 2, status: "ok",
      human_summary: "Prepared registered Kaggle workload.", next_allowed_actions: ["experiment_submit"], blocking_reason: null,
      machine_state: { run_id: runId, plan_fingerprint: fingerprint }, approved_plan: gatewayPlan }),
    { status: 200, headers: { "content-type": "application/json" } });
    if (body.tool === "experiment_list") return new Response(JSON.stringify({ schema_version: 2, status: "ok",
      human_summary: "Listed.", machine_state: { count: 1 }, next_allowed_actions: [], blocking_reason: null,
      experiments: [{ run_id: runId, state: "queued", provider: "kaggle" }] }),
    { status: 200, headers: { "content-type": "application/json" } });
    if (body.tool === "experiment_status") return new Response(JSON.stringify({ schema_version: 2, status: "blocked",
      human_summary: "Stalled.", next_allowed_actions: ["experiment_status"],
      blocking_reason: "PROVIDER_DEADLINE_EXCEEDED_CLEANUP_UNCONFIRMED",
      machine_state: { run_id: runId, state: "running", provider: "kaggle",
        provider_handle: body.arguments.provider_handle } }),
    { status: 200, headers: { "content-type": "application/json" } });
    submitCalls++;
    if (submitCalls === 1) throw new TypeError("lost response");
    return new Response(JSON.stringify({ schema_version: 2, status: "pending", human_summary: "Queued.",
      next_allowed_actions: ["experiment_status"], blocking_reason: null,
      machine_state: { run_id: runId, state: "queued",
        provider_handle: { provider: "kaggle", run_id: runId, version: 7 } } }),
    { status: 200, headers: { "content-type": "application/json" } });
  };
  try {
    const prepareArgs = { workload: "orbitune-kaggle-100-step-v1", repository: "Unjuno/orbitune",
      commit: "44a1b806160ab5bc721a370d034a6dfcb28f27a8", parameters: {}, runtime_seconds: 300,
      max_cost_usd: "0.00", idempotency_key: "kaggle-retry-001" };
    const prepared = await toolCall(env, "test-owner", "experiment_prepare", prepareArgs);
    const preparedValue = JSON.parse((await prepared.json()).result.content[0].text);
    assert.equal(preparedValue.provider_approved_plan.workload, "orbitune-kaggle-100-step-v1");
    assert.equal(preparedValue.authorization_validity_seconds, 600);
    const storedPlan = plans.get(`test-owner:${runId}`);
    assert.equal(storedPlan.expires_at - storedPlan.created_at, 600);
    const delegatedPrepare = delegatedBodies.find((body) => body.tool === "experiment_prepare");
    assert.equal(delegatedPrepare.arguments.max_cost_usd, "0");
    const submit = { run_id: runId, plan_fingerprint: fingerprint, provider_approved_plan: gatewayPlan };
    const lost = await toolCall(env, "test-owner", "experiment_submit", submit);
    assert.equal(JSON.parse((await lost.json()).result.content[0].text).error, "GATEWAY_DELEGATION_FAILED");
    assert.equal(plans.get(`test-owner:${runId}`).state, "submitted",
      "the durable local submit claim is written before the adapter call");
    const recoveredStatus = await toolCall(env, "test-owner", "experiment_status", { run_id: runId });
    const recoveredStatusValue = JSON.parse((await recoveredStatus.json()).result.content[0].text);
    assert.equal(recoveredStatusValue.machine_state.state, "running");
    assert.equal(delegatedBodies.at(-1).tool, "experiment_status");
    assert.equal(delegatedBodies.at(-1).arguments.provider_handle.transport, "modal_spawn_v1");
    const retried = await toolCall(env, "test-owner", "experiment_submit", submit);
    const retriedValue = JSON.parse((await retried.json()).result.content[0].text);
    assert.equal(retriedValue.machine_state.state, "queued");
    assert.equal(retriedValue.machine_state.provider_handle, undefined);
    assert.equal(plans.get(`test-owner:${runId}`).provider_handle_json,
      canonicalJson({ provider: "kaggle", run_id: runId, version: 7 }));
    const submits = delegatedBodies.filter((body) => body.tool === "experiment_submit");
    assert.equal(submits.length, 2);
    assert.equal(submits[0].arguments.authorization.authorization_id,
      submits[1].arguments.authorization.authorization_id);
    assert.equal(authorizations.size, 1);
    assert.equal(freePolicyAuthorizations.size, 1);
    assert.equal(freePolicyAuthorizations.get(runId).authorized_microusd, 0);
    const status = await toolCall(env, "test-owner", "experiment_status", { run_id: runId });
    const statusValue = JSON.parse((await status.json()).result.content[0].text);
    assert.equal(statusValue.blocking_reason, "PROVIDER_DEADLINE_EXCEEDED_CLEANUP_UNCONFIRMED");
    const delegatedStatus = delegatedBodies.find((body) => body.tool === "experiment_status");
    assert.equal(delegatedStatus.arguments.runtime_seconds, 300);
    const listed = await toolCall(env, "test-owner", "experiment_list", {});
    const listedValue = JSON.parse((await listed.json()).result.content[0].text);
    assert.equal(listedValue.error, undefined, JSON.stringify(listedValue));
    assert.equal(listedValue.machine_state.provider_adapter.configured, true);
    assert.equal(listedValue.machine_state.experiments[0].run_id, runId);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
