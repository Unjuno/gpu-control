import { readGoogleColabCapabilities } from "./google_colab_tools.js";
import { canonicalJson } from "./canonical_json.js";
import { verifyGithubCommit, resolvePublicDefaultBranchCommit } from "./training_source.js";
import { readTrainingSourceContract } from "./training_contract.js";
import { parseTrainingSource } from "./training_source.js";
import { validateTrainingManifest } from "./training_contract.js";
import { sha256Hex } from "./sha256.js";
import { googleColabAdmissionEnabled } from "./google_colab_policy.js";
import { GOOGLE_COLAB_MAX_RUNTIME_SECONDS } from "./google_colab_execution_limits.js";

export const GOOGLE_COLAB_WORKLOAD = "owner-selected-colab-training-v1";
const PLAN_TTL_SECONDS = 600;
const MAX_IDEMPOTENCY_KEY_LENGTH = 128;

function randomHex(byteLength = 16) {
  return [...crypto.getRandomValues(new Uint8Array(byteLength))]
    .map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

export function validGoogleColabPrepare(input) {
  if (!input || typeof input !== "object" || Array.isArray(input) || input.provider !== "google_colab" ||
      !Object.keys(input).every((key) => ["provider", "repository", "commit", "accelerator", "runtime_seconds", "idempotency_key"].includes(key)) ||
      typeof input.repository !== "string") return false;
  try { parseTrainingSource(input.repository, input.commit ?? "0".repeat(40)); }
  catch { return false; }
  if (input.commit !== undefined && !/^[0-9a-f]{40}$/.test(input.commit)) return false;
  if (input.accelerator !== undefined && !["T4", "L4"].includes(input.accelerator)) return false;
  if (input.runtime_seconds !== undefined && (!Number.isSafeInteger(input.runtime_seconds) ||
      input.runtime_seconds < 1 || input.runtime_seconds > GOOGLE_COLAB_MAX_RUNTIME_SECONDS)) return false;
  return typeof input.idempotency_key === "string" &&
    input.idempotency_key.length >= 8 && input.idempotency_key.length <= MAX_IDEMPOTENCY_KEY_LENGTH &&
    /^[A-Za-z0-9_.:-]+$/.test(input.idempotency_key);
}

function chooseRuntimeSpec(capability, requestedAccelerator, manifest) {
  if (capability.subscription_tier === "SUBSCRIPTION_TIER_FREE") return null;
  const eligible = capability.eligible_gpu_specs.filter((spec) => spec.eligible === true &&
    ["T4", "L4"].includes(spec.accelerator) && spec.shape === "SHAPE_STANDARD" &&
    manifest.gpu_profiles.includes(spec.accelerator));
  return eligible.find((spec) => spec.accelerator === requestedAccelerator) ||
    (requestedAccelerator ? null : eligible.find((spec) => spec.accelerator === "T4") || eligible[0]) || null;
}

/** Prepare a public, immutable, owner-selected source on an eligible Colab GPU. */
export async function prepareGoogleColabExperiment(env, owner, args, {
  getSourceToken, fetchImpl = fetch, readCapabilities = readGoogleColabCapabilities,
  now = Math.floor(Date.now() / 1000), makeId = () => randomHex(16),
} = {}) {
  if (!validGoogleColabPrepare(args) || !env?.DB || typeof getSourceToken !== "function" || !Number.isSafeInteger(now)) {
    throw new Error("GOOGLE_COLAB_PLAN_INVALID");
  }
  if (!googleColabAdmissionEnabled(env)) return { schema_version: 2, status: "blocked",
    human_summary: "Google Colab実行受付は停止中です。OAuthやruntime capabilityだけでは実行許可になりません。",
    machine_state: { provider: "google_colab", admission_enabled: false, runtime_allocated: false },
    next_allowed_actions: [], blocking_reason: "GOOGLE_COLAB_WORKLOAD_ADMISSION_DISABLED" };
  const sourceHint = parseTrainingSource(args.repository, args.commit ?? "0".repeat(40));
  const installationToken = await getSourceToken(sourceHint.repository);
  const repositoryState = await resolvePublicDefaultBranchCommit(sourceHint.repository, fetchImpl, installationToken);
  const resolved = args.commit
    ? await verifyGithubCommit(sourceHint.repository, args.commit, fetchImpl, installationToken)
    : repositoryState;
  if (repositoryState.visibility !== "public") return { schema_version: 2, status: "blocked",
    human_summary: "Colab runnerは公開GitHubコミットのみ取得できます。非公開ソースをColab runtimeへ送信しません。",
    machine_state: { repository: sourceHint.repository, commit: resolved.commit, source_visibility: "private",
      runtime_allocated: false }, next_allowed_actions: [], blocking_reason: "GOOGLE_COLAB_PRIVATE_SOURCE_UNSUPPORTED" };
  if (resolved.visibility !== "public") return { schema_version: 2, status: "blocked",
    human_summary: "Colab runnerは公開GitHubコミットのみ取得できます。非公開ソースをColab runtimeへ送信しません。",
    machine_state: { repository: sourceHint.repository, commit: resolved.commit, source_visibility: "private",
      runtime_allocated: false }, next_allowed_actions: [], blocking_reason: "GOOGLE_COLAB_PRIVATE_SOURCE_UNSUPPORTED" };
  const source = parseTrainingSource(sourceHint.repository, resolved.commit);
  const contract = await readTrainingSourceContract(source.repository, source.commit, fetchImpl, installationToken);
  if (!contract.source_readiness.ready) return { schema_version: 2, status: "blocked",
    human_summary: "公開コミットの実験マニフェストまたはhash-locked依存関係がColab契約を満たしていません。",
    machine_state: { repository: source.repository, commit: source.commit,
      source_readiness: contract.source_readiness, runtime_allocated: false },
    next_allowed_actions: ["training_inspect"], blocking_reason: "TRAINING_MANIFEST_OR_LOCK_INVALID" };
  const capability = await readCapabilities(env, owner);
  if (!capability.connected || !capability.configured) return { schema_version: 2, status: "blocked",
    human_summary: "Colabアカウント接続とSites OAuth設定を確認できません。runtimeは作成していません。",
    machine_state: { repository: source.repository, commit: source.commit, runtime_allocated: false },
    next_allowed_actions: capability.configured ? ["colab_connection_start"] : [],
    blocking_reason: capability.blocking_reason || "GOOGLE_COLAB_CONNECTION_REQUIRED" };
  if (capability.execution_lifecycle_enabled === false) return { schema_version: 2, status: "blocked",
    human_summary: "Colabのrun journalまたは成果物ストレージが未設定です。runtimeは作成していません。",
    machine_state: { repository: source.repository, commit: source.commit, runtime_allocated: false,
      execution_lifecycle_enabled: false }, next_allowed_actions: [],
    blocking_reason: capability.blocking_reason || "COLAB_RUN_STORAGE_NOT_CONFIGURED" };
  if (["SUBSCRIPTION_TIER_FREE", "SUBSCRIPTION_TIER_UNSPECIFIED"].includes(capability.subscription_tier)) {
    return { schema_version: 2, status: "blocked",
      human_summary: "Google Colabの自動実行は有料tierと正のCompute Unit残高が必要です。残高はAPIから確認できないため、無料tierでは計画を作成しません。",
      machine_state: { repository: source.repository, commit: source.commit, subscription_tier: capability.subscription_tier,
        positive_compute_units_verified: false, runtime_allocated: false }, next_allowed_actions: [],
      blocking_reason: "GOOGLE_COLAB_POSITIVE_COMPUTE_UNITS_REQUIRED" };
  }
  const runtimeSpec = chooseRuntimeSpec(capability, args.accelerator, contract.manifest);
  if (!runtimeSpec) return { schema_version: 2, status: "blocked",
    human_summary: "公開ソースのGPU要件と、現在Colabアカウントで利用可能なT4/L4 runtimeが一致しません。runtimeは作成していません。",
    machine_state: { repository: source.repository, commit: source.commit,
      eligible_gpu_specs: capability.eligible_gpu_specs, runtime_allocated: false },
    next_allowed_actions: ["colab_capabilities"], blocking_reason: "GOOGLE_COLAB_GPU_PROFILE_UNAVAILABLE" };

  const idempotencyKey = args.idempotency_key || `colab-${randomHex(16)}`;
  const plan = { schema_version: 2, workload: GOOGLE_COLAB_WORKLOAD, provider: "google_colab",
    repository: source.repository, source_sha: source.commit, manifest_path: ".gpu-control/experiment.json",
    manifest_sha256: contract.manifest_sha256, manifest: contract.manifest,
    dependencies_lock_sha256: contract.dependency_lock.sha256, runtime_seconds: args.runtime_seconds ?? 300,
    runtime_spec: { variant: "VARIANT_GPU", accelerator: runtimeSpec.accelerator, shape: runtimeSpec.shape },
    cost_classification: "QUOTA_UNKNOWN", known_cost_usd: null, max_cost_usd: null,
    positive_compute_units_attestation_required: true, positive_compute_units_verified: false,
    paid_fallback_allowed: false, automatic_top_up_allowed: false, network_egress: "unrestricted",
    private_data_allowed: false, provider_credentials_allowed: false,
    runtime_deletion_authorized_by_submit: true };
  const fingerprint = await sha256Hex(canonicalJson([owner, plan]));
  const expiresAt = now + PLAN_TTL_SECONDS;
  let existing = await env.DB.prepare(`SELECT id, fingerprint, workload, approved_plan_json, state, expires_at
    FROM gateway_delegated_plans WHERE owner_id=? AND idempotency_key=?`)
    .bind(owner, idempotencyKey).first();
  if (!existing) {
    const runId = makeId();
    if (!/^[0-9a-f]{32}$/.test(runId || "")) throw new Error("GOOGLE_COLAB_PLAN_INVALID");
    await env.DB.prepare(`INSERT OR IGNORE INTO gateway_delegated_plans
      (id, owner_id, idempotency_key, fingerprint, workload, approved_plan_json, state, created_at, expires_at, updated_at)
      VALUES (?, ?, ?, ?, ?, ?, 'prepared', ?, ?, ?)`)
      .bind(runId, owner, idempotencyKey, fingerprint, GOOGLE_COLAB_WORKLOAD, canonicalJson(plan), now, expiresAt, now).run();
    existing = await env.DB.prepare(`SELECT id, fingerprint, workload, approved_plan_json, state, expires_at
      FROM gateway_delegated_plans WHERE owner_id=? AND idempotency_key=?`)
      .bind(owner, idempotencyKey).first();
  }
  if (!existing || existing.fingerprint !== fingerprint || existing.workload !== GOOGLE_COLAB_WORKLOAD ||
      existing.approved_plan_json !== canonicalJson(plan)) {
    throw new Error("IDEMPOTENCY_KEY_CONFLICT");
  }
  if (existing.expires_at < now || existing.state !== "prepared") return { schema_version: 2,
    status: "blocked", human_summary: "このColab planは期限切れまたはすでに送信済みです。同じ実験を再実行する場合は新しいprepareを作成してください。",
    machine_state: { run_id: existing.id, state: existing.state, expires_at: existing.expires_at,
      provider: "google_colab", runtime_allocated: existing.state !== "prepared" },
    next_allowed_actions: existing.state === "submitted" ? ["experiment_status"] : [],
    blocking_reason: existing.expires_at < now ? "PLAN_EXPIRED_OR_ALREADY_USED" : "PLAN_ALREADY_SUBMITTED" };
  return { schema_version: 2, status: "ok",
    human_summary: `Colab GPU planを作成しました。${runtimeSpec.accelerator}、最大${plan.runtime_seconds}秒、USD費用は不明です。Googleアカウントの正のCompute Unit残高を送信時に確認し、runtime内の全データを成果物確認後に削除します。`,
    provider_approved_plan: plan,
    machine_state: { run_id: existing.id, plan_fingerprint: fingerprint, provider: "google_colab",
      workload: GOOGLE_COLAB_WORKLOAD, repository: source.repository, source_sha: source.commit,
      state: existing.state, expires_at: existing.expires_at, runtime_spec: plan.runtime_spec,
      cost_classification: plan.cost_classification, known_cost_usd: null, max_cost_usd: null,
      network_egress: "unrestricted", private_data_allowed: false, positive_compute_units_verified: false,
      runtime_deletion_authorized_by_submit: true, runtime_allocated: false },
    approval_required: true, authorization_surface: "mcp_destructive_write_action",
    next_allowed_actions: ["experiment_submit"], blocking_reason: null };
}

export function validGoogleColabApprovedPlan(value) {
  if (!value || typeof value !== "object" || Array.isArray(value) || value.schema_version !== 2 ||
      value.workload !== GOOGLE_COLAB_WORKLOAD || value.provider !== "google_colab" ||
      typeof value.repository !== "string" || !/^[a-z0-9-]+\/[A-Za-z0-9_.-]+$/.test(value.repository) ||
      !/^[0-9a-f]{40}$/.test(value.source_sha || "") || value.manifest_path !== ".gpu-control/experiment.json" ||
      !/^[0-9a-f]{64}$/.test(value.manifest_sha256 || "") ||
      !/^[0-9a-f]{64}$/.test(value.dependencies_lock_sha256 || "") ||
      !validateTrainingManifest(value.manifest) || !value.manifest.outputs.includes("metrics.json") ||
      !value.manifest.outputs.some((path) => /(^|\/)(checkpoint|checkpoints)(\/|$)/i.test(path)) ||
      !value.manifest.gpu_profiles.includes(value.runtime_spec?.accelerator) ||
      !Number.isSafeInteger(value.runtime_seconds) || value.runtime_seconds < 1 ||
      value.runtime_seconds > GOOGLE_COLAB_MAX_RUNTIME_SECONDS ||
      !value.runtime_spec || value.runtime_spec.variant !== "VARIANT_GPU" ||
      !["T4", "L4"].includes(value.runtime_spec.accelerator) || value.runtime_spec.shape !== "SHAPE_STANDARD" ||
      value.cost_classification !== "QUOTA_UNKNOWN" || value.known_cost_usd !== null || value.max_cost_usd !== null ||
      value.positive_compute_units_attestation_required !== true || value.positive_compute_units_verified !== false ||
      value.paid_fallback_allowed !== false || value.automatic_top_up_allowed !== false ||
      value.network_egress !== "unrestricted" || value.private_data_allowed !== false ||
      value.provider_credentials_allowed !== false || value.runtime_deletion_authorized_by_submit !== true) return false;
  return new TextEncoder().encode(canonicalJson(value)).byteLength <= 12 * 1024;
}
