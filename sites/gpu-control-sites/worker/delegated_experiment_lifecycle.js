import { canonicalJson as canonical } from "./canonical_json.js";
import { validGatewayApprovedPlan } from "./experiment_input_contract.js";
import { callProviderAdapterTool, providerAdapterConfigured } from "./provider_adapter_client.js";
import { readDelegatedPlan as delegatedPlan, persistProviderAdapterObservation,
  publicProviderAdapterResponse } from "./provider_adapter_run_store.js";
import { HUMAN_AUTHORIZATION_TTL_SECONDS } from "./human_authorization_policy.js";
import { prepareModalComputeBudgetReservation, utcMonthKey } from "./provider_budget_policy.js";
import { WORKLOADS } from "./workload_registry.js";

const KAGGLE_WORKLOAD = WORKLOADS.kaggle_training.id;
const ZERO_GPU_WORKLOAD = WORKLOADS.huggingface_evaluation.id;
const MODAL_GPU_WORKLOAD = WORKLOADS.modal_gpu_canary.id;
const GPU_CONTROL_REPOSITORY = WORKLOADS.modal_gpu_canary.repository;
const MODAL_GPU_SOURCE_SHA = WORKLOADS.modal_gpu_canary.source_sha;

async function authorizeFreeProviderPolicy(env, { runId, provider, fingerprint, now }) {
  const inserted = await env.DB.prepare(`INSERT OR IGNORE INTO provider_free_run_authorizations
      (run_id, provider, plan_fingerprint, authorized_microusd, created_at)
    SELECT ?, p.provider, ?, 0, ? FROM provider_free_policies p
    WHERE p.provider=? AND p.max_cost_microusd=0 AND p.paid_fallback_allowed=0`)
    .bind(runId, fingerprint, now, provider).run();
  const authorization = await env.DB.prepare(`SELECT provider, plan_fingerprint, authorized_microusd
    FROM provider_free_run_authorizations WHERE run_id=?`).bind(runId).first();
  return inserted?.meta?.changes === 1 ||
    (authorization?.provider === provider && authorization?.plan_fingerprint === fingerprint &&
      authorization?.authorized_microusd === 0);
}

export async function reserveModalGpuLease(env, { runId, fingerprint, now }) {
  const inserted = await env.DB.prepare(`INSERT OR IGNORE INTO modal_gpu_active_lease
      (scope, run_id, plan_fingerprint, state, acquired_at, updated_at)
    VALUES ('workspace', ?, ?, 'submitting', ?, ?)`)
    .bind(runId, fingerprint, now, now).run();
  const lease = await env.DB.prepare(`SELECT run_id, plan_fingerprint, state
    FROM modal_gpu_active_lease WHERE scope='workspace'`).first();
  return inserted?.meta?.changes === 1 ||
    (lease?.run_id === runId && lease?.plan_fingerprint === fingerprint &&
      ["submitting", "active", "cancel_pending"].includes(lease?.state));
}

export async function prepareDelegatedExperiment(env, owner, args, services) {
  const sourceRunId = args.workload === ZERO_GPU_WORKLOAD
    ? (args.source_run_id || /^runs\/([0-9a-f]{32})\/orbitune-output\.zip$/.exec(args.parameters?.artifact_path || "")?.[1] || null)
    : null;
  const adapterArguments = { ...args };
  delete adapterArguments.source_run_id;
  if (!providerAdapterConfigured(env)) throw new Error("GATEWAY_DELEGATION_NOT_CONFIGURED");
  // The public tool accepts equivalent zero-dollar spellings for usability,
  // but the adapter and persisted fingerprint use one canonical free value.
  // Normalize before the adapter prepares the plan so prepare and submit bind
  // the same exact JSON representation.
  let delegatedArgs = [KAGGLE_WORKLOAD, ZERO_GPU_WORKLOAD].includes(args.workload)
    ? { ...adapterArguments, max_cost_usd: "0" }
    : adapterArguments;
  if (args.workload === MODAL_GPU_WORKLOAD) {
    const evidence = await services.modalGpuProviderEvidence(env, Math.floor(Date.now() / 1000));
    if (!evidence) return { schema_version: 2, status: "blocked",
      human_summary: "Modal Workspace上限・利用額・T4価格の短期証拠が未設定または期限切れです。GPU Functionは起動していません。",
      machine_state: { provider: "modal_gpu", account_evidence_valid: false, gpu_started: false },
      next_allowed_actions: [], blocking_reason: "MODAL_GPU_ACCOUNT_EVIDENCE_REQUIRED" };
    delegatedArgs = { ...args, provider_evidence: evidence };
  }
  const response = await callProviderAdapterTool(env, owner, "experiment_prepare", delegatedArgs);
  const state = response?.machine_state;
  const plan = response?.approved_plan;
  const runId = state?.run_id;
  const fingerprint = state?.plan_fingerprint;
  if (!/^[0-9a-f]{32}$/.test(runId || "") || !/^[0-9a-f]{64}$/.test(fingerprint || "") ||
      !validGatewayApprovedPlan(plan) || plan.workload !== args.workload ||
      plan.repository !== args.repository || plan.source_sha !== args.commit) {
    throw new Error("GATEWAY_DELEGATION_INVALID_RESPONSE");
  }
  const planJson = canonical(plan);
  const now = Math.floor(Date.now() / 1000);
  const expires = now + HUMAN_AUTHORIZATION_TTL_SECONDS;
  await env.DB.prepare(`INSERT OR IGNORE INTO gateway_delegated_plans
    (id, owner_id, idempotency_key, fingerprint, workload, approved_plan_json, state, created_at, expires_at, source_run_id)
    VALUES (?, ?, ?, ?, ?, ?, 'prepared', ?, ?, ?)`)
    .bind(runId, owner, args.idempotency_key, fingerprint, args.workload, planJson, now, expires, sourceRunId).run();
  const persisted = await env.DB.prepare(`SELECT id, fingerprint, workload, approved_plan_json, state, expires_at
    FROM gateway_delegated_plans WHERE owner_id=? AND idempotency_key=?`)
    .bind(owner, args.idempotency_key).first();
  if (!persisted || persisted.id !== runId || persisted.fingerprint !== fingerprint ||
      persisted.workload !== args.workload || persisted.approved_plan_json !== planJson) {
    throw new Error("IDEMPOTENCY_KEY_CONFLICT");
  }
  return { ...response,
    machine_state: { ...response.machine_state, ...(sourceRunId ? { source_run_id: sourceRunId } : {}) },
    provider_approved_plan: plan, expires_at: persisted.expires_at,
    approval_required: true, authorization_surface: "mcp_destructive_write_action",
    authorization_validity_seconds: HUMAN_AUTHORIZATION_TTL_SECONDS,
    max_runs_per_authorization: 1 };
}

export async function submitDelegatedExperiment(env, owner, args, services) {
  const now = Math.floor(Date.now() / 1000);
  const plan = await delegatedPlan(env, owner, args.run_id);
  const approvedPlanJson = canonical(args.provider_approved_plan);
  if (!plan || plan.cancelled_at || plan.fingerprint !== args.plan_fingerprint || plan.approved_plan_json !== approvedPlanJson ||
      plan.expires_at < now || !["prepared", "submitted"].includes(plan.state)) {
    return { schema_version: 2, status: "blocked",
      human_summary: "MCPクライアントからの実行要求が、このownerの現在有効なprovider planと完全一致しません。新しいplanを準備してください。",
      machine_state: { run_id: args.run_id, plan_valid: false }, next_allowed_actions: [],
      blocking_reason: "APPROVED_PLAN_MISMATCH_OR_EXPIRED" };
  }
  const approvedPlan = args.provider_approved_plan;
  const provider = approvedPlan?.provider;
  let policyAuthorized = false;
  if (provider === "modal_gpu") {
    if (env.MODAL_GPU_WORKLOAD_ADMISSION_ENABLED !== "true") return { schema_version: 2, status: "blocked",
      human_summary: "Modal GPU admissionは停止中です。GPU Functionは起動していません。",
      machine_state: { run_id: args.run_id, provider_policy_authorized: false, gpu_started: false },
      next_allowed_actions: [], blocking_reason: "MODAL_GPU_WORKLOAD_ADMISSION_DISABLED" };
    const currentEvidence = await services.modalGpuProviderEvidence(env, now);
    if (!currentEvidence || canonical(currentEvidence) !== canonical(approvedPlan.provider_evidence)) {
      return { schema_version: 2, status: "blocked",
        human_summary: "Modal Workspace上限・利用額・T4価格の証拠が期限切れまたはplanと不一致です。GPU Functionは起動していません。",
        machine_state: { run_id: args.run_id, account_evidence_valid: false, gpu_started: false },
        next_allowed_actions: [], blocking_reason: "MODAL_GPU_ACCOUNT_EVIDENCE_STALE_OR_MISMATCHED" };
    }
    if (approvedPlan.workload !== MODAL_GPU_WORKLOAD || approvedPlan.repository !== GPU_CONTROL_REPOSITORY ||
        approvedPlan.source_sha !== MODAL_GPU_SOURCE_SHA || approvedPlan.max_cost_usd !== WORKLOADS.modal_gpu_canary.cost_ceiling_usd ||
        approvedPlan.known_cost_usd !== null || approvedPlan.cost_classification !== "PAID_BOUNDED" ||
        approvedPlan.paid_fallback_allowed !== false) {
      return { schema_version: 2, status: "blocked",
        human_summary: "Modal GPUの上限付きpolicyとplanが一致しないため、GPU Functionは起動していません。",
        machine_state: { run_id: args.run_id, provider_policy_authorized: false, gpu_started: false },
        next_allowed_actions: [], blocking_reason: "MODAL_GPU_PLAN_POLICY_MISMATCH" };
    }
  } else {
    if (!["kaggle", "huggingface_space"].includes(provider) || approvedPlan.max_cost_usd !== "0" ||
        approvedPlan.known_cost_usd !== "0" || approvedPlan.paid_fallback_allowed !== false) {
      return { schema_version: 2, status: "blocked",
        human_summary: "無料provider policyとplanが一致しないため、providerには接続していません。",
        machine_state: { run_id: args.run_id, provider_policy_authorized: false }, next_allowed_actions: [],
        blocking_reason: "FREE_PROVIDER_PLAN_POLICY_MISMATCH" };
    }
    try {
      policyAuthorized = await authorizeFreeProviderPolicy(env, {
        runId: args.run_id, provider, fingerprint: args.plan_fingerprint, now,
      });
    } catch {}
    if (!policyAuthorized) return { schema_version: 2, status: "blocked",
      human_summary: "無料providerのD1 policyを確保できないため、providerには接続していません。",
      machine_state: { run_id: args.run_id, provider_policy_authorized: false }, next_allowed_actions: [],
      blocking_reason: "FREE_PROVIDER_POLICY_UNAVAILABLE" };
  }
  let authorization = await env.DB.prepare(`SELECT authorization_id, authorization_source, authorized_at, expires_at, consumed_at
    FROM gateway_delegated_authorizations WHERE owner_id=? AND plan_id=? AND fingerprint=?`)
    .bind(owner, args.run_id, args.plan_fingerprint).first();
  if (!authorization) {
    const authorizationId = services.randomHex(16);
    const expiresAt = Math.min(now + HUMAN_AUTHORIZATION_TTL_SECONDS, plan.expires_at);
    await env.DB.prepare(`INSERT OR IGNORE INTO gateway_delegated_authorizations
      (authorization_id, owner_id, plan_id, fingerprint, authorization_source, authorized_at, expires_at, consumed_at)
      SELECT ?, owner_id, id, fingerprint, 'chatgpt_mcp_write_confirmation', ?, ?, ?
      FROM gateway_delegated_plans WHERE owner_id=? AND id=? AND fingerprint=? AND state IN ('prepared','submitted') AND cancelled_at IS NULL AND expires_at>=?`)
      .bind(authorizationId, now, expiresAt, now, owner, args.run_id, args.plan_fingerprint, now).run();
    authorization = await env.DB.prepare(`SELECT authorization_id, authorization_source, authorized_at, expires_at, consumed_at
      FROM gateway_delegated_authorizations WHERE owner_id=? AND plan_id=? AND fingerprint=?`)
      .bind(owner, args.run_id, args.plan_fingerprint).first();
  }
  if (!authorization || authorization.expires_at < now) throw new Error("PLAN_EXPIRED_OR_ALREADY_USED");
  if (provider === "modal_gpu") {
    let leaseReserved = false;
    try { leaseReserved = await reserveModalGpuLease(env, {
      runId: args.run_id, fingerprint: args.plan_fingerprint, now,
    }); } catch {}
    if (!leaseReserved) return { schema_version: 2, status: "blocked",
      human_summary: "別のModal GPU実行がterminal cleanup確認前です。新しいGPU Functionは起動していません。",
      machine_state: { run_id: args.run_id, gpu_started: false, active_lease_acquired: false },
      next_allowed_actions: [], blocking_reason: "MODAL_GPU_ACTIVE_LEASE_BUSY" };
  }
  // Persist the shared Modal reservation and submit claim atomically before
  // the network call. A lost response keeps the same reservation and run.
  const attemptAt = Math.floor(Date.now() / 1000);
  if (plan.state === "prepared") {
    let claimed;
    if (provider === "modal_gpu") {
      const periodKey = utcMonthKey(attemptAt);
      let batch;
      try {
        const reservation = prepareModalComputeBudgetReservation(env.DB, {
          runId: args.run_id, source: "modal_gpu_canary", fingerprint: args.plan_fingerprint,
          periodKey, requestedMicrousd: 10000, now: attemptAt, requireGpuAdmission: true,
        });
        batch = await env.DB.batch([
          reservation,
          env.DB.prepare(`UPDATE gateway_delegated_plans
            SET state='submitted', submit_attempted_at=COALESCE(submit_attempted_at, ?), updated_at=?
            WHERE owner_id=? AND id=? AND fingerprint=? AND state='prepared' AND cancelled_at IS NULL
              AND EXISTS (SELECT 1 FROM modal_gpu_admission_policy a
                WHERE a.scope='workspace' AND a.admission_enabled=1)
              AND EXISTS (SELECT 1 FROM modal_compute_budget_reservations r
                WHERE r.run_id=? AND r.source='modal_gpu_canary' AND r.plan_fingerprint=?
                  AND r.period_key=? AND r.reserved_microusd=10000)
            RETURNING id`).bind(attemptAt, attemptAt, owner, args.run_id, args.plan_fingerprint,
              args.run_id, args.plan_fingerprint, periodKey),
          env.DB.prepare(`DELETE FROM modal_compute_budget_reservations
            WHERE run_id=? AND source='modal_gpu_canary' AND plan_fingerprint=? AND period_key=?
              AND reserved_microusd=10000 AND NOT EXISTS (SELECT 1 FROM gateway_delegated_plans p
                WHERE p.id=? AND p.owner_id=? AND p.fingerprint=? AND p.state='submitted')`)
            .bind(args.run_id, args.plan_fingerprint, periodKey, args.run_id, owner,
              args.plan_fingerprint),
        ]);
      } catch (error) {
        try {
          await env.DB.prepare(`DELETE FROM modal_gpu_active_lease WHERE scope='workspace'
            AND run_id=? AND plan_fingerprint=? AND state='submitting'`)
            .bind(args.run_id, args.plan_fingerprint).run();
        } catch {}
        throw error;
      }
      if (batch?.[0]?.meta?.changes === 0) {
        const existingReservation = await env.DB.prepare(`SELECT source, plan_fingerprint, period_key, reserved_microusd
          FROM modal_compute_budget_reservations WHERE run_id=?`).bind(args.run_id).first();
        if (existingReservation?.source !== "modal_gpu_canary" ||
            existingReservation.plan_fingerprint !== args.plan_fingerprint ||
            existingReservation.period_key !== periodKey || existingReservation.reserved_microusd !== 10000) {
          await env.DB.prepare(`DELETE FROM modal_gpu_active_lease WHERE scope='workspace'
            AND run_id=? AND plan_fingerprint=? AND state='submitting'`)
            .bind(args.run_id, args.plan_fingerprint).run();
          return { schema_version: 2, status: "blocked",
            human_summary: "Modal計算の共通予算上限に達したか、受付が閉じました。GPU Functionは起動していません。",
            machine_state: { run_id: args.run_id, provider_policy_authorized: false, gpu_started: false },
            next_allowed_actions: ["experiment_status"], blocking_reason: "MODAL_GPU_BUDGET_UNAVAILABLE" };
        }
      }
      claimed = batch?.[1]?.results?.[0] || null;
    } else {
      claimed = await env.DB.prepare(`UPDATE gateway_delegated_plans
        SET state='submitted', submit_attempted_at=COALESCE(submit_attempted_at, ?), updated_at=?
        WHERE owner_id=? AND id=? AND fingerprint=? AND state='prepared' AND cancelled_at IS NULL
        RETURNING id`).bind(attemptAt, attemptAt, owner, args.run_id, args.plan_fingerprint).first();
    }
    if (!claimed) {
      const latest = await delegatedPlan(env, owner, args.run_id);
      if (!latest || latest.cancelled_at || latest.state !== "submitted") {
        if (provider === "modal_gpu") await env.DB.prepare(`DELETE FROM modal_gpu_active_lease WHERE scope='workspace'
          AND run_id=? AND plan_fingerprint=? AND state='submitting'`)
          .bind(args.run_id, args.plan_fingerprint).run();
        return { schema_version: 2, status: "blocked", human_summary: "このplanは取消済みか、送信権を取得できませんでした。",
          machine_state: { run_id: args.run_id, plan_valid: false }, next_allowed_actions: [],
          blocking_reason: "PLAN_CANCELLED_OR_ALREADY_CLAIMED" };
      }
    }
  } else if (provider === "modal_gpu") {
    const reservation = await env.DB.prepare(`SELECT source, plan_fingerprint, reserved_microusd
      FROM modal_compute_budget_reservations WHERE run_id=?`).bind(args.run_id).first();
    if (reservation?.source !== "modal_gpu_canary" || reservation.plan_fingerprint !== args.plan_fingerprint ||
        reservation.reserved_microusd !== 10000) return { schema_version: 2, status: "blocked",
      human_summary: "既存Modal GPU runの予算予約を照合できません。新しいrunは作成せず、状態を確認してください。",
      machine_state: { run_id: args.run_id, provider_policy_authorized: false, gpu_started: false },
      next_allowed_actions: ["experiment_status"], blocking_reason: "MODAL_GPU_BUDGET_RESERVATION_MISSING" };
  }
  const response = await callProviderAdapterTool(env, owner, "experiment_submit", {
    run_id: args.run_id, plan_fingerprint: args.plan_fingerprint, approved_plan: args.provider_approved_plan,
    authorization: { authorization_id: authorization.authorization_id, source: authorization.authorization_source,
      authorized_at: authorization.authorized_at, expires_at: authorization.expires_at },
  });
  if (provider === "modal_gpu") {
    await env.DB.prepare(`UPDATE modal_gpu_active_lease SET state='active', updated_at=?
      WHERE scope='workspace' AND run_id=? AND plan_fingerprint=? AND state='submitting'`)
      .bind(now, args.run_id, args.plan_fingerprint).run();
  }
  await persistProviderAdapterObservation(env, owner, args.run_id, response);
  return publicProviderAdapterResponse(response);
}

export async function maybeDelegateRunTool(env, owner, name, args) {
  const plan = await delegatedPlan(env, owner, args.run_id);
  if (!plan) return null;
  // A RunPod run created by the native Sites lifecycle can coexist with a
  // stale gateway_delegated_plans row from the pre-native deployment. Prefer
  // the authoritative native run so status/cancel can reconcile and release
  // its provider-account lease instead of calling the retired adapter path.
  const nativeRunpodRun = await env.DB.prepare(`SELECT r.id FROM runs r
    JOIN plans p ON p.id=r.plan_id
    WHERE r.id=? AND r.owner_id=? AND p.provider='runpod_gpu' LIMIT 1`)
    .bind(args.run_id, owner).first();
  if (nativeRunpodRun) return null;
  if (plan.cancelled_at && plan.state === "prepared") {
    return { schema_version: 2, status: "ok", human_summary: "Prepared provider plan was cancelled before submission; no provider resource was created.",
      machine_state: { run_id: plan.id, state: "cancelled", workload: plan.workload,
        provider_resource_created: false, cleanup_state: "confirmed", cancelled_at: plan.cancelled_at },
      next_allowed_actions: [], blocking_reason: null };
  }
  if (plan.state === "prepared") {
    const now = Math.floor(Date.now() / 1000);
    const expired = plan.expires_at < now;
    const localState = expired ? "expired" : "prepared";
    if (name === "experiment_status") return {
      schema_version: 2,
      status: expired ? "blocked" : "ok",
      human_summary: expired
        ? "Prepared provider plan expired before submission; no provider resource was created."
        : "Prepared provider plan retrieved; no provider resource has been created yet.",
      machine_state: { run_id: plan.id, state: localState, workload: plan.workload,
        plan_fingerprint: plan.fingerprint, expires_at: plan.expires_at,
        provider_resource_created: false, cleanup_state: "not_required" },
      next_allowed_actions: expired ? [] : ["experiment_submit", "experiment_cancel"],
      blocking_reason: expired ? "PLAN_EXPIRED_OR_ALREADY_USED" : null,
    };
    if (name === "experiment_cancel") {
      const cancelled = await env.DB.prepare(`UPDATE gateway_delegated_plans SET cancelled_at=?, updated_at=?
        WHERE owner_id=? AND id=? AND state='prepared' AND cancelled_at IS NULL
        RETURNING id, cancelled_at`).bind(now, now, owner, args.run_id).first();
      if (!cancelled) {
        const latest = await delegatedPlan(env, owner, args.run_id);
        if (latest?.state === "submitted") return maybeDelegateRunTool(env, owner, "experiment_cancel", args);
        if (!latest?.cancelled_at) throw new Error("DELEGATED_PLAN_CANCELLATION_NOT_CONFIRMED");
      }
      return { schema_version: 2, status: "ok",
        human_summary: "Prepared provider plan cancelled before submission; no provider resource was created.",
        machine_state: { run_id: plan.id, state: "cancelled", cancelled_at: cancelled?.cancelled_at || plan.cancelled_at || now, workload: plan.workload,
          provider_resource_created: false, cleanup_state: "confirmed" },
        next_allowed_actions: [], blocking_reason: null };
    }
    return { schema_version: 2, status: "blocked",
      human_summary: "The provider run has not been submitted, so no result or artifact exists.",
      machine_state: { run_id: plan.id, state: localState, workload: plan.workload,
        provider_resource_created: false, cleanup_state: "not_required" },
      next_allowed_actions: expired ? [] : ["experiment_status"],
      blocking_reason: expired ? "PLAN_EXPIRED_OR_ALREADY_USED" : "RESULT_NOT_READY" };
  }
  let providerHandle = plan.provider_handle_json === null || plan.provider_handle_json === undefined
    ? null : JSON.parse(plan.provider_handle_json);
  let approvedPlan;
  try { approvedPlan = JSON.parse(plan.approved_plan_json); } catch { approvedPlan = null; }
  if (!approvedPlan || typeof approvedPlan !== "object" || Array.isArray(approvedPlan)) {
    throw new Error("GATEWAY_DELEGATION_INVALID_PLAN");
  }
  if (!providerHandle && plan.submit_attempted_at) providerHandle = {
    transport: "modal_spawn_v1", run_id: plan.id, plan_fingerprint: plan.fingerprint,
    provider: approvedPlan.provider,
  };
  let externalArtifact = null;
  if (name === "experiment_artifact") {
    let persistedResponse;
    try { persistedResponse = JSON.parse(plan.provider_response_json); } catch { persistedResponse = null; }
    const result = persistedResponse?.result || persistedResponse?.machine_state?.result;
    const references = Array.isArray(result?.external_artifacts) ? result.external_artifacts : [];
    externalArtifact = references.find((reference) => reference?.service === "huggingface_hub" &&
      reference?.run_id === args.run_id && reference?.path_in_repo === `runs/${args.run_id}/orbitune-output.zip` &&
      (reference?.artifact_id === undefined || reference.artifact_id === args.artifact_id));
    if (!externalArtifact || args.artifact_id !== "orbitune-output.zip") {
      return { schema_version: 2, status: "blocked",
        human_summary: "This run has no MCP-readable external artifact.",
        machine_state: { run_id: args.run_id, artifact_id: args.artifact_id },
        next_allowed_actions: ["experiment_result"], blocking_reason: "ARTIFACT_NOT_READY" };
    }
  }
  const delegatedArgs = name === "experiment_artifact"
    ? { run_id: args.run_id, artifact_id: args.artifact_id, offset: args.offset,
      length: args.max_bytes, provider_handle: providerHandle, external_artifact: externalArtifact }
    : { ...args, provider_handle: providerHandle,
      ...(plan.workload === KAGGLE_WORKLOAD ? { runtime_seconds: approvedPlan.runtime_seconds } : {}) };
  if (plan.workload === MODAL_GPU_WORKLOAD && name === "experiment_cancel") {
    await env.DB.prepare(`UPDATE modal_gpu_active_lease SET state='cancel_pending', updated_at=?
      WHERE scope='workspace' AND run_id=? AND plan_fingerprint=? AND state IN ('submitting','active')`)
      .bind(Math.floor(Date.now() / 1000), args.run_id, plan.fingerprint).run();
  }
  let response;
  try {
    response = await callProviderAdapterTool(env, owner, name, delegatedArgs);
  } catch (error) {
    if (plan.submit_attempted_at && !plan.provider_handle_json && name !== "experiment_artifact") {
      return { schema_version: 2, status: "pending",
        human_summary: "Submitの応答が未確定です。新しいrunは作らず、同じrunの受付記録を照合しています。",
        machine_state: { run_id: plan.id, state: "uncertain", provider: approvedPlan.provider,
          submission_attempted: true, provider_resource_created: "unknown", cleanup_state: "unknown" },
        next_allowed_actions: ["experiment_status"], blocking_reason: "SUBMISSION_OUTCOME_UNCONFIRMED" };
    }
    throw error;
  }
  // Artifact reads are read-only. Persisting a chunk response would replace
  // the terminal provider result that owns the immutable external reference,
  // break subsequent chunks, and retain private artifact bytes in D1.
  if (name !== "experiment_artifact") {
    await persistProviderAdapterObservation(env, owner, args.run_id, response);
  }
  if (plan.workload === MODAL_GPU_WORKLOAD &&
      ["succeeded", "failed", "cancelled"].includes(response?.machine_state?.state) &&
      response?.machine_state?.cleanup_state === "confirmed") {
    await env.DB.prepare(`DELETE FROM modal_gpu_active_lease
      WHERE scope='workspace' AND run_id=? AND plan_fingerprint=?`)
      .bind(args.run_id, plan.fingerprint).run();
  }
  return publicProviderAdapterResponse(response);
}

