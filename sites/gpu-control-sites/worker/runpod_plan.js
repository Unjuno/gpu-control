import { runpodConfigured } from "./runpod_provider.js";

export const RUNPOD_WORKLOAD = "runpod-gpu-canary-v1";
export const RUNPOD_REPOSITORY = "Unjuno/gpu-control";
export const RUNPOD_RUNTIME_SECONDS = 30;
// Runpod may bill worker initialization and automatic retries. The job TTL is
// the provider-managed hard window; add the exact endpoint idle timeout.
export const RUNPOD_BILLABLE_CEILING_SECONDS = 305;
export const RUNPOD_COST_CEILING_USD = "1.00";
export const RUNPOD_COST_CEILING_MICROUSD = 1_000_000;
export const RUNPOD_PLAN_TTL_SECONDS = 600;

function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonical(value[key])}`).join(",")}}`;
  }
  if (typeof value === "number" && !Number.isFinite(value)) throw new Error("RUNPOD_PLAN_INVALID");
  return JSON.stringify(value);
}

async function sha256(value) {
  const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value)));
  return [...digest].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

function imageDigest(image) {
  const match = typeof image === "string" ? image.match(/@(sha256:[0-9a-f]{64})$/) : null;
  return match?.[1] ?? null;
}

export function validRunpodPrepare(input, env) {
  return runpodConfigured(env) && input && typeof input === "object" && !Array.isArray(input) &&
    Object.keys(input).sort().join(",") === "commit,idempotency_key,max_cost_usd,parameters,repository,runtime_seconds,workload" &&
    input.workload === RUNPOD_WORKLOAD && input.repository === RUNPOD_REPOSITORY &&
    typeof env.RUNPOD_WORKLOAD_SOURCE_SHA === "string" && /^[0-9a-f]{40}$/.test(env.RUNPOD_WORKLOAD_SOURCE_SHA) &&
    input.commit === env.RUNPOD_WORKLOAD_SOURCE_SHA && input.runtime_seconds === RUNPOD_RUNTIME_SECONDS &&
    input.max_cost_usd === RUNPOD_COST_CEILING_USD && input.parameters &&
    typeof input.parameters === "object" && !Array.isArray(input.parameters) && Object.keys(input.parameters).length === 0 &&
    typeof input.idempotency_key === "string" && /^[A-Za-z0-9_.:-]{8,128}$/.test(input.idempotency_key) &&
    imageDigest(env.RUNPOD_WORKLOAD_IMAGE) !== null;
}

function estimatedCost(hourlyPriceUsd) {
  const microusd = Math.ceil(hourlyPriceUsd * RUNPOD_BILLABLE_CEILING_SECONDS * 1_000_000 / 3600);
  if (!Number.isSafeInteger(microusd) || microusd < 1 || microusd > RUNPOD_COST_CEILING_MICROUSD) {
    throw new Error("RUNPOD_ESTIMATED_COST_OUT_OF_BOUNDS");
  }
  return { microusd, usd: (microusd / 1_000_000).toFixed(6) };
}

function configuredOffer(env, checkedAt) {
  const hourlyPriceUsd = Number(env.RUNPOD_SERVERLESS_HOURLY_PRICE_USD);
  if (!Number.isFinite(hourlyPriceUsd) || hourlyPriceUsd <= 0) {
    throw new Error("RUNPOD_CONFIGURED_PRICE_INVALID");
  }
  return {
    gpuId: env.RUNPOD_GPU_ID,
    cloud: "SERVERLESS",
    gpuCount: 1,
    hourlyPriceUsd,
    availability: "CONFIGURED",
    dataCenterId: env.RUNPOD_SERVERLESS_ENDPOINT_ID,
    checkedAt,
    validForSeconds: RUNPOD_PLAN_TTL_SECONDS,
    source: "sites-operator-pinned-serverless-maximum",
  };
}

export async function prepareRunpodExperiment(env, owner, args, { client = null, now = null } = {}) {
  if (!validRunpodPrepare(args, env)) throw new Error("REGISTERED_WORKLOAD_OR_ARGUMENTS_INVALID");
  const checkedAt = now === null ? Math.floor(Date.now() / 1000) : now;
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
  const digest = imageDigest(env.RUNPOD_WORKLOAD_IMAGE);
  const plan = {
    schema_version: 1, workload: RUNPOD_WORKLOAD, provider: "runpod_gpu",
    repository: RUNPOD_REPOSITORY, source_sha: env.RUNPOD_WORKLOAD_SOURCE_SHA,
    image: env.RUNPOD_WORKLOAD_IMAGE, image_digest: digest, parameters: {},
    runtime_seconds: RUNPOD_RUNTIME_SECONDS, max_cost_usd: RUNPOD_COST_CEILING_USD,
    cost_ceiling_microusd: RUNPOD_COST_CEILING_MICROUSD,
    estimated_cost_usd: cost.usd, estimated_cost_microusd: cost.microusd,
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
      env.RUNPOD_WORKLOAD_SOURCE_SHA, digest, RUNPOD_RUNTIME_SECONDS, checkedAt, expiresAt,
      canonical(plan), RUNPOD_COST_CEILING_MICROUSD).run();
  const persisted = await env.DB.prepare(`SELECT id, fingerprint, provider_plan_json, state, expires_at
    FROM plans WHERE owner_id=? AND idempotency_key=?`).bind(owner, args.idempotency_key).first();
  if (!persisted || persisted.fingerprint !== fingerprint || persisted.provider_plan_json !== canonical(plan)) {
    throw new Error("IDEMPOTENCY_KEY_CONFLICT");
  }
  return {
    schema_version: 2, status: "ok",
    human_summary: `Runpodの登録済みServerless GPU canary planを準備しました。まだジョブは送信していません。承認窓は10分、送信後のprovider側実行TTLは5分、5秒idleを含む最悪窓見積りは$${cost.usd}、損失上限は$1.00です。`,
    machine_state: { run_id: persisted.id, state: persisted.state, provider: "runpod_gpu",
      plan_fingerprint: persisted.fingerprint },
    next_allowed_actions: ["experiment_submit"], blocking_reason: null,
    run_id: persisted.id, plan_fingerprint: persisted.fingerprint, expires_at: persisted.expires_at,
    provider_approved_plan: plan, approval_required: true,
    authorization_surface: "chatgpt_mcp_write_confirmation", authorization_validity_seconds: 600,
    max_runs_per_authorization: 1,
  };
}
