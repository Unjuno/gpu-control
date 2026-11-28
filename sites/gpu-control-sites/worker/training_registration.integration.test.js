import assert from "node:assert/strict";
import { createHash, generateKeyPairSync, randomBytes } from "node:crypto";
import { readFileSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";
import test from "node:test";
import worker from "./index.js";
import { submitTrainingPlan } from "./training_submit.js";
import { persistTrainingTerminalResult } from "./training_plan_state.js";
import { claimTrainingDispatch } from "./training_dispatch_claim.js";
import { confirmTrainingChallenge, issueTrainingChallenge } from "./training_authorization.js";
import { getOwnedTrainingSource } from "./training_source.js";
import { trainingRuntimeProfileFingerprint } from "./training_contract.js";
import { canonicalJson } from "./canonical_json.js";
import { beginGithubInstallationOAuth, completeGithubInstallationOAuth, createGithubInstallationUrl } from "./github_app_connection.js";

const imageDigest = `sha256:${"a".repeat(64)}`;
const sourceSha = "b".repeat(40);
const siteOrigin = "https://gpu-control-sites.unjuno.chatgpt.site";

function environment() {
  return {
    CPU_WORKLOAD_ADMISSION_ENABLED: "false",
    GPU_CONTROL_ALLOWED_USER_IDS: "test-owner,other-owner",
    CPU_WORKLOAD_REPOSITORY: "Unjuno/gpu-control",
    CPU_WORKLOAD_SOURCE_SHA: sourceSha,
    CPU_WORKLOAD_IMAGE_DIGEST: imageDigest,
  };
}

function modalAccountEvidence({ gpu, usageLimitUsd, hourlyPriceUsd, creditsUsedUsd = "0.15",
  chargesUsd = "0.00", verifiedAt = Math.floor(Date.now() / 1000), expiresAt = verifiedAt + 1800 }) {
  const body = { schema_version: 1, workspace: "unjuno", environment: "main",
    usage_limit_usd: usageLimitUsd, credits_used_usd: creditsUsedUsd, charges_usd: chargesUsd,
    gpu, hourly_price_usd: hourlyPriceUsd, price_source: "https://modal.com/pricing",
    verified_at: verifiedAt, expires_at: expiresAt };
  return { ...body, evidence_id: createHash("sha256").update(canonicalJson(body)).digest("hex") };
}

async function toolCall(env, user, name, args) {
  return worker.fetch(new Request("https://site.invalid/mcp", {
    method: "POST",
    headers: { "content-type": "application/json", "oai-authenticated-user-id": user },
    body: JSON.stringify({ jsonrpc: "2.0", id: 99, method: "tools/call", params: { name, arguments: args } }),
  }), env);
}

test("training registration is authenticated, owner-scoped, and repeatable", async () => {
  const db = new DatabaseSync(":memory:");
  try {
    db.exec(readFileSync(new URL("../drizzle/0022_training_registrations.sql", import.meta.url), "utf8"));
    db.exec(readFileSync(new URL("../drizzle/0023_training_plans.sql", import.meta.url), "utf8"));
    db.exec(readFileSync(new URL("../drizzle/0024_training_plan_cancellation.sql", import.meta.url), "utf8"));
    db.exec(readFileSync(new URL("../drizzle/0025_training_submission_claim.sql", import.meta.url), "utf8"));
    db.exec(readFileSync(new URL("../drizzle/0026_training_authorizations.sql", import.meta.url), "utf8"));
    db.exec(readFileSync(new URL("../drizzle/0027_training_dispatch_rejection.sql", import.meta.url), "utf8"));
    db.exec(readFileSync(new URL("../drizzle/0028_training_execution_specs.sql", import.meta.url), "utf8"));
    db.exec(readFileSync(new URL("../drizzle/0029_training_authorization_evidence.sql", import.meta.url), "utf8"));
    db.exec(readFileSync(new URL("../drizzle/0030_github_app_connections.sql", import.meta.url), "utf8"));
    db.exec(readFileSync(new URL("../drizzle/0033_github_installation_user_authorization.sql", import.meta.url), "utf8"));
    db.exec(readFileSync(new URL("../drizzle/0035_github_owner_identity.sql", import.meta.url), "utf8"));
    db.exec(readFileSync(new URL("../drizzle/0041_github_user_repository_scope.sql", import.meta.url), "utf8"));
    db.exec(readFileSync(new URL("../drizzle/0042_github_live_user_authorization.sql", import.meta.url), "utf8"));
    db.exec(readFileSync(new URL("../drizzle/0031_training_cleanup_confirmation.sql", import.meta.url), "utf8"));
    db.exec(readFileSync(new URL("../drizzle/0040_training_terminal_result.sql", import.meta.url), "utf8"));
    db.exec(`CREATE TABLE provider_budget_policies (
      provider TEXT PRIMARY KEY, monthly_limit_microusd INTEGER, per_run_limit_microusd INTEGER NOT NULL);
      INSERT INTO provider_budget_policies VALUES ('runpod_gpu', NULL, 1000000);
      CREATE TABLE provider_free_policies (
        provider TEXT PRIMARY KEY, max_cost_microusd INTEGER NOT NULL, paid_fallback_allowed INTEGER NOT NULL);
      INSERT INTO provider_free_policies VALUES ('kaggle', 0, 0), ('huggingface_space', 0, 0);
      CREATE TABLE modal_compute_budget_policy (
        scope TEXT PRIMARY KEY, monthly_limit_microusd INTEGER NOT NULL,
        per_run_limit_microusd INTEGER NOT NULL, updated_at INTEGER NOT NULL);
      INSERT INTO modal_compute_budget_policy VALUES ('workspace', 30000000, 1000000, 0);
      CREATE TABLE modal_compute_budget_reservations (
        run_id TEXT PRIMARY KEY, source TEXT NOT NULL, plan_fingerprint TEXT NOT NULL,
        period_key TEXT NOT NULL, reserved_microusd INTEGER NOT NULL, created_at INTEGER NOT NULL);
      CREATE TABLE modal_gpu_admission_policy (
        scope TEXT PRIMARY KEY, admission_enabled INTEGER NOT NULL, updated_at INTEGER NOT NULL);
      INSERT INTO modal_gpu_admission_policy VALUES ('workspace', 1, 0);`);
    const env = { ...environment(), GPU_CONTROL_ALLOWED_USER_IDS: "test-owner,other-owner",
      MAP_TRAINING_CONTROL_PLANE_SHA: "e".repeat(40), MAP_TRAINING_MONTHLY_MICROUSD: "1000000", DB: {
      prepare(sql) {
        const statement = db.prepare(sql);
        return { sql, first: async () => statement.get(), all: async () => ({ results: statement.all() }),
          bind: (...args) => ({ sql, values: args,
          run: async () => statement.run(...args),
          first: async () => statement.get(...args),
          all: async () => ({ results: statement.all(...args) }),
        }) };
      },
      async batch(statements) {
        db.exec("BEGIN");
        try {
          const results = statements.map(({ sql, values }) => {
            const statement = db.prepare(sql);
            if (sql.includes("RETURNING")) {
              const rows = statement.all(...values);
              return { results: rows, meta: { changes: rows.length } };
            }
            const result = statement.run(...values);
            return { results: [], meta: { changes: Number(result.changes) } };
          });
          db.exec("COMMIT");
          return results;
        } catch (error) {
          db.exec("ROLLBACK");
          throw error;
        }
      },
    } };
    const call = async (owner, name, args) => {
      const response = await toolCall(env, owner, name, args);
      return JSON.parse((await response.json()).result.content[0].text);
    };
    const args = { repository: "Unjuno/model-as-a-paper", commit: sourceSha };
    assert.equal((await toolCall(env, "", "training_register", args)).status, 401);
    assert.equal((await toolCall(env, "unauthorized", "training_register", args)).status, 403);
    assert.equal((await call("test-owner", "training_register", { ...args, repository: "https://example.com/a/b" })).error, "TRAINING_SOURCE_INVALID");
    const first = await call("test-owner", "training_register", args);
    assert.equal(first.machine_state.state, "registered");
    assert.equal(first.machine_state.executable, undefined);
    const configured = { ...args, dataset: "papers", run_name: "map44m-first", steps: 100 };
    const spec = await call("test-owner", "training_register", configured);
    const specRetry = await call("test-owner", "training_register", configured);
    const anotherSpec = await call("test-owner", "training_register", { ...args, steps: 50 });
    assert.equal(spec.machine_state.execution_spec_id, specRetry.machine_state.execution_spec_id);
    assert.notEqual(spec.machine_state.execution_spec_id, anotherSpec.machine_state.execution_spec_id);
    const ownSpecs = (await call("test-owner", "training_list", {})).machine_state.execution_specs;
    assert.deepEqual({
      dataset: ownSpecs.find(item => item.execution_spec_id === spec.machine_state.execution_spec_id).dataset,
      run_name: ownSpecs.find(item => item.execution_spec_id === spec.machine_state.execution_spec_id).run_name,
      steps: ownSpecs.find(item => item.execution_spec_id === spec.machine_state.execution_spec_id).steps,
    }, { dataset: "papers", run_name: "map44m-first", steps: 100 });
    assert.deepEqual((await call("other-owner", "training_list", {})).machine_state.execution_specs, []);
    assert.equal((await call("test-owner", "training_register", { ...args, dataset: "../papers" })).error, "INVALID_ARGUMENTS");
    assert.equal((await call("test-owner", "training_register", { ...args, command: ["python", "train.py"] })).error, "INVALID_ARGUMENTS");
    const unsupportedConfig = await call("test-owner", "training_register", {
      repository: "some-owner/some-repo", commit: "e".repeat(40), steps: 10,
    });
    assert.equal(unsupportedConfig.blocking_reason, "TRAINING_PROFILE_UNAVAILABLE");
    const retry = await call("test-owner", "training_register", { ...args, repository: "https://github.com/unjuno/model-as-a-paper" });
    assert.equal(retry.machine_state.registration_id, first.machine_state.registration_id);
    env.GPU_CONTROL_ALLOWED_USER_IDS += ",selected-owner";
    const appKeys = generateKeyPairSync("rsa", { modulusLength: 2048 });
    env.GITHUB_APP_ID = "12345";
    env.GITHUB_APP_SLUG = "gpu-control-source";
    env.GITHUB_APP_PRIVATE_KEY = appKeys.privateKey.export({ type: "pkcs8", format: "pem" });
    env.GITHUB_APP_CLIENT_ID = "Iv1.client-id";
    env.GITHUB_APP_CLIENT_SECRET = "github-app-client-secret-for-tests";
    env.GITHUB_APP_OAUTH_CALLBACK_URL = "https://gpu-control-sites.unjuno.chatgpt.site/github/oauth/callback";
    env.GITHUB_APP_TOKEN_ENCRYPTION_KEY = randomBytes(32).toString("base64url");
    const setup = await createGithubInstallationUrl(env.DB, "selected-owner", env.GITHUB_APP_SLUG, 2_000_000_000);
    const setupState = new URL(setup.authorization_url).searchParams.get("state");
    const auth = await beginGithubInstallationOAuth(env.DB, setupState, "98765", {
      id: "98765", account: { login: "sample-owner" }, repository_selection: "selected", suspended_at: null,
      permissions: { contents: "read", metadata: "read" },
    }, env, 2_000_000_001);
    const authState = new URL(auth.authorization_url).searchParams.get("state");
    await completeGithubInstallationOAuth(env, env.DB, authState, {
      access_token: "ghu_aaaaaaaaaaaaaaaaaaaa", refresh_token: "ghr_bbbbbbbbbbbbbbbbbbbb",
      access_expires_in: 28_800, refresh_expires_in: 15_897_600,
    }, async (url) => String(url).endsWith("/user")
      ? new Response(JSON.stringify({ id: 567890, login: "sample-owner" }), { status: 200 })
      : new Response(JSON.stringify({ total_count: 1, repositories: [
        { id: 123, full_name: "sample-owner/sample-model" },
      ] }), { status: 200 }), 2_000_000_002);
    const ownerCapabilities = await call("selected-owner", "experiment_capabilities", {});
    assert.equal(ownerCapabilities.machine_state.owner_selected_training.github_app_configured, true);
    assert.equal(ownerCapabilities.machine_state.owner_selected_training.github_connected, true);
    assert.equal(ownerCapabilities.machine_state.owner_selected_training.blocker, "PROVIDER_ADAPTER_NOT_CONFIGURED");
    assert.deepEqual(ownerCapabilities.machine_state.owner_selected_training.next_actions,
      ["github_repositories", "training_register", "training_preview", "training_list"]);
    const originalFetch = globalThis.fetch;
    const requests = [];
    let installedRepo = "sample-owner/sample-model";
    let lockUnavailable = false;
    globalThis.fetch = async (url, options) => {
      const parsed = new URL(String(url));
      requests.push({ url: parsed, options });
      if (parsed.pathname === "/user") return new Response(JSON.stringify({ id: 567890, login: "sample-owner" }), { status: 200 });
      if (parsed.pathname === "/user/installations/98765/repositories") return new Response(JSON.stringify({
        total_count: 1, repositories: [{ id: 123, full_name: "sample-owner/sample-model" }],
      }), { status: 200 });
      if (parsed.pathname === "/app/installations/98765/access_tokens") {
        const body = options.body ? JSON.parse(options.body) : {};
        if (body.repositories) return new Response(JSON.stringify({ token: "single-repo-token",
          expires_at: new Date(Date.now() + 60 * 60 * 1000).toISOString(),
          permissions: { contents: "read", metadata: "read" },
          repositories: [{ full_name: "sample-owner/sample-model" }] }), { status: 201 });
        return new Response(JSON.stringify({ token: "listing-token",
          expires_at: new Date(Date.now() + 60 * 60 * 1000).toISOString(),
          permissions: { contents: "read", metadata: "read" } }), { status: 201 });
      }
      if (parsed.pathname === "/installation/repositories") return new Response(JSON.stringify({
        total_count: 1, repositories: [{ id: 123, full_name: installedRepo, private: true, default_branch: "main" }],
      }), { status: 200 });
      if (parsed.pathname === "/repos/sample-owner/sample-model") return new Response(JSON.stringify({
        private: true, archived: false, default_branch: "main",
      }), { status: 200 });
      if (parsed.pathname === "/repos/sample-owner/sample-model/commits") return new Response(JSON.stringify([
        { sha: "d".repeat(40) },
      ]), { status: 200 });
      if (parsed.pathname === "/repos/sample-owner/sample-model/contents/.gpu-control/experiment.json") {
        const manifest = Buffer.from(JSON.stringify({ schema_version: 1, task: "train",
          entrypoint: "src/train.py", python_version: "3.12", dependencies_lock: "requirements.lock",
          gpu_profiles: ["T4"], outputs: ["checkpoints", "metrics.json"] }));
        return new Response(JSON.stringify({ type: "file", path: ".gpu-control/experiment.json",
          encoding: "base64", size: manifest.length, content: manifest.toString("base64") }), { status: 200 });
      }
      if (parsed.pathname === "/repos/sample-owner/sample-model/contents/requirements.lock") {
        if (lockUnavailable) return new Response("not found", { status: 404 });
        const lock = Buffer.from(`torch==2.11.0 --hash=sha256:${"a".repeat(64)}\n`);
        return new Response(JSON.stringify({ type: "file", path: "requirements.lock",
          encoding: "base64", size: lock.length, content: lock.toString("base64") }), { status: 200 });
      }
      throw new Error(`unexpected mocked GitHub request ${parsed.pathname}`);
    };
    try {
      const selectedRepo = await call("selected-owner", "training_register",
        { repository: "Sample-Owner/Sample-Model" });
      assert.equal(selectedRepo.machine_state.repository, "sample-owner/sample-model");
      assert.equal(selectedRepo.machine_state.commit, "d".repeat(40));
      assert.equal(selectedRepo.machine_state.state, "registered");
      assert.deepEqual(selectedRepo.next_allowed_actions, ["training_preview"]);
      assert.match(selectedRepo.human_summary, /training_previewで実験契約、GPU、runtime、見積もりをまとめて確認/);
      assert.equal(JSON.stringify(selectedRepo).includes("single-repo-token"), false);
      assert.equal(requests.filter((entry) => entry.url.pathname.endsWith("/access_tokens")).length, 2);
      assert.ok(requests.some((entry) => entry.url.pathname === "/repos/sample-owner/sample-model" &&
        entry.options.headers.authorization === "Bearer single-repo-token"));
      assert.ok(requests.some((entry) => entry.url.pathname === "/installation/repositories" &&
        entry.options.headers.authorization === "Bearer listing-token"));
      const inspection = await call("selected-owner", "training_inspect",
        { registration_id: selectedRepo.machine_state.registration_id });
      assert.equal(inspection.blocking_reason, "CUSTOM_TRAINING_RUNTIME_NOT_CONNECTED");
      assert.equal(inspection.machine_state.manifest.entrypoint, "src/train.py");
      assert.match(inspection.human_summary, /training_preview/);
      assert.match(inspection.human_summary, /hash-locked依存を検証/);
      assert.deepEqual(inspection.next_allowed_actions, ["training_preview", "training_list"]);
      assert.equal(JSON.stringify(inspection).includes("single-repo-token"), false);
      assert.ok(requests.some((entry) => entry.url.pathname.endsWith("/contents/.gpu-control/experiment.json") &&
        entry.options.headers.authorization === "Bearer single-repo-token"));
      lockUnavailable = true;
      const missingLock = await call("selected-owner", "training_inspect",
        { registration_id: selectedRepo.machine_state.registration_id });
      assert.equal(missingLock.blocking_reason, "TRAINING_MANIFEST_OR_LOCK_INVALID");
      assert.equal(missingLock.machine_state.dependency_lock.state, "unavailable");
      assert.match(missingLock.human_summary, /依存lockは見つからないか取得・検証できませんでした/);
      assert.doesNotMatch(missingLock.human_summary, /hash-locked依存を検証しました/);
      lockUnavailable = false;
      installedRepo = "sample-owner/sample-model";
      env.OWNER_TRAINING_RUNTIME_IMAGE_ID = "im-Abcdefgh1234";
      env.OWNER_TRAINING_HOURLY_MICROUSD = "100000";
      env.OWNER_TRAINING_STAGING_HOURLY_MICROUSD = "100000";
      env.OWNER_TRAINING_QUOTE_EXPIRES_AT = String(Math.floor(Date.now() / 1000) + 600);
      env.OWNER_TRAINING_MAX_RUNTIME_SECONDS = "300";
      env.OWNER_TRAINING_MONTHLY_MICROUSD = "30000000";
      env.OWNER_TRAINING_MAX_COST_MICROUSD = "1000000";
      env.MAP_TRAINING_CONTROL_PLANE_SHA = sourceSha;
      env.OWNER_TRAINING_ADMISSION_ENABLED = "true";
      const readyInspection = await call("selected-owner", "training_inspect",
        { registration_id: selectedRepo.machine_state.registration_id });
      assert.equal(readyInspection.status, "ok");
      assert.equal(readyInspection.blocking_reason, null);
      const customPreview = await call("selected-owner", "training_preview",
        { registration_id: selectedRepo.machine_state.registration_id });
      assert.equal(customPreview.status, "ok", JSON.stringify(customPreview));
      const customPlan = await call("selected-owner", "training_prepare",
        { registration_id: selectedRepo.machine_state.registration_id });
      assert.equal(customPlan.status, "ok");
      assert.equal(customPlan.approved_plan.execution_kind, "owner_selected_python");
      assert.equal(customPlan.machine_state.executable, false);
      assert.ok(!customPlan.next_allowed_actions.includes("training_submit"));
      const adapterProfileFingerprint = await trainingRuntimeProfileFingerprint({
        image_id: env.OWNER_TRAINING_RUNTIME_IMAGE_ID,
        hourly_microusd: Number(env.OWNER_TRAINING_HOURLY_MICROUSD),
        staging_hourly_microusd: Number(env.OWNER_TRAINING_STAGING_HOURLY_MICROUSD),
        quote_expires_at: Number(env.OWNER_TRAINING_QUOTE_EXPIRES_AT),
        max_runtime_seconds: Number(env.OWNER_TRAINING_MAX_RUNTIME_SECONDS),
        max_cost_microusd: Number(env.OWNER_TRAINING_MAX_COST_MICROUSD),
        monthly_microusd: Number(env.OWNER_TRAINING_MONTHLY_MICROUSD),
        control_plane_sha: env.MAP_TRAINING_CONTROL_PLANE_SHA,
      });
      db.prepare("UPDATE modal_gpu_admission_policy SET admission_enabled=0 WHERE scope='workspace'").run();
      const budgetPolicyBlocked = await submitTrainingPlan(env, "selected-owner", {
        run_id: customPlan.machine_state.run_id,
        plan_fingerprint: customPlan.machine_state.plan_fingerprint,
        approved_plan: customPlan.approved_plan,
      }, async () => { throw new Error("closed D1 budget policy must block before adapter preflight"); },
      () => true, async () => "single-repo-token");
      assert.equal(budgetPolicyBlocked.blocking_reason, "MODAL_GPU_WORKLOAD_ADMISSION_DISABLED");
      assert.equal(db.prepare("SELECT dispatch_claimed_at FROM training_plans WHERE id=?")
        .get(customPlan.machine_state.run_id).dispatch_claimed_at, null);
      assert.equal(db.prepare("SELECT COUNT(*) AS count FROM training_authorizations WHERE plan_id=?")
        .get(customPlan.machine_state.run_id).count, 0);
      db.prepare("UPDATE modal_gpu_admission_policy SET admission_enabled=1 WHERE scope='workspace'").run();
      db.prepare("DELETE FROM modal_gpu_admission_policy WHERE scope='workspace'").run();
      const missingBudgetPolicy = await submitTrainingPlan(env, "selected-owner", {
        run_id: customPlan.machine_state.run_id,
        plan_fingerprint: customPlan.machine_state.plan_fingerprint,
        approved_plan: customPlan.approved_plan,
      }, async () => { throw new Error("missing D1 budget policy must block before adapter preflight"); },
      () => true, async () => "single-repo-token");
      assert.equal(missingBudgetPolicy.blocking_reason, "PROVIDER_BUDGET_POLICY_UNAVAILABLE");
      assert.equal(db.prepare("SELECT dispatch_claimed_at FROM training_plans WHERE id=?")
        .get(customPlan.machine_state.run_id).dispatch_claimed_at, null);
      assert.equal(db.prepare("SELECT COUNT(*) AS count FROM training_authorizations WHERE plan_id=?")
        .get(customPlan.machine_state.run_id).count, 0);
      db.prepare(`INSERT INTO modal_gpu_admission_policy
        (scope, admission_enabled, updated_at) VALUES ('workspace', 1, 0)`).run();
      const preflightBlocked = await submitTrainingPlan(env, "selected-owner", {
        run_id: customPlan.machine_state.run_id,
        plan_fingerprint: customPlan.machine_state.plan_fingerprint,
        approved_plan: customPlan.approved_plan,
      }, async (_env, _owner, tool) => {
        assert.equal(tool, "experiment_capabilities");
        return { machine_state: { owner_selected_training: {
          profile_configured: true, control_plane_configured: true,
          admission_enabled: false, profile_fingerprint: adapterProfileFingerprint,
          blocker: "OWNER_TRAINING_ADMISSION_DISABLED",
        } } };
      }, () => true, async () => "single-repo-token");
      assert.equal(preflightBlocked.blocking_reason, "OWNER_TRAINING_ADMISSION_DISABLED");
      assert.equal(preflightBlocked.machine_state.adapter_readiness_available, true);
      assert.equal(db.prepare("SELECT dispatch_claimed_at FROM training_plans WHERE id=?")
        .get(customPlan.machine_state.run_id).dispatch_claimed_at, null);
      assert.equal(db.prepare("SELECT COUNT(*) AS count FROM training_authorizations WHERE plan_id=?")
        .get(customPlan.machine_state.run_id).count, 0);
      const profileMismatch = await submitTrainingPlan(env, "selected-owner", {
        run_id: customPlan.machine_state.run_id,
        plan_fingerprint: customPlan.machine_state.plan_fingerprint,
        approved_plan: customPlan.approved_plan,
      }, async () => ({ machine_state: { owner_selected_training: {
        profile_configured: true, control_plane_configured: true, admission_enabled: true,
        profile_fingerprint: "0".repeat(64),
      } } }), () => true, async () => "single-repo-token");
      assert.equal(profileMismatch.blocking_reason, "OWNER_TRAINING_ADAPTER_PROFILE_MISMATCH");
      assert.equal(db.prepare("SELECT dispatch_claimed_at FROM training_plans WHERE id=?")
        .get(customPlan.machine_state.run_id).dispatch_claimed_at, null);
      assert.equal(db.prepare("SELECT COUNT(*) AS count FROM training_authorizations WHERE plan_id=?")
        .get(customPlan.machine_state.run_id).count, 0);
      const admissionRace = await submitTrainingPlan(env, "selected-owner", {
        run_id: customPlan.machine_state.run_id,
        plan_fingerprint: customPlan.machine_state.plan_fingerprint,
        approved_plan: customPlan.approved_plan,
      }, async () => {
        db.prepare("UPDATE modal_gpu_admission_policy SET admission_enabled=0 WHERE scope='workspace'").run();
        return { machine_state: { owner_selected_training: {
          profile_configured: true, control_plane_configured: true, admission_enabled: true,
          profile_fingerprint: adapterProfileFingerprint,
        } } };
      }, () => true, async () => "single-repo-token");
      assert.equal(admissionRace.blocking_reason, "TRAINING_DISPATCH_NOT_RESERVED");
      assert.equal(db.prepare("SELECT dispatch_claimed_at FROM training_plans WHERE id=?")
        .get(customPlan.machine_state.run_id).dispatch_claimed_at, null);
      assert.equal(db.prepare("SELECT COUNT(*) AS count FROM training_authorizations WHERE plan_id=? AND consumed_at IS NOT NULL")
        .get(customPlan.machine_state.run_id).count, 0);
      assert.equal(db.prepare("SELECT COUNT(*) AS count FROM modal_compute_budget_reservations WHERE run_id=?")
        .get(customPlan.machine_state.run_id).count, 0,
      "a reservation is removed atomically when GPU admission closes before the claim");
      db.prepare("UPDATE modal_gpu_admission_policy SET admission_enabled=1 WHERE scope='workspace'").run();
      const blockedStatus = await call("selected-owner", "training_status",
        { run_id: customPlan.machine_state.run_id });
      assert.equal(blockedStatus.blocking_reason, "TRAINING_PROVIDER_ADAPTER_NOT_CONFIGURED");
      assert.ok(!blockedStatus.next_allowed_actions.includes("training_submit"));
      await call("selected-owner", "training_cancel", { run_id: customPlan.machine_state.run_id });
      installedRepo = "sample-owner/another-repository";
      assert.equal((await call("selected-owner", "training_register",
        { repository: "sample-owner/not-selected" })).error, "GITHUB_REPOSITORY_NOT_SELECTED");
    } finally { globalThis.fetch = originalFetch; }
    assert.equal((await call("selected-owner", "training_register",
      { repository: "sample-owner/sample-model", command: ["python", "train.py"] })).error, "INVALID_ARGUMENTS");
    assert.deepEqual((await call("other-owner", "training_list", {})).machine_state.registrations, []);
    const own = (await call("test-owner", "training_list", {})).machine_state.registrations;
    assert.equal(own.length, 1);
    assert.equal(own[0].execution_profile_configured, false);
    assert.equal(own[0].state, "registered");
    assert.equal(own[0].can_prepare, false);
    assert.equal(own[0].registration_id, first.machine_state.registration_id);
    const specPreview = { registration_id: first.machine_state.registration_id,
      execution_spec_id: spec.machine_state.execution_spec_id, runtime_seconds: 120, max_cost_microusd: 100000 };
    assert.equal((await call("test-owner", "training_preview",
      { ...specPreview, max_cost_microusd: 250001 })).error, "INVALID_ARGUMENTS");
    const previewSpec = await call("test-owner", "training_preview", specPreview);
    assert.equal(previewSpec.blocking_reason, "TRAINING_PROFILE_UNAVAILABLE");
    assert.equal(previewSpec.machine_state.dataset, "papers");
    assert.equal(previewSpec.machine_state.steps, 100);
    const prepareSpec = await call("test-owner", "training_prepare",
      { ...specPreview, idempotency_key: "map-training-no-profile" });
    assert.equal(prepareSpec.status, "blocked");
    assert.equal(prepareSpec.blocking_reason, "TRAINING_PROFILE_UNAVAILABLE");
    assert.ok(!prepareSpec.next_allowed_actions.includes("training_submit"));
    assert.equal(db.prepare("SELECT COUNT(*) AS count FROM training_plans WHERE owner_id=?")
      .get("test-owner").count, 0);
    env.MAP_TRAINING_SOURCE_SHA = sourceSha;
    env.MAP_TRAINING_IMAGE_DIGEST = imageDigest;
    env.MAP_TRAINING_HOURLY_MICROUSD = "400000";
    env.MAP_TRAINING_QUOTE_EXPIRES_AT = String(Math.floor(Date.now() / 1000) + 600);
    env.MAP_TRAINING_MONTHLY_MICROUSD = "1000000";
    env.MAP_TRAINING_ACCOUNT_EVIDENCE_JSON = JSON.stringify(modalAccountEvidence({
      gpu: "L4", usageLimitUsd: "1.00", hourlyPriceUsd: "0.400000",
    }));
    env.GPU_CONTROL_ALLOWED_USER_IDS += ",minimal-owner";
    const repoOnly = await call("minimal-owner", "training_register", { repository: "https://github.com/Unjuno/model-as-a-paper" });
    assert.equal(repoOnly.machine_state.commit, sourceSha);
    assert.match(repoOnly.machine_state.registration_id, /^[0-9a-f]{32}$/);
    const readyPreview = await call("test-owner", "training_preview", specPreview);
    assert.equal(readyPreview.status, "ok");
    assert.equal(readyPreview.machine_state.image_digest, env.MAP_TRAINING_IMAGE_DIGEST);
    const minimalPreview = await call("minimal-owner", "training_preview", { registration_id: repoOnly.machine_state.registration_id });
    assert.equal(minimalPreview.status, "ok");
    assert.equal(minimalPreview.machine_state.runtime_seconds, 120);
    assert.equal(minimalPreview.machine_state.max_cost_microusd, 250000);
    const minimalPrepare = await call("minimal-owner", "training_prepare", { registration_id: repoOnly.machine_state.registration_id });
    assert.equal(minimalPrepare.status, "ok");
    assert.match(minimalPrepare.machine_state.idempotency_key, /^map-[0-9a-f]{32}$/);
    assert.equal((await call("minimal-owner", "training_cancel", { run_id: minimalPrepare.machine_state.run_id })).machine_state.state, "cancelled");
    const savedPlan = await call("test-owner", "training_prepare",
      { ...specPreview, idempotency_key: "map-prepared-without-admission" });
    assert.equal(savedPlan.status, "ok");
    assert.equal(savedPlan.approved_plan.dataset, "papers");
    assert.equal(savedPlan.approved_plan.run_name, "map44m-first");
    assert.equal(savedPlan.approved_plan.steps, 100);
    assert.equal(savedPlan.machine_state.executable, false);
    assert.ok(!savedPlan.next_allowed_actions.includes("training_submit"));
    assert.equal(savedPlan.machine_state.authorization_state, "unavailable");
    assert.equal(savedPlan.machine_state.authorization_url, undefined);
    const disabledStatus = await call("test-owner", "training_status", { run_id: savedPlan.machine_state.run_id });
    assert.equal(disabledStatus.machine_state.authorization_state, "unavailable");
    assert.equal(disabledStatus.machine_state.authorization_url, undefined);
    env.MAP_TRAINING_ADMISSION_ENABLED = "true";
    const attempted = await call("test-owner", "training_submit", { run_id: savedPlan.machine_state.run_id,
      plan_fingerprint: savedPlan.machine_state.plan_fingerprint, approved_plan: savedPlan.approved_plan });
    assert.equal(attempted.blocking_reason, "TRAINING_ADMISSION_DISABLED");
    delete env.MAP_TRAINING_ADMISSION_ENABLED;
    delete env.MAP_TRAINING_SOURCE_SHA;
    delete env.MAP_TRAINING_IMAGE_DIGEST;
    delete env.MAP_TRAINING_HOURLY_MICROUSD;
    delete env.MAP_TRAINING_QUOTE_EXPIRES_AT;
    assert.equal((await call("other-owner", "training_preview", specPreview)).error,
      "TRAINING_REGISTRATION_NOT_FOUND");
    const otherSource = await call("test-owner", "training_register", { ...args, commit: "f".repeat(40) });
    assert.equal((await call("test-owner", "training_preview",
      { ...specPreview, registration_id: otherSource.machine_state.registration_id })).error,
      "TRAINING_REGISTRATION_NOT_FOUND");
    const registrationId = own[0].registration_id;
    assert.deepEqual({ ...await getOwnedTrainingSource(env.DB, "test-owner", registrationId) }, {
      registration_id: registrationId, repository: "unjuno/model-as-a-paper", commit: sourceSha,
    });
    await assert.rejects(getOwnedTrainingSource(env.DB, "other-owner", registrationId),
      { message: "TRAINING_REGISTRATION_NOT_FOUND" });
    const preview = { registration_id: registrationId, execution_spec_id: spec.machine_state.execution_spec_id,
      runtime_seconds: 120,
      max_cost_microusd: 100000 };
    assert.equal((await call("other-owner", "training_preview", preview)).error,
      "TRAINING_REGISTRATION_NOT_FOUND");
    assert.equal((await call("test-owner", "training_preview", preview)).blocking_reason,
      "TRAINING_PROFILE_UNAVAILABLE");
    env.MAP_TRAINING_SOURCE_SHA = "c".repeat(40);
    env.MAP_TRAINING_IMAGE_DIGEST = imageDigest;
    assert.equal((await call("test-owner", "training_preview", preview)).blocking_reason,
      "TRAINING_PROFILE_UNAVAILABLE");
    env.MAP_TRAINING_SOURCE_SHA = sourceSha;
    assert.equal((await call("test-owner", "training_list", {})).machine_state.registrations.find(item => item.registration_id === registrationId).execution_profile_configured, true);
    const configuredList = await call("test-owner", "training_list", {});
    const configuredRegistration = configuredList.machine_state.registrations.find(item => item.registration_id === registrationId);
    assert.equal(configuredRegistration.state, "registered");
    assert.equal(configuredRegistration.can_prepare, true);
    assert.ok(configuredList.next_allowed_actions.includes("training_preview"));
    assert.equal((await call("test-owner", "training_preview", preview)).blocking_reason,
      "TRAINING_QUOTE_UNAVAILABLE");
    env.MAP_TRAINING_HOURLY_MICROUSD = "400000";
    const quoteNow = Math.floor(Date.now() / 1000);
    env.MAP_TRAINING_QUOTE_EXPIRES_AT = String(quoteNow + 31 * 86400);
    assert.equal((await call("test-owner", "training_preview", preview)).blocking_reason,
      "TRAINING_QUOTE_UNAVAILABLE");
    env.MAP_TRAINING_QUOTE_EXPIRES_AT = String(quoteNow + 7 * 86400);
    assert.equal((await call("test-owner", "training_preview", { ...preview, max_cost_microusd: 1 })).blocking_reason,
      "TRAINING_BUDGET_TOO_LOW");
    const l4Evidence = modalAccountEvidence({ gpu: "L4", usageLimitUsd: "1.00",
      hourlyPriceUsd: "0.400000", verifiedAt: quoteNow, expiresAt: quoteNow + 1800 });
    env.MAP_TRAINING_ACCOUNT_EVIDENCE_JSON = JSON.stringify(l4Evidence);
    const plan = await call("test-owner", "training_preview", preview);
    assert.equal(plan.status, "ok");
    assert.equal(plan.machine_state.image_digest, imageDigest);
    assert.equal(plan.machine_state.provider_evidence.evidence_id, l4Evidence.evidence_id);
    assert.equal(plan.machine_state.workspace_usage_limit_usd, "1.00");
    env.MAP_TRAINING_MONTHLY_MICROUSD = "1000001";
    assert.equal((await call("test-owner", "training_preview", preview)).blocking_reason,
      "TRAINING_BUDGET_EXCEEDS_MODAL_PROVIDER_POLICY");
    env.MAP_TRAINING_MONTHLY_MICROUSD = "1000000";
    env.MAP_TRAINING_MODAL_IMAGE_ID = "invalid";
    assert.equal((await call("test-owner", "training_preview", preview)).blocking_reason,
      "TRAINING_PROFILE_UNAVAILABLE");
    env.MAP_TRAINING_MODAL_IMAGE_ID = "im-Abcdefgh1234";
    assert.equal((await call("test-owner", "training_preview", preview)).machine_state.image_digest,
      env.MAP_TRAINING_MODAL_IMAGE_ID);
    delete env.MAP_TRAINING_MODAL_IMAGE_ID;
    assert.equal(plan.machine_state.gpu, "L4");
    assert.equal(plan.machine_state.estimated_cost_microusd, 88889);
    assert.equal(plan.machine_state.executable, false);
    const bySource = { ...args, runtime_seconds: 120, max_cost_microusd: 100000 };
    assert.equal((await call("test-owner", "training_preview", bySource)).blocking_reason,
      "TRAINING_CONFIGURATION_SELECTION_REQUIRED");
    const prepare = { ...preview, idempotency_key: "training-prepare-retry" };
    const saved = await call("test-owner", "training_prepare", prepare);
    assert.match(saved.machine_state.run_id, /^[0-9a-f]{32}$/);
    assert.equal(saved.approved_plan.execution_kind, "map_training");
    assert.equal(saved.approved_plan.control_plane_sha, env.MAP_TRAINING_CONTROL_PLANE_SHA);
    assert.ok(saved.machine_state.expires_at <= Math.floor(Date.now() / 1000) + 600);
    const run = { run_id: saved.machine_state.run_id };
    assert.equal((await call("other-owner", "training_cancel", run)).error, "RUN_NOT_FOUND");
    assert.equal((await call("test-owner", "training_status", run)).machine_state.state, "prepared");
    assert.equal(saved.machine_state.executable, false);
    assert.deepEqual((await call("test-owner", "training_prepare", prepare)).machine_state, saved.machine_state);
    assert.equal((await call("test-owner", "training_prepare",
      { ...prepare, max_cost_microusd: 200000 })).error, "IDEMPOTENCY_KEY_CONFLICT");
    assert.equal((await call("other-owner", "training_prepare", prepare)).error,
      "TRAINING_REGISTRATION_NOT_FOUND");
    const cancelled = await call("test-owner", "training_cancel", run);
    assert.equal(cancelled.machine_state.state, "cancelled");
    assert.deepEqual(await call("test-owner", "training_cancel", run), cancelled);
    assert.equal((await call("test-owner", "training_prepare", prepare)).machine_state.state, "cancelled");
    const now = Math.floor(Date.now() / 1000);
    await assert.rejects(claimTrainingDispatch(env.DB, "test-owner", run.run_id,
      saved.machine_state.plan_fingerprint, now, 100000, null),
    { message: "TRAINING_AUTHORIZATION_INVALID" });
    await assert.rejects(claimTrainingDispatch(env.DB, "test-owner", run.run_id,
      saved.machine_state.plan_fingerprint, now, 1000001, null),
    { message: "TRAINING_BUDGET_NOT_CONFIGURED" });
    const fresh = (await call("test-owner", "training_prepare",
      { ...prepare, idempotency_key: "training-prepare-fresh" })).machine_state;
    const authorizePlan = async (plan) => {
      const challenge = await issueTrainingChallenge(env.DB, "test-owner", plan.run_id,
        plan.plan_fingerprint, env.MAP_TRAINING_CONTROL_PLANE_SHA, now);
      assert.ok(challenge);
      assert.equal(await confirmTrainingChallenge(env.DB, "test-owner", plan.run_id,
        plan.plan_fingerprint, env.MAP_TRAINING_CONTROL_PLANE_SHA, challenge.token, now), true);
    };
    const authorizationPageUrl = `${siteOrigin}/authorize-training?run_id=${fresh.run_id}&plan_fingerprint=${fresh.plan_fingerprint}`;
    const authorizationPage = await worker.fetch(new Request(authorizationPageUrl, {
      headers: { "oai-authenticated-user-id": "test-owner" },
    }), env);
    assert.equal(authorizationPage.status, 200);
    const authorizationHtml = await authorizationPage.text();
    assert.match(authorizationHtml, /unjuno\/model-as-a-paper/);
    assert.match(authorizationHtml, /Modal \/ L4 × 1/);
    assert.match(authorizationHtml, /<dd>papers<\/dd>/);
    assert.match(authorizationHtml, /<dd>map44m-first<\/dd>/);
    assert.match(authorizationHtml, /<dd>100<\/dd>/);
    const challengeToken = authorizationHtml.match(/name="challenge" value="([0-9a-f]{64})"/)?.[1];
    assert.ok(challengeToken);
    const confirmationResponse = await worker.fetch(new Request(`${siteOrigin}/authorize-training`, {
      method: "POST",
      headers: { "oai-authenticated-user-id": "test-owner", origin: siteOrigin,
        "content-type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ run_id: fresh.run_id, plan_fingerprint: fresh.plan_fingerprint,
        challenge: challengeToken, confirm: "yes" }),
    }), env);
    assert.equal(confirmationResponse.status, 200);
    assert.match(await confirmationResponse.text(), /学習計画を承認しました/);
    const freshAuthorization = db.prepare(`SELECT * FROM training_authorizations WHERE plan_id=?`).get(fresh.run_id);
    const claim = () => claimTrainingDispatch(env.DB, "test-owner", fresh.run_id,
      fresh.plan_fingerprint, now, 100000, freshAuthorization);
    const concurrentClaims = await Promise.all([claim(), claim()]);
    assert.equal(concurrentClaims.filter(Boolean).length, 1);
    assert.equal(await claim(), null);
    const second = (await call("test-owner", "training_prepare",
      { ...prepare, idempotency_key: "training-monthly-limit" })).machine_state;
    await authorizePlan(second);
    const secondAuthorization = db.prepare(`SELECT * FROM training_authorizations WHERE plan_id=?`).get(second.run_id);
    assert.equal(await claimTrainingDispatch(env.DB, "test-owner", second.run_id,
      second.plan_fingerprint, now, 100000, secondAuthorization), null);
    db.prepare("UPDATE training_plans SET cleanup_confirmed_at=? WHERE id=?").run(now, fresh.run_id);
    assert.ok(await claimTrainingDispatch(env.DB, "test-owner", second.run_id,
      second.plan_fingerprint, now, 200000, secondAuthorization));
    db.prepare("UPDATE training_plans SET cleanup_confirmed_at=? WHERE id=?").run(now, second.run_id);
    assert.equal((await call("test-owner", "training_cancel",
      { run_id: fresh.run_id })).error, "GATEWAY_DELEGATION_FAILED");
    assert.equal(db.prepare("SELECT cancelled_at FROM training_plans WHERE id=?")
      .get(fresh.run_id).cancelled_at, null);
    const candidate = await call("test-owner", "training_prepare",
      { ...prepare, idempotency_key: "training-submit-transport" });
    const submission = { run_id: candidate.machine_state.run_id,
      plan_fingerprint: candidate.machine_state.plan_fingerprint, approved_plan: candidate.approved_plan };
    let sends = 0;
    const transport = async (_env, owner, tool, args) => {
      sends++;
      assert.equal(owner, "test-owner");
      assert.equal(tool, "training_submit");
      assert.deepEqual(args.plan, { ...candidate.approved_plan, run_id: submission.run_id });
      assert.equal(args.authorization.owner, owner);
      assert.equal(args.authorization.authorized_by, owner);
      assert.equal(args.authorization.run_id, submission.run_id);
      assert.equal(args.authorization.plan_fingerprint, submission.plan_fingerprint);
      assert.equal(args.authorization.authorization_source, "chatgpt_mcp_write_confirmation");
      assert.equal(Object.hasOwn(args.authorization, "consumed_at"), false);
      assert.deepEqual(Object.keys(args.authorization).sort(), [
        "authorization_id", "authorization_source", "authorization_reference", "decision_record_id",
        "authorized_by", "control_plane_sha", "target_repository", "target_sha", "image_digest",
        "provider", "provider_resource_id", "gpu_count", "runtime_seconds", "max_cost_microusd",
        "authorized_at", "expires_at", "owner", "run_id", "plan_fingerprint",
      ].sort());
      throw new Error("simulated lost response");
    };
    assert.equal((await submitTrainingPlan(env, "test-owner", submission, transport, () => true)).blocking_reason,
      "TRAINING_ADMISSION_DISABLED");
    env.MAP_TRAINING_ADMISSION_ENABLED = "true";
    env.MAP_TRAINING_MONTHLY_MICROUSD = "300000";
    await assert.rejects(submitTrainingPlan(env, "other-owner", submission, transport, () => true),
      { message: "RUN_NOT_FOUND" });
    await assert.rejects(submitTrainingPlan(env, "test-owner",
      { ...submission, approved_plan: { ...submission.approved_plan, runtime_seconds: 121 } },
      transport, () => true), { message: "INVALID_ARGUMENTS" });
    assert.equal((await submitTrainingPlan(env, "test-owner", submission, transport, () => true))
      .blocking_reason, "TRAINING_RUNTIME_MISMATCH");
    assert.equal(sends, 0);
    env.MAP_TRAINING_RUNTIME_SECONDS = "120";
    env.PROVIDER_ADAPTER_URL = "https://unjuno--gpu-control-provider-adapter-provider-adapter-api.us-east.modal.run";
    env.PROVIDER_ADAPTER_HMAC_KEY_B64 = Buffer.alloc(32, 1).toString("base64");
    env.PROVIDER_ADAPTER_KEY_ID = "test-adapter-key";
    env.PROVIDER_ADAPTER_PROXY_TOKEN_ID = "wk-testtoken123";
    env.PROVIDER_ADAPTER_PROXY_TOKEN_SECRET = "ws-testsecret123";
    const readyStatus = await call("test-owner", "training_status", { run_id: submission.run_id });
    assert.ok(readyStatus.next_allowed_actions.includes("training_submit"),
      "an MCP-native exact-plan confirmation is available without a ChatGPT-only browser step");
    assert.equal(readyStatus.machine_state.authorization_state, "required");
    assert.equal(readyStatus.machine_state.authorization_url, undefined);
    env.MAP_TRAINING_ACCOUNT_EVIDENCE_JSON = JSON.stringify(modalAccountEvidence({
      gpu: "L4", usageLimitUsd: "1.00", hourlyPriceUsd: "0.400000",
      creditsUsedUsd: "0.80", verifiedAt: quoteNow, expiresAt: quoteNow + 1800,
    }));
    assert.equal((await submitTrainingPlan(env, "test-owner", submission, transport, () => true))
      .blocking_reason, "MAP_TRAINING_ACCOUNT_EVIDENCE_STALE_OR_MISMATCHED");
    assert.equal(sends, 0);
    env.MAP_TRAINING_ACCOUNT_EVIDENCE_JSON = JSON.stringify(l4Evidence);
    assert.equal((await submitTrainingPlan(env, "test-owner", submission, transport, () => true))
      .machine_state.state, "uncertain");
    const modalReservation = db.prepare(`SELECT source, reserved_microusd FROM modal_compute_budget_reservations WHERE run_id=?`)
      .get(submission.run_id);
    assert.equal(modalReservation.source, "map_training");
    assert.equal(modalReservation.reserved_microusd, 100000,
      "the shared provider ceiling is reserved before dispatch");
    const authorization = db.prepare(`SELECT authorization_source, decision_record_id, authorized_by,
      control_plane_sha, target_repository, target_sha, image_digest, provider, provider_resource_id,
      gpu_count, runtime_seconds, max_cost_microusd, authorized_at, expires_at, consumed_at
      FROM training_authorizations WHERE plan_id=?`).get(submission.run_id);
    assert.equal(authorization.authorization_source, "chatgpt_mcp_write_confirmation");
    assert.equal(authorization.decision_record_id,
      `training-plan:${submission.run_id}:${submission.plan_fingerprint}`);
    assert.equal(authorization.authorized_by, "test-owner");
    assert.equal(authorization.control_plane_sha, env.MAP_TRAINING_CONTROL_PLANE_SHA);
    assert.equal(authorization.target_repository, "unjuno/model-as-a-paper");
    assert.equal(authorization.target_sha, sourceSha);
    assert.equal(authorization.provider, "modal");
    assert.equal(authorization.provider_resource_id, "gpu-control-map-training/train_map");
    assert.equal(authorization.gpu_count, 1);
    assert.equal(authorization.runtime_seconds, 120);
    assert.equal(authorization.max_cost_microusd, 100000);
    assert.ok(Number.isSafeInteger(authorization.consumed_at));
    assert.ok(authorization.consumed_at >= authorization.authorized_at);
    assert.equal((await submitTrainingPlan(env, "test-owner", submission, transport, () => true))
      .machine_state.state, "dispatching");
    assert.equal(sends, 1);
    const history = await call("test-owner", "training_list", {});
    assert.ok(history.machine_state.runs.some(run => run.run_id === submission.run_id));
    assert.equal(history.machine_state.runs.find(run => run.run_id === submission.run_id).state, "dispatching");
    assert.ok(history.machine_state.runs.every(run => Number.isInteger(run.dispatch_claimed_at)));
    assert.deepEqual(history.next_allowed_actions, ["training_preview", "training_status"]);
    assert.deepEqual((await call("other-owner", "training_list", {})).machine_state.runs, []);
    assert.equal(await persistTrainingTerminalResult(env.DB, "test-owner", submission.run_id,
      submission.plan_fingerprint, { state: "succeeded", cleanup: "confirmed", gpu_used: true,
        exit_code: 0, checkpoint: { filename: "checkpoint.pt", size_bytes: 1, sha256: "d".repeat(64) },
        metrics: { filename: "metrics.json", size_bytes: 2, sha256: "e".repeat(64), values: { loss: 0.5 } },
        artifacts: [] }, now), true);
    const recoveredHistory = await call("test-owner", "training_list", {});
    assert.equal(recoveredHistory.machine_state.runs.find(run => run.run_id === submission.run_id).state,
      "succeeded");
    const rejectedPlan = await call("test-owner", "training_prepare",
      { ...prepare, idempotency_key: "training-definite-rejection" });
    await authorizePlan(rejectedPlan.machine_state);
    const rejectedArgs = { run_id: rejectedPlan.machine_state.run_id,
      plan_fingerprint: rejectedPlan.machine_state.plan_fingerprint,
      approved_plan: rejectedPlan.approved_plan };
    env.MAP_TRAINING_MONTHLY_MICROUSD = "400000";
    const rejected = await submitTrainingPlan(env, "test-owner", rejectedArgs,
      async () => ({ state: "blocked", reason: "TRAINING_ADMISSION_DISABLED" }), () => true);
    assert.equal(rejected.blocking_reason, "TRAINING_ADMISSION_DISABLED");
    const rejectedStatus = await call("test-owner", "training_status", { run_id: rejectedArgs.run_id });
    assert.equal(rejectedStatus.machine_state.state, "blocked");
    assert.equal(rejectedStatus.machine_state.reason, "TRAINING_ADMISSION_DISABLED");
    assert.deepEqual(rejectedStatus.next_allowed_actions, []);
    assert.equal((await call("other-owner", "training_status",
      { run_id: submission.run_id })).error, "RUN_NOT_FOUND");
    assert.equal((await call("other-owner", "training_checkpoint",
      { run_id: submission.run_id, offset: 0, max_bytes: 64 })).error, "RUN_NOT_FOUND");
    assert.equal((await call("other-owner", "training_preview", bySource)).error,
      "TRAINING_REGISTRATION_NOT_FOUND");
    assert.equal((await call("test-owner", "training_preview",
      { ...preview, runtime_seconds: 3001 })).error, "INVALID_ARGUMENTS");
    assert.equal((await call("test-owner", "training_preview",
      { ...preview, runtime_seconds: 121 })).error, "INVALID_ARGUMENTS");

  } finally {
    db.close();
  }
});

