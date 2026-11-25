import { getOwnedTrainingSource } from "./training_source.js";

const MAP_REPOSITORY = "unjuno/model-as-a-paper";

export async function previewTrainingPlan(env, owner, args) {
  const source = await getOwnedTrainingSource(env.DB, owner, args.registration_id);
  const machine = { ...source, executable: false };
  // These values are set by the operator after reviewing the commit and building
  // the image. A registration alone never gives a commit execution authority.
  if (source.repository !== MAP_REPOSITORY ||
      source.commit !== env.MAP_TRAINING_SOURCE_SHA ||
      !/^sha256:[0-9a-f]{64}$/.test(env.MAP_TRAINING_IMAGE_DIGEST || "")) {
    return { schema_version: 2, status: "blocked",
      human_summary: "このコミットに対応する検証済みの学習イメージが設定されていません。",
      machine_state: machine, next_allowed_actions: [], blocking_reason: "TRAINING_PROFILE_UNAVAILABLE" };
  }
  const now = Math.floor(Date.now() / 1000);
  const hourlyRate = Number(env.MAP_TRAINING_HOURLY_MICROUSD);
  const quoteExpires = Number(env.MAP_TRAINING_QUOTE_EXPIRES_AT);
  if (!Number.isSafeInteger(hourlyRate) || hourlyRate <= 0 || hourlyRate > 1000000000 ||
      !Number.isSafeInteger(quoteExpires) || quoteExpires <= now || quoteExpires > now + 3600) {
    return { schema_version: 2, status: "blocked",
      human_summary: "有効な学習料金の見積もりが設定されていません。",
      machine_state: machine, next_allowed_actions: [], blocking_reason: "TRAINING_QUOTE_UNAVAILABLE" };
  }
  // The source app allows up to 600 seconds of startup. Reserve that
  // separately and apply the source policy's 10 percent budget margin.
  const estimatedCost = Math.ceil(hourlyRate * (args.runtime_seconds + 600) / 3240);
  if (estimatedCost > args.max_cost_microusd) {
    return { schema_version: 2, status: "blocked",
      human_summary: "指定された予算上限では、この実行時間の見積もりをカバーできません。",
      machine_state: { ...machine, estimated_cost_microusd: estimatedCost },
      next_allowed_actions: [], blocking_reason: "TRAINING_BUDGET_TOO_LOW" };
  }
  return { schema_version: 2, status: "ok",
    human_summary: "学習条件を確認しました。実行受付は別途必要です。",
    machine_state: { ...machine, image_digest: env.MAP_TRAINING_IMAGE_DIGEST,
      gpu: "L4", gpu_count: 1, runtime_seconds: args.runtime_seconds,
      estimated_cost_microusd: estimatedCost, quote_expires_at: quoteExpires,
      max_cost_microusd: args.max_cost_microusd, checkpoint_visibility: "owner_private" },
    next_allowed_actions: [], blocking_reason: null };
}
