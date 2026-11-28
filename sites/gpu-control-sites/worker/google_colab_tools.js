import { createGoogleColabConnectionUrl, disconnectGoogleColab, googleColabConnectionConfigured,
  googleColabConnectionStatus } from "./google_colab_connection.js";
import { callGoogleColabMcpTool, googleColabStructuredResult } from "./google_colab_mcp_client.js";
import { projectGoogleColabCapabilities } from "./google_colab_capabilities.js";
import { googleColabAdmissionEnabled } from "./google_colab_policy.js";

const COLAB_TOOLS = new Set([
  "colab_connection_start", "colab_connection_status", "colab_connection_disconnect", "colab_capabilities",
]);
export function isGoogleColabTool(name) { return COLAB_TOOLS.has(name); }

export async function googleColabLifecycleConfigured(env) {
  if (!env?.DB || !env?.BUCKET || typeof env.BUCKET.put !== "function" || typeof env.BUCKET.get !== "function") return false;
  try {
    const rows = await env.DB.prepare(`SELECT name FROM sqlite_master WHERE type='table'
      AND name IN ('google_colab_run_operations','google_colab_run_artifacts')`).all();
    return Array.isArray(rows?.results) && rows.results.length === 2;
  } catch { return false; }
}

/** Read fresh owner-scoped subscription, GPU eligibility, and runtime facts. */
export async function readGoogleColabCapabilities(env, owner, options = {}) {
  const connection = await googleColabConnectionStatus(env.DB, owner);
  const configured = googleColabConnectionConfigured(env);
  const admissionEnabled = googleColabAdmissionEnabled(env);
  const executionLifecycleEnabled = await googleColabLifecycleConfigured(env);
  if (!configured || !connection.connected) return { configured, connected: connection.connected,
    account_email_redacted: connection.account_email_redacted || null, execution_lifecycle_enabled: false,
    admission_enabled: admissionEnabled, eligible_gpu_specs: [], active_runtime_count: null, active_gpu_runtime_count: null,
    blocking_reason: configured ? "GOOGLE_COLAB_CONNECTION_REQUIRED" : "GOOGLE_COLAB_OAUTH_NOT_CONFIGURED" };
  const [subscriptionResponse, specResponse, runtimeResponse] = await Promise.all([
    callGoogleColabMcpTool(env, owner, "get_subscription", {}, options),
    callGoogleColabMcpTool(env, owner, "list_runtime_specs", {}, options),
    callGoogleColabMcpTool(env, owner, "list_runtimes", {}, options),
  ]);
  const subscription = googleColabStructuredResult(subscriptionResponse);
  const specData = googleColabStructuredResult(specResponse);
  const runtimeData = googleColabStructuredResult(runtimeResponse);
  const capability = projectGoogleColabCapabilities(subscription, specData, runtimeData);
  return { configured: true, connected: true, account_email_redacted: connection.account_email_redacted,
    subscription_tier: capability.tier, eligible_gpu_specs: capability.eligibleGpuSpecs,
    active_runtime_count: capability.activeRuntimeCount, active_gpu_runtime_count: capability.activeGpuRuntimeCount,
    execution_lifecycle_enabled: executionLifecycleEnabled, admission_enabled: admissionEnabled,
    cost_terms: { per_run_usd: null, remaining_quota: null,
      semantics: "google_account_subscription_quota_not_quantified_per_run",
      quota_exhaustion_effect: "google_paid_account_reverts_to_free_tier_restrictions",
      compute_unit_balance_available_via_api: false, positive_compute_units_required_for_automation: true,
      positive_compute_units_verified: false, automatic_top_up_available: false, paid_fallback_allowed: false },
    execution_security: { network_egress: "unrestricted", private_data_allowed: false,
      provider_credentials_allowed: false, run_owned_runtime_deletion_requires_exact_plan_confirmation: true },
    blocking_reason: !executionLifecycleEnabled ? "COLAB_RUN_STORAGE_NOT_CONFIGURED"
      : !admissionEnabled ? "GOOGLE_COLAB_WORKLOAD_ADMISSION_DISABLED" : null,
    exact_run_cost_available: false };
}

/** Manage the authenticated owner's Google Colab identity connection. */
export async function handleGoogleColabTool(name, env, owner, options = {}) {
  if (!isGoogleColabTool(name)) return null;
  if (name === "colab_capabilities") {
    const capability = await readGoogleColabCapabilities(env, owner, options);
    if (!capability.connected || !capability.configured) return { schema_version: 2,
      status: "blocked", human_summary: "Google Colabの接続またはSites側OAuth設定がありません。Google APIは呼び出していません。",
      machine_state: capability, next_allowed_actions: capability.configured ? ["colab_connection_start"] : [],
      blocking_reason: capability.blocking_reason };
    return { schema_version: 2, status: "ok",
      human_summary: !capability.execution_lifecycle_enabled
        ? "Google ColabのGPU eligibilityを読み取りましたが、実行ライフサイクルのストレージ設定が未完了です。runtimeは作成していません。"
        : !capability.admission_enabled
          ? "Google ColabのGPU eligibilityは読み取りましたが、実行受付は閉じています。runtimeは作成していません。"
          : "Google ColabのGPU eligibilityと実行経路を確認しました。実験ごとにplanを作成し、ChatGPTの実行確認後にowner専用runtimeを使います。USD費用とCompute Unit残高はAPIで確認できません。",
      machine_state: capability, next_allowed_actions: capability.execution_lifecycle_enabled && capability.admission_enabled ? ["experiment_prepare"] : [],
      blocking_reason: capability.blocking_reason };
  }
  if (name === "colab_connection_status") {
    const connection = await googleColabConnectionStatus(env.DB, owner);
    return { schema_version: 2, status: "ok",
      human_summary: connection.connected ? "このGPU Control ownerにはGoogle Colab accountが接続されています。"
        : "Google Colab accountは未接続です。",
      machine_state: { configured: googleColabConnectionConfigured(env), ...connection },
      next_allowed_actions: connection.connected ? ["colab_connection_disconnect"]
        : googleColabConnectionConfigured(env) ? ["colab_connection_start"] : [],
      blocking_reason: googleColabConnectionConfigured(env) ? null : "GOOGLE_COLAB_OAUTH_NOT_CONFIGURED" };
  }
  if (name === "colab_connection_disconnect") {
    const disconnected = await disconnectGoogleColab(env.DB, env, owner);
    return { schema_version: 2, status: "ok",
      human_summary: disconnected.remote_revoked
        ? "Google Colab接続を削除し、Google側でもOAuth grantを失効しました。"
        : "Google Colab接続をSitesから削除しました。Google側での失効を確認できなかったため、必要ならGoogle Accountの接続済みアプリからGPU Controlの権限を取り消してください。",
      machine_state: disconnected, next_allowed_actions: googleColabConnectionConfigured(env) ? ["colab_connection_start"] : [],
      blocking_reason: null };
  }
  if (!googleColabConnectionConfigured(env)) return { schema_version: 2, status: "blocked",
    human_summary: "Google Colab接続のOAuth clientまたは暗号化設定が未完了です。GPU実行は開始していません。",
    machine_state: { configured: false, connected: false }, next_allowed_actions: [],
    blocking_reason: "GOOGLE_COLAB_OAUTH_NOT_CONFIGURED" };
  if (name === "colab_connection_start") {
    const current = await googleColabConnectionStatus(env.DB, owner);
    if (current.connected) return { schema_version: 2, status: "blocked",
      human_summary: "別のGoogleアカウントへ切り替える場合は、先に現在のColab接続を解除してください。",
      machine_state: { connected: true, account_email_redacted: current.account_email_redacted },
      next_allowed_actions: ["colab_connection_status", "colab_connection_disconnect"],
      blocking_reason: "GOOGLE_COLAB_RECONNECT_REQUIRES_DISCONNECT" };
    const link = await createGoogleColabConnectionUrl(env.DB, owner);
    return { schema_version: 2, status: "ok",
      human_summary: "Google Colabの接続リンクを作成しました。Googleで一度認証すると、このSites ownerにColab accountが紐付きます。OAuth tokenはチャットに返しません。",
      machine_state: { connected: false, authorization_url: link.authorization_url, expires_at: link.expires_at,
        requested_scopes: ["openid", "email", "https://www.googleapis.com/auth/colaboratory"],
        starts_runtime: false }, next_allowed_actions: ["colab_connection_status"], blocking_reason: null };
  }
  return { schema_version: 2, status: "error", human_summary: "Google Colab connection tool handling failed.",
    machine_state: {}, next_allowed_actions: [], blocking_reason: "GOOGLE_COLAB_TOOL_INVALID" };
}
