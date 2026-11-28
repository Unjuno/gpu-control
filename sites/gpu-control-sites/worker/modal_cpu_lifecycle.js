import { sha256Hex as sha256 } from "./sha256.js";
import { canonicalJson as canonical } from "./canonical_json.js";
import { WORKLOADS } from "./workload_registry.js";
import { modalPayload, modalRequest } from "./modal_http_client.js";
import { persistRunResultArtifact, runArtifactBytes, RUN_ARTIFACT_MAX_BYTES } from "./run_artifacts.js";

const WORKLOAD = WORKLOADS.tiny_stories.id;
const STATUS_CHECK_WINDOW_SECONDS = 86400;
const STATUS_CHECK_COOLDOWN_SECONDS = 3;
const STATUS_CHECK_MAX_PER_WINDOW = 20;
const NOT_FOUND_RECOVERY_GRACE_SECONDS = 300;
const MODEL_ID = "karpathy/tinyllamas@0bd21da7698eaf29a0d7de3992de8a46ef624add/stories15M.bin";
const MODEL_SHA256 = "cd590644d963867a2b6e5a1107f51fad663c41d79c149fbecbbb1f95fa81f49a";

export async function reserveModalStatusCheck(env, now) {
  const result = await env.DB.prepare(`INSERT INTO modal_status_check_limits
      (scope, window_started_at, last_checked_at, call_count)
    VALUES ('workspace', ?, ?, 1)
    ON CONFLICT(scope) DO UPDATE SET
      window_started_at=CASE
        WHEN modal_status_check_limits.window_started_at <= excluded.window_started_at - ?
          THEN excluded.window_started_at
        ELSE modal_status_check_limits.window_started_at END,
      last_checked_at=excluded.last_checked_at,
      call_count=CASE
        WHEN modal_status_check_limits.window_started_at <= excluded.window_started_at - ?
          THEN 1
        ELSE modal_status_check_limits.call_count + 1 END
    WHERE modal_status_check_limits.window_started_at <= excluded.window_started_at - ?
      OR (modal_status_check_limits.call_count < ?
        AND modal_status_check_limits.last_checked_at <= excluded.last_checked_at - ?)`)
    .bind(now, now, STATUS_CHECK_WINDOW_SECONDS, STATUS_CHECK_WINDOW_SECONDS,
      STATUS_CHECK_WINDOW_SECONDS, STATUS_CHECK_MAX_PER_WINDOW,
      STATUS_CHECK_COOLDOWN_SECONDS).run();
  return result?.meta?.changes === 1;
}

function workloadFailureCode(providerResult) {
  if (providerResult?.state === "not_found") return "MODAL_WORKLOAD_NOT_FOUND";
  const exitCode = providerResult?.exit_code;
  if (Number.isInteger(exitCode) && exitCode >= 0 && exitCode <= 255) {
    if (exitCode === 2 && typeof providerResult.diagnostic_code === "string" &&
        (/^PREFLIGHT_RETURN_LINE_[1-9][0-9]{0,3}$/.test(providerResult.diagnostic_code) ||
         providerResult.diagnostic_code === "PREFLIGHT_SYSTEM_EXIT_2")) {
      return `MODAL_WORKLOAD_EXIT_2_${providerResult.diagnostic_code}`;
    }
    return exitCode === 0 ? "MODAL_RESULT_MISSING" : `MODAL_WORKLOAD_EXIT_${exitCode}`;
  }
  return "MODAL_WORKLOAD_FAILED";
}

async function recoverMissingRunAfterHorizon(env, row, ownerId, now) {
  if (row.state !== "running" || row.cleanup_state !== "pending" ||
      !Number.isSafeInteger(row.lease_expires_at) ||
      now < row.lease_expires_at + NOT_FOUND_RECOVERY_GRACE_SECONDS) return false;
  const receipt = JSON.stringify({ provider: "modal_cpu",
    evidence: "modal_named_sandbox_absent_after_bounded_lifetime", observed_at: now,
    lease_expires_at: row.lease_expires_at, recovery_grace_seconds: NOT_FOUND_RECOVERY_GRACE_SECONDS });
  const result = await env.DB.prepare(`UPDATE runs SET state='failed',
      failure_code='MODAL_SANDBOX_ABSENT_AFTER_RECOVERY_GRACE', cleanup_state='confirmed',
      cleanup_receipt_json=?, updated_at=?
    WHERE id=? AND owner_id=? AND state='running' AND cleanup_state='pending'
      AND lease_expires_at=? AND lease_expires_at<=?`)
    .bind(receipt, now, row.id, ownerId, row.lease_expires_at,
      now - NOT_FOUND_RECOVERY_GRACE_SECONDS).run();
  return result?.meta?.changes === 1;
}

export async function synchronizeModalRun(env, runId, ownerId,
  { submit = false, cancel = false, authorizationExpiresAt = null } = {}) {
  const row = await env.DB.prepare(`SELECT r.id, r.state, r.cancel_requested, r.cleanup_state, r.lease_expires_at,
      p.workload, p.repository, p.source_sha,
      p.image_digest, p.fingerprint, p.parameters_json, p.runtime_seconds
    FROM runs r JOIN plans p ON p.id=r.plan_id WHERE r.id=? AND r.owner_id=?`).bind(runId, ownerId).first();
  if (!row || !["queued", "running"].includes(row.state)) return;
  if (submit && (!Number.isSafeInteger(authorizationExpiresAt) || authorizationExpiresAt < Math.floor(Date.now() / 1000))) {
    const now = Math.floor(Date.now() / 1000);
    await env.DB.prepare(`UPDATE runs SET state='failed', failure_code='HUMAN_AUTHORIZATION_EXPIRED', cleanup_state='confirmed', updated_at=?
      WHERE id=? AND owner_id=? AND state IN ('queued','running')`).bind(now, runId, ownerId).run();
    return;
  }
  const payload = modalPayload(row, env);
  let providerResult;
  if (cancel || row.cancel_requested === 1) {
    providerResult = await modalRequest(env, `/v1/runs/${runId}/cancel`, payload);
  } else if (submit) {
    providerResult = await modalRequest(env, `/v1/runs/${runId}/submit`, payload);
  } else {
    try {
      providerResult = await modalRequest(env, `/v1/runs/${runId}/status`, payload);
    } catch (error) {
      if (error?.message === "MODAL_RUN_NOT_FOUND" && row.state === "queued") {
        const authorization = await env.DB.prepare(`SELECT expires_at, consumed_at FROM human_authorizations
          WHERE owner_id=? AND plan_id=? AND fingerprint=?`).bind(ownerId, runId, row.fingerprint).first();
        if (!authorization || authorization.consumed_at === null || authorization.expires_at < Math.floor(Date.now() / 1000)) {
          const now = Math.floor(Date.now() / 1000);
          await env.DB.prepare(`UPDATE runs SET state='failed', failure_code='HUMAN_AUTHORIZATION_EXPIRED', cleanup_state='confirmed', updated_at=?
            WHERE id=? AND owner_id=? AND state='queued'`).bind(now, runId, ownerId).run();
          return;
        }
        providerResult = await modalRequest(env, `/v1/runs/${runId}/submit`, payload);
      } else if (error?.message === "MODAL_RUN_NOT_FOUND") {
        providerResult = { state: "not_found", cleanup_state: "unknown" };
      } else throw error;
    }
  }
  const now = Math.floor(Date.now() / 1000);
  if (providerResult.state === "not_found" && providerResult.cleanup_state !== "confirmed") {
    await recoverMissingRunAfterHorizon(env, row, ownerId, now);
    return;
  }
  if (providerResult.sandbox_id && typeof providerResult.sandbox_id === "string" && providerResult.sandbox_id.length <= 128) {
    await env.DB.prepare("UPDATE runs SET lease_id=?, updated_at=? WHERE id=? AND owner_id=? AND state IN ('queued','running')")
      .bind(providerResult.sandbox_id, now, runId, ownerId).run();
  }
  if (providerResult.cleanup_state !== "confirmed") return;
  if (providerResult.state === "succeeded" &&
      providerResult.image_fingerprint !== env.MODAL_WORKLOAD_IMAGE_FINGERPRINT) {
    await env.DB.prepare(`UPDATE runs SET state='failed', failure_code='MODAL_IMAGE_FINGERPRINT_MISMATCH', cleanup_state='confirmed', updated_at=?
      WHERE id=? AND owner_id=? AND state IN ('queued','running')`).bind(now, runId, ownerId).run();
    return;
  }
  if (cancel || row.cancel_requested === 1 || providerResult.state === "cancelled") {
    await env.DB.prepare(`UPDATE runs SET state='cancelled', failure_code='caller_cancelled', cleanup_state='confirmed', updated_at=?
      WHERE id=? AND owner_id=? AND state IN ('queued','running')`).bind(now, runId, ownerId).run();
    return;
  }
  if (providerResult.state === "running") return;
  if (providerResult.state !== "succeeded" || !providerResult.result || providerResult.result.status !== "passed") {
    if (["failed", "not_found"].includes(providerResult.state)) {
      await env.DB.prepare(`UPDATE runs SET state='failed', failure_code=?, cleanup_state='confirmed', updated_at=?
        WHERE id=? AND owner_id=? AND state IN ('queued','running')`)
        .bind(workloadFailureCode(providerResult), now, runId, ownerId).run();
    }
    return;
  }
  const result = providerResult.result;
  const metrics = result.metrics;
  const parameters = JSON.parse(row.parameters_json);
  const expectedChecks = ["source_identity_present", "parameter_bounds", "model_digest_verified", "inference_completed",
    "non_root", "no_secret_environment", "no_docker_socket", "read_only_rootfs", "network_disabled"];
  if (result.schema_version !== 1 || result.run_id !== runId || result.source_sha !== row.source_sha ||
      result.plan_fingerprint !== row.fingerprint || result.check !== WORKLOAD || result.gpu_used !== false ||
      !Array.isArray(result.checks) || canonical(result.checks) !== canonical(expectedChecks) ||
      !metrics || metrics.model_id !== MODEL_ID || metrics.model_sha256 !== MODEL_SHA256 ||
      metrics.max_new_tokens !== parameters.max_new_tokens || metrics.seed !== parameters.seed ||
      typeof metrics.generated_text !== "string" || new TextEncoder().encode(metrics.generated_text).byteLength > 1536 ||
      !Number.isInteger(metrics.generated_tokens) || metrics.generated_tokens < 1 || metrics.generated_tokens > metrics.max_new_tokens ||
      !/^[0-9a-f]{64}$/.test(metrics.prompt_sha256 || "") ||
      typeof result.checksum !== "string" || !/^[0-9a-f]{64}$/.test(result.checksum) ||
      await sha256(canonical({ run_id: result.run_id, source_sha: result.source_sha, plan_fingerprint: result.plan_fingerprint, metrics })) !== result.checksum) {
    await env.DB.prepare(`UPDATE runs SET state='failed', failure_code='MODAL_RESULT_VALIDATION_FAILED', cleanup_state='confirmed', updated_at=?
      WHERE id=? AND owner_id=? AND state IN ('queued','running')`).bind(now, runId, ownerId).run();
    return;
  }
  const resultJson = canonical(result);
  const resultBytes = runArtifactBytes(resultJson);
  if (resultBytes.byteLength > RUN_ARTIFACT_MAX_BYTES) {
    await env.DB.prepare(`UPDATE runs SET state='failed', failure_code='MODAL_RESULT_TOO_LARGE', cleanup_state='confirmed', updated_at=?
      WHERE id=? AND owner_id=? AND state IN ('queued','running')`).bind(now, runId, ownerId).run();
    return;
  }
  await persistRunResultArtifact(env, { runId, ownerId, sourceSha: row.source_sha,
    planFingerprint: row.fingerprint, resultJson, now });
}
