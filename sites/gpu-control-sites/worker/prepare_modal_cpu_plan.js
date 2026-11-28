import { validPlan } from "./experiment_input_contract.js";
import { sha256Hex as sha256 } from "./sha256.js";
import { canonicalJson } from "./canonical_json.js";
import { MODAL_PRICING_CHECKED_AT, MODAL_PRICING_SOURCE, MODAL_SANDBOX_CPU_LIMIT_CORES,
  MODAL_SANDBOX_MEMORY_LIMIT_MIB, MODAL_SANDBOX_RESOURCES, estimateModalSandboxCostUsd } from "./modal_cpu_policy.js";
import { HUMAN_AUTHORIZATION_TTL_SECONDS } from "./human_authorization_policy.js";

export async function prepareModalCpuPlan(env, owner, prepareArgs) {
  if (!validPlan(prepareArgs, env)) throw new Error("REGISTERED_WORKLOAD_OR_ARGUMENTS_INVALID");
  const fingerprint = await sha256(canonicalJson({
    workload: prepareArgs.workload, repository: prepareArgs.repository, source_sha: prepareArgs.commit,
    parameters: prepareArgs.parameters, runtime_seconds: prepareArgs.runtime_seconds, max_cost_usd: prepareArgs.max_cost_usd,
    image_digest: env.CPU_WORKLOAD_IMAGE_DIGEST,
    image_fingerprint: env.MODAL_WORKLOAD_IMAGE_FINGERPRINT || null,
  }, "INVALID_ARGUMENTS"));
  const planId = crypto.randomUUID().replaceAll("-", "");
  const now = Math.floor(Date.now() / 1000);
  const expires = now + HUMAN_AUTHORIZATION_TTL_SECONDS;
  await env.DB.prepare(`INSERT OR IGNORE INTO plans
      (id, owner_id, idempotency_key, fingerprint, workload, repository, source_sha, image_digest, parameters_json, runtime_seconds, max_cost_usd, state, created_at, expires_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'prepared', ?, ?)`).bind(planId, owner, prepareArgs.idempotency_key,
    fingerprint, prepareArgs.workload, prepareArgs.repository, prepareArgs.commit, env.CPU_WORKLOAD_IMAGE_DIGEST,
    JSON.stringify(prepareArgs.parameters), prepareArgs.runtime_seconds, prepareArgs.max_cost_usd, now, expires).run();
  const persisted = await env.DB.prepare("SELECT id, fingerprint, image_digest, state, expires_at FROM plans WHERE owner_id = ? AND idempotency_key = ?")
    .bind(owner, prepareArgs.idempotency_key).first();
  if (!persisted || persisted.fingerprint !== fingerprint || persisted.image_digest !== env.CPU_WORKLOAD_IMAGE_DIGEST) {
    throw new Error("IDEMPOTENCY_KEY_CONFLICT");
  }
  const estimatedCost = estimateModalSandboxCostUsd(prepareArgs.runtime_seconds);
  return { schema_version: 2, status: "ok", human_summary: `登録済みTinyStories推論planを準備しました。ここではまだ実行していません。ChatGPTでこのplanを確認し、experiment_submitの実行確認を承認した場合だけ開始します。別のブラウザーでサインインする必要はありません。CPU request/limitは1 physical core、メモリrequest/limitは512 MiB、最大実行時間は30秒です。現在の料金表でSandbox CPU・メモリ使用料の最大見積もりは約$${estimatedCost}です。CPU超過時はthrottle、メモリ超過時はOOMで実験が失敗します。Modal制御関数料金は含みません。`, run_id: persisted.id, plan_fingerprint: persisted.fingerprint, state: persisted.state, expires_at: persisted.expires_at, provider: "modal_cpu", approved_plan: { workload: prepareArgs.workload, repository: prepareArgs.repository, commit: prepareArgs.commit, prompt: prepareArgs.parameters.prompt, max_new_tokens: prepareArgs.parameters.max_new_tokens, seed: prepareArgs.parameters.seed, runtime_seconds: prepareArgs.runtime_seconds, estimated_sandbox_cost_usd: estimatedCost, max_cost_usd: prepareArgs.max_cost_usd, cpu_limit_physical_cores: MODAL_SANDBOX_CPU_LIMIT_CORES, memory_limit_mib: MODAL_SANDBOX_MEMORY_LIMIT_MIB, gpu_allowed: false, control_function_cost_included: false }, sandbox_resources: { ...MODAL_SANDBOX_RESOURCES }, estimated_sandbox_cost_usd: estimatedCost, max_sandbox_cost_usd: prepareArgs.max_cost_usd, control_function_cost_included: false, cost_is_estimate: true, credit_eligible: true, price_source: MODAL_PRICING_SOURCE, price_checked_at: MODAL_PRICING_CHECKED_AT, approval_required: true, authorization_surface: "chatgpt_mcp_write_confirmation", authorization_validity_seconds: HUMAN_AUTHORIZATION_TTL_SECONDS, max_runs_per_authorization: 1 };
}
