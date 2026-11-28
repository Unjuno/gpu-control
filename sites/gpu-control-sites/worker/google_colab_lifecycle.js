import { canonicalJson } from "./canonical_json.js";
import { googleColabStructuredResult, callGoogleColabMcpTool } from "./google_colab_mcp_client.js";
import { validGoogleColabApprovedPlan, GOOGLE_COLAB_WORKLOAD } from "./google_colab_plan.js";
import { googleColabAdmissionEnabled } from "./google_colab_policy.js";
import { createGoogleColabOperation, readGoogleColabOperation, transitionGoogleColabOperation } from "./google_colab_operation_store.js";
import { encryptGoogleColabOperationData, decryptGoogleColabOperationData } from "./google_colab_connection.js";
import { buildGoogleColabExecutionCode } from "./google_colab_execution_code.js";
import { parseGoogleColabExecutionReceipt } from "./google_colab_result.js";
import { persistGoogleColabArtifacts } from "./google_colab_artifacts.js";
import { validGoogleColabExecution, validGoogleColabRuntime, validGoogleColabRuntimeDeletion,
  validGoogleColabSession } from "./google_colab_mcp_contract.js";
import { sha256Hex } from "./sha256.js";

const MAX_RESULT_BYTES = 64 * 1024;

function result(status, summary, runId, state, cleanup, actions, blocker = null, details = {}) {
  return { schema_version: 2, status, human_summary: summary,
    machine_state: { run_id: runId, provider: "google_colab", workload: GOOGLE_COLAB_WORKLOAD,
      state, cleanup_state: cleanup, ...details }, next_allowed_actions: actions, blocking_reason: blocker };
}

function missingOperationRecord(runId) {
  return result("pending", "Colabのrun操作記録がありません。provider実行とcleanupの状態を確定できないため、新しいruntimeは作成せず同じrunを不確定状態で保持します。",
    runId, "uncertain", "unknown", ["experiment_status", "experiment_cancel"],
    "GOOGLE_COLAB_OPERATION_RECORD_MISSING",
    { operation_state: "missing", provider_resource_created: "unknown" });
}

async function readPlan(env, owner, runId) {
  return env.DB.prepare(`SELECT id, owner_id, fingerprint, approved_plan_json, state, expires_at,
      cancelled_at, submit_attempted_at, provider_state, provider_response_json
    FROM gateway_delegated_plans WHERE owner_id=? AND id=? AND workload=?`)
    .bind(owner, runId, GOOGLE_COLAB_WORKLOAD).first();
}

function runtimeId(runId) { return `gpu-control-${runId.slice(0, 24)}`; }
function sessionId(runId) { return `gpu-control-${runId.slice(0, 24)}`; }
function validResultJson(value) {
  const serialized = canonicalJson(value);
  if (new TextEncoder().encode(serialized).byteLength > MAX_RESULT_BYTES) throw new Error("GOOGLE_COLAB_RESULT_TOO_LARGE");
  return serialized;
}

async function call(env, owner, name, args, options = {}) {
  return googleColabStructuredResult(await callGoogleColabMcpTool(env, owner, name, args, options));
}

async function finish(env, owner, plan, operation, receipt, artifacts, state, now) {
  const output = { state, repository: plan.repository, source_sha: plan.source_sha,
    runtime_spec: plan.runtime_spec, cost_classification: "QUOTA_UNKNOWN", known_cost_usd: null,
    max_cost_usd: null, compute_units_verified: false, positive_compute_units_verified: false,
    gpu_evidence: receipt?.gpu || null, metrics: receipt?.metrics || null,
    exit_code: receipt?.exit_code ?? null, error_code: receipt?.error_code || null,
    elapsed_seconds: receipt?.elapsed_seconds ?? null, artifacts,
    cleanup_state: "confirmed", runtime_deleted: true,
    network_egress: "unrestricted", private_data_allowed: false,
    provider_credentials_allowed: false };
  const response = result(state === "succeeded" ? "ok" : "error",
    state === "succeeded" ? "Colab GPU実験が完了しました。GPU証拠、成果物checksum、run-owned runtimeの削除を確認しました。"
      : "Colab GPU実験は失敗しました。成果物とruntimeのcleanup状態を記録しました。",
    plan.id, state, "confirmed", state === "succeeded" ? [] : ["experiment_result"],
    state === "succeeded" ? null : (receipt?.error_code || "GOOGLE_COLAB_EXECUTION_FAILED"), output);
  const json = validResultJson(response);
  await env.DB.prepare(`UPDATE gateway_delegated_plans SET provider_state=?, provider_response_json=?, terminal_at=?, updated_at=?
    WHERE owner_id=? AND id=? AND fingerprint=? AND state='submitted'`)
    .bind(state, json, now, now, owner, plan.id, plan.fingerprint).run();
  await transitionGoogleColabOperation(env.DB, { owner, runId: plan.id, fingerprint: plan.fingerprint,
    fromState: "cleanup_pending", toState: "terminal", now,
    patch: { execution_result_json: output } });
  return response;
}

/** Execute one exact confirmed Colab plan; all provider identities are run-owned and persisted. */
export async function submitGoogleColabExperiment(env, owner, args, options = {}) {
  const now = options.now ?? Math.floor(Date.now() / 1000);
  const planRow = await readPlan(env, owner, args.run_id);
  let plan;
  try { plan = JSON.parse(planRow?.approved_plan_json); } catch { plan = null; }
  if (!planRow || !validGoogleColabApprovedPlan(plan) || planRow.fingerprint !== args.plan_fingerprint ||
      planRow.approved_plan_json !== canonicalJson(args.provider_approved_plan) ||
      args.provider_approved_plan?.provider !== "google_colab" || planRow.cancelled_at ||
      planRow.expires_at < now || !["prepared", "submitted"].includes(planRow.state)) {
    return result("blocked", "このColab planは現在のownerに属さないか、期限切れまたはplanが一致しません。",
      args.run_id, "prepared", "not_required", [], "APPROVED_PLAN_MISMATCH_OR_EXPIRED");
  }
  if (planRow.state === "prepared" && !googleColabAdmissionEnabled(env)) return result("blocked",
    "Google Colab実行受付は停止中です。runtimeは作成していません。", args.run_id,
    "prepared", "not_required", [], "GOOGLE_COLAB_WORKLOAD_ADMISSION_DISABLED");
  if (planRow.state === "prepared" && args.positive_compute_units_attested !== true) return result("blocked",
    "Google Colabの正のCompute Unit残高と、上限を確認できない実消費へのowner確認がありません。runtimeは作成していません。",
    args.run_id, "prepared", "not_required", [], "GOOGLE_COLAB_POSITIVE_COMPUTE_UNITS_ATTESTATION_REQUIRED",
    { provider_resource_created: false });
  if (!env.BUCKET || typeof env.BUCKET.put !== "function" || typeof env.BUCKET.get !== "function") return result("blocked",
    "Colab成果物を安全に保存するR2がありません。runtimeは作成していません。", args.run_id,
    "prepared", "not_required", [], "ARTIFACT_STORAGE_NOT_CONFIGURED");
  let operation = await readGoogleColabOperation(env.DB, owner, args.run_id, args.plan_fingerprint);
  if (!operation && (planRow.state !== "prepared" || planRow.submit_attempted_at !== null)) {
    return missingOperationRecord(args.run_id);
  }
  if (!operation) {
    let authorization = await env.DB.prepare(`SELECT authorization_id, expires_at, positive_compute_units_attested FROM gateway_delegated_authorizations
      WHERE owner_id=? AND plan_id=? AND fingerprint=? AND authorization_source='chatgpt_mcp_write_confirmation'`)
      .bind(owner, args.run_id, args.plan_fingerprint).first();
    if (!authorization) {
      const authorizationId = crypto.randomUUID().replaceAll("-", "");
      const expiresAt = Math.min(now + 300, planRow.expires_at);
      await env.DB.prepare(`INSERT OR IGNORE INTO gateway_delegated_authorizations
        (authorization_id, owner_id, plan_id, fingerprint, authorization_source, authorized_at, expires_at, consumed_at,
         positive_compute_units_attested)
        SELECT ?, owner_id, id, fingerprint, 'chatgpt_mcp_write_confirmation', ?, ?, ?, ?
        FROM gateway_delegated_plans WHERE owner_id=? AND id=? AND fingerprint=?
          AND state='prepared' AND cancelled_at IS NULL AND expires_at>=?`)
        .bind(authorizationId, now, expiresAt, now, args.positive_compute_units_attested === true ? 1 : 0,
          owner, args.run_id, args.plan_fingerprint, now).run();
      authorization = await env.DB.prepare(`SELECT authorization_id, expires_at, positive_compute_units_attested FROM gateway_delegated_authorizations
        WHERE owner_id=? AND plan_id=? AND fingerprint=? AND authorization_source='chatgpt_mcp_write_confirmation'`)
        .bind(owner, args.run_id, args.plan_fingerprint).first();
    }
    if (!authorization || authorization.expires_at < now) return result("blocked",
      "ChatGPTのこの正確なplanに対する実行確認がありません。runtimeは作成していません。",
      args.run_id, "prepared", "not_required", [], "HUMAN_AUTHORIZATION_REQUIRED");
    if (authorization.positive_compute_units_attested !== 1) return result("blocked",
      "このColab planの実行確認に、正のCompute Unit残高のowner attestationが記録されていません。runtimeは作成していません。",
      args.run_id, "prepared", "not_required", [], "GOOGLE_COLAB_POSITIVE_COMPUTE_UNITS_ATTESTATION_REQUIRED");
    try {
      operation = await createGoogleColabOperation(env.DB, { owner, runId: args.run_id,
        fingerprint: args.plan_fingerprint, runtimeRequestId: crypto.randomUUID(), now });
    } catch {
      operation = await readGoogleColabOperation(env.DB, owner, args.run_id, args.plan_fingerprint);
      if (!operation) throw new Error("GOOGLE_COLAB_OPERATION_NOT_CREATED");
    }
    const claimed = await env.DB.prepare(`UPDATE gateway_delegated_plans SET state='submitted',
      submit_attempted_at=COALESCE(submit_attempted_at, ?), provider_state='running', updated_at=?
      WHERE owner_id=? AND id=? AND fingerprint=? AND state='prepared' AND cancelled_at IS NULL`).bind(now, now, owner, args.run_id, args.plan_fingerprint).run();
    operation = await readGoogleColabOperation(env.DB, owner, args.run_id, args.plan_fingerprint);
    const latestPlan = await readPlan(env, owner, args.run_id);
    if (!latestPlan || latestPlan.cancelled_at || latestPlan.state !== "submitted") {
      if (operation?.state === "runtime_create_pending") await transitionGoogleColabOperation(env.DB, {
        owner, runId: args.run_id, fingerprint: args.plan_fingerprint,
        fromState: "runtime_create_pending", toState: "terminal", now,
      });
      return result("ok", "Colab planは送信前に取り消されました。runtimeは作成していません。",
        args.run_id, "cancelled", "confirmed", [], null, { provider_resource_created: false });
    }
    if (!operation && claimed?.meta?.changes) throw new Error("GOOGLE_COLAB_OPERATION_NOT_CREATED");
  }
  if (operation.state === "terminal") {
    const prior = await env.DB.prepare(`SELECT provider_response_json FROM gateway_delegated_plans WHERE owner_id=? AND id=?`)
      .bind(owner, args.run_id).first();
    try { return JSON.parse(prior?.provider_response_json); } catch { return result("pending", "Colab runの保存済み結果を読めません。", args.run_id, "uncertain", "unknown", ["experiment_status"], "GOOGLE_COLAB_RESULT_UNAVAILABLE"); }
  }
  return advanceGoogleColabRun(env, owner, planRow, plan, operation, { ...options, now });
}

async function advanceGoogleColabRun(env, owner, planRow, plan, operation, options) {
  const { runId, fingerprint } = { runId: planRow.id, fingerprint: planRow.fingerprint };
  if (operation.runtime_name && operation.runtime_name !== `runtimes/${runtimeId(runId)}`) {
    return result("error", "保存されたColab runtime identityがこのrunの要求値と一致しません。provider操作を停止しました。",
      runId, "uncertain", "unknown", ["experiment_cancel"], "COLAB_RUNTIME_IDENTITY_MISMATCH",
      { operation_state: operation.state, provider_resource_created: true });
  }
  if (operation.session_name && operation.session_name !== `runtimes/${runtimeId(runId)}/sessions/${sessionId(runId)}`) {
    return result("error", "保存されたColab session identityがこのrunの要求値と一致しません。provider操作を停止しました。",
      runId, "uncertain", "unknown", ["experiment_cancel"], "COLAB_SESSION_IDENTITY_MISMATCH",
      { operation_state: operation.state, provider_resource_created: true });
  }
  const fetchImpl = options.fetchImpl || fetch;
  let runtime = null;
  let receipt = null;
  let artifacts = [];
  try {
    if (operation.state === "runtime_create_pending") {
      const value = await call(env, owner, "create_runtime", { runtime: { runtimeSpec: plan.runtime_spec },
        runtimeId: runtimeId(runId), requestId: operation.runtime_request_id }, { fetchImpl });
      runtime = value?.runtime || value;
      if (!validGoogleColabRuntime(runtime) || runtime.name !== `runtimes/${runtimeId(runId)}` ||
          runtime.runtimeSpec.accelerator !== plan.runtime_spec.accelerator) {
        throw new Error("GOOGLE_COLAB_RUNTIME_INVALID");
      }
      const sealed = await encryptGoogleColabOperationData(env, owner, runId, fingerprint, runtime.connectionInfo);
      const changed = await transitionGoogleColabOperation(env.DB, { owner, runId, fingerprint,
        fromState: "runtime_create_pending", toState: "runtime_ready", now: options.now,
        patch: { runtime_name: runtime.name, connection_ciphertext: sealed.ciphertext, connection_iv: sealed.iv } });
      if (!changed) operation = await readGoogleColabOperation(env.DB, owner, runId, fingerprint);
      else operation = await readGoogleColabOperation(env.DB, owner, runId, fingerprint);
    }
    if (!runtime && operation.runtime_name) {
      const sealed = await decryptGoogleColabOperationData(env, owner, runId, fingerprint,
        { ciphertext: operation.connection_ciphertext, iv: operation.connection_iv });
      runtime = { name: operation.runtime_name, runtimeSpec: plan.runtime_spec, connectionInfo: sealed };
      if (!validGoogleColabRuntime(runtime)) throw new Error("GOOGLE_COLAB_RUNTIME_INVALID");
    }
    if (operation.state === "runtime_ready") {
      await transitionGoogleColabOperation(env.DB, { owner, runId, fingerprint,
        fromState: "runtime_ready", toState: "session_create_pending", now: options.now });
      operation = await readGoogleColabOperation(env.DB, owner, runId, fingerprint);
    }
    if (operation.state === "session_create_pending") {
      // create_session is create-or-get for a caller-selected stable session ID.
      const session = await call(env, owner, "create_session", { parent: operation.runtime_name,
        sessionId: sessionId(runId) }, { expectedRuntimeName: operation.runtime_name,
        expectedSessionId: sessionId(runId), fetchImpl });
      const sessionValue = session?.session || session;
      if (!validGoogleColabSession(sessionValue, operation.runtime_name) ||
          sessionValue.name !== `${operation.runtime_name}/sessions/${sessionId(runId)}`) {
        throw new Error("GOOGLE_COLAB_SESSION_INVALID");
      }
      const code = buildGoogleColabExecutionCode({ runId, repository: plan.repository, commit: plan.source_sha,
        visibility: "public", manifest: plan.manifest, runtimeSeconds: plan.runtime_seconds,
        accelerator: plan.runtime_spec.accelerator });
      const codeHash = await sha256Hex(code);
      const executionId = crypto.randomUUID();
      await transitionGoogleColabOperation(env.DB, { owner, runId, fingerprint,
        fromState: "session_create_pending", toState: "execution_pending", now: options.now,
        patch: { session_name: sessionValue.name, execution_id: executionId,
          execution_code_sha256: codeHash } });
      operation = await readGoogleColabOperation(env.DB, owner, runId, fingerprint);
    }
    if (operation.state === "execution_pending") {
      const code = buildGoogleColabExecutionCode({ runId, repository: plan.repository, commit: plan.source_sha,
        visibility: "public", manifest: plan.manifest, runtimeSeconds: plan.runtime_seconds,
        accelerator: plan.runtime_spec.accelerator });
      if (await sha256Hex(code) !== operation.execution_code_sha256) throw new Error("GOOGLE_COLAB_EXECUTION_CODE_MISMATCH");
      const execution = await call(env, owner, "execute_code", { code, executionId: operation.execution_id,
        session: operation.session_name }, { expectedSessionName: operation.session_name,
        expectedExecutionId: operation.execution_id, fetchImpl });
      if (!validGoogleColabExecution(execution, operation.session_name, operation.execution_id) || execution.outputTruncated) {
        throw new Error("GOOGLE_COLAB_EXECUTION_RESULT_INVALID");
      }
      receipt = parseGoogleColabExecutionReceipt(execution.stdout, { runId, repository: plan.repository,
        commit: plan.source_sha, outputs: plan.manifest.outputs, accelerator: plan.runtime_spec.accelerator });
      await transitionGoogleColabOperation(env.DB, { owner, runId, fingerprint,
        fromState: "execution_pending", toState: "execution_complete", now: options.now,
        patch: { execution_result_json: receipt } });
      operation = await readGoogleColabOperation(env.DB, owner, runId, fingerprint);
    }
    if (operation.state === "execution_complete") {
      const stored = typeof operation.execution_result_json === "string"
        ? JSON.parse(operation.execution_result_json) : operation.execution_result_json;
      receipt = stored?.run_id === runId ? stored : null;
      if (!receipt) throw new Error("GOOGLE_COLAB_EXECUTION_RESULT_INVALID");
      artifacts = await persistGoogleColabArtifacts(env, owner, runId, fingerprint, runtime, receipt,
        fetchImpl, options.now);
      await transitionGoogleColabOperation(env.DB, { owner, runId, fingerprint,
        fromState: "execution_complete", toState: "cleanup_pending", now: options.now });
      operation = await readGoogleColabOperation(env.DB, owner, runId, fingerprint);
    }
    if (operation.state === "cleanup_pending" && !receipt) {
      try { receipt = JSON.parse(operation.execution_result_json); } catch { receipt = null; }
      if (!receipt || receipt.run_id !== runId) throw new Error("GOOGLE_COLAB_EXECUTION_RESULT_INVALID");
      const { results = [] } = await env.DB.prepare(`SELECT artifact_id, path, sha256, size_bytes
        FROM google_colab_run_artifacts WHERE owner_id=? AND run_id=? AND plan_fingerprint=? ORDER BY artifact_id`)
        .bind(owner, runId, fingerprint).all();
      artifacts = results;
    }
    if (operation.state === "cleanup_pending") {
      const cleanup = await call(env, owner, "delete_runtime", { name: operation.runtime_name, allowMissing: true },
        { expectedRuntimeName: operation.runtime_name, fetchImpl });
      if (!validGoogleColabRuntimeDeletion(cleanup)) throw new Error("GOOGLE_COLAB_CLEANUP_UNCONFIRMED");
      const finalState = receipt?.state === "succeeded" ? "succeeded" : "failed";
      return finish(env, owner, planRow, operation, receipt, artifacts, finalState, options.now);
    }
    return result("pending", "Colab実行を再開できる状態で保存しました。新しいruntimeやrunは作成せず、同じrunを照合してください。",
      runId, "uncertain", "unknown", ["experiment_status", "experiment_cancel"], "COLAB_RUN_IN_PROGRESS");
  } catch {
    const latest = await readGoogleColabOperation(env.DB, owner, runId, fingerprint);
    return result("pending", "Colabの応答が未確定です。重複実行を避け、同じrunの状態確認またはcancelで復旧できます。",
      runId, "uncertain", latest?.state === "terminal" ? "confirmed" : "unknown",
      ["experiment_status", "experiment_cancel"], "COLAB_RUN_OUTCOME_UNCONFIRMED",
      { operation_state: latest?.state || "unknown", provider_resource_created: Boolean(latest?.runtime_name) });
  }
}

export async function googleColabRunTool(env, owner, name, runId, options = {}) {
  const row = await readPlan(env, owner, runId);
  if (!row) return null;
  let plan;
  try { plan = JSON.parse(row.approved_plan_json); } catch { plan = null; }
  if (!validGoogleColabApprovedPlan(plan)) return null;
  if (name === "experiment_cancel") {
    if (row.provider_response_json) {
      try { return JSON.parse(row.provider_response_json); } catch {}
    }
    let operation = await readGoogleColabOperation(env.DB, owner, runId, row.fingerprint);
    if (!operation) {
      const now = options.now ?? Math.floor(Date.now() / 1000);
      if (row.state !== "prepared" || row.submit_attempted_at !== null) {
        return missingOperationRecord(runId);
      }
      const cancelled = await env.DB.prepare(`UPDATE gateway_delegated_plans SET cancelled_at=?, updated_at=?
        WHERE owner_id=? AND id=? AND state='prepared' AND cancelled_at IS NULL`).bind(now, now, owner, runId).run();
      if (cancelled?.meta?.changes === 1) return result("ok", "Colab planを実行前に取り消しました。runtimeは作成されていません。", runId,
        "cancelled", "confirmed", [], null, { provider_resource_created: false });
      const raced = await readGoogleColabOperation(env.DB, owner, runId, row.fingerprint);
      const latest = await readPlan(env, owner, runId);
      if (latest?.cancelled_at) return result("ok", "Colab planを実行前に取り消しました。runtimeは作成されていません。", runId,
        "cancelled", "confirmed", [], null, { provider_resource_created: false });
      if (raced) return googleColabRunTool(env, owner, name, runId, options);
      return result("pending", "Colab submitとcancelが同時に進行しました。状態を照合してください。", runId,
        "uncertain", "unknown", ["experiment_status", "experiment_cancel"], "COLAB_RUN_OUTCOME_UNCONFIRMED");
    }
    const cancelAt = options.now ?? Math.floor(Date.now() / 1000);
    await env.DB.prepare(`UPDATE gateway_delegated_plans SET cancelled_at=COALESCE(cancelled_at, ?), updated_at=?
      WHERE owner_id=? AND id=? AND fingerprint=?`).bind(cancelAt, cancelAt, owner, runId, row.fingerprint).run();
    if (operation.state !== "cleanup_pending" && operation.state !== "terminal") {
      await transitionGoogleColabOperation(env.DB, { owner, runId, fingerprint: row.fingerprint,
        fromState: operation.state, toState: "cleanup_pending", now: cancelAt });
      operation = await readGoogleColabOperation(env.DB, owner, runId, row.fingerprint);
    }
    if (!operation.runtime_name) {
      try {
        const listing = await call(env, owner, "list_runtimes", {}, { fetchImpl: options.fetchImpl || fetch });
        const found = Array.isArray(listing?.runtimes)
          ? listing.runtimes.find((runtime) => runtime?.name === `runtimes/${runtimeId(runId)}`) : null;
        if (!found) return result("pending", "Colabのruntime作成応答はまだ確定していません。作成要求と同じrunで再確認します。",
          runId, "uncertain", "unknown", ["experiment_status", "experiment_cancel"], "COLAB_RUNTIME_ID_UNKNOWN");
        if (operation.state === "runtime_create_pending" || operation.state === "cleanup_pending") {
          await transitionGoogleColabOperation(env.DB, { owner, runId, fingerprint: row.fingerprint,
            fromState: operation.state, toState: "cleanup_pending",
            now: options.now ?? Math.floor(Date.now() / 1000), patch: { runtime_name: found.name } });
          operation = await readGoogleColabOperation(env.DB, owner, runId, row.fingerprint);
        }
        operation.runtime_name = found.name;
      } catch { return result("pending", "Colab runtimeの存在を照合できません。cleanup状態は未確認のまま保持します。",
        runId, "uncertain", "unknown", ["experiment_status", "experiment_cancel"], "COLAB_RUNTIME_ID_UNKNOWN"); }
    }
    if (operation.runtime_name !== `runtimes/${runtimeId(runId)}`) {
      return result("error", "保存されたColab runtime identityがこのrunの要求値と一致しません。削除しません。", runId,
        "uncertain", "unknown", ["experiment_status"], "COLAB_RUNTIME_IDENTITY_MISMATCH",
        { provider_resource_created: true });
    }
    if (operation.state === "terminal") {
      return result("ok", "このColab runはすでにterminalで、run-owned runtimeのcleanupが確認されています。",
        runId, row.provider_state || "cancelled", "confirmed", [], null,
        { runtime_deleted: true, operation_state: "terminal" });
    }
    try {
      const cleanup = await call(env, owner, "delete_runtime", { name: operation.runtime_name, allowMissing: true },
        { expectedRuntimeName: operation.runtime_name, fetchImpl: options.fetchImpl || fetch });
      if (!validGoogleColabRuntimeDeletion(cleanup)) throw new Error("GOOGLE_COLAB_CLEANUP_UNCONFIRMED");
      const now = options.now ?? Math.floor(Date.now() / 1000);
      await env.DB.prepare(`UPDATE gateway_delegated_plans SET provider_state='cancelled', terminal_at=?, updated_at=?
        WHERE owner_id=? AND id=? AND fingerprint=?`).bind(now, now, owner, runId, row.fingerprint).run();
      if (operation.state !== "terminal") {
        if (operation.state !== "cleanup_pending") await transitionGoogleColabOperation(env.DB, { owner, runId,
          fingerprint: row.fingerprint, fromState: operation.state, toState: "cleanup_pending", now });
        await transitionGoogleColabOperation(env.DB, { owner, runId, fingerprint: row.fingerprint,
          fromState: "cleanup_pending", toState: "terminal", now });
      }
      const response = result("ok", "このrun専用のColab runtimeを削除し、cleanupを確認しました。", runId,
        "cancelled", "confirmed", [], null, { runtime_deleted: true });
      await env.DB.prepare(`UPDATE gateway_delegated_plans SET provider_response_json=?, provider_state='cancelled',
        terminal_at=?, updated_at=? WHERE owner_id=? AND id=? AND fingerprint=?`)
        .bind(validResultJson(response), now, now, owner, runId, row.fingerprint).run();
      return response;
    } catch { return result("pending", "Colab runtime削除を確認できません。削除確認が取れるまでrunはactive扱いです。",
      runId, "cancelling", "unknown", ["experiment_status", "experiment_cancel"], "COLAB_CLEANUP_UNCONFIRMED"); }
  }
  if (name === "experiment_status" || name === "experiment_result") {
    if (row.provider_response_json) {
      try { return JSON.parse(row.provider_response_json); } catch {}
    }
    const operation = await readGoogleColabOperation(env.DB, owner, runId, row.fingerprint);
    if (!operation) {
      if (row.cancelled_at) return result("ok", "Colab planを送信前に取り消しました。runtimeは作成されていません。",
        runId, "cancelled", "not_required", [], null, { expires_at: row.expires_at, runtime_allocated: false });
      if (row.state === "prepared" && row.submit_attempted_at === null) return result("ok",
        "Colab planは準備済みです。runtimeは作成されていません。", runId, "prepared", "not_required",
        ["experiment_submit", "experiment_cancel"], null, { expires_at: row.expires_at, runtime_allocated: false });
      return missingOperationRecord(runId);
    }
    if (row.cancelled_at) return googleColabRunTool(env, owner, "experiment_cancel", runId, options);
    if (operation.state !== "terminal") return advanceGoogleColabRun(env, owner, row, plan, operation, {
      ...options, now: options.now ?? Math.floor(Date.now() / 1000),
    });
    return result("pending", "Colab runのterminal結果がありません。runtime削除状態を確認してください。",
      runId, row.provider_state || "uncertain", "unknown", ["experiment_status", "experiment_cancel"],
      "COLAB_RUN_OUTCOME_UNCONFIRMED", { operation_state: operation.state, provider_resource_created: Boolean(operation.runtime_name) });
  }
  return null;
}
