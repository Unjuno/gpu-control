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
  return { schema_version: 2, status: "ok",
    human_summary: "学習条件を確認しました。実行受付と料金確認は別途必要です。",
    machine_state: { ...machine, image_digest: env.MAP_TRAINING_IMAGE_DIGEST,
      gpu: "L4", gpu_count: 1, runtime_seconds: args.runtime_seconds,
      max_cost_microusd: args.max_cost_microusd, checkpoint_visibility: "owner_private" },
    next_allowed_actions: [], blocking_reason: null };
}
