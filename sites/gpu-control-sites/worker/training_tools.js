import { prepareTrainingPlan } from "./training_prepare.js";
import { previewTrainingPlan } from "./training_preview.js";
import { submitTrainingPlan } from "./training_submit.js";
import { loadApprovedTrainingPlan, persistTrainingTerminalResult, trainingPlanState } from "./training_plan_state.js";
import { ownerTrainingExecutionConfig } from "./training_runtime_profile.js";
import { listTrainingSources, MAP_TRAINING_REPOSITORY, parseTrainingRepository, registerTrainingSource,
  resolvePublicDefaultBranchCommit, verifyGithubCommit } from "./training_source.js";
import { inspectTrainingSource } from "./training_inspection.js";

const trainingTools = new Set([
  "training_checkpoint", "training_artifact", "training_status", "training_cancel",
  "training_submit", "training_prepare", "training_preview", "training_list",
  "training_inspect", "training_register",
]);

export function isTrainingTool(name) {
  return trainingTools.has(name);
}

/** Route the owner training lifecycle behind one domain boundary. */
export async function handleTrainingTool(name, args, { env, owner, delegate, isConfigured, getSourceToken }) {
  if (name === "training_checkpoint") {
    const local = await trainingPlanState(env, owner, args.run_id);
    if (local.machine_state.state !== "dispatching" && local.machine_state.state !== "succeeded") {
      throw new Error("RESULT_NOT_READY");
    }
    const approvedPlan = await loadApprovedTrainingPlan(env.DB, owner, args.run_id,
      local.machine_state.plan_fingerprint);
    const remote = await delegate(env, owner, name, {
      ...args, plan_fingerprint: local.machine_state.plan_fingerprint, approved_plan: approvedPlan,
    });
    if (["not_found", "uncertain", "checkpoint_not_ready"].includes(remote?.state)) throw new Error("RESULT_NOT_READY");
    if (remote?.state !== "succeeded" || !remote.checkpoint_chunk) throw new Error("GATEWAY_DELEGATION_INVALID_RESPONSE");
    return { schema_version: 2, status: "ok", human_summary: "チェックポイントの一部を取得しました。",
      machine_state: { run_id: args.run_id, ...remote.checkpoint_chunk },
      next_allowed_actions: remote.checkpoint_chunk.eof ? [] : ["training_checkpoint"], blocking_reason: null };
  }
  if (name === "training_artifact") {
    const local = await trainingPlanState(env, owner, args.run_id);
    if (local.machine_state.state !== "dispatching" && local.machine_state.state !== "succeeded") {
      throw new Error("RESULT_NOT_READY");
    }
    const approvedPlan = await loadApprovedTrainingPlan(env.DB, owner, args.run_id,
      local.machine_state.plan_fingerprint);
    const remote = await delegate(env, owner, name, {
      ...args, plan_fingerprint: local.machine_state.plan_fingerprint, approved_plan: approvedPlan,
    });
    if (["not_found", "uncertain", "artifact_not_ready"].includes(remote?.state)) throw new Error("RESULT_NOT_READY");
    if (remote?.state !== "succeeded" || !remote.artifact_chunk) throw new Error("GATEWAY_DELEGATION_INVALID_RESPONSE");
    return { schema_version: 2, status: "ok", human_summary: "宣言済み成果物の一部を取得しました。",
      machine_state: { run_id: args.run_id, ...remote.artifact_chunk },
      next_allowed_actions: remote.artifact_chunk.eof ? [] : ["training_artifact"], blocking_reason: null };
  }
  if (name === "training_status" || name === "training_cancel") {
    const local = await trainingPlanState(env, owner, args.run_id, name === "training_cancel", isConfigured);
    if (local.machine_state.state !== "dispatching") return local;
    const approvedPlan = await loadApprovedTrainingPlan(env.DB, owner, args.run_id,
      local.machine_state.plan_fingerprint);
    const remote = await delegate(env, owner, name, {
      run_id: args.run_id, plan_fingerprint: local.machine_state.plan_fingerprint, approved_plan: approvedPlan,
    });
    const adapterOutcomeUnknown = remote?.state === "not_found" || remote?.state === "uncertain";
    const state = adapterOutcomeUnknown ? "uncertain" : remote?.state;
    if (!["staging", "running", "cleanup_pending", "cancel_requested", "cancelled", "succeeded", "failed", "uncertain"].includes(state)) {
      throw new Error("GATEWAY_DELEGATION_INVALID_RESPONSE");
    }
    const nextActions = ["staging", "running"].includes(state) ? ["training_status", "training_cancel"]
      : state === "cleanup_pending" ? ["training_status"]
      : ["cancel_requested", "uncertain"].includes(state) ? ["training_status"]
      : state === "succeeded" || remote.failure_code === "TRAINING_RUNTIME_LIMIT" ? ["training_checkpoint"] : [];
    if (state === "succeeded" && Array.isArray(remote.artifacts) && remote.artifacts.length > 0) {
      nextActions.push("training_artifact");
    }
    const cleanupConfirmed = ["succeeded", "failed", "cancelled"].includes(state) &&
      (remote?.cleanup_state === "confirmed" || remote?.cleanup === "confirmed");
    const persistedResult = cleanupConfirmed ? { ...remote,
      execution_kind: local.machine_state.execution_kind || "map_training", cleanup: "confirmed" } : remote;
    if (cleanupConfirmed && !await persistTrainingTerminalResult(env.DB, owner, args.run_id,
      local.machine_state.plan_fingerprint, persistedResult, Math.floor(Date.now() / 1000))) {
      throw new Error("TRAINING_RESULT_PERSIST_FAILED");
    }
    return { ...local, human_summary: adapterOutcomeUnknown
        ? "Modalの実行結果を確定できないため、provider resource・cleanup状態は不明です。二重実行を避けて同じrunの照合を続けます。"
        : "Modalの学習実行状態です。",
      machine_state: { ...local.machine_state, ...remote, state,
        ...(adapterOutcomeUnknown ? { provider_resource_created: "unknown", cleanup_state: "unknown" } : {}),
        ...(cleanupConfirmed ? { cleanup_state: "confirmed" } : {}) },
      next_allowed_actions: nextActions,
      ...(adapterOutcomeUnknown ? { blocking_reason: "SUBMISSION_OUTCOME_UNCONFIRMED" } : {}) };
  }
  if (name === "training_submit") return submitTrainingPlan(env, owner, args, delegate,
    isConfigured, getSourceToken);
  if (name === "training_prepare") return prepareTrainingPlan(env, owner, args, getSourceToken, isConfigured);
  if (name === "training_preview") return previewTrainingPlan(env, owner, args, getSourceToken);
  if (name === "training_list") return listTrainingSources(env.DB, owner, env);
  if (name === "training_inspect") return inspectTrainingSource(env, owner, args.registration_id,
    getSourceToken, ownerTrainingExecutionConfig(env));
  if (name === "training_register") {
    const repository = parseTrainingRepository(args.repository);
    const isMap = repository === MAP_TRAINING_REPOSITORY;
    let installationToken = null;
    if (!isMap && (args.dataset !== undefined || args.run_name !== undefined || args.steps !== undefined)) {
      return registerTrainingSource(env.DB, owner, args);
    }
    if (!isMap) installationToken = await getSourceToken(repository);
    if (!isMap && args.commit !== undefined) {
      await verifyGithubCommit(repository, args.commit, fetch, installationToken);
    }
    const resolver = (slug) => resolvePublicDefaultBranchCommit(slug, fetch, installationToken);
    return registerTrainingSource(env.DB, owner, args, { resolveCommit: resolver });
  }
  throw new Error("TRAINING_TOOL_NOT_SUPPORTED");
}
