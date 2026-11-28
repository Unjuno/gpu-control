import assert from "node:assert/strict";
import test from "node:test";
import { prepareGoogleColabExperiment, validGoogleColabApprovedPlan, validGoogleColabPrepare } from "./google_colab_plan.js";

const commit = "a".repeat(40);
const manifest = { schema_version: 1, task: "train", entrypoint: "train.py", python_version: "3.11",
  dependencies_lock: "requirements.lock", gpu_profiles: ["T4"],
  outputs: ["metrics.json", "checkpoints/final.pt"] };
const manifestBytes = new TextEncoder().encode(JSON.stringify(manifest));
const lockText = `torch==2.1.2 --hash=sha256:${"b".repeat(64)}\n`;

function githubFile(path, bytes) {
  return new Response(JSON.stringify({ type: "file", path, encoding: "base64", size: bytes.byteLength,
    content: btoa(String.fromCharCode(...bytes)) }), { status: 200,
    headers: { "content-type": "application/json" } });
}

function database() {
  const rows = new Map();
  return {
    rows,
    prepare(sql) {
      return {
        bind(...values) {
          return {
            async first() {
              if (sql.startsWith("SELECT id, fingerprint, workload, approved_plan_json")) {
                return rows.get(`${values[0]}:${values[1]}`) || null;
              }
              throw new Error("unexpected query");
            },
            async run() {
              if (sql.includes("INSERT OR IGNORE INTO gateway_delegated_plans")) {
                const [id, owner, key, fingerprint, workload, plan, createdAt, expiresAt, updatedAt] = values;
                rows.set(`${owner}:${key}`, { id, fingerprint, workload, approved_plan_json: plan,
                  state: "prepared", expires_at: expiresAt, created_at: createdAt, updated_at: updatedAt });
                return { meta: { changes: 1 } };
              }
              throw new Error("unexpected query");
            },
          };
        },
      };
    },
  };
}

function setup() {
  const db = database();
  let id = 0;
  const runtimeCapability = { configured: true, connected: true, subscription_tier: "SUBSCRIPTION_TIER_PRO",
    eligible_gpu_specs: [{ accelerator: "T4", shape: "SHAPE_STANDARD", eligible: true }],
    blocking_reason: "COLAB_EXECUTION_LIFECYCLE_NOT_IMPLEMENTED" };
  const fetchImpl = async (url) => {
    const parsed = new URL(url);
    if (parsed.pathname === "/repos/research/map44m") return new Response(JSON.stringify({
      private: false, archived: false, default_branch: "main" }), { status: 200 });
    if (parsed.pathname === "/repos/research/map44m/commits") return new Response(JSON.stringify([{ sha: commit }]), { status: 200 });
    if (parsed.pathname.endsWith(`/git/commits/${commit}`)) return new Response(JSON.stringify({ sha: commit,
      repository: { private: false } }), { status: 200 });
    if (parsed.pathname.endsWith("/.gpu-control/experiment.json")) return githubFile(".gpu-control/experiment.json", manifestBytes);
    if (parsed.pathname.endsWith("/requirements.lock")) return githubFile("requirements.lock", new TextEncoder().encode(lockText));
    throw new Error(`unexpected GitHub URL: ${url}`);
  };
  return { db, fetchImpl, runtimeCapability,
    args: { provider: "google_colab", repository: "Research/Map44m", commit,
      idempotency_key: "map-colab-run-0001" },
    options: { now: 1_800_000_000, fetchImpl,
      getSourceToken: async (repository) => { assert.equal(repository, "research/map44m"); return "scoped-install-token"; },
      readCapabilities: async () => runtimeCapability,
      makeId: () => (++id).toString(16).padStart(32, "0") } };
}

test("Colab prepare is closed by default before resolving source or account state", async () => {
  const state = setup();
  const blocked = await prepareGoogleColabExperiment({ DB: state.db }, "owner-1", state.args, state.options);
  assert.equal(blocked.blocking_reason, "GOOGLE_COLAB_WORKLOAD_ADMISSION_DISABLED");
  assert.equal(blocked.machine_state.runtime_allocated, false);
  assert.equal(state.db.rows.size, 0);
});

test("Colab prepare binds selected public source, manifest, eligible GPU, and unknown quota", async () => {
  const state = setup();
  const result = await prepareGoogleColabExperiment({ DB: state.db, GOOGLE_COLAB_WORKLOAD_ADMISSION_ENABLED: "true" }, "owner-1", state.args, state.options);
  assert.equal(result.status, "ok");
  assert.equal(result.provider_approved_plan.repository, "research/map44m");
  assert.equal(result.provider_approved_plan.source_sha, commit);
  assert.equal(result.provider_approved_plan.runtime_spec.accelerator, "T4");
  assert.equal(result.provider_approved_plan.known_cost_usd, null);
  assert.equal(result.provider_approved_plan.max_cost_usd, null);
  assert.equal(result.provider_approved_plan.network_egress, "unrestricted");
  assert.equal(result.machine_state.runtime_allocated, false);
  assert.equal(validGoogleColabApprovedPlan(result.provider_approved_plan), true);
  assert.equal(state.db.rows.size, 1);
});

test("Colab prepare retries resolve the same owner-bound plan and key conflicts fail", async () => {
  const state = setup();
  const env = { DB: state.db, GOOGLE_COLAB_WORKLOAD_ADMISSION_ENABLED: "true" };
  const first = await prepareGoogleColabExperiment(env, "owner-1", state.args, state.options);
  const retry = await prepareGoogleColabExperiment(env, "owner-1", state.args, state.options);
  assert.equal(retry.machine_state.run_id, first.machine_state.run_id);
  assert.equal(state.db.rows.size, 1);
  const conflict = await prepareGoogleColabExperiment(env, "owner-2", state.args, state.options);
  assert.equal(conflict.machine_state.run_id, "00000000000000000000000000000002");
});

test("Colab prepare rejects private sources, unentitled runtimes, and malformed input", async () => {
  const state = setup();
  state.options.fetchImpl = async (url) => {
    if (new URL(url).pathname.endsWith(`/git/commits/${commit}`)) return new Response(JSON.stringify({ sha: commit,
      repository: { private: true } }), { status: 200 });
    return state.fetchImpl(url);
  };
  const env = { DB: state.db, GOOGLE_COLAB_WORKLOAD_ADMISSION_ENABLED: "true" };
  const privateSource = await prepareGoogleColabExperiment(env, "owner-1", state.args, state.options);
  assert.equal(privateSource.blocking_reason, "GOOGLE_COLAB_PRIVATE_SOURCE_UNSUPPORTED");
  assert.equal(state.db.rows.size, 0);

  const unentitled = setup();
  unentitled.runtimeCapability.subscription_tier = "SUBSCRIPTION_TIER_FREE";
  const noTier = await prepareGoogleColabExperiment({ DB: unentitled.db,
    GOOGLE_COLAB_WORKLOAD_ADMISSION_ENABLED: "true" }, "owner-1", unentitled.args, unentitled.options);
  assert.equal(noTier.blocking_reason, "GOOGLE_COLAB_POSITIVE_COMPUTE_UNITS_REQUIRED");
  assert.equal(unentitled.db.rows.size, 0);

  assert.equal(validGoogleColabPrepare({ provider: "google_colab", repository: "owner/repo",
    accelerator: "A100" }), false);
  assert.equal(validGoogleColabPrepare({ provider: "google_colab", repository: "https://evil.example/owner/repo" }), false);
});
