import { readModalGpuAccountEvidence } from "./modal_account_evidence.js";
import { MAP_TRAINING_REPOSITORY } from "./training_source.js";
import { DEFAULT_MAP_EXECUTION, MAP_TRAINING_MAX_COST_MICROUSD, MAP_TRAINING_MAX_RUNTIME_SECONDS,
  MAP_TRAINING_WORKSPACE_USAGE_LIMIT_USD } from "./training_policy.js";
import { mapTrainingConfiguration } from "./map_training_configuration.js";
import { trainingControlPlaneSha } from "./training_security_configuration.js";

const MAX_PRICING_AGE_SECONDS = 30 * 24 * 60 * 60;

function validMapExecution(value) {
  return value && typeof value === "object" && !Array.isArray(value) &&
    Object.keys(value).sort().join(",") === "dataset,run_name,steps" &&
    typeof value.dataset === "string" && /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/.test(value.dataset) &&
    typeof value.run_name === "string" && /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/.test(value.run_name) &&
    Number.isSafeInteger(value.steps) && value.steps >= 1 && value.steps <= 100000;
}

export async function previewMapTrainingPlan(env, owner, args, source) {
  const mapConfig = mapTrainingConfiguration(env);
  if (args.runtime_seconds !== MAP_TRAINING_MAX_RUNTIME_SECONDS) return { schema_version: 2, status: "blocked",
    human_summary: "MAP-44Mの1回あたりの実行時間上限は120秒です。",
    machine_state: { max_runtime_seconds: MAP_TRAINING_MAX_RUNTIME_SECONDS },
    next_allowed_actions: [], blocking_reason: "TRAINING_RUNTIME_TOO_HIGH" };
  const machine = { ...source, executable: false };
  let execution = DEFAULT_MAP_EXECUTION;
  let executionSpecId = args.execution_spec_id;
  if (!executionSpecId) {
    const { results = [] } = await env.DB.prepare(`SELECT id AS execution_spec_id, spec_json
      FROM training_execution_specs WHERE owner_id=? AND registration_id=?
      ORDER BY created_at DESC, id DESC LIMIT 2`).bind(owner, source.registration_id).all();
    if (results.length > 1) return { schema_version: 2, status: "blocked",
      human_summary: "このソースには複数の学習設定があります。training_listから実行設定を選んでください。",
      machine_state: { ...machine, execution_specs: results.map(({ execution_spec_id, spec_json }) => ({
        execution_spec_id, ...JSON.parse(spec_json),
      })) }, next_allowed_actions: [], blocking_reason: "TRAINING_CONFIGURATION_SELECTION_REQUIRED" };
    if (results.length === 1) {
      executionSpecId = results[0].execution_spec_id;
      execution = JSON.parse(results[0].spec_json);
    }
  } else {
    const spec = await env.DB.prepare(`SELECT spec_json FROM training_execution_specs
      WHERE owner_id=? AND registration_id=? AND id=?`)
      .bind(owner, source.registration_id, executionSpecId).first();
    if (!spec) throw new Error("TRAINING_REGISTRATION_NOT_FOUND");
    execution = JSON.parse(spec.spec_json);
  }
  if (!validMapExecution(execution)) return { schema_version: 2, status: "blocked",
    human_summary: "MAP-44Mの学習設定が不正です。登録済み設定を確認してください。",
    machine_state: { ...machine, ...(executionSpecId ? { execution_spec_id: executionSpecId } : {}) },
    next_allowed_actions: [], blocking_reason: "TRAINING_PROFILE_INVALID" };
  if (!Number.isSafeInteger(args.max_cost_microusd) || args.max_cost_microusd < 1 ||
      args.max_cost_microusd > MAP_TRAINING_MAX_COST_MICROUSD) return { schema_version: 2, status: "blocked",
    human_summary: "MAP-44Mの1回あたりの費用上限は$0.25です。",
    machine_state: { ...machine, ...execution,
      ...(executionSpecId ? { execution_spec_id: executionSpecId } : {}),
      max_cost_ceiling_microusd: MAP_TRAINING_MAX_COST_MICROUSD },
    next_allowed_actions: [], blocking_reason: "TRAINING_BUDGET_TOO_HIGH" };
  const imageId = mapConfig.image_id;
  const imageIdentity = imageId || mapConfig.image_digest;
  const imagePattern = imageId ? /^im-[A-Za-z0-9]{8,128}$/ : /^sha256:[0-9a-f]{64}$/;
  // These values are set by the operator after reviewing the commit and building
  // the image. A registration alone never gives a commit execution authority.
  if (source.repository !== MAP_TRAINING_REPOSITORY ||
      source.commit !== mapConfig.source_sha ||
      !imagePattern.test(imageIdentity || "")) {
    return { schema_version: 2, status: "blocked",
      human_summary: "このコミットに対応する検証済みの学習イメージが設定されていません。",
      machine_state: { ...machine, ...execution,
        ...(executionSpecId ? { execution_spec_id: executionSpecId } : {}) },
      next_allowed_actions: [], blocking_reason: "TRAINING_PROFILE_UNAVAILABLE" };
  }
  const now = Math.floor(Date.now() / 1000);
  const hourlyRate = mapConfig.hourly_microusd;
  const quoteExpires = mapConfig.quote_expires_at;
  if (!Number.isSafeInteger(hourlyRate) || hourlyRate <= 0 || hourlyRate > 1000000000 ||
      !Number.isSafeInteger(quoteExpires) || quoteExpires <= now || quoteExpires > now + MAX_PRICING_AGE_SECONDS) {
    return { schema_version: 2, status: "blocked",
      human_summary: "有効な学習料金の見積もりが設定されていません。",
      machine_state: { ...machine, ...execution,
        ...(executionSpecId ? { execution_spec_id: executionSpecId } : {}) },
      next_allowed_actions: [], blocking_reason: "TRAINING_QUOTE_UNAVAILABLE" };
  }
  // The source app allows up to 600 seconds of startup. Reserve that
  // separately and apply the source policy's 10 percent budget margin.
  const estimatedCost = Math.ceil(hourlyRate * (args.runtime_seconds + 600) / 3240);
  if (estimatedCost > args.max_cost_microusd) {
    return { schema_version: 2, status: "blocked",
      human_summary: "指定された予算上限では、この実行時間の見積もりをカバーできません。",
      machine_state: { ...machine, ...execution,
        ...(executionSpecId ? { execution_spec_id: executionSpecId } : {}),
        estimated_cost_microusd: estimatedCost },
      next_allowed_actions: [], blocking_reason: "TRAINING_BUDGET_TOO_LOW" };
  }
  const accountEvidence = await readModalGpuAccountEvidence(env, {
    key: "MAP_TRAINING_ACCOUNT_EVIDENCE_JSON", gpu: "L4",
    usageLimitUsd: MAP_TRAINING_WORKSPACE_USAGE_LIMIT_USD,
    expectedHourlyMicrousd: hourlyRate,
    requiredHeadroomMicrousd: args.max_cost_microusd + 10_000,
    now,
  });
  if (!accountEvidence) return { schema_version: 2, status: "blocked",
    human_summary: "MAPのL4価格またはModal Workspaceの利用額・$1上限の短期証拠が未設定、期限切れ、または不一致です。GPUは起動していません。",
    machine_state: { ...machine, ...execution, account_evidence_valid: false, gpu_started: false },
    next_allowed_actions: [], blocking_reason: "MAP_TRAINING_ACCOUNT_EVIDENCE_REQUIRED" };
  const controlPlaneSha = trainingControlPlaneSha(env);
  if (!/^[0-9a-f]{40}$/.test(controlPlaneSha || "")) return { schema_version: 2, status: "blocked",
    human_summary: "学習planを現在のGPU Control commitへ固定できません。",
    machine_state: { ...machine, ...execution, ...(executionSpecId ? { execution_spec_id: executionSpecId } : {}) },
    next_allowed_actions: [], blocking_reason: "TRAINING_AUTHORIZATION_NOT_CONFIGURED" };
  return { schema_version: 2, status: "ok",
    human_summary: "MAP-44Mの学習条件を確認しました。実行計画を準備できます。",
    machine_state: { ...machine, execution_kind: "map_training", control_plane_sha: controlPlaneSha,
      ...(executionSpecId ? { execution_spec_id: executionSpecId } : {}),
      ...execution, image_digest: imageIdentity, provider: "modal",
      provider_resource_id: "gpu-control-map-training/train_map",
      gpu: "L4", gpu_count: 1, runtime_seconds: args.runtime_seconds,
      estimated_cost_microusd: estimatedCost, hourly_microusd: hourlyRate, quote_expires_at: quoteExpires,
      max_cost_microusd: args.max_cost_microusd, provider_evidence: accountEvidence,
      workspace_usage_limit_usd: MAP_TRAINING_WORKSPACE_USAGE_LIMIT_USD,
      checkpoint_visibility: "owner_private" },
    next_allowed_actions: [], blocking_reason: null };
}
