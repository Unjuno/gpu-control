import { readRunpodConfiguration } from "./runpod_configuration.js";
import { canonicalJson } from "./canonical_json.js";
import { sha256Hex as sha256 } from "./sha256.js";
import { runpodAdmissionBlocker } from "./runpod_admission.js";
import {
  RUNPOD_COST_ESTIMATE_ASSUMPTIONS,
  RUNPOD_DEFAULT_INITIALIZATION_SECONDS,
  RUNPOD_ESTIMATED_BILLABLE_SECONDS,
  RUNPOD_JOB_TTL_SECONDS,
  RUNPOD_RUNTIME_SECONDS,
  RUNPOD_WORKER_IDLE_TIMEOUT_SECONDS,
} from "./runpod_execution_policy.js";
import { WORKLOADS } from "./workload_registry.js";

export const RUNPOD_WORKLOAD = WORKLOADS.runpod_canary.id;
export const RUNPOD_REPOSITORY = WORKLOADS.runpod_canary.repository;
export { RUNPOD_RUNTIME_SECONDS };
export const RUNPOD_COST_CEILING_USD = WORKLOADS.runpod_canary.cost_ceiling_usd;
export const RUNPOD_COST_CEILING_MICROUSD = Number(RUNPOD_COST_CEILING_USD) * 1_000_000;
export const RUNPOD_PLAN_TTL_SECONDS = 600;

function canonical(value) { return canonicalJson(value, "RUNPOD_PLAN_INVALID"); }

function imageDigest(image) {
  const match = typeof image === "string" ? image.match(/@(sha256:[0-9a-f]{64})$/) : null;
  return match?.[1] ?? null;
}

export function validRunpodPrepare(input, env) {
  const configuration = readRunpodConfiguration(env);
  return configuration !== null && input && typeof input === "object" && !Array.isArray(input) &&
    Object.keys(input).sort().join(",") === "commit,idempotency_key,max_cost_usd,parameters,repository,runtime_seconds,workload" &&
    input.workload === RUNPOD_WORKLOAD && input.repository === RUNPOD_REPOSITORY &&
    input.commit === configuration.sourceSha && input.runtime_seconds === RUNPOD_RUNTIME_SECONDS &&
    input.max_cost_usd === RUNPOD_COST_CEILING_USD && input.parameters &&
    typeof input.parameters === "object" && !Array.isArray(input.parameters) && Object.keys(input.parameters).length === 0 &&
    typeof input.idempotency_key === "string" && /^[A-Za-z0-9_.:-]{8,128}$/.test(input.idempotency_key) &&
    imageDigest(configuration.image) !== null;
}

export function validRunpodApprovedPlan(plan) {
  const sha256Digest = /^[0-9a-f]{64}$/;
  if (!plan || typeof plan !== "object" || Array.isArray(plan) || plan.schema_version !== 2 ||
      plan.provider !== "runpod_gpu" || plan.workload !== RUNPOD_WORKLOAD || plan.max_cost_usd !== RUNPOD_COST_CEILING_USD ||
      plan.cost_ceiling_microusd !== RUNPOD_COST_CEILING_MICROUSD || plan.gpu_count !== 1 ||
      plan.cloud !== "SERVERLESS" || plan.paid !== true || plan.credit_eligible !== false ||
      !sha256Digest.test(plan.owner_binding_sha256 || "") || !sha256Digest.test((plan.image_digest || "").replace(/^sha256:/, "")) ||
      typeof plan.image !== "string" || !plan.image.endsWith(`@${plan.image_digest}`) ||
      typeof plan.source_sha !== "string" || !/^[0-9a-f]{40}$/.test(plan.source_sha) ||
      typeof plan.data_center_id !== "string" || !/^[A-Za-z0-9_-]{4,128}$/.test(plan.data_center_id) ||
      typeof plan.hourly_price_usd !== "string" || !/^[0-9]+\.[0-9]{6}$/.test(plan.hourly_price_usd) ||
      plan.estimated_initialization_seconds !== RUNPOD_DEFAULT_INITIALIZATION_SECONDS ||
      plan.estimated_execution_seconds !== RUNPOD_JOB_TTL_SECONDS ||
      plan.estimated_idle_seconds !== RUNPOD_WORKER_IDLE_TIMEOUT_SECONDS || plan.provider_charge_hard_capped !== false ||
      plan.cost_estimate_assumptions !== RUNPOD_COST_ESTIMATE_ASSUMPTIONS ||
      !Number.isSafeInteger(plan.pricing_valid_until) || !Number.isSafeInteger(plan.estimated_cost_microusd) ||
      plan.estimated_cost_microusd < 1 || plan.estimated_cost_microusd > RUNPOD_COST_CEILING_MICROUSD) return false;
  try { return new TextEncoder().encode(canonical(plan)).byteLength <= 4096; } catch { return false; }
}

function estimatedCost(hourlyPriceUsd) {
  const microusd = Math.ceil(hourlyPriceUsd * RUNPOD_ESTIMATED_BILLABLE_SECONDS * 1_000_000 / 3600);
  if (!Number.isSafeInteger(microusd) || microusd < 1 || microusd > RUNPOD_COST_CEILING_MICROUSD) {
    throw new Error("RUNPOD_ESTIMATED_COST_OUT_OF_BOUNDS");
  }
  return { microusd, usd: (microusd / 1_000_000).toFixed(6) };
}

function configuredOffer(env, checkedAt) {
  const configuration = readRunpodConfiguration(env);
  if (!configuration) throw new Error("RUNPOD_PROVIDER_NOT_CONFIGURED");
  const hourlyPriceUsd = configuration.maximumHourlyPriceUsd;
  return {
    gpuId: configuration.gpuId,
    cloud: "SERVERLESS",
    gpuCount: 1,
    hourlyPriceUsd,
    availability: "CONFIGURED",
    dataCenterId: configuration.endpointId,
    checkedAt,
    validForSeconds: RUNPOD_PLAN_TTL_SECONDS,
    source: "sites-operator-pinned-serverless-maximum",
  };
}

export async function prepareRunpodExperiment(env, owner, args, { client = null, now = null } = {}) {
  if (!validRunpodPrepare(args, env)) throw new Error("REGISTERED_WORKLOAD_OR_ARGUMENTS_INVALID");
  const configuration = readRunpodConfiguration(env);
  const admissionBlocker = runpodAdmissionBlocker(env);
  if (admissionBlocker) return runpodPrepareBlocked(admissionBlocker);
  const checkedAt = now === null ? Math.floor(Date.now() / 1000) : now;
  // Resolve the owner-scoped idempotency record before sampling mutable price
  // evidence. A retry must return the exact accepted plan, even if the quote's
  // checked_at timestamp (or provider price) has changed since the first call.
  const existing = await env.DB.prepare(`SELECT id, fingerprint, provider_plan_json, state, expires_at
    FROM plans WHERE owner_id=? AND idempotency_key=?`).bind(owner, args.idempotency_key).first();
  if (existing) {
    let plan;
    try { plan = JSON.parse(existing.provider_plan_json); } catch { throw new Error("IDEMPOTENCY_RECORD_INVALID"); }
    if (!plan || plan.workload !== RUNPOD_WORKLOAD || plan.repository !== RUNPOD_REPOSITORY ||
        plan.source_sha !== configuration.sourceSha || plan.image_digest !== imageDigest(configuration.image) ||
        plan.owner_binding_sha256 !== await sha256(owner) ||
        await sha256(canonical(plan)) !== existing.fingerprint) throw new Error("IDEMPOTENCY_KEY_CONFLICT");
    return runpodPreparedResponse(existing, plan, checkedAt, true);
  }
  // The runtime key is deliberately endpoint-limited and must not require
  // management/catalog permissions. The operator-pinned value is a
  // conservative maximum; submit/result still use the endpoint API and the
  // owner-bound authenticated completion receipt.
  const offer = client === null ? configuredOffer(env, checkedAt) : await client.getVerifiedOffer();
  if (offer.checkedAt < checkedAt - 30 || offer.checkedAt > checkedAt + 30 ||
      offer.validForSeconds > RUNPOD_PLAN_TTL_SECONDS) {
    throw new Error("RUNPOD_PRICING_EVIDENCE_INVALID");
  }
  const cost = estimatedCost(offer.hourlyPriceUsd);
  const digest = imageDigest(configuration.image);
  const plan = {
    schema_version: 2, workload: RUNPOD_WORKLOAD, provider: "runpod_gpu",
    repository: RUNPOD_REPOSITORY, source_sha: configuration.sourceSha,
    image: configuration.image, image_digest: digest, parameters: {},
    runtime_seconds: RUNPOD_RUNTIME_SECONDS, max_cost_usd: RUNPOD_COST_CEILING_USD,
    cost_ceiling_microusd: RUNPOD_COST_CEILING_MICROUSD,
    estimated_cost_usd: cost.usd, estimated_cost_microusd: cost.microusd,
    estimated_initialization_seconds: RUNPOD_DEFAULT_INITIALIZATION_SECONDS,
    estimated_execution_seconds: RUNPOD_JOB_TTL_SECONDS,
    estimated_idle_seconds: RUNPOD_WORKER_IDLE_TIMEOUT_SECONDS, provider_charge_hard_capped: false,
    cost_estimate_assumptions: RUNPOD_COST_ESTIMATE_ASSUMPTIONS,
    gpu_id: offer.gpuId, gpu_count: 1, cloud: offer.cloud,
    data_center_id: offer.dataCenterId, hourly_price_usd: offer.hourlyPriceUsd.toFixed(6),
    pricing_checked_at: offer.checkedAt, pricing_valid_until: offer.checkedAt + offer.validForSeconds,
    pricing_source: offer.source,
    owner_binding_sha256: await sha256(owner), paid: true, credit_eligible: false,
  };
  const fingerprint = await sha256(canonical(plan));
  const planId = crypto.randomUUID().replaceAll("-", "");
  const expiresAt = Math.min(checkedAt + RUNPOD_PLAN_TTL_SECONDS, plan.pricing_valid_until);
  await env.DB.prepare(`INSERT OR IGNORE INTO plans
      (id, owner_id, idempotency_key, fingerprint, workload, repository, source_sha, image_digest,
       parameters_json, runtime_seconds, max_cost_usd, state, created_at, expires_at, provider,
       provider_plan_json, provider_cost_ceiling_microusd)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, '{}', ?, '0.01', 'prepared', ?, ?, 'runpod_gpu', ?, ?)`)
    .bind(planId, owner, args.idempotency_key, fingerprint, RUNPOD_WORKLOAD, RUNPOD_REPOSITORY,
      configuration.sourceSha, digest, RUNPOD_RUNTIME_SECONDS, checkedAt, expiresAt,
      canonical(plan), RUNPOD_COST_CEILING_MICROUSD).run();
  const persisted = await env.DB.prepare(`SELECT id, fingerprint, provider_plan_json, state, expires_at
    FROM plans WHERE owner_id=? AND idempotency_key=?`).bind(owner, args.idempotency_key).first();
  if (!persisted || persisted.fingerprint !== fingerprint || persisted.provider_plan_json !== canonical(plan)) {
    throw new Error("IDEMPOTENCY_KEY_CONFLICT");
  }
  return runpodPreparedResponse(persisted, plan, checkedAt, false);
}

function runpodPrepareBlocked(blocker) {
  const transportUnverified = blocker === "RUNPOD_LIVE_COMPLETION_TRANSPORT_UNVERIFIED";
  return {
    schema_version: 2, status: "blocked",
    human_summary: transportUnverified
      ? "Runpod completion transport is not verified; no plan was prepared and no Serverless job was submitted."
      : "Runpod admission is disabled; no plan was prepared and no Serverless job was submitted.",
    machine_state: { plan_prepared: false, job_submitted: false }, next_allowed_actions: [],
    blocking_reason: blocker,
  };
}

function runpodPreparedResponse(persisted, plan, now, replay) {
  const expired = persisted.expires_at < now;
  const submitAllowed = !expired && persisted.state === "prepared";
  const cost = { usd: plan.estimated_cost_usd };
  return {
    schema_version: 2, status: "ok",
    human_summary: `Runpodの登録済みServerless GPU canary planを${expired ? "再取得しましたが期限切れです" : "準備しました"}。まだジョブは送信していません。承認窓は10分です。見積り$${cost.usd}は初期化${plan.estimated_initialization_seconds}秒・TTL ${plan.estimated_execution_seconds}秒・idle ${plan.estimated_idle_seconds}秒の仮定です。endpoint設定と自動retryで増額し得るためRunPod側の請求上限ではありません。GPU Controlの$1.00は予約上限です。`,
    machine_state: { run_id: persisted.id, state: expired ? "expired" : persisted.state, provider: "runpod_gpu",
      plan_fingerprint: persisted.fingerprint, idempotent_replay: replay },
    next_allowed_actions: submitAllowed ? ["experiment_submit"] : persisted.state === "prepared" ? [] : ["experiment_status"],
    blocking_reason: expired ? "PLAN_EXPIRED_OR_ALREADY_USED" : null,
    run_id: persisted.id, plan_fingerprint: persisted.fingerprint, expires_at: persisted.expires_at,
    provider_approved_plan: plan, approval_required: submitAllowed,
    authorization_surface: "mcp_destructive_write_action", authorization_validity_seconds: 600,
    max_runs_per_authorization: 1,
  };
}
