import { deriveProviderAccountScopeHash, reserveProviderAccountLease, transitionProviderAccountLease } from "./provider_account_lease.js";
import { verifyRunpodCompletion } from "./runpod_completion.js";
import { RUNPOD_COST_CEILING_MICROUSD, RUNPOD_WORKLOAD } from "./runpod_plan.js";
import { RunpodProviderError, RunpodV2Client, validateJobStatus, validateSubmittedJob } from "./runpod_provider.js";
import { openCompletionKey, sealCompletionKey } from "./runpod_secret.js";

const SHA256 = /^[0-9a-f]{64}$/;
const JOB_ID = /^[A-Za-z0-9_-]{4,128}$/;

function hex(bytes) { return [...bytes].map((value) => value.toString(16).padStart(2, "0")).join(""); }
function randomHex(bytes) { return hex(crypto.getRandomValues(new Uint8Array(bytes))); }
function toBase64(bytes) { let text = ""; for (const byte of bytes) text += String.fromCharCode(byte); return btoa(text); }
async function digest(value) {
  return hex(new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value))));
}
function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value && typeof value === "object") return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonical(value[key])}`).join(",")}}`;
  if (typeof value === "number" && !Number.isFinite(value)) throw new Error("RUNPOD_PLAN_INVALID");
  return JSON.stringify(value);
}
function parsePlan(row) { try { return JSON.parse(row.provider_plan_json); } catch { return null; } }
function executionName(runId) { return `gpu-control-${runId.slice(0, 12)}`; }

export function validRunpodApprovedPlan(plan) {
  if (!plan || typeof plan !== "object" || Array.isArray(plan) || plan.schema_version !== 1 ||
      plan.provider !== "runpod_gpu" || plan.workload !== RUNPOD_WORKLOAD || plan.max_cost_usd !== "1.00" ||
      plan.cost_ceiling_microusd !== RUNPOD_COST_CEILING_MICROUSD || plan.gpu_count !== 1 ||
      plan.cloud !== "SERVERLESS" || plan.paid !== true || plan.credit_eligible !== false ||
      !SHA256.test(plan.owner_binding_sha256 || "") || !SHA256.test((plan.image_digest || "").replace(/^sha256:/, "")) ||
      typeof plan.image !== "string" || !plan.image.endsWith(`@${plan.image_digest}`) ||
      typeof plan.source_sha !== "string" || !/^[0-9a-f]{40}$/.test(plan.source_sha) ||
      typeof plan.data_center_id !== "string" || !/^[A-Za-z0-9_-]{4,128}$/.test(plan.data_center_id) ||
      typeof plan.hourly_price_usd !== "string" || !/^[0-9]+\.[0-9]{6}$/.test(plan.hourly_price_usd) ||
      !Number.isSafeInteger(plan.pricing_valid_until) || !Number.isSafeInteger(plan.estimated_cost_microusd) ||
      plan.estimated_cost_microusd < 1 || plan.estimated_cost_microusd > RUNPOD_COST_CEILING_MICROUSD) return false;
  try { return new TextEncoder().encode(canonical(plan)).byteLength <= 4096; } catch { return false; }
}

async function planRow(env, owner, args) {
  return env.DB.prepare(`SELECT id, owner_id, fingerprint, workload, repository, source_sha, image_digest,
      runtime_seconds, state, expires_at, provider, provider_plan_json, provider_cost_ceiling_microusd
    FROM plans WHERE id=? AND owner_id=? AND fingerprint=?`).bind(args.run_id, owner, args.plan_fingerprint).first();
}

async function currentLease(env, accountScopeSha256) {
  return env.DB.prepare(`SELECT provider, account_scope_sha256, generation, revision, lease_token, run_id,
      owner_id, plan_fingerprint, authorization_id, challenge_sha256, state, provider_job_id
    FROM provider_account_leases WHERE provider='runpod' AND account_scope_sha256=?`)
    .bind(accountScopeSha256).first();
}

async function recordTerminal(env, { runId, owner, state, failureCode = null, result = null, receipt, now }) {
  await env.DB.prepare(`UPDATE runs SET state=?, provider_phase='terminal', failure_code=?, result_json=?,
      cleanup_state='confirmed', cleanup_receipt_json=?, updated_at=? WHERE id=? AND owner_id=?`)
    .bind(state, failureCode, result === null ? null : canonical(result), canonical(receipt), now, runId, owner).run();
}

async function cancelAndRelease(env, client, row, lease, terminal) {
  const now = Math.floor(Date.now() / 1000);
  let termination = "not_submitted";
  if (JOB_ID.test(row.provider_job_id || "")) {
    try { await client.cancelJob(row.provider_job_id); termination = "cancelled_or_terminal"; }
    catch (error) {
      if (!(error instanceof RunpodProviderError) || error.code !== "RUNPOD_NOT_FOUND") throw error;
      termination = "already_expired";
    }
  }
  const receipt = { provider: "runpod_gpu", serverless_job_id: row.provider_job_id, provider_managed: true, termination, observed_at: now };
  await recordTerminal(env, { runId: row.id, owner: row.owner_id, ...terminal, receipt, now });
  const cleanup = lease.state === "cleanup_pending" ? lease : await transitionProviderAccountLease(env.DB, {
    accountScopeSha256: lease.account_scope_sha256, leaseToken: lease.lease_token,
    generation: lease.generation, revision: lease.revision, toState: "cleanup_pending",
    providerJobId: row.provider_job_id, evidenceType: "cleanup_started", evidenceSha256: await digest(canonical(receipt)), now,
  });
  await transitionProviderAccountLease(env.DB, {
    accountScopeSha256: cleanup.account_scope_sha256, leaseToken: cleanup.lease_token,
    generation: cleanup.generation, revision: cleanup.revision, toState: "released",
    evidenceType: "pod_termination_confirmed", evidenceSha256: await digest(canonical(receipt)), now,
  });
}

async function releaseManagedTerminal(env, row, lease, terminal, providerStatus) {
  const now = Math.floor(Date.now() / 1000);
  const receipt = { provider: "runpod_gpu", serverless_job_id: row.provider_job_id,
    provider_managed: true, provider_status: providerStatus, observed_at: now };
  await recordTerminal(env, { runId: row.id, owner: row.owner_id, ...terminal, receipt, now });
  const cleanup = lease.state === "cleanup_pending" ? lease : await transitionProviderAccountLease(env.DB, {
    accountScopeSha256: lease.account_scope_sha256, leaseToken: lease.lease_token, generation: lease.generation,
    revision: lease.revision, toState: "cleanup_pending", providerJobId: row.provider_job_id,
    evidenceType: "serverless_terminal_observed", evidenceSha256: await digest(canonical(receipt)), now,
  });
  await transitionProviderAccountLease(env.DB, { accountScopeSha256: cleanup.account_scope_sha256,
    leaseToken: cleanup.lease_token, generation: cleanup.generation, revision: cleanup.revision, toState: "released",
    evidenceType: "pod_termination_confirmed", evidenceSha256: await digest(canonical(receipt)), now });
}

export async function submitRunpodExperiment(env, owner, args, { reserveBudget, client = null, now = null } = {}) {
  const timestamp = now ?? Math.floor(Date.now() / 1000);
  const row = await planRow(env, owner, args);
  const plan = row ? parsePlan(row) : null;
  if (!row || !["prepared", "queued"].includes(row.state) || row.expires_at < timestamp || row.provider !== "runpod_gpu" ||
      row.provider_cost_ceiling_microusd !== RUNPOD_COST_CEILING_MICROUSD || !validRunpodApprovedPlan(plan) ||
      canonical(plan) !== canonical(args.provider_approved_plan) || plan.owner_binding_sha256 !== await digest(owner)) {
    return { schema_version: 2, status: "blocked", human_summary: "Runpod plan mismatch or expired.",
      machine_state: { run_id: args.run_id, pod_started: false }, next_allowed_actions: [],
      blocking_reason: "APPROVED_PLAN_MISMATCH_OR_EXPIRED" };
  }
  const existing = await env.DB.prepare(`SELECT id, state, created_at FROM runs WHERE id=? AND owner_id=?`).bind(row.id, owner).first();
  if (existing) return { schema_version: 2, status: ["queued", "running"].includes(existing.state) ? "pending" : "ok",
    human_summary: "Existing idempotent Runpod run returned.", machine_state: existing,
    next_allowed_actions: ["experiment_status"], blocking_reason: null };
  if (env.RUNPOD_WORKLOAD_ADMISSION_ENABLED !== "true") return { schema_version: 2, status: "blocked",
    human_summary: "Runpod admission is disabled; no Serverless job was submitted.", machine_state: { run_id: row.id, job_submitted: false },
    next_allowed_actions: [], blocking_reason: "RUNPOD_ADMISSION_DISABLED" };
  if (typeof reserveBudget !== "function" || !await reserveBudget({ runId: row.id, provider: "runpod_gpu",
    requestedMicrousd: RUNPOD_COST_CEILING_MICROUSD, now: timestamp })) {
    return { schema_version: 2, status: "blocked", human_summary: "Runpod per-run budget unavailable; no Pod was created.",
      machine_state: { run_id: row.id, pod_started: false }, next_allowed_actions: [], blocking_reason: "PROVIDER_BUDGET_EXHAUSTED" };
  }
  const authorizationId = randomHex(16);
  const challenge = await digest(canonical({ run_id: row.id, fingerprint: row.fingerprint, owner, plan }));
  await env.DB.batch([
    env.DB.prepare(`INSERT INTO human_authorizations
      (id, owner_id, plan_id, fingerprint, authorization_reference, authorized_at, expires_at, consumed_at, authorization_source)
      SELECT ?, owner_id, id, fingerprint, ?, ?, MIN(?, expires_at), ?, 'chatgpt_mcp_write_confirmation'
      FROM plans WHERE id=? AND owner_id=? AND fingerprint=? AND state='prepared' AND expires_at>=?
      ON CONFLICT(plan_id) DO NOTHING`).bind(authorizationId, `chatgpt-tool:${challenge.slice(0, 32)}`,
        timestamp, timestamp + 600, timestamp, row.id, owner, row.fingerprint, timestamp),
    env.DB.prepare(`UPDATE plans SET state='queued' WHERE id=? AND owner_id=? AND fingerprint=? AND state='prepared'`)
      .bind(row.id, owner, row.fingerprint),
    env.DB.prepare(`INSERT INTO runs (id, owner_id, plan_id, state, provider_phase, created_at, updated_at)
      SELECT id, owner_id, id, 'queued', 'not_started', ?, ? FROM plans WHERE id=? AND owner_id=? AND state='queued'`)
      .bind(timestamp, timestamp, row.id, owner),
  ]);
  const authorization = await env.DB.prepare(`SELECT id FROM human_authorizations WHERE plan_id=? AND owner_id=? AND fingerprint=? AND consumed_at=?`)
    .bind(row.id, owner, row.fingerprint, timestamp).first();
  if (!authorization) throw new Error("RUNPOD_AUTHORIZATION_TRANSACTION_FAILED");
  const accountScopeSha256 = await deriveProviderAccountScopeHash({ scopeId: env.RUNPOD_ACCOUNT_SCOPE_ID,
    hmacKeyB64: env.RUNPOD_ACCOUNT_SCOPE_HMAC_KEY_B64 });
  let lease = await reserveProviderAccountLease(env.DB, { accountScopeSha256, runId: row.id, ownerId: owner,
    planId: row.id, planFingerprint: row.fingerprint, authorizationId: authorization.id,
    challengeSha256: challenge, now: timestamp });
  const provider = client ?? new RunpodV2Client(env);
  let completionKey; let keyId; let nonce; let currentOffer;
  try {
    completionKey = crypto.getRandomValues(new Uint8Array(32));
    keyId = randomHex(16); nonce = randomHex(32);
    const sealed = await sealCompletionKey({ stateEncryptionKeyB64: env.RUNPOD_STATE_KEY_B64,
      completionKeyBytes: completionKey, binding: { runId: row.id, ownerId: owner, planFingerprint: row.fingerprint, keyId } });
    const persisted = await env.DB.prepare(`UPDATE runs SET state='running', provider_phase='creating', provider_nonce=?, provider_started_at=?,
        completion_key_id=?, completion_key_iv_b64=?, completion_key_ciphertext_b64=?, lease_expires_at=?, updated_at=?
      WHERE id=? AND owner_id=? AND state='queued' RETURNING id`).bind(nonce, timestamp, keyId, sealed.ivB64,
        sealed.ciphertextB64, timestamp + row.runtime_seconds + 300, timestamp, row.id, owner).first();
    if (!persisted) throw new Error("RUNPOD_RUNTIME_STATE_PERSISTENCE_FAILED");
    currentOffer = await provider.getVerifiedOffer();
  } catch (error) {
    completionKey?.fill(0);
    const failureCode = error?.code || (error?.message === "RUNPOD_RUNTIME_STATE_PERSISTENCE_FAILED"
      ? error.message : "RUNPOD_PRECREATE_FAILED");
    await recordTerminal(env, { runId: row.id, owner, state: "failed", failureCode,
      receipt: { provider: "runpod_gpu", serverless_job_id: null, termination: "not_submitted", observed_at: timestamp }, now: timestamp });
    await transitionProviderAccountLease(env.DB, { accountScopeSha256, leaseToken: lease.lease_token,
      generation: lease.generation, revision: lease.revision, toState: "released",
      evidenceType: "provider_create_not_started", evidenceSha256: await digest(failureCode), now: timestamp });
    return { schema_version: 2, status: "blocked", human_summary: "Runpod pre-submit checks failed; no Serverless job was submitted.",
      machine_state: { run_id: row.id, state: "failed", job_submitted: false }, next_allowed_actions: ["experiment_status"],
      blocking_reason: failureCode };
  }
  if (currentOffer.gpuId !== plan.gpu_id || currentOffer.cloud !== plan.cloud ||
      currentOffer.dataCenterId !== plan.data_center_id || currentOffer.hourlyPriceUsd.toFixed(6) !== plan.hourly_price_usd ||
      currentOffer.checkedAt > plan.pricing_valid_until) {
    completionKey.fill(0);
    await recordTerminal(env, { runId: row.id, owner, state: "failed", failureCode: "RUNPOD_PRICE_OR_CAPACITY_CHANGED",
      receipt: { provider: "runpod_gpu", serverless_job_id: null, termination: "not_submitted", observed_at: timestamp }, now: timestamp });
    await transitionProviderAccountLease(env.DB, { accountScopeSha256, leaseToken: lease.lease_token, generation: lease.generation,
      revision: lease.revision, toState: "released", evidenceType: "provider_create_not_started", evidenceSha256: challenge, now: timestamp });
    return { schema_version: 2, status: "blocked", human_summary: "Runpod endpoint or price changed; no Serverless job was submitted.",
      machine_state: { run_id: row.id, state: "failed", job_submitted: false }, next_allowed_actions: ["experiment_status"],
      blocking_reason: "RUNPOD_PRICE_OR_CAPACITY_CHANGED" };
  }
  lease = await transitionProviderAccountLease(env.DB, { accountScopeSha256, leaseToken: lease.lease_token,
    generation: lease.generation, revision: lease.revision, toState: "submitting", evidenceType: "provider_create_intent",
    evidenceSha256: challenge, now: timestamp });
  try {
    const created = await provider.submitJob({ runId: row.id, planFingerprint: row.fingerprint, nonce,
      completionKeyB64: toBase64(completionKey), completionKeyId: keyId, sourceSha: row.source_sha });
    const receipt = validateSubmittedJob(created);
    lease = await transitionProviderAccountLease(env.DB, { accountScopeSha256, leaseToken: lease.lease_token,
      generation: lease.generation, revision: lease.revision, toState: "active", providerJobId: receipt.id,
      evidenceType: "validated_provider_receipt", evidenceSha256: await digest(canonical(receipt)), now: timestamp });
    const persisted = await env.DB.prepare(`UPDATE runs SET provider_job_id=?, provider_phase='provisioning', updated_at=?
      WHERE id=? AND owner_id=? AND state='running' AND provider_job_id IS NULL RETURNING id`)
      .bind(receipt.id, timestamp, row.id, owner).first();
    if (!persisted) throw new Error("RUNPOD_PROVIDER_JOB_PERSISTENCE_FAILED");
  } catch (error) {
    const definitive = error instanceof RunpodProviderError && Number.isInteger(error.status) && error.status >= 400 && error.status < 500 && error.status !== 429;
    if (definitive) {
      await recordTerminal(env, { runId: row.id, owner, state: "failed", failureCode: error.code,
        receipt: { provider: "runpod_gpu", serverless_job_id: null, termination: "submit_rejected", observed_at: timestamp }, now: timestamp });
      await transitionProviderAccountLease(env.DB, { accountScopeSha256, leaseToken: lease.lease_token, generation: lease.generation,
        revision: lease.revision, toState: "released", evidenceType: "provider_create_rejected", evidenceSha256: await digest(error.code), now: timestamp });
    } else if (lease.state !== "active") {
      await transitionProviderAccountLease(env.DB, { accountScopeSha256, leaseToken: lease.lease_token, generation: lease.generation,
        revision: lease.revision, toState: "uncertain", evidenceType: "ambiguous_create_outcome", evidenceSha256: challenge, now: timestamp });
    }
    await env.DB.prepare(`UPDATE runs SET provider_phase='uncertain', updated_at=? WHERE id=? AND owner_id=? AND state='running'`)
      .bind(timestamp, row.id, owner).run();
  } finally { completionKey.fill(0); }
  const run = await env.DB.prepare(`SELECT id, state, provider_phase, provider_job_id, cleanup_state FROM runs WHERE id=? AND owner_id=?`)
    .bind(row.id, owner).first();
  return { schema_version: 2, status: run.state === "running" ? "pending" : "ok", human_summary: "Runpod submission recorded.",
    machine_state: run, next_allowed_actions: ["experiment_status", ...(run.state === "running" ? ["experiment_cancel"] : [])], blocking_reason: null };
}

export async function synchronizeRunpodExperiment(env, owner, runId, { client = null, cancel = false } = {}) {
  const row = await env.DB.prepare(`SELECT r.*, p.fingerprint, p.source_sha, p.image_digest, p.runtime_seconds, p.provider_plan_json
    FROM runs r JOIN plans p ON p.id=r.plan_id WHERE r.id=? AND r.owner_id=? AND p.provider='runpod_gpu'`)
    .bind(runId, owner).first();
  if (!row) return null;
  const accountScopeSha256 = await deriveProviderAccountScopeHash({ scopeId: env.RUNPOD_ACCOUNT_SCOPE_ID,
    hmacKeyB64: env.RUNPOD_ACCOUNT_SCOPE_HMAC_KEY_B64 });
  let lease = await currentLease(env, accountScopeSha256);
  if (!lease || lease.run_id !== runId) throw new Error("RUNPOD_ACCOUNT_LEASE_MISSING");
  if (lease.state === "active" && !JOB_ID.test(row.provider_job_id || "") && JOB_ID.test(lease.provider_job_id || "")) {
    const recovered = await env.DB.prepare(`UPDATE runs SET provider_job_id=?, provider_phase='provisioning', updated_at=?
      WHERE id=? AND owner_id=? AND state='running' AND provider_job_id IS NULL RETURNING id`)
      .bind(lease.provider_job_id, Math.floor(Date.now() / 1000), runId, owner).first();
    if (!recovered) throw new Error("RUNPOD_PROVIDER_JOB_RECOVERY_FAILED");
    row.provider_job_id = lease.provider_job_id;
    row.provider_phase = "provisioning";
  }
  if (!["queued", "running"].includes(row.state)) {
    if (["succeeded", "failed", "cancelled"].includes(row.state) && row.cleanup_state === "confirmed" &&
        ["active", "cleanup_pending"].includes(lease.state) && JOB_ID.test(row.provider_job_id || "")) {
      const now = Math.floor(Date.now() / 1000);
      const evidence = await digest(row.cleanup_receipt_json || canonical({ run_id: runId, cleanup: "confirmed" }));
      if (lease.state === "active") lease = await transitionProviderAccountLease(env.DB, {
        accountScopeSha256, leaseToken: lease.lease_token, generation: lease.generation, revision: lease.revision,
        toState: "cleanup_pending", providerJobId: row.provider_job_id, evidenceType: "cleanup_resume",
        evidenceSha256: evidence, now,
      });
      await transitionProviderAccountLease(env.DB, {
        accountScopeSha256, leaseToken: lease.lease_token, generation: lease.generation, revision: lease.revision,
        toState: "released", evidenceType: "pod_termination_confirmed", evidenceSha256: evidence, now,
      });
    }
    return env.DB.prepare(`SELECT * FROM runs WHERE id=? AND owner_id=?`).bind(runId, owner).first();
  }
  const provider = client ?? new RunpodV2Client(env);
  const now = Math.floor(Date.now() / 1000);
  if (row.provider_phase === "uncertain") {
    if (now <= row.provider_started_at + 300) return row;
    const receipt = { provider: "runpod_gpu", serverless_job_id: null, provider_managed: true,
      termination: "job_ttl_elapsed_after_ambiguous_submit", observed_at: now };
    await recordTerminal(env, { runId, owner, state: "failed", failureCode: "RUNPOD_AMBIGUOUS_SUBMIT_TTL_ELAPSED",
      receipt, now });
    const cleanup = await transitionProviderAccountLease(env.DB, { accountScopeSha256,
      leaseToken: lease.lease_token, generation: lease.generation, revision: lease.revision,
      toState: "cleanup_pending", providerJobId: `unknown-${runId}`, evidenceType: "serverless_job_ttl_elapsed",
      evidenceSha256: await digest(canonical(receipt)), now });
    await transitionProviderAccountLease(env.DB, { accountScopeSha256, leaseToken: cleanup.lease_token,
      generation: cleanup.generation, revision: cleanup.revision, toState: "released",
      evidenceType: "pod_termination_confirmed", evidenceSha256: await digest(canonical(receipt)), now });
    return env.DB.prepare(`SELECT * FROM runs WHERE id=? AND owner_id=?`).bind(runId, owner).first();
  }
  if (!JOB_ID.test(row.provider_job_id || "")) return row;
  if (cancel || now > row.provider_started_at + row.runtime_seconds + 60) {
    await cancelAndRelease(env, provider, row, lease, { state: cancel ? "cancelled" : "failed",
      failureCode: cancel ? "CALLER_CANCELLED" : "RUNPOD_RUNTIME_EXCEEDED" });
    return env.DB.prepare(`SELECT * FROM runs WHERE id=? AND owner_id=?`).bind(runId, owner).first();
  }
  const observed = validateJobStatus(await provider.getJob(row.provider_job_id), row.provider_job_id);
  if (["IN_QUEUE", "IN_PROGRESS"].includes(observed.status)) {
    await env.DB.prepare(`UPDATE runs SET provider_phase=?, updated_at=? WHERE id=? AND owner_id=? AND state='running'`)
      .bind(observed.status === "IN_QUEUE" ? "provisioning" : "executing", now, runId, owner).run();
    return env.DB.prepare(`SELECT * FROM runs WHERE id=? AND owner_id=?`).bind(runId, owner).first();
  }
  if (observed.status !== "COMPLETED") {
    await releaseManagedTerminal(env, row, lease, { state: observed.status === "CANCELLED" ? "cancelled" : "failed",
      failureCode: `RUNPOD_${observed.status}` }, observed.status);
    return env.DB.prepare(`SELECT * FROM runs WHERE id=? AND owner_id=?`).bind(runId, owner).first();
  }
  const lines = Array.isArray(observed.output?.lines) && observed.output.lines.length <= 10 &&
    observed.output.lines.every((line) => typeof line === "string" && line.length <= 65536) ? observed.output.lines : null;
  if (!lines) {
    await releaseManagedTerminal(env, row, lease, { state: "failed", failureCode: "RUNPOD_OUTPUT_INVALID" }, observed.status);
    return env.DB.prepare(`SELECT * FROM runs WHERE id=? AND owner_id=?`).bind(runId, owner).first();
  }
  const key = await openCompletionKey({ stateEncryptionKeyB64: env.RUNPOD_STATE_KEY_B64,
    ivB64: row.completion_key_iv_b64, ciphertextB64: row.completion_key_ciphertext_b64,
    binding: { runId, ownerId: owner, planFingerprint: row.fingerprint, keyId: row.completion_key_id } });
  try {
    const verified = await verifyRunpodCompletion(lines, key, { keyId: row.completion_key_id, nonce: row.provider_nonce,
      planFingerprint: row.fingerprint, sourceSha: row.source_sha, imageDigest: row.image_digest,
      executionName: executionName(runId) });
    await releaseManagedTerminal(env, row, lease, { state: "succeeded", result: verified.result }, observed.status);
  } catch (error) {
    await releaseManagedTerminal(env, row, lease, { state: "failed",
      failureCode: error?.code || "RUNPOD_COMPLETION_INVALID" }, observed.status);
  } finally { key.fill(0); }
  return env.DB.prepare(`SELECT * FROM runs WHERE id=? AND owner_id=?`).bind(runId, owner).first();
}

