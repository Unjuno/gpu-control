import { readPublicTrainingContract } from "./training_contract.js";
import { getOwnedTrainingSource, MAP_TRAINING_REPOSITORY } from "./training_source.js";

function inspectionFailure(source, error) {
  const reason = error?.message === "GITHUB_REPOSITORY_NOT_SELECTED" ? error.message
    : typeof error?.message === "string" && /^(?:GITHUB_|TRAINING_(?:EXPERIMENT_MANIFEST|GITHUB)_)/.test(error.message)
      ? error.message : "TRAINING_EXPERIMENT_MANIFEST_UNAVAILABLE";
  const humanSummary = reason === "TRAINING_EXPERIMENT_MANIFEST_NOT_FOUND"
    ? "固定commitに .gpu-control/experiment.json がありません。実験は開始していません。"
    : reason === "GITHUB_APP_NOT_CONFIGURED"
      ? "独自repositoryを確認するGitHub AppがGPU Controlに設定されていません。実験は開始していません。"
      : reason === "GITHUB_CONNECTION_REQUIRED"
        ? "GitHub accountを接続し、対象repositoryを選択してください。実験は開始していません。"
        : reason === "GITHUB_REPOSITORY_NOT_SELECTED"
          ? "対象repositoryがこのGitHub App installで選択されていません。GitHub側で対象repositoryを追加してください。実験は開始していません。"
          : "固定commitの実験manifestを安全に確認できませんでした。実験は開始していません。";
  return { schema_version: 2, status: "blocked", human_summary: humanSummary,
    machine_state: { ...source, manifest_path: ".gpu-control/experiment.json", manifest_state: "unavailable" },
    next_allowed_actions: ["training_list"], blocking_reason: reason };
}

/** Inspect an owner's immutable source without creating a plan or starting compute. */
export async function inspectTrainingSource(env, owner, registrationId, getSourceToken = async () => null,
  executionConfig = null) {
  const source = await getOwnedTrainingSource(env.DB, owner, registrationId);
  let inspected;
  try {
    const installationToken = source.repository === MAP_TRAINING_REPOSITORY
      ? null : await getSourceToken(source.repository);
    inspected = await readPublicTrainingContract(source.repository, source.commit, fetch, installationToken,
      source.repository === MAP_TRAINING_REPOSITORY ? null : executionConfig);
  } catch (error) {
    return inspectionFailure(source, error);
  }
  const dependencyLockVerified = inspected.readiness?.checks?.dependency_lock_present_at_commit === true &&
    inspected.readiness?.checks?.dependency_lock_has_exact_versions_and_hashes === true;
  const ready = inspected.readiness?.ready === true;
  return { schema_version: 2, status: ready ? "ok" : "blocked",
    human_summary: !dependencyLockVerified
      ? "固定commitの実験manifestを検証しましたが、依存lockは見つからないか取得・検証できませんでした。実験は開始していません。ソースを修正した後にtraining_inspectを再実行してください。"
      : ready
      ? "固定commit、実験manifest、hash-locked依存、現在の共有GPU runtime profileを確認しました。これは検査のみで、実験は開始していません。必要ならtraining_previewで個別の実行時間と費用見積もりを確認してください。"
      : "固定commitの実験manifestとhash-locked依存を検証しました。training_inspectは実験を開始しません。現在の実行可否はtraining_previewで確認してください。",
    machine_state: { ...source, ...inspected }, next_allowed_actions: ["training_preview", "training_list"],
    blocking_reason: ready ? null : inspected.execution_blocking_reason };
}
