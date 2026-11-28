import { createGoogleColabConnectionUrl, disconnectGoogleColab, googleColabConnectionConfigured,
  googleColabConnectionStatus } from "./google_colab_connection.js";
import { callGoogleColabMcpTool, googleColabStructuredResult } from "./google_colab_mcp_client.js";

const COLAB_TOOLS = new Set([
  "colab_connection_start", "colab_connection_status", "colab_connection_disconnect", "colab_capabilities",
]);

export function isGoogleColabTool(name) { return COLAB_TOOLS.has(name); }

/** Manage the authenticated owner's Google Colab identity connection. */
export async function handleGoogleColabTool(name, env, owner, options = {}) {
  if (!isGoogleColabTool(name)) return null;
  if (name === "colab_capabilities") {
    const connection = await googleColabConnectionStatus(env.DB, owner);
    if (!googleColabConnectionConfigured(env) || !connection.connected) return { schema_version: 2,
      status: "blocked", human_summary: "Google Colabの接続またはSites側OAuth設定がありません。Google APIは呼び出していません。",
      machine_state: { configured: googleColabConnectionConfigured(env), connected: false,
        execution_lifecycle_enabled: false }, next_allowed_actions: googleColabConnectionConfigured(env)
          ? ["colab_connection_start"] : [], blocking_reason: connection.connected ? "GOOGLE_COLAB_OAUTH_NOT_CONFIGURED" : "GOOGLE_COLAB_CONNECTION_REQUIRED" };
    const [subscriptionResponse, specResponse, runtimeResponse] = await Promise.all([
      callGoogleColabMcpTool(env, owner, "get_subscription", {}, options),
      callGoogleColabMcpTool(env, owner, "list_runtime_specs", {}, options),
      callGoogleColabMcpTool(env, owner, "list_runtimes", {}, options),
    ]);
    const subscription = googleColabStructuredResult(subscriptionResponse);
    const specData = googleColabStructuredResult(specResponse);
    const runtimeData = googleColabStructuredResult(runtimeResponse);
    const tier = subscription.tier;
    const runtimeSpecs = specData.runtimeSpecs;
    const runtimes = runtimeData.runtimes;
    if (!new Set(["SUBSCRIPTION_TIER_FREE", "SUBSCRIPTION_TIER_PRO", "SUBSCRIPTION_TIER_PRO_PLUS"]).has(tier) ||
        !Array.isArray(runtimeSpecs) || runtimeSpecs.length > 200 || !Array.isArray(runtimes) || runtimes.length > 1_000) {
      throw new Error("GOOGLE_COLAB_RESPONSE_INVALID");
    }
    const gpuSpecs = runtimeSpecs.filter((item) => item?.key?.variant === "VARIANT_GPU" &&
      typeof item.key.accelerator === "string" && /^[A-Za-z0-9._-]{1,32}$/.test(item.key.accelerator) &&
      new Set(["SHAPE_STANDARD", "SHAPE_HIGHMEM"]).has(item.key.shape) && typeof item.eligible === "boolean")
      .map((item) => ({ accelerator: item.key.accelerator, shape: item.key.shape, eligible: item.eligible }));
    const existingGpuRuntimes = runtimes.filter((runtime) => runtime?.runtimeSpec?.key?.variant === "VARIANT_GPU").length;
    return { schema_version: 2, status: "ok",
      human_summary: "Google ColabアカウントとGoogleのGPU eligibilityを読み取りました。GPU Controlからの実験実行ライフサイクルはまだ無効です。",
      machine_state: { configured: true, connected: true, account_email: connection.account_email,
        subscription_tier: tier, eligible_gpu_specs: gpuSpecs.slice(0, 100), active_runtime_count: runtimes.length,
        active_gpu_runtime_count: existingGpuRuntimes, execution_lifecycle_enabled: false,
        blocking_reason: "COLAB_EXECUTION_LIFECYCLE_NOT_IMPLEMENTED", exact_run_cost_available: false },
      next_allowed_actions: [], blocking_reason: "COLAB_EXECUTION_LIFECYCLE_NOT_IMPLEMENTED" };
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
      machine_state: { connected: true, account_email: current.account_email },
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
