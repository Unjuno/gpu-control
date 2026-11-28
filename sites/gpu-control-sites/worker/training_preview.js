import { findOwnedTrainingSource, getOwnedTrainingSource, MAP_TRAINING_REPOSITORY } from "./training_source.js";
import { previewModalOwnerTrainingPlan } from "./modal_owner_training_plan.js";
import { previewMapTrainingPlan } from "./map_training_plan.js";
import { assessModalTrainingBudget, readProviderBudgetPolicy } from "./provider_budget_policy.js";
import { MAP_TRAINING_MAX_COST_MICROUSD, MAP_TRAINING_MAX_RUNTIME_SECONDS,
  OWNER_TRAINING_MAX_COST_MICROUSD, OWNER_TRAINING_MAX_MONTHLY_MICROUSD,
  MAP_TRAINING_MAX_MONTHLY_MICROUSD } from "./training_policy.js";
import { ownerTrainingExecutionConfig } from "./training_runtime_profile.js";
import { mapTrainingConfiguration } from "./map_training_configuration.js";

/** Resolve an owner source and build the currently supported exact plan. */
export async function previewTrainingPlan(env, owner, args, getSourceToken = async () => null) {
  const ownerConfig = ownerTrainingExecutionConfig(env);
  const mapConfig = mapTrainingConfiguration(env);
  const source = args.registration_id
    ? await getOwnedTrainingSource(env.DB, owner, args.registration_id)
    : await findOwnedTrainingSource(env.DB, owner, args);
  // Keep the simple chat path simple: a registered source can be previewed
  // and prepared with only its registration ID. MAP keeps its reviewed fixed
  // bounds; an owner-selected source defaults to a short run and the
  // independently configured per-run ceiling. The caller may narrow either.
  if (source.repository === MAP_TRAINING_REPOSITORY) {
    args = { ...args,
      runtime_seconds: args.runtime_seconds ?? MAP_TRAINING_MAX_RUNTIME_SECONDS,
      max_cost_microusd: args.max_cost_microusd ?? MAP_TRAINING_MAX_COST_MICROUSD };
  } else {
    const configuredRuntime = ownerConfig.max_runtime_seconds;
    const configuredCost = ownerConfig.max_cost_microusd;
    args = { ...args,
      runtime_seconds: args.runtime_seconds ?? Math.min(Number.isSafeInteger(configuredRuntime) ? configuredRuntime : 300, 300),
      max_cost_microusd: args.max_cost_microusd ?? Math.min(Number.isSafeInteger(configuredCost)
        ? configuredCost : OWNER_TRAINING_MAX_COST_MICROUSD, OWNER_TRAINING_MAX_COST_MICROUSD) };
  }
  const budgetPolicy = await readProviderBudgetPolicy(env.DB);
  const laneMonthlyLimit = source.repository === MAP_TRAINING_REPOSITORY
    ? mapConfig.monthly_microusd
    : ownerConfig.monthly_microusd;
  const laneMonthlyMaximum = source.repository === MAP_TRAINING_REPOSITORY
    ? MAP_TRAINING_MAX_MONTHLY_MICROUSD : OWNER_TRAINING_MAX_MONTHLY_MICROUSD;
  const budgetAssessment = assessModalTrainingBudget(budgetPolicy, { maxCostMicrousd: args.max_cost_microusd,
    monthlyLimitMicrousd: laneMonthlyLimit, monthlyMaximumMicrousd: laneMonthlyMaximum, requireRemaining: true });
  const modalBudget = budgetAssessment.providerBudget;
  if (!budgetAssessment.policyAvailable) return { schema_version: 2, status: "blocked",
    human_summary: "Modal計算ルート共通の予算ポリシーを確認できないため、計画を作成できません。",
    machine_state: { repository: source.repository, commit: source.commit,
      provider_budget_policy_state: "unavailable" },
    next_allowed_actions: ["experiment_capabilities"], blocking_reason: "PROVIDER_BUDGET_POLICY_UNAVAILABLE" };
  if (!budgetAssessment.limitsSatisfied) return { schema_version: 2, status: "blocked",
    human_summary: "指定された実験上限がModal計算ルート共通の1回または月次上限を超えています。",
    machine_state: { provider: "modal", per_run_limit_usd: modalBudget.per_run_limit_usd,
      monthly_limit_usd: modalBudget.monthly_limit_usd },
    next_allowed_actions: [], blocking_reason: "TRAINING_BUDGET_EXCEEDS_MODAL_PROVIDER_POLICY" };
  if (source.repository === MAP_TRAINING_REPOSITORY) return previewMapTrainingPlan(env, owner, args, source);
  return previewModalOwnerTrainingPlan(env, args, source, getSourceToken);
}

