import { issueTrainingChallenge, confirmTrainingChallenge } from "./training_authorization.js";
import { sha256Hex as sha256 } from "./sha256.js";
import { isMcpToolReadOnly, listMcpTools, OUTPUT_SCHEMA, schemas } from "./mcp_tool_contract.js";
import { normalizeTrainingArguments, safeJson, validGatewayApprovedPlan, validGatewayPrepare,
  validProviderApprovedPlan, validToolArguments } from "./experiment_input_contract.js";
import { handleGithubTool, isGithubTool } from "./github_tools.js";
import { completeGoogleColabOAuth, beginGoogleColabOAuth, googleColabOAuthConfigured } from "./google_colab_connection.js";
import { handleGoogleColabTool, isGoogleColabTool } from "./google_colab_tools.js";
import { handleTrainingTool, isTrainingTool } from "./training_tools.js";
import { beginGithubInstallationOAuth, completeGithubInstallationOAuth, createOwnedRepositoryReadToken,
  exchangeGithubOAuthCode, githubAppOAuthConfigured,
  verifyGithubInstallation } from "./github_app_connection.js";
import { prepareRunpodExperiment, RUNPOD_WORKLOAD, validRunpodPrepare } from "./runpod_plan.js";
import { submitRunpodExperiment, synchronizeRunpodExperiment } from "./runpod_lifecycle.js";
import { callProviderAdapterTool, providerAdapterConfigured } from "./provider_adapter_client.js";
import { readModalGpuAccountEvidence } from "./modal_account_evidence.js";
import { registeredPrepareArguments, resolveZeroGpuPrepare } from "./registered_prepare.js";
import { WORKLOADS, WORKLOAD_IDS } from "./workload_registry.js";
import { prepareModalComputeBudgetReservation, readProviderBudgetPolicy, usdFromMicrousd, utcMonthKey } from "./provider_budget_policy.js";
import { MODAL_PRICING_CHECKED_AT, estimateModalSandboxCostUsd } from "./modal_cpu_policy.js";
import { getExperimentCapabilities } from "./provider_capabilities.js";
import { modalConfigured, modalPayload, modalRequest } from "./modal_http_client.js";
import { providerHealthDiagnostic, providerHealthDiagnosticForAuthorizedSubmit } from "./provider_health_diagnostic.js";
import { prepareModalCpuPlan } from "./prepare_modal_cpu_plan.js";
import { listExperiments } from "./experiment_list.js";
import { executionOrigin } from "./execution_origin.js";
import { readExperimentStatus } from "./experiment_status.js";
import { cancelLocalRun } from "./local_run_cancellation.js";
import { reconcileProviderRuns } from "./run_reconciliation.js";
import { submitModalCpuRun } from "./modal_cpu_submission.js";
import { readDelegatedPlan as delegatedPlan, persistProviderAdapterObservation,
  publicProviderAdapterResponse } from "./provider_adapter_run_store.js";
import { HUMAN_AUTHORIZATION_TTL_SECONDS } from "./human_authorization_policy.js";
import { canonicalJson as canonical } from "./canonical_json.js";
import { persistRunResultArtifact, readRunResultArtifact, runArtifactBytes, RUN_ARTIFACT_MAX_BYTES } from "./run_artifacts.js";
import { authenticateMcpAccessToken, beginMcpOAuthGitHubLogin, completeMcpOAuthGitHubLogin,
  createMcpOAuthConsent, exchangeMcpOAuthToken, isMcpOAuthGitHubState, mcpAuthorizationServerMetadata,
  mcpOAuthError, mcpProtectedResourceMetadata, registerMcpOAuthClient, revokeMcpOAuthToken,
  READ_SCOPE, EXECUTE_SCOPE } from "./mcp_oauth.js";

const LEGACY_VERSIONS = ["2025-03-26", "2025-06-18", "2025-11-25"];
const MCP_VERSION = "2026-07-28";
const MCP_VERSIONS = [...LEGACY_VERSIONS, MCP_VERSION];
const META_PREFIX = "io.modelcontextprotocol/";
const MAX_BODY_BYTES = 16 * 1024;
const WORKLOAD = WORKLOADS.tiny_stories.id;
const KAGGLE_WORKLOAD = WORKLOADS.kaggle_training.id;
const ZERO_GPU_WORKLOAD = WORKLOADS.huggingface_evaluation.id;
const MODAL_GPU_WORKLOAD = WORKLOADS.modal_gpu_canary.id;
const MODAL_GPU_PROVIDER_USAGE_LIMIT_USD = "30.00";
const ORBITUNE_REPOSITORY = WORKLOADS.kaggle_training.repository;
const ORBITUNE_SOURCE_SHA = WORKLOADS.kaggle_training.source_sha;
const GPU_CONTROL_REPOSITORY = WORKLOADS.modal_gpu_canary.repository;
const MODAL_GPU_SOURCE_SHA = WORKLOADS.modal_gpu_canary.source_sha;
const MODAL_GPU_IMAGE_DIGEST = WORKLOADS.modal_gpu_canary.adapter_manifest.image_digest;
const MODAL_STATUS_CHECK_WINDOW_SECONDS = 86400;
const MODAL_STATUS_CHECK_COOLDOWN_SECONDS = 3;
const MODAL_STATUS_CHECK_MAX_PER_WINDOW = 20;
// Hold a lost submit reservation beyond Modal's documented 150s Web Function
// request window and the fixed Sandbox runtime before releasing a missing run.
const MODAL_NOT_FOUND_RECOVERY_GRACE_SECONDS = 300;
const RUNPOD_PER_RUN_BUDGET_USD = WORKLOADS.runpod_canary.cost_ceiling_usd;
const MODAL_MODEL_ID = "karpathy/tinyllamas@0bd21da7698eaf29a0d7de3992de8a46ef624add/stories15M.bin";
const MODAL_MODEL_SHA256 = "cd590644d963867a2b6e5a1107f51fad663c41d79c149fbecbbb1f95fa81f49a";
const MODAL_TOKENIZER_SHA256 = "50a52ef822ee9e83de5ce9d0be0a025a773d019437f58b5ff9dcafb063ece361";
const SITE_PUBLIC_ORIGIN = "https://gpu-control-sites.unjuno.chatgpt.site";

function json(data, status = 200, headers = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", ...headers },
  });
}

function oauthJson(data, status = 200) {
  return json(data, status, { pragma: "no-cache", "x-content-type-options": "nosniff" });
}

function hasMediaType(request, expected) {
  return (request.headers.get("content-type") || "").split(";", 1)[0].trim().toLowerCase() === expected;
}

function rpcError(id, code, message) {
  return json({ jsonrpc: "2.0", id: id ?? null, error: { code, message } });
}

function mcpResult(id, value) {
  return json({ jsonrpc: "2.0", id, result: { content: [{ type: "text", text: JSON.stringify(value) }] } });
}

function envelope(name, value) {
  if (value && value.schema_version === 2 && ["blocked", "pending", "ok", "error"].includes(value.status) &&
      typeof value.human_summary === "string" && value.machine_state && typeof value.machine_state === "object") {
    return { next_allowed_actions: [], blocking_reason: null, ...value };
  }
  return {
    schema_version: 2,
    status: value?.status === "blocked" ? "blocked" : "ok",
    human_summary: typeof value?.human_summary === "string" ? value.human_summary : `${name} completed.`,
    machine_state: value && typeof value === "object" ? value : { value },
    next_allowed_actions: [],
    blocking_reason: null,
  };
}

function submitSummary(state) {
  const summaries = {
    queued: "この実験はqueue済みです。",
    running: "この実験は実行中です。",
    succeeded: "この実験は完了しています。",
    failed: "この実験は失敗として記録されています。",
    cancelled: "この実験はキャンセル済みです。",
  };
  return summaries[state] || "この実験の保存済み状態を取得しました。";
}

function randomHex(byteLength) {
  const bytes = crypto.getRandomValues(new Uint8Array(byteLength));
  return [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
  })[character]);
}

function htmlPage(title, content, status = 200) {
  const body = `<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${escapeHtml(title)}</title><style>body{font:16px/1.6 system-ui,sans-serif;max-width:720px;margin:3rem auto;padding:0 1rem;color:#171717}main{border:1px solid #ddd;border-radius:12px;padding:1.5rem}dt{font-weight:700;margin-top:1rem}dd{margin-left:0;overflow-wrap:anywhere}.cost{background:#fff6d5;padding:1rem;border-radius:8px}button{font:inherit;padding:.75rem 1rem}label{display:block;margin:1.5rem 0}</style><main><h1>${escapeHtml(title)}</h1>${content}</main></html>`;
  return new Response(body, { status, headers: {
    "content-type": "text/html; charset=utf-8", "cache-control": "no-store",
    "content-security-policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'",
    "referrer-policy": "no-referrer", "x-content-type-options": "nosniff", "x-frame-options": "DENY",
  } });
}

function authorizationUrl(_request, runId, fingerprint) {
  const url = new URL("/authorize", SITE_PUBLIC_ORIGIN);
  url.searchParams.set("run_id", runId);
  url.searchParams.set("plan_fingerprint", fingerprint);
  return url.toString();
}

function chatGPTSignInPath(returnTo) {
  let safeReturnTo = "/";
  if (typeof returnTo === "string" && returnTo.startsWith("/") && !returnTo.startsWith("//")) {
    try {
      const parsed = new URL(returnTo, "https://app.local");
      if (parsed.origin === "https://app.local" &&
          !["/signin-with-chatgpt", "/signout-with-chatgpt", "/callback"].includes(parsed.pathname)) {
        safeReturnTo = `${parsed.pathname}${parsed.search}${parsed.hash}`;
      }
    } catch { /* Fall back to the Site root for malformed return paths. */ }
  }
  return `/signin-with-chatgpt?return_to=${encodeURIComponent(safeReturnTo)}`;
}

function authorizationReturnPath(request) {
  const url = new URL(request.url);
  const runId = url.searchParams.get("run_id") || "";
  const fingerprint = url.searchParams.get("plan_fingerprint") || "";
  if (!/^[0-9a-f]{32}$/.test(runId) || !/^[0-9a-f]{64}$/.test(fingerprint)) return "/";
  const returnTo = new URL(url.pathname, SITE_PUBLIC_ORIGIN);
  returnTo.searchParams.set("run_id", runId);
  returnTo.searchParams.set("plan_fingerprint", fingerprint);
  return `${returnTo.pathname}${returnTo.search}`;
}

async function renderAuthorizationPage(request, env, owner) {
  const url = new URL(request.url);
  const runId = url.searchParams.get("run_id") || "";
  const fingerprint = url.searchParams.get("plan_fingerprint") || "";
  if (!/^[0-9a-f]{32}$/.test(runId) || !/^[0-9a-f]{64}$/.test(fingerprint)) {
    return htmlPage("承認リンクが無効です", "<p>チャットで実験planをもう一度準備してください。</p>", 400);
  }
  const now = Math.floor(Date.now() / 1000);
  const plan = await env.DB.prepare(`SELECT id, owner_id, fingerprint, workload, repository, source_sha,
      parameters_json, runtime_seconds, max_cost_usd, state, expires_at
    FROM plans WHERE id=? AND owner_id=? AND fingerprint=?`).bind(runId, owner, fingerprint).first();
  if (!plan || plan.state !== "prepared" || plan.expires_at < now) {
    return htmlPage("実験planを確認できません", "<p>このplanは期限切れ、使用済み、またはこのSitesアカウントのものではありません。チャットで新しいplanを準備してください。</p>", 404);
  }
  const prior = await env.DB.prepare(`SELECT authorized_at, expires_at, consumed_at FROM human_authorizations
    WHERE owner_id=? AND plan_id=? AND fingerprint=?`).bind(owner, runId, fingerprint).first();
  if (prior) {
    const message = prior.consumed_at !== null
      ? "<p>このplanの承認はすでに1回分の実行に使用されています。</p>"
      : prior.expires_at < now
        ? "<p>承認の有効期限が切れました。チャットで新しいplanを準備してください。</p>"
        : "<p>このplanは承認済みです。期限内にチャットへ戻り、実験を送信してください。</p>";
    return htmlPage("承認状態", message);
  }
  const token = randomHex(32);
  const challengeId = randomHex(16);
  const challengeExpiry = Math.min(now + HUMAN_AUTHORIZATION_TTL_SECONDS, plan.expires_at);
  if (challengeExpiry <= now) return htmlPage("実験planの期限切れ", "<p>チャットで新しいplanを準備してください。</p>", 410);
  await env.DB.prepare(`INSERT OR REPLACE INTO authorization_challenges
      (id, owner_id, plan_id, fingerprint, token_hash, created_at, expires_at, consumed_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, NULL)`)
    .bind(challengeId, owner, runId, fingerprint, await sha256(token), now, challengeExpiry).run();
  let parameters;
  try { parameters = JSON.parse(plan.parameters_json); } catch { return htmlPage("planの形式が無効です", "<p>チャットで新しいplanを準備してください。</p>", 500); }
  const estimatedCost = estimateModalSandboxCostUsd(plan.runtime_seconds);
  const action = authorizationUrl(request, runId, fingerprint);
  const content = `<p>以下の内容で登録済みのCPU推論を1回実行する承認です。GPUは使いません。</p><dl>
    <dt>Workload</dt><dd>${escapeHtml(plan.workload)}</dd>
    <dt>Repository / commit</dt><dd>${escapeHtml(plan.repository)}<br><code>${escapeHtml(plan.source_sha)}</code></dd>
    <dt>Prompt</dt><dd><code>${escapeHtml(parameters.prompt)}</code></dd>
    <dt>生成上限 / seed</dt><dd>${escapeHtml(parameters.max_new_tokens)} tokens / ${escapeHtml(parameters.seed)}</dd>
    <dt>最大実行時間</dt><dd>${escapeHtml(plan.runtime_seconds)}秒</dd>
    <dt>固定リソース上限</dt><dd>CPU request/limit: 1 physical core / memory request/limit: 512 MiB</dd></dl>
    <p>CPUは上限を超えて使えず、超過時はthrottleされます。メモリ上限超過時はSandboxがOOM終了し、実験が失敗します。</p>
    <p>現在の料金表（${MODAL_PRICING_CHECKED_AT}確認）では、このplanの最大Sandbox CPU・メモリ料金見積もりは約$${estimatedCost}です。</p>
    <p class="cost">Sandbox CPU・メモリのplan上限は <strong>$${escapeHtml(plan.max_cost_usd)}</strong> です。この見積もりは固定リソース上限と実行時間、確認時点の料金に基づきます。料金表が変わると見積もりも変わります。Modal制御関数料金はこの上限に含まれず、別途発生する場合があります。アカウント残高やクレジットは追加料金が発生しない保証ではありません。</p>
    <p>この承認はこのplanにだけ紐づき、有効期限は最大10分かplan期限までで、1回の送信で消費されます。</p>
    <form method="post" action="${escapeHtml(action)}">
      <input type="hidden" name="run_id" value="${escapeHtml(runId)}">
      <input type="hidden" name="plan_fingerprint" value="${escapeHtml(fingerprint)}">
      <input type="hidden" name="challenge" value="${escapeHtml(token)}">
      <label><input type="checkbox" name="confirm" value="yes" required> 表示された内容と料金条件を確認し、この実験の実行を承認します。</label>
      <button type="submit">このplanを1回承認する</button>
    </form>`;
  return htmlPage("実験の実行を確認", content);
}

async function renderTrainingAuthorizationPage(request, env, owner) {
  const url = new URL(request.url);
  const runId = url.searchParams.get("run_id") || "";
  const fingerprint = url.searchParams.get("plan_fingerprint") || "";
  if (!/^[0-9a-f]{32}$/.test(runId) || !/^[0-9a-f]{64}$/.test(fingerprint)) {
    return htmlPage("承認リンクが無効です", "<p>チャットで学習計画を確認してください。</p>", 400);
  }
  const now = Math.floor(Date.now() / 1000);
  const row = await env.DB.prepare(`SELECT plan_json FROM training_plans
    WHERE id=? AND owner_id=? AND fingerprint=? AND expires_at>?
      AND cancelled_at IS NULL AND dispatch_claimed_at IS NULL`).bind(runId, owner, fingerprint, now).first();
  if (!row) return htmlPage("学習計画を確認できません", "<p>チャットで学習計画の状態を確認してください。</p>", 404);
  const plan = JSON.parse(row.plan_json);
  const challenge = await issueTrainingChallenge(env.DB, owner, runId, fingerprint,
    env.MAP_TRAINING_CONTROL_PLANE_SHA, now);
  if (!challenge) return htmlPage("承認状態", "<p>チャットに戻り、学習計画の状態を確認してください。</p>");
  const evidence = plan.provider_evidence;
  const accountEvidenceDetails = evidence ? `<dt>Modal Workspace利用証拠</dt><dd>上限 USD ${escapeHtml(evidence.usage_limit_usd)} / L4料金 USD ${escapeHtml(evidence.hourly_price_usd)}/h / クレジット利用 USD ${escapeHtml(evidence.credits_used_usd)} / 請求 USD ${escapeHtml(evidence.charges_usd)} / 確認 ${escapeHtml(new Date(evidence.verified_at * 1000).toISOString())}</dd>` : "";
  return htmlPage("GPU学習の実行を確認", `<dl>
    <dt>リポジトリとコミット</dt><dd>${escapeHtml(plan.repository)}<br><code>${escapeHtml(plan.commit)}</code></dd>
    <dt>実行イメージ</dt><dd><code>${escapeHtml(plan.image_digest)}</code></dd>
    <dt>プロバイダーとGPU</dt><dd>Modal / ${escapeHtml(plan.gpu)} × ${escapeHtml(plan.gpu_count)}</dd>
    <dt>データセット</dt><dd>${escapeHtml(plan.dataset)}</dd>
    <dt>run名</dt><dd>${escapeHtml(plan.run_name)}</dd>
    <dt>学習step上限</dt><dd>${escapeHtml(plan.steps.toLocaleString("en-US"))}</dd>
    <dt>実行時間上限</dt><dd>${escapeHtml(plan.runtime_seconds)}秒</dd>
    <dt>計画の費用上限</dt><dd>USD ${escapeHtml((plan.max_cost_microusd / 1000000).toFixed(6))}</dd>
    ${accountEvidenceDetails}
    </dl>
    <form method="post" action="/authorize-training">
      <input type="hidden" name="run_id" value="${runId}">
      <input type="hidden" name="plan_fingerprint" value="${fingerprint}">
      <input type="hidden" name="challenge" value="${challenge.token}">
      <label><input type="checkbox" name="confirm" value="yes" required> この条件で有料のGPU学習を1回承認します。</label>
      <button type="submit">承認する</button>
    </form>`);
}

async function handleAuthorizationRequest(request, env) {
  const authenticatedUserId = request.headers.get("oai-authenticated-user-id");
  const owner = userId(request, env);
  if (!authenticatedUserId) {
    const signInPath = chatGPTSignInPath(authorizationReturnPath(request));
    return htmlPage("ChatGPT Sitesへのサインインが必要です",
      `<p>あなたのChatGPTアカウントでサインインして、このplanの確認に戻ってください。</p><p><a href="${escapeHtml(signInPath)}" target="_top" rel="noreferrer">ChatGPTでサインイン</a></p>`, 401);
  }
  if (!owner) return htmlPage("このアカウントは許可されていません", "<p>GPU Controlを許可したChatGPTアカウントで開いてください。</p>", 403);
  if (!env.DB) return htmlPage("データベースを利用できません", "<p>このSiteでは承認を記録できません。</p>", 503);
  const training = new URL(request.url).pathname === "/authorize-training";
  if (training && !/^[0-9a-f]{40}$/.test(env.MAP_TRAINING_CONTROL_PLANE_SHA || "")) {
    return htmlPage("学習の承認を受け付けていません", "<p>チャットで学習計画の状態を確認してください。</p>", 503);
  }
  if (request.method === "GET") {
    return training ? renderTrainingAuthorizationPage(request, env, owner)
      : renderAuthorizationPage(request, env, owner);
  }
  if (request.method !== "POST") return htmlPage("Method Not Allowed", "<p>この操作にはGETまたはPOSTを使用してください。</p>", 405);
  const url = new URL(request.url);
  const origin = request.headers.get("origin");
  const fetchSite = request.headers.get("sec-fetch-site");
  if (url.origin !== SITE_PUBLIC_ORIGIN || origin !== SITE_PUBLIC_ORIGIN || (fetchSite && fetchSite !== "same-origin") ||
      !request.headers.get("content-type")?.toLowerCase().startsWith("application/x-www-form-urlencoded")) {
    return htmlPage("リクエストを確認できません", "<p>Siteの確認ページから操作してください。</p>", 403);
  }
  let form;
  try { form = await readUrlEncodedForm(request); }
  catch (error) {
    return htmlPage(error?.message === "FORM_TOO_LARGE" ? "リクエストが大きすぎます" : "承認フォームを読み取れません",
      "<p>確認ページを開き直してください。</p>", error?.message === "FORM_TOO_LARGE" ? 413 : 400);
  }
  const runId = String(form.get("run_id") || "");
  const fingerprint = String(form.get("plan_fingerprint") || "");
  const token = String(form.get("challenge") || "");
  if ([...form.keys()].sort().join(",") !== "challenge,confirm,plan_fingerprint,run_id" ||
      ["challenge", "confirm", "plan_fingerprint", "run_id"].some((key) => form.getAll(key).length !== 1) ||
      form.get("confirm") !== "yes" || !/^[0-9a-f]{32}$/.test(runId) ||
      !/^[0-9a-f]{64}$/.test(fingerprint) || !/^[0-9a-f]{64}$/.test(token)) {
    return htmlPage("承認内容が不完全です", "<p>チャットから承認リンクを開き直してください。</p>", 400);
  }
  const now = Math.floor(Date.now() / 1000);
  if (training) {
    const confirmed = await confirmTrainingChallenge(env.DB, owner, runId, fingerprint,
      env.MAP_TRAINING_CONTROL_PLANE_SHA, token, now);
    return confirmed
      ? htmlPage("学習計画を承認しました", "<p>チャットに戻り、この学習計画を実行してください。</p>")
      : htmlPage("承認できませんでした", "<p>チャットで学習計画の状態を確認してください。</p>", 409);
  }
  const challengeHash = await sha256(token);
  const authorizationId = randomHex(16);
  let results;
  try {
    results = await env.DB.batch([
      env.DB.prepare(`UPDATE authorization_challenges SET consumed_at=?
        WHERE token_hash=? AND owner_id=? AND plan_id=? AND fingerprint=? AND expires_at>=? AND consumed_at IS NULL
          AND EXISTS (SELECT 1 FROM plans p WHERE p.id=? AND p.owner_id=? AND p.fingerprint=? AND p.state='prepared' AND p.expires_at>=?)`)
        .bind(now, challengeHash, owner, runId, fingerprint, now, runId, owner, fingerprint, now),
      env.DB.prepare(`INSERT INTO human_authorizations
        (id, owner_id, plan_id, fingerprint, authorization_reference, authorized_at, expires_at, consumed_at)
        SELECT ?, c.owner_id, c.plan_id, c.fingerprint, c.id, ?, MIN(c.expires_at, p.expires_at), NULL
        FROM authorization_challenges c JOIN plans p ON p.id=c.plan_id
        WHERE c.token_hash=? AND c.owner_id=? AND c.plan_id=? AND c.fingerprint=? AND c.consumed_at=?
          AND p.state='prepared' AND p.expires_at>=?
          AND NOT EXISTS (SELECT 1 FROM human_authorizations a WHERE a.plan_id=c.plan_id)`)
        .bind(authorizationId, now, challengeHash, owner, runId, fingerprint, now, now),
    ]);
  } catch {
    return htmlPage("承認を記録できませんでした", "<p>チャットに戻り、planの状態を確認してください。</p>", 409);
  }
  const authorized = results?.[1]?.meta?.changes === 1;
  if (!authorized) return htmlPage("承認リンクは期限切れか使用済みです", "<p>チャットで状態を確認するか、新しいplanを準備してください。</p>", 409);
  return htmlPage("このplanを承認しました", "<p>承認はこのplanに1回だけ有効です。チャットに戻り、実験を送信してください。</p>");
}

async function handleGithubSetup(request, env) {
  if (request.method !== "GET") return htmlPage("GitHub接続", "<p>このcallbackはGETのみ受け付けます。</p>", 405);
  if (!env.DB || !githubAppOAuthConfigured(env)) return htmlPage("GitHub接続を確認できません",
    "<p>GPU Control側のGitHub App設定がまだ完了していません。</p>", 503);
  const url = new URL(request.url);
  const state = url.searchParams.get("state") || "";
  const installationId = url.searchParams.get("installation_id") || "";
  if (url.searchParams.get("setup_action") !== "install") return htmlPage("GitHub接続を完了できません",
    "<p>GitHub Appの新規installから接続を開始してください。設定変更後はチャットで新しい接続linkを作成してください。</p>", 400);
  try {
    const installation = await verifyGithubInstallation(env, installationId);
    const authorization = await beginGithubInstallationOAuth(env.DB, state, installationId,
      installation, env);
    return new Response(null, { status: 302, headers: { location: authorization.authorization_url,
      "set-cookie": authorization.pkce_cookie, "cache-control": "no-store", "referrer-policy": "no-referrer" } });
  } catch {
    return htmlPage("GitHub接続を完了できません",
      "<p>接続linkが期限切れ、使用済み、またはAppのrepository権限が条件を満たしません。チャットで新しい接続linkを作成してください。</p>", 400);
  }
}

async function handleGithubOAuthCallback(request, env) {
  if (request.method !== "GET") return htmlPage("GitHub接続", "<p>このcallbackはGETのみ受け付けます。</p>", 405);
  if (!env.DB || !githubAppOAuthConfigured(env)) return htmlPage("GitHub接続を確認できません",
    "<p>GPU Control側のGitHub App設定がまだ完了していません。</p>", 503);
  const url = new URL(request.url);
  const finish = (response, oauthKind = "github") => {
    response.headers.append("set-cookie", "__Host-gpu-control-oauth=; Max-Age=0; Path=/; Secure; HttpOnly; SameSite=Lax");
    if (oauthKind === "mcp") response.headers.append("set-cookie", "__Host-gpu-control-mcp-oauth=; Max-Age=0; Path=/; Secure; HttpOnly; SameSite=Lax");
    response.headers.set("cache-control", "no-store");
    response.headers.set("referrer-policy", "no-referrer");
    return response;
  };
  const callback = new URL(env.GITHUB_APP_OAUTH_CALLBACK_URL);
  if (`${url.origin}${url.pathname}` !== `${callback.origin}${callback.pathname}`) {
    return finish(htmlPage("GitHub接続を完了できません", "<p>接続先URLが設定と一致しません。</p>", 400));
  }
  const state = url.searchParams.get("state") || "";
  if (url.searchParams.has("error")) {
    const mcpOAuth = await isMcpOAuthGitHubState(env.DB, state);
    return finish(htmlPage("GitHub接続をキャンセルしました",
      "<p>接続を許可しませんでした。MCPクライアントへ戻ってください。</p>", 400), mcpOAuth ? "mcp" : "github");
  }
  const code = url.searchParams.get("code") || "";
  const mcpOAuth = await isMcpOAuthGitHubState(env.DB, state);
  const cookie = request.headers.get("cookie") || "";
  const cookieName = mcpOAuth ? "__Host-gpu-control-mcp-oauth=" : "__Host-gpu-control-oauth=";
  const cookieValue = cookie.split(";").map((item) => item.trim())
    .find((item) => item.startsWith(cookieName))?.slice(cookieName.length) || "";
  const [cookieState, codeVerifier, ...extra] = cookieValue.split(".");
  if (!(mcpOAuth ? /^[A-Za-z0-9_-]{43}$/.test(state) : /^[a-f0-9]{64}$/.test(state)) || cookieState !== state || extra.length !== 0 ||
      !/^[A-Za-z0-9._~-]{43,128}$/.test(codeVerifier || "")) {
    return finish(htmlPage("GitHub接続を完了できません",
      "<p>本人確認stateまたはPKCE verifierを確認できません。新しい接続linkを作成してください。</p>", 400));
  }
  try {
    const userToken = await exchangeGithubOAuthCode(env, code, codeVerifier);
    if (mcpOAuth) {
      const completed = await completeMcpOAuthGitHubLogin(env.DB, state, userToken);
      return finish(completed.response, "mcp");
    }
    const connected = await completeGithubInstallationOAuth(env.DB, state, userToken);
    return finish(htmlPage("GitHub接続完了", `<p>${escapeHtml(connected.account_login)}の選択済みrepositoryをGPU Controlへ接続しました。</p>
      <p>GitHub利用者本人がinstallationへアクセスできることを確認しました。短時間のuser tokenは保存せず破棄しました。</p>
      <p>許可されたのは選択repositoryのContents readとMetadata readです。installation tokenもGPU Controlの実験コンテナへ渡しません。</p>
      <p>チャットへ戻り、github_repositoriesで接続結果を確認できます。</p>`));
  } catch {
    return finish(htmlPage("GitHub接続を完了できません",
      "<p>GitHub本人確認が期限切れ、使用済み、またはこのGPU Control ownerへリンク済みの本人確認を完了できません。必要ならChatGPTのGPU ControlでGitHub接続を確認し、MCP clientから最初の接続をやり直してください。</p>", 400), mcpOAuth ? "mcp" : "github");
  }
}

function googleColabOAuthCookie(request) {
  const cookie = request.headers.get("cookie") || "";
  return cookie.split(";").map((item) => item.trim())
    .find((item) => item.startsWith("__Host-gpu-control-colab-oauth="))
    ?.slice("__Host-gpu-control-colab-oauth=".length) || "";
}

function clearGoogleColabOAuthCookie(response) {
  response.headers.set("set-cookie", "__Host-gpu-control-colab-oauth=; Max-Age=0; Path=/; Secure; HttpOnly; SameSite=Lax");
  response.headers.set("cache-control", "no-store");
  response.headers.set("referrer-policy", "no-referrer");
  return response;
}

async function handleGoogleColabSetup(request, env) {
  if (request.method !== "GET") return htmlPage("Google Colab接続", "<p>この接続はGETのみ受け付けます。</p>", 405);
  if (!env.DB || !googleColabOAuthConfigured(env) || !env.GOOGLE_COLAB_TOKEN_ENCRYPTION_KEY) {
    return htmlPage("Google Colab接続を確認できません", "<p>GPU Control側のGoogle OAuth設定がまだ完了していません。</p>", 503);
  }
  const state = new URL(request.url).searchParams.get("state") || "";
  try {
    const authorization = await beginGoogleColabOAuth(env.DB, state, env);
    return new Response(null, { status: 302, headers: {
      location: authorization.authorization_url, "set-cookie": authorization.pkce_cookie,
      "cache-control": "no-store", "referrer-policy": "no-referrer",
    } });
  } catch {
    return htmlPage("Google Colab接続を開始できません",
      "<p>接続リンクが期限切れ、使用済み、またはSitesのOAuth設定が不足しています。チャットで新しい接続リンクを作成してください。</p>", 400);
  }
}

async function handleGoogleColabOAuthCallback(request, env) {
  if (request.method !== "GET") return clearGoogleColabOAuthCookie(
    htmlPage("Google Colab接続", "<p>このcallbackはGETのみ受け付けます。</p>", 405));
  if (!env.DB || !googleColabOAuthConfigured(env)) return clearGoogleColabOAuthCookie(
    htmlPage("Google Colab接続を確認できません", "<p>GPU Control側のGoogle OAuth設定がまだ完了していません。</p>", 503));
  const url = new URL(request.url);
  let callback;
  try { callback = new URL(env.GOOGLE_COLAB_OAUTH_CALLBACK_URL); } catch { callback = null; }
  if (!callback || url.origin + url.pathname !== callback.origin + callback.pathname) {
    return clearGoogleColabOAuthCookie(htmlPage("Google Colab接続を完了できません",
      "<p>接続先URLが設定と一致しません。</p>", 400));
  }
  if (url.searchParams.has("error")) return clearGoogleColabOAuthCookie(
    htmlPage("Google Colab接続をキャンセルしました", "<p>チャットに戻り、必要なら新しい接続リンクを作成してください。</p>", 400));
  const oauthState = url.searchParams.get("state") || "";
  const code = url.searchParams.get("code") || "";
  const [cookieState, verifier, ...extra] = googleColabOAuthCookie(request).split(".");
  if (url.searchParams.getAll("state").length !== 1 || url.searchParams.getAll("code").length !== 1 ||
      !/^[a-f0-9]{64}$/.test(oauthState) || cookieState !== oauthState || extra.length !== 0 ||
      !/^[A-Za-z0-9_-]{43}$/.test(verifier || "") || !/^[A-Za-z0-9._~-]{1,2048}$/.test(code)) {
    return clearGoogleColabOAuthCookie(htmlPage("Google Colab接続を完了できません",
      "<p>接続リンクが期限切れか、ブラウザー確認に失敗しました。チャットで新しいリンクを作成してください。</p>", 400));
  }
  try {
    const linked = await completeGoogleColabOAuth(env.DB, env, oauthState, verifier, code);
    const body = "<p>Googleアカウント <strong>" + escapeHtml(linked.account_email) +
      "</strong> をGPU Control ownerに接続しました。</p><p>チャットに戻り、Colab接続状態を確認してください。</p>";
    return clearGoogleColabOAuthCookie(htmlPage("Google Colabを接続しました", body));
  } catch {
    return clearGoogleColabOAuthCookie(htmlPage("Google Colab接続を完了できません",
      "<p>Googleの認証を検証または安全に保存できませんでした。チャットで新しい接続リンクを作成してください。</p>", 400));
  }
}

function clearCookie(name) {
  return `${name}=; Max-Age=0; Path=/; Secure; HttpOnly; SameSite=Lax`;
}

async function handleMcpOAuthAuthorization(request, env) {
  if (!env.DB) return htmlPage("GPU Control OAuthを利用できません", "<p>owner-scoped storage is not configured.</p>", 503);
  if (request.method === "GET") {
    try {
      const url = new URL(request.url);
      const getOne = (name) => url.searchParams.getAll(name).length === 1 ? url.searchParams.get(name) : null;
      const consent = await createMcpOAuthConsent(env.DB, {
        client_id: getOne("client_id"), redirect_uri: getOne("redirect_uri"), response_type: getOne("response_type"),
        scope: getOne("scope"), state: getOne("state"), code_challenge: getOne("code_challenge"),
        code_challenge_method: getOne("code_challenge_method"), resource: getOne("resource"),
      }, url.origin);
      return consent.response;
    } catch (error) {
      const message = mcpOAuthError(error);
      return htmlPage("GPU Controlへの接続を開始できません",
        `<p>OAuth要求を確認できませんでした（${escapeHtml(message)}）。MCPクライアント設定を確認してください。</p>`, 400);
    }
  }
  if (request.method !== "POST") return htmlPage("Method Not Allowed", "<p>GETまたはPOSTを使用してください。</p>", 405);
  try {
    const form = await readUrlEncodedForm(request);
    const csrf = form.get("csrf") || "";
    const cookie = request.headers.get("cookie") || "";
    const savedCsrf = cookie.split(";").map((item) => item.trim())
      .find((item) => item.startsWith("__Host-gpu-control-mcp-consent="))
      ?.slice("__Host-gpu-control-mcp-consent=".length) || "";
    if (!csrf || csrf !== savedCsrf) throw new Error("MCP_OAUTH_CONSENT_CSRF_INVALID");
    const login = await beginMcpOAuthGitHubLogin(env.DB, csrf, env);
    return new Response(null, { status: 302, headers: { location: login.authorization_url,
      "set-cookie": login.cookie, "cache-control": "no-store", "referrer-policy": "no-referrer" } });
  } catch (error) {
    const message = mcpOAuthError(error);
    const detail = message === "MCP_OAUTH_OWNER_LINK_REQUIRED"
      ? "先にChatGPTのGPU ControlでGitHub接続を完了してください。"
      : `認可を開始できませんでした（${escapeHtml(message)}）。最初のMCP接続からやり直してください。`;
    return htmlPage("GPU Controlへの接続を完了できません", `<p>${detail}</p>`, 400,
      { "set-cookie": clearCookie("__Host-gpu-control-mcp-consent") });
  }
}

async function handleMcpOAuthRegistration(request, env) {
  if (request.method !== "POST") return oauthJson({ error: "invalid_request" }, 405);
  if (!env.DB || !hasMediaType(request, "application/json")) {
    return oauthJson({ error: "invalid_client_metadata" }, 400);
  }
  try {
    const body = await readJson(request, 16 * 1024);
    const result = await registerMcpOAuthClient(env.DB, body, request.headers.get("cf-connecting-ip"));
    return oauthJson(result, 201);
  } catch (error) {
    const code = mcpOAuthError(error);
    const status = code === "MCP_OAUTH_REGISTRATION_RATE_LIMITED" ? 429
      : ["MCP_OAUTH_REGISTRATION_RATE_LIMIT_UNAVAILABLE", "MCP_OAUTH_REGISTRATION_STORAGE_UNAVAILABLE"].includes(code) ? 503 : 400;
    return oauthJson({ error: status === 429 ? "temporarily_unavailable" : "invalid_client_metadata" }, status);
  }
}

async function handleMcpOAuthToken(request, env) {
  if (request.method !== "POST") return oauthJson({ error: "invalid_request" }, 405);
  if (!env.DB || request.headers.has("authorization") || !hasMediaType(request, "application/x-www-form-urlencoded")) {
    return oauthJson({ error: "invalid_request" }, 400);
  }
  try { return await exchangeMcpOAuthToken(env.DB, await readUrlEncodedForm(request), new URL(request.url).origin); }
  catch { return oauthJson({ error: "server_error" }, 500); }
}

async function handleMcpOAuthRevoke(request, env) {
  if (request.method !== "POST") return oauthJson({ error: "invalid_request" }, 405);
  if (!env.DB || request.headers.has("authorization") || !hasMediaType(request, "application/x-www-form-urlencoded")) {
    return oauthJson({ error: "invalid_request" }, 400);
  }
  try { return await revokeMcpOAuthToken(env.DB, await readUrlEncodedForm(request)); }
  catch { return oauthJson({ error: "server_error" }, 500); }
}

async function modalGpuProviderEvidence(env, now) {
  return readModalGpuAccountEvidence(env, { gpu: "T4", usageLimitUsd: MODAL_GPU_PROVIDER_USAGE_LIMIT_USD, now });
}

function userId(request, env) {
  const id = request.headers.get("oai-authenticated-user-id");
  if (!id || id.length > 256) return null;
  const allowed = new Set(typeof env.GPU_CONTROL_ALLOWED_USER_IDS === "string"
    ? env.GPU_CONTROL_ALLOWED_USER_IDS.split(",").map((value) => value.trim()).filter(Boolean)
    : []);
  return allowed.has(id) ? id : null;
}

async function authenticateMcpPrincipal(request, env) {
  const platformIdentity = request.headers.get("oai-authenticated-user-id");
  if (platformIdentity) {
    const owner = userId(request, env);
    return owner ? { owner_id: owner, auth_method: "chatgpt_sites", scopes: [READ_SCOPE, EXECUTE_SCOPE] }
      : { denied: "forbidden" };
  }
  const authorization = request.headers.get("authorization") || "";
  const match = authorization.match(/^Bearer (gpc_at_[A-Za-z0-9_-]{43})$/);
  if (!match || !env.DB) return null;
  return authenticateMcpAccessToken(env.DB, match[1], `${new URL(request.url).origin}/mcp`);
}

function mcpAuthorizationChallenge(request, { error = null, scope = READ_SCOPE } = {}) {
  const resourceMetadata = `${new URL(request.url).origin}/.well-known/oauth-protected-resource`;
  const challenge = [`Bearer resource_metadata="${resourceMetadata}"`, `scope="${scope}"`];
  if (error) challenge.push(`error="${error}"`);
  return new Response(null, { status: ["insufficient_scope", "forbidden"].includes(error) ? 403 : 401, headers: {
    "www-authenticate": challenge.join(", "), "cache-control": "no-store", "content-length": "0",
  } });
}

async function readJson(request, limit = MAX_BODY_BYTES) {
  const declared = Number(request.headers.get("content-length") || 0);
  if (declared > limit) throw new Error("BODY_TOO_LARGE");
  if (!request.body) throw new Error("INVALID_JSON");
  const reader = request.body.getReader();
  const chunks = [];
  let size = 0;
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > limit) {
        await reader.cancel();
        throw new Error("BODY_TOO_LARGE");
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
  return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
}

async function readUrlEncodedForm(request, limit = 4096) {
  const declared = Number(request.headers.get("content-length") || 0);
  if (declared > limit) throw new Error("FORM_TOO_LARGE");
  if (!request.body) throw new Error("INVALID_FORM");
  const reader = request.body.getReader();
  const chunks = [];
  let size = 0;
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > limit) {
        await reader.cancel();
        throw new Error("FORM_TOO_LARGE");
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
  return new URLSearchParams(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
}

async function reserveModalStatusCheck(env, now) {
  const result = await env.DB.prepare(`INSERT INTO modal_status_check_limits
      (scope, window_started_at, last_checked_at, call_count)
    VALUES ('workspace', ?, ?, 1)
    ON CONFLICT(scope) DO UPDATE SET
      window_started_at=CASE
        WHEN modal_status_check_limits.window_started_at <= excluded.window_started_at - ?
          THEN excluded.window_started_at
        ELSE modal_status_check_limits.window_started_at END,
      last_checked_at=excluded.last_checked_at,
      call_count=CASE
        WHEN modal_status_check_limits.window_started_at <= excluded.window_started_at - ?
          THEN 1
        ELSE modal_status_check_limits.call_count + 1 END
    WHERE modal_status_check_limits.window_started_at <= excluded.window_started_at - ?
      OR (modal_status_check_limits.call_count < ?
        AND modal_status_check_limits.last_checked_at <= excluded.last_checked_at - ?)`)
    .bind(now, now, MODAL_STATUS_CHECK_WINDOW_SECONDS, MODAL_STATUS_CHECK_WINDOW_SECONDS,
      MODAL_STATUS_CHECK_WINDOW_SECONDS, MODAL_STATUS_CHECK_MAX_PER_WINDOW,
      MODAL_STATUS_CHECK_COOLDOWN_SECONDS).run();
  return result?.meta?.changes === 1;
}

async function authorizeFreeProviderPolicy(env, { runId, provider, fingerprint, now }) {
  const inserted = await env.DB.prepare(`INSERT OR IGNORE INTO provider_free_run_authorizations
      (run_id, provider, plan_fingerprint, authorized_microusd, created_at)
    SELECT ?, p.provider, ?, 0, ? FROM provider_free_policies p
    WHERE p.provider=? AND p.max_cost_microusd=0 AND p.paid_fallback_allowed=0`)
    .bind(runId, fingerprint, now, provider).run();
  const authorization = await env.DB.prepare(`SELECT provider, plan_fingerprint, authorized_microusd
    FROM provider_free_run_authorizations WHERE run_id=?`).bind(runId).first();
  return inserted?.meta?.changes === 1 ||
    (authorization?.provider === provider && authorization?.plan_fingerprint === fingerprint &&
      authorization?.authorized_microusd === 0);
}

async function reserveModalGpuLease(env, { runId, fingerprint, now }) {
  const inserted = await env.DB.prepare(`INSERT OR IGNORE INTO modal_gpu_active_lease
      (scope, run_id, plan_fingerprint, state, acquired_at, updated_at)
    VALUES ('workspace', ?, ?, 'submitting', ?, ?)`)
    .bind(runId, fingerprint, now, now).run();
  const lease = await env.DB.prepare(`SELECT run_id, plan_fingerprint, state
    FROM modal_gpu_active_lease WHERE scope='workspace'`).first();
  return inserted?.meta?.changes === 1 ||
    (lease?.run_id === runId && lease?.plan_fingerprint === fingerprint &&
      ["submitting", "active", "cancel_pending"].includes(lease?.state));
}

async function reserveProviderBudget(env, { runId, provider, requestedMicrousd, now }) {
  const periodKey = utcMonthKey(now);
  const inserted = await env.DB.prepare(`INSERT INTO provider_budget_reservations
      (run_id, provider, period_key, reserved_microusd, created_at)
    SELECT ?, p.provider, ?, ?, ? FROM provider_budget_policies p
    WHERE p.provider=? AND ?<=p.per_run_limit_microusd
      AND (p.monthly_limit_microusd IS NULL OR
        COALESCE((SELECT SUM(r.reserved_microusd) FROM provider_budget_reservations r
          WHERE r.provider=p.provider AND r.period_key=?), 0) + ? <= p.monthly_limit_microusd)
    ON CONFLICT(run_id) DO NOTHING`)
    .bind(runId, periodKey, requestedMicrousd, now, provider, requestedMicrousd,
      periodKey, requestedMicrousd).run();
  const reservation = await env.DB.prepare(`SELECT provider, period_key, reserved_microusd
    FROM provider_budget_reservations WHERE run_id=?`).bind(runId).first();
  return inserted?.meta?.changes === 1 ||
    (reservation?.provider === provider && reservation?.period_key === periodKey &&
      reservation?.reserved_microusd === requestedMicrousd);
}

function modalWorkloadFailureCode(providerResult) {
  if (providerResult?.state === "not_found") return "MODAL_WORKLOAD_NOT_FOUND";
  const exitCode = providerResult?.exit_code;
  if (Number.isInteger(exitCode) && exitCode >= 0 && exitCode <= 255) {
    if (exitCode === 2 && typeof providerResult.diagnostic_code === "string" &&
        (/^PREFLIGHT_RETURN_LINE_[1-9][0-9]{0,3}$/.test(providerResult.diagnostic_code) ||
         providerResult.diagnostic_code === "PREFLIGHT_SYSTEM_EXIT_2")) {
      return `MODAL_WORKLOAD_EXIT_2_${providerResult.diagnostic_code}`;
    }
    return exitCode === 0 ? "MODAL_RESULT_MISSING" : `MODAL_WORKLOAD_EXIT_${exitCode}`;
  }
  return "MODAL_WORKLOAD_FAILED";
}


async function recoverMissingModalRunAfterHorizon(env, row, ownerId, now) {
  if (row.state !== "running" || row.cleanup_state !== "pending" ||
      !Number.isSafeInteger(row.lease_expires_at) ||
      now < row.lease_expires_at + MODAL_NOT_FOUND_RECOVERY_GRACE_SECONDS) return false;
  const receipt = JSON.stringify({ provider: "modal_cpu",
    evidence: "modal_named_sandbox_absent_after_bounded_lifetime", observed_at: now,
    lease_expires_at: row.lease_expires_at, recovery_grace_seconds: MODAL_NOT_FOUND_RECOVERY_GRACE_SECONDS });
  const result = await env.DB.prepare(`UPDATE runs SET state='failed',
      failure_code='MODAL_SANDBOX_ABSENT_AFTER_RECOVERY_GRACE', cleanup_state='confirmed',
      cleanup_receipt_json=?, updated_at=?
    WHERE id=? AND owner_id=? AND state='running' AND cleanup_state='pending'
      AND lease_expires_at=? AND lease_expires_at<=?`)
    .bind(receipt, now, row.id, ownerId, row.lease_expires_at,
      now - MODAL_NOT_FOUND_RECOVERY_GRACE_SECONDS).run();
  return result?.meta?.changes === 1;
}

async function synchronizeModalRun(env, runId, ownerId, { submit = false, cancel = false, authorizationExpiresAt = null } = {}) {
  const row = await env.DB.prepare(`SELECT r.id, r.state, r.cancel_requested, r.cleanup_state, r.lease_expires_at,
      p.workload, p.repository, p.source_sha,
      p.image_digest, p.fingerprint, p.parameters_json, p.runtime_seconds
    FROM runs r JOIN plans p ON p.id=r.plan_id WHERE r.id=? AND r.owner_id=?`).bind(runId, ownerId).first();
  if (!row || !["queued", "running"].includes(row.state)) return;
  if (submit && (!Number.isSafeInteger(authorizationExpiresAt) || authorizationExpiresAt < Math.floor(Date.now() / 1000))) {
    const now = Math.floor(Date.now() / 1000);
    await env.DB.prepare(`UPDATE runs SET state='failed', failure_code='HUMAN_AUTHORIZATION_EXPIRED', cleanup_state='confirmed', updated_at=?
      WHERE id=? AND owner_id=? AND state IN ('queued','running')`).bind(now, runId, ownerId).run();
    return;
  }
  const payload = modalPayload(row, env);
  let providerResult;
  if (cancel || row.cancel_requested === 1) {
    providerResult = await modalRequest(env, `/v1/runs/${runId}/cancel`, payload);
  } else if (submit) {
    providerResult = await modalRequest(env, `/v1/runs/${runId}/submit`, payload);
  } else {
    try {
      providerResult = await modalRequest(env, `/v1/runs/${runId}/status`, payload);
    } catch (error) {
      if (error?.message === "MODAL_RUN_NOT_FOUND" && row.state === "queued") {
        const authorization = await env.DB.prepare(`SELECT expires_at, consumed_at FROM human_authorizations
          WHERE owner_id=? AND plan_id=? AND fingerprint=?`).bind(ownerId, runId, row.fingerprint).first();
        if (!authorization || authorization.consumed_at === null || authorization.expires_at < Math.floor(Date.now() / 1000)) {
          const now = Math.floor(Date.now() / 1000);
          await env.DB.prepare(`UPDATE runs SET state='failed', failure_code='HUMAN_AUTHORIZATION_EXPIRED', cleanup_state='confirmed', updated_at=?
            WHERE id=? AND owner_id=? AND state='queued'`).bind(now, runId, ownerId).run();
          return;
        }
        providerResult = await modalRequest(env, `/v1/runs/${runId}/submit`, payload);
      } else if (error?.message === "MODAL_RUN_NOT_FOUND") {
        providerResult = { state: "not_found", cleanup_state: "unknown" };
      } else throw error;
    }
  }
  const now = Math.floor(Date.now() / 1000);
  if (providerResult.state === "not_found" && providerResult.cleanup_state !== "confirmed") {
    await recoverMissingModalRunAfterHorizon(env, row, ownerId, now);
    return;
  }
  if (providerResult.sandbox_id && typeof providerResult.sandbox_id === "string" && providerResult.sandbox_id.length <= 128) {
    await env.DB.prepare("UPDATE runs SET lease_id=?, updated_at=? WHERE id=? AND owner_id=? AND state IN ('queued','running')")
      .bind(providerResult.sandbox_id, now, runId, ownerId).run();
  }
  if (providerResult.cleanup_state !== "confirmed") return;
  if (providerResult.state === "succeeded" &&
      providerResult.image_fingerprint !== env.MODAL_WORKLOAD_IMAGE_FINGERPRINT) {
    await env.DB.prepare(`UPDATE runs SET state='failed', failure_code='MODAL_IMAGE_FINGERPRINT_MISMATCH', cleanup_state='confirmed', updated_at=?
      WHERE id=? AND owner_id=? AND state IN ('queued','running')`).bind(now, runId, ownerId).run();
    return;
  }
  if (cancel || row.cancel_requested === 1 || providerResult.state === "cancelled") {
    await env.DB.prepare(`UPDATE runs SET state='cancelled', failure_code='caller_cancelled', cleanup_state='confirmed', updated_at=?
      WHERE id=? AND owner_id=? AND state IN ('queued','running')`).bind(now, runId, ownerId).run();
    return;
  }
  if (providerResult.state === "running") return;
  if (providerResult.state !== "succeeded" || !providerResult.result || providerResult.result.status !== "passed") {
    if (["failed", "not_found"].includes(providerResult.state)) {
      await env.DB.prepare(`UPDATE runs SET state='failed', failure_code=?, cleanup_state='confirmed', updated_at=?
        WHERE id=? AND owner_id=? AND state IN ('queued','running')`)
        .bind(modalWorkloadFailureCode(providerResult), now, runId, ownerId).run();
    }
    return;
  }
  const result = providerResult.result;
  const metrics = result.metrics;
  const expectedChecks = ["source_identity_present", "parameter_bounds", "model_digest_verified", "inference_completed",
    "non_root", "no_secret_environment", "no_docker_socket", "read_only_rootfs", "network_disabled"];
  if (result.schema_version !== 1 || result.run_id !== runId || result.source_sha !== row.source_sha ||
      result.plan_fingerprint !== row.fingerprint || result.check !== WORKLOAD || result.gpu_used !== false ||
      !Array.isArray(result.checks) || canonical(result.checks) !== canonical(expectedChecks) ||
      !metrics || metrics.model_id !== MODAL_MODEL_ID || metrics.model_sha256 !== MODAL_MODEL_SHA256 ||
      metrics.max_new_tokens !== JSON.parse(row.parameters_json).max_new_tokens ||
      metrics.seed !== JSON.parse(row.parameters_json).seed ||
      typeof metrics.generated_text !== "string" || new TextEncoder().encode(metrics.generated_text).byteLength > 1536 ||
      !Number.isInteger(metrics.generated_tokens) || metrics.generated_tokens < 1 || metrics.generated_tokens > metrics.max_new_tokens ||
      !/^[0-9a-f]{64}$/.test(metrics.prompt_sha256 || "") ||
      typeof result.checksum !== "string" || !/^[0-9a-f]{64}$/.test(result.checksum) ||
      await sha256(canonical({ run_id: result.run_id, source_sha: result.source_sha, plan_fingerprint: result.plan_fingerprint, metrics })) !== result.checksum) {
    await env.DB.prepare(`UPDATE runs SET state='failed', failure_code='MODAL_RESULT_VALIDATION_FAILED', cleanup_state='confirmed', updated_at=?
      WHERE id=? AND owner_id=? AND state IN ('queued','running')`).bind(now, runId, ownerId).run();
    return;
  }
  const resultJson = canonical(result);
  const resultBytes = runArtifactBytes(resultJson);
  if (resultBytes.byteLength > RUN_ARTIFACT_MAX_BYTES) {
    await env.DB.prepare(`UPDATE runs SET state='failed', failure_code='MODAL_RESULT_TOO_LARGE', cleanup_state='confirmed', updated_at=?
      WHERE id=? AND owner_id=? AND state IN ('queued','running')`).bind(now, runId, ownerId).run();
    return;
  }
  await persistRunResultArtifact(env, { runId, ownerId, sourceSha: row.source_sha,
    planFingerprint: row.fingerprint, resultJson, now });
}

async function prepareDelegatedExperiment(env, owner, args) {
  const sourceRunId = args.workload === ZERO_GPU_WORKLOAD
    ? (args.source_run_id || /^runs\/([0-9a-f]{32})\/orbitune-output\.zip$/.exec(args.parameters?.artifact_path || "")?.[1] || null)
    : null;
  const adapterArguments = { ...args };
  delete adapterArguments.source_run_id;
  if (!providerAdapterConfigured(env)) throw new Error("GATEWAY_DELEGATION_NOT_CONFIGURED");
  // The public tool accepts equivalent zero-dollar spellings for usability,
  // but the adapter and persisted fingerprint use one canonical free value.
  // Normalize before the adapter prepares the plan so prepare and submit bind
  // the same exact JSON representation.
  let delegatedArgs = [KAGGLE_WORKLOAD, ZERO_GPU_WORKLOAD].includes(args.workload)
    ? { ...adapterArguments, max_cost_usd: "0" }
    : adapterArguments;
  if (args.workload === MODAL_GPU_WORKLOAD) {
    const evidence = await modalGpuProviderEvidence(env, Math.floor(Date.now() / 1000));
    if (!evidence) return { schema_version: 2, status: "blocked",
      human_summary: "Modal Workspace上限・利用額・T4価格の短期証拠が未設定または期限切れです。GPU Functionは起動していません。",
      machine_state: { provider: "modal_gpu", account_evidence_valid: false, gpu_started: false },
      next_allowed_actions: [], blocking_reason: "MODAL_GPU_ACCOUNT_EVIDENCE_REQUIRED" };
    delegatedArgs = { ...args, provider_evidence: evidence };
  }
  const response = await callProviderAdapterTool(env, owner, "experiment_prepare", delegatedArgs);
  const state = response?.machine_state;
  const plan = response?.approved_plan;
  const runId = state?.run_id;
  const fingerprint = state?.plan_fingerprint;
  if (!/^[0-9a-f]{32}$/.test(runId || "") || !/^[0-9a-f]{64}$/.test(fingerprint || "") ||
      !validGatewayApprovedPlan(plan) || plan.workload !== args.workload ||
      plan.repository !== args.repository || plan.source_sha !== args.commit) {
    throw new Error("GATEWAY_DELEGATION_INVALID_RESPONSE");
  }
  const planJson = canonical(plan);
  const now = Math.floor(Date.now() / 1000);
  const expires = now + HUMAN_AUTHORIZATION_TTL_SECONDS;
  await env.DB.prepare(`INSERT OR IGNORE INTO gateway_delegated_plans
    (id, owner_id, idempotency_key, fingerprint, workload, approved_plan_json, state, created_at, expires_at, source_run_id)
    VALUES (?, ?, ?, ?, ?, ?, 'prepared', ?, ?, ?)`)
    .bind(runId, owner, args.idempotency_key, fingerprint, args.workload, planJson, now, expires, sourceRunId).run();
  const persisted = await env.DB.prepare(`SELECT id, fingerprint, workload, approved_plan_json, state, expires_at
    FROM gateway_delegated_plans WHERE owner_id=? AND idempotency_key=?`)
    .bind(owner, args.idempotency_key).first();
  if (!persisted || persisted.id !== runId || persisted.fingerprint !== fingerprint ||
      persisted.workload !== args.workload || persisted.approved_plan_json !== planJson) {
    throw new Error("IDEMPOTENCY_KEY_CONFLICT");
  }
  return { ...response,
    machine_state: { ...response.machine_state, ...(sourceRunId ? { source_run_id: sourceRunId } : {}) },
    provider_approved_plan: plan, expires_at: persisted.expires_at,
    approval_required: true, authorization_surface: "chatgpt_mcp_write_confirmation",
    authorization_validity_seconds: HUMAN_AUTHORIZATION_TTL_SECONDS,
    max_runs_per_authorization: 1 };
}

async function submitDelegatedExperiment(env, owner, args) {
  const now = Math.floor(Date.now() / 1000);
  const plan = await delegatedPlan(env, owner, args.run_id);
  const approvedPlanJson = canonical(args.provider_approved_plan);
  if (!plan || plan.cancelled_at || plan.fingerprint !== args.plan_fingerprint || plan.approved_plan_json !== approvedPlanJson ||
      plan.expires_at < now || !["prepared", "submitted"].includes(plan.state)) {
    return { schema_version: 2, status: "blocked",
      human_summary: "ChatGPTの確認内容が、このownerの現在有効なprovider planと完全一致しません。新しいplanを準備してください。",
      machine_state: { run_id: args.run_id, plan_valid: false }, next_allowed_actions: [],
      blocking_reason: "APPROVED_PLAN_MISMATCH_OR_EXPIRED" };
  }
  const approvedPlan = args.provider_approved_plan;
  const provider = approvedPlan?.provider;
  let policyAuthorized = false;
  if (provider === "modal_gpu") {
    if (env.MODAL_GPU_WORKLOAD_ADMISSION_ENABLED !== "true") return { schema_version: 2, status: "blocked",
      human_summary: "Modal GPU admissionは停止中です。GPU Functionは起動していません。",
      machine_state: { run_id: args.run_id, provider_policy_authorized: false, gpu_started: false },
      next_allowed_actions: [], blocking_reason: "MODAL_GPU_WORKLOAD_ADMISSION_DISABLED" };
    const currentEvidence = await modalGpuProviderEvidence(env, now);
    if (!currentEvidence || canonical(currentEvidence) !== canonical(approvedPlan.provider_evidence)) {
      return { schema_version: 2, status: "blocked",
        human_summary: "Modal Workspace上限・利用額・T4価格の証拠が期限切れまたはplanと不一致です。GPU Functionは起動していません。",
        machine_state: { run_id: args.run_id, account_evidence_valid: false, gpu_started: false },
        next_allowed_actions: [], blocking_reason: "MODAL_GPU_ACCOUNT_EVIDENCE_STALE_OR_MISMATCHED" };
    }
    if (approvedPlan.workload !== MODAL_GPU_WORKLOAD || approvedPlan.repository !== GPU_CONTROL_REPOSITORY ||
        approvedPlan.source_sha !== MODAL_GPU_SOURCE_SHA || approvedPlan.max_cost_usd !== WORKLOADS.modal_gpu_canary.cost_ceiling_usd ||
        approvedPlan.known_cost_usd !== null || approvedPlan.cost_classification !== "PAID_BOUNDED" ||
        approvedPlan.paid_fallback_allowed !== false) {
      return { schema_version: 2, status: "blocked",
        human_summary: "Modal GPUの上限付きpolicyとplanが一致しないため、GPU Functionは起動していません。",
        machine_state: { run_id: args.run_id, provider_policy_authorized: false, gpu_started: false },
        next_allowed_actions: [], blocking_reason: "MODAL_GPU_PLAN_POLICY_MISMATCH" };
    }
  } else {
    if (!["kaggle", "huggingface_space"].includes(provider) || approvedPlan.max_cost_usd !== "0" ||
        approvedPlan.known_cost_usd !== "0" || approvedPlan.paid_fallback_allowed !== false) {
      return { schema_version: 2, status: "blocked",
        human_summary: "無料provider policyとplanが一致しないため、providerには接続していません。",
        machine_state: { run_id: args.run_id, provider_policy_authorized: false }, next_allowed_actions: [],
        blocking_reason: "FREE_PROVIDER_PLAN_POLICY_MISMATCH" };
    }
    try {
      policyAuthorized = await authorizeFreeProviderPolicy(env, {
        runId: args.run_id, provider, fingerprint: args.plan_fingerprint, now,
      });
    } catch {}
    if (!policyAuthorized) return { schema_version: 2, status: "blocked",
      human_summary: "無料providerのD1 policyを確保できないため、providerには接続していません。",
      machine_state: { run_id: args.run_id, provider_policy_authorized: false }, next_allowed_actions: [],
      blocking_reason: "FREE_PROVIDER_POLICY_UNAVAILABLE" };
  }
  let authorization = await env.DB.prepare(`SELECT authorization_id, authorization_source, authorized_at, expires_at, consumed_at
    FROM gateway_delegated_authorizations WHERE owner_id=? AND plan_id=? AND fingerprint=?`)
    .bind(owner, args.run_id, args.plan_fingerprint).first();
  if (!authorization) {
    const authorizationId = randomHex(16);
    const expiresAt = Math.min(now + HUMAN_AUTHORIZATION_TTL_SECONDS, plan.expires_at);
    await env.DB.prepare(`INSERT OR IGNORE INTO gateway_delegated_authorizations
      (authorization_id, owner_id, plan_id, fingerprint, authorization_source, authorized_at, expires_at, consumed_at)
      SELECT ?, owner_id, id, fingerprint, 'chatgpt_mcp_write_confirmation', ?, ?, ?
      FROM gateway_delegated_plans WHERE owner_id=? AND id=? AND fingerprint=? AND state IN ('prepared','submitted') AND cancelled_at IS NULL AND expires_at>=?`)
      .bind(authorizationId, now, expiresAt, now, owner, args.run_id, args.plan_fingerprint, now).run();
    authorization = await env.DB.prepare(`SELECT authorization_id, authorization_source, authorized_at, expires_at, consumed_at
      FROM gateway_delegated_authorizations WHERE owner_id=? AND plan_id=? AND fingerprint=?`)
      .bind(owner, args.run_id, args.plan_fingerprint).first();
  }
  if (!authorization || authorization.expires_at < now) throw new Error("PLAN_EXPIRED_OR_ALREADY_USED");
  if (provider === "modal_gpu") {
    let leaseReserved = false;
    try { leaseReserved = await reserveModalGpuLease(env, {
      runId: args.run_id, fingerprint: args.plan_fingerprint, now,
    }); } catch {}
    if (!leaseReserved) return { schema_version: 2, status: "blocked",
      human_summary: "別のModal GPU実行がterminal cleanup確認前です。新しいGPU Functionは起動していません。",
      machine_state: { run_id: args.run_id, gpu_started: false, active_lease_acquired: false },
      next_allowed_actions: [], blocking_reason: "MODAL_GPU_ACTIVE_LEASE_BUSY" };
  }
  // Persist the shared Modal reservation and submit claim atomically before
  // the network call. A lost response keeps the same reservation and run.
  const attemptAt = Math.floor(Date.now() / 1000);
  if (plan.state === "prepared") {
    let claimed;
    if (provider === "modal_gpu") {
      const periodKey = utcMonthKey(attemptAt);
      let batch;
      try {
        const reservation = prepareModalComputeBudgetReservation(env.DB, {
          runId: args.run_id, source: "modal_gpu_canary", fingerprint: args.plan_fingerprint,
          periodKey, requestedMicrousd: 10000, now: attemptAt, requireGpuAdmission: true,
        });
        batch = await env.DB.batch([
          reservation,
          env.DB.prepare(`UPDATE gateway_delegated_plans
            SET state='submitted', submit_attempted_at=COALESCE(submit_attempted_at, ?), updated_at=?
            WHERE owner_id=? AND id=? AND fingerprint=? AND state='prepared' AND cancelled_at IS NULL
              AND EXISTS (SELECT 1 FROM modal_gpu_admission_policy a
                WHERE a.scope='workspace' AND a.admission_enabled=1)
              AND EXISTS (SELECT 1 FROM modal_compute_budget_reservations r
                WHERE r.run_id=? AND r.source='modal_gpu_canary' AND r.plan_fingerprint=?
                  AND r.period_key=? AND r.reserved_microusd=10000)
            RETURNING id`).bind(attemptAt, attemptAt, owner, args.run_id, args.plan_fingerprint,
              args.run_id, args.plan_fingerprint, periodKey),
          env.DB.prepare(`DELETE FROM modal_compute_budget_reservations
            WHERE run_id=? AND source='modal_gpu_canary' AND plan_fingerprint=? AND period_key=?
              AND reserved_microusd=10000 AND NOT EXISTS (SELECT 1 FROM gateway_delegated_plans p
                WHERE p.id=? AND p.owner_id=? AND p.fingerprint=? AND p.state='submitted')`)
            .bind(args.run_id, args.plan_fingerprint, periodKey, args.run_id, owner,
              args.plan_fingerprint),
        ]);
      } catch (error) {
        try {
          await env.DB.prepare(`DELETE FROM modal_gpu_active_lease WHERE scope='workspace'
            AND run_id=? AND plan_fingerprint=? AND state='submitting'`)
            .bind(args.run_id, args.plan_fingerprint).run();
        } catch {}
        throw error;
      }
      if (batch?.[0]?.meta?.changes === 0) {
        const existingReservation = await env.DB.prepare(`SELECT source, plan_fingerprint, period_key, reserved_microusd
          FROM modal_compute_budget_reservations WHERE run_id=?`).bind(args.run_id).first();
        if (existingReservation?.source !== "modal_gpu_canary" ||
            existingReservation.plan_fingerprint !== args.plan_fingerprint ||
            existingReservation.period_key !== periodKey || existingReservation.reserved_microusd !== 10000) {
          await env.DB.prepare(`DELETE FROM modal_gpu_active_lease WHERE scope='workspace'
            AND run_id=? AND plan_fingerprint=? AND state='submitting'`)
            .bind(args.run_id, args.plan_fingerprint).run();
          return { schema_version: 2, status: "blocked",
            human_summary: "Modal計算の共通予算上限に達したか、受付が閉じました。GPU Functionは起動していません。",
            machine_state: { run_id: args.run_id, provider_policy_authorized: false, gpu_started: false },
            next_allowed_actions: ["experiment_status"], blocking_reason: "MODAL_GPU_BUDGET_UNAVAILABLE" };
        }
      }
      claimed = batch?.[1]?.results?.[0] || null;
    } else {
      claimed = await env.DB.prepare(`UPDATE gateway_delegated_plans
        SET state='submitted', submit_attempted_at=COALESCE(submit_attempted_at, ?), updated_at=?
        WHERE owner_id=? AND id=? AND fingerprint=? AND state='prepared' AND cancelled_at IS NULL
        RETURNING id`).bind(attemptAt, attemptAt, owner, args.run_id, args.plan_fingerprint).first();
    }
    if (!claimed) {
      const latest = await delegatedPlan(env, owner, args.run_id);
      if (!latest || latest.cancelled_at || latest.state !== "submitted") {
        if (provider === "modal_gpu") await env.DB.prepare(`DELETE FROM modal_gpu_active_lease WHERE scope='workspace'
          AND run_id=? AND plan_fingerprint=? AND state='submitting'`)
          .bind(args.run_id, args.plan_fingerprint).run();
        return { schema_version: 2, status: "blocked", human_summary: "このplanは取消済みか、送信権を取得できませんでした。",
          machine_state: { run_id: args.run_id, plan_valid: false }, next_allowed_actions: [],
          blocking_reason: "PLAN_CANCELLED_OR_ALREADY_CLAIMED" };
      }
    }
  } else if (provider === "modal_gpu") {
    const reservation = await env.DB.prepare(`SELECT source, plan_fingerprint, reserved_microusd
      FROM modal_compute_budget_reservations WHERE run_id=?`).bind(args.run_id).first();
    if (reservation?.source !== "modal_gpu_canary" || reservation.plan_fingerprint !== args.plan_fingerprint ||
        reservation.reserved_microusd !== 10000) return { schema_version: 2, status: "blocked",
      human_summary: "既存Modal GPU runの予算予約を照合できません。新しいrunは作成せず、状態を確認してください。",
      machine_state: { run_id: args.run_id, provider_policy_authorized: false, gpu_started: false },
      next_allowed_actions: ["experiment_status"], blocking_reason: "MODAL_GPU_BUDGET_RESERVATION_MISSING" };
  }
  const response = await callProviderAdapterTool(env, owner, "experiment_submit", {
    run_id: args.run_id, plan_fingerprint: args.plan_fingerprint, approved_plan: args.provider_approved_plan,
    authorization: { authorization_id: authorization.authorization_id, source: authorization.authorization_source,
      authorized_at: authorization.authorized_at, expires_at: authorization.expires_at },
  });
  if (provider === "modal_gpu") {
    await env.DB.prepare(`UPDATE modal_gpu_active_lease SET state='active', updated_at=?
      WHERE scope='workspace' AND run_id=? AND plan_fingerprint=? AND state='submitting'`)
      .bind(now, args.run_id, args.plan_fingerprint).run();
  }
  await persistProviderAdapterObservation(env, owner, args.run_id, response);
  return publicProviderAdapterResponse(response);
}

async function maybeDelegateRunTool(env, owner, name, args) {
  const plan = await delegatedPlan(env, owner, args.run_id);
  if (!plan) return null;
  // A RunPod run created by the native Sites lifecycle can coexist with a
  // stale gateway_delegated_plans row from the pre-native deployment. Prefer
  // the authoritative native run so status/cancel can reconcile and release
  // its provider-account lease instead of calling the retired adapter path.
  const nativeRunpodRun = await env.DB.prepare(`SELECT r.id FROM runs r
    JOIN plans p ON p.id=r.plan_id
    WHERE r.id=? AND r.owner_id=? AND p.provider='runpod_gpu' LIMIT 1`)
    .bind(args.run_id, owner).first();
  if (nativeRunpodRun) return null;
  if (plan.cancelled_at && plan.state === "prepared") {
    return { schema_version: 2, status: "ok", human_summary: "Prepared provider plan was cancelled before submission; no provider resource was created.",
      machine_state: { run_id: plan.id, state: "cancelled", workload: plan.workload,
        provider_resource_created: false, cleanup_state: "confirmed", cancelled_at: plan.cancelled_at },
      next_allowed_actions: [], blocking_reason: null };
  }
  if (plan.state === "prepared") {
    const now = Math.floor(Date.now() / 1000);
    const expired = plan.expires_at < now;
    const localState = expired ? "expired" : "prepared";
    if (name === "experiment_status") return {
      schema_version: 2,
      status: expired ? "blocked" : "ok",
      human_summary: expired
        ? "Prepared provider plan expired before submission; no provider resource was created."
        : "Prepared provider plan retrieved; no provider resource has been created yet.",
      machine_state: { run_id: plan.id, state: localState, workload: plan.workload,
        plan_fingerprint: plan.fingerprint, expires_at: plan.expires_at,
        provider_resource_created: false, cleanup_state: "not_required" },
      next_allowed_actions: expired ? [] : ["experiment_submit", "experiment_cancel"],
      blocking_reason: expired ? "PLAN_EXPIRED_OR_ALREADY_USED" : null,
    };
    if (name === "experiment_cancel") {
      const cancelled = await env.DB.prepare(`UPDATE gateway_delegated_plans SET cancelled_at=?, updated_at=?
        WHERE owner_id=? AND id=? AND state='prepared' AND cancelled_at IS NULL
        RETURNING id, cancelled_at`).bind(now, now, owner, args.run_id).first();
      if (!cancelled) {
        const latest = await delegatedPlan(env, owner, args.run_id);
        if (latest?.state === "submitted") return maybeDelegateRunTool(env, owner, "experiment_cancel", args);
        if (!latest?.cancelled_at) throw new Error("DELEGATED_PLAN_CANCELLATION_NOT_CONFIRMED");
      }
      return { schema_version: 2, status: "ok",
        human_summary: "Prepared provider plan cancelled before submission; no provider resource was created.",
        machine_state: { run_id: plan.id, state: "cancelled", cancelled_at: cancelled?.cancelled_at || plan.cancelled_at || now, workload: plan.workload,
          provider_resource_created: false, cleanup_state: "confirmed" },
        next_allowed_actions: [], blocking_reason: null };
    }
    return { schema_version: 2, status: "blocked",
      human_summary: "The provider run has not been submitted, so no result or artifact exists.",
      machine_state: { run_id: plan.id, state: localState, workload: plan.workload,
        provider_resource_created: false, cleanup_state: "not_required" },
      next_allowed_actions: expired ? [] : ["experiment_status"],
      blocking_reason: expired ? "PLAN_EXPIRED_OR_ALREADY_USED" : "RESULT_NOT_READY" };
  }
  let providerHandle = plan.provider_handle_json === null || plan.provider_handle_json === undefined
    ? null : JSON.parse(plan.provider_handle_json);
  let approvedPlan;
  try { approvedPlan = JSON.parse(plan.approved_plan_json); } catch { approvedPlan = null; }
  if (!approvedPlan || typeof approvedPlan !== "object" || Array.isArray(approvedPlan)) {
    throw new Error("GATEWAY_DELEGATION_INVALID_PLAN");
  }
  if (!providerHandle && plan.submit_attempted_at) providerHandle = {
    transport: "modal_spawn_v1", run_id: plan.id, plan_fingerprint: plan.fingerprint,
    provider: approvedPlan.provider,
  };
  let externalArtifact = null;
  if (name === "experiment_artifact") {
    let persistedResponse;
    try { persistedResponse = JSON.parse(plan.provider_response_json); } catch { persistedResponse = null; }
    const result = persistedResponse?.result || persistedResponse?.machine_state?.result;
    const references = Array.isArray(result?.external_artifacts) ? result.external_artifacts : [];
    externalArtifact = references.find((reference) => reference?.service === "huggingface_hub" &&
      reference?.run_id === args.run_id && reference?.path_in_repo === `runs/${args.run_id}/orbitune-output.zip` &&
      (reference?.artifact_id === undefined || reference.artifact_id === args.artifact_id));
    if (!externalArtifact || args.artifact_id !== "orbitune-output.zip") {
      return { schema_version: 2, status: "blocked",
        human_summary: "This run has no MCP-readable external artifact.",
        machine_state: { run_id: args.run_id, artifact_id: args.artifact_id },
        next_allowed_actions: ["experiment_result"], blocking_reason: "ARTIFACT_NOT_READY" };
    }
  }
  const delegatedArgs = name === "experiment_artifact"
    ? { run_id: args.run_id, artifact_id: args.artifact_id, offset: args.offset,
      length: args.max_bytes, provider_handle: providerHandle, external_artifact: externalArtifact }
    : { ...args, provider_handle: providerHandle,
      ...(plan.workload === KAGGLE_WORKLOAD ? { runtime_seconds: approvedPlan.runtime_seconds } : {}) };
  if (plan.workload === MODAL_GPU_WORKLOAD && name === "experiment_cancel") {
    await env.DB.prepare(`UPDATE modal_gpu_active_lease SET state='cancel_pending', updated_at=?
      WHERE scope='workspace' AND run_id=? AND plan_fingerprint=? AND state IN ('submitting','active')`)
      .bind(Math.floor(Date.now() / 1000), args.run_id, plan.fingerprint).run();
  }
  let response;
  try {
    response = await callProviderAdapterTool(env, owner, name, delegatedArgs);
  } catch (error) {
    if (plan.submit_attempted_at && !plan.provider_handle_json && name !== "experiment_artifact") {
      return { schema_version: 2, status: "pending",
        human_summary: "Submitの応答が未確定です。新しいrunは作らず、同じrunの受付記録を照合しています。",
        machine_state: { run_id: plan.id, state: "uncertain", provider: approvedPlan.provider,
          submission_attempted: true, provider_resource_created: "unknown", cleanup_state: "unknown" },
        next_allowed_actions: ["experiment_status"], blocking_reason: "SUBMISSION_OUTCOME_UNCONFIRMED" };
    }
    throw error;
  }
  // Artifact reads are read-only. Persisting a chunk response would replace
  // the terminal provider result that owns the immutable external reference,
  // break subsequent chunks, and retain private artifact bytes in D1.
  if (name !== "experiment_artifact") {
    await persistProviderAdapterObservation(env, owner, args.run_id, response);
  }
  if (plan.workload === MODAL_GPU_WORKLOAD &&
      ["succeeded", "failed", "cancelled"].includes(response?.machine_state?.state) &&
      response?.machine_state?.cleanup_state === "confirmed") {
    await env.DB.prepare(`DELETE FROM modal_gpu_active_lease
      WHERE scope='workspace' AND run_id=? AND plan_fingerprint=?`)
      .bind(args.run_id, plan.fingerprint).run();
  }
  return publicProviderAdapterResponse(response);
}

async function callTool(name, args, request, env, context = null, principal = null) {
  const owner = principal?.owner_id || userId(request, env);
  if (!owner) throw new Error(request.headers.get("oai-authenticated-user-id") ? "SITE_USER_NOT_AUTHORIZED" : "AUTHENTICATED_SITE_USER_REQUIRED");
  if (!env.DB) return { schema_version: 2, status: "blocked", human_summary: "D1 database is not configured.", machine_state: {}, next_allowed_actions: [], blocking_reason: "D1_NOT_CONFIGURED" };
  if (isGoogleColabTool(name)) return handleGoogleColabTool(name, env, owner);
  if (isGithubTool(name)) return handleGithubTool(name, env, owner);
  if (isTrainingTool(name)) return handleTrainingTool(name, args, { env, owner,
    delegate: callProviderAdapterTool, isConfigured: providerAdapterConfigured,
    getSourceToken: async (repository) => (await createOwnedRepositoryReadToken(env, env.DB, owner, repository)).token });
  if (name === "experiment_provider_health") return providerHealthDiagnostic(env, owner, args.run_id, args.plan_fingerprint);
  if (name === "experiment_capabilities") return getExperimentCapabilities(env, owner, { modalConfigured });
  if (name === "experiment_prepare") {
    let prepareArgs = args;
    if (args.workload_id === ZERO_GPU_WORKLOAD) {
      prepareArgs = await resolveZeroGpuPrepare(env, owner, args);
      if (!prepareArgs) return { schema_version: 2, status: "blocked",
        human_summary: "指定された所有者のKaggle実行から、cleanup済みの固定artifact参照を解決できませんでした。Kaggle run IDを確認してください。",
        machine_state: { workload: ZERO_GPU_WORKLOAD, source_run_id: args.source_run_id },
        next_allowed_actions: ["experiment_list"], blocking_reason: "KAGGLE_ARTIFACT_REFERENCE_UNAVAILABLE" };
    } else if (args.workload_id) {
      prepareArgs = registeredPrepareArguments(args, env);
      if (!prepareArgs) throw new Error("REGISTERED_WORKLOAD_DEFAULTS_UNAVAILABLE");
    }
    if (prepareArgs.workload === RUNPOD_WORKLOAD) {
      if (!validRunpodPrepare(prepareArgs, env)) throw new Error("REGISTERED_WORKLOAD_OR_ARGUMENTS_INVALID");
      if (env.RUNPOD_LIVE_COMPLETION_TRANSPORT_VERIFIED !== "true") return {
        schema_version: 2, status: "blocked",
        human_summary: "Runpod completion transport is not verified; no plan was prepared and no Serverless job was submitted.",
        machine_state: { plan_prepared: false, job_submitted: false }, next_allowed_actions: [],
        blocking_reason: "RUNPOD_LIVE_COMPLETION_TRANSPORT_UNVERIFIED",
      };
      if (env.RUNPOD_WORKLOAD_ADMISSION_ENABLED !== "true") return {
        schema_version: 2, status: "blocked",
        human_summary: "Runpod admission is disabled; no plan was prepared and no Serverless job was submitted.",
        machine_state: { plan_prepared: false, job_submitted: false }, next_allowed_actions: [],
        blocking_reason: "RUNPOD_ADMISSION_DISABLED",
      };
      return prepareRunpodExperiment(env, owner, prepareArgs);
    }
    if (validGatewayPrepare(prepareArgs)) return prepareDelegatedExperiment(env, owner, prepareArgs);
    return prepareModalCpuPlan(env, owner, prepareArgs);
  }
  if (name === "experiment_submit") {
    if (!validToolArguments(name, args, env)) throw new Error("INVALID_ARGUMENTS");
    if (args.provider_approved_plan?.provider === "runpod_gpu") {
      return submitRunpodExperiment(env, owner, args, {
        reserveBudget: (input) => reserveProviderBudget(env, input),
        context,
      });
    }
    if (args.provider_approved_plan !== undefined) return submitDelegatedExperiment(env, owner, args);
    return submitModalCpuRun(env, owner, args, request, {
      randomHex, authorizationUrl, submitSummary, synchronizeModalRun,
    });
  }
  if (name === "experiment_status" || name === "experiment_result") {
    const delegated = await maybeDelegateRunTool(env, owner, name, args);
    if (delegated) return delegated;
    return readExperimentStatus(env, owner, name, args, {
      synchronizeRunpod: synchronizeRunpodExperiment,
      modalConfigured,
      reserveModalStatusCheck,
      synchronizeModalRun,
    });
  }
  if (name === "experiment_cancel") {
    const delegated = await maybeDelegateRunTool(env, owner, name, args);
    if (delegated) return delegated;
    return cancelLocalRun(env, owner, args.run_id, { synchronizeRunpod: synchronizeRunpodExperiment });
  }
  if (name === "experiment_reconcile") return reconcileProviderRuns(env, owner, {
    maybeDelegateRunTool,
    synchronizeRunpod: synchronizeRunpodExperiment,
  });
  if (name === "experiment_artifact") {
    const delegated = await maybeDelegateRunTool(env, owner, name, args);
    if (delegated) return delegated;
    return readRunResultArtifact(env, owner, args);
  }
  if (name === "experiment_list") return listExperiments(env, owner, args);
  throw new Error("UNKNOWN_TOOL");
}

async function handleMcp(request, env, context = null, principal = null) {
  let message;
  try { message = await readJson(request); } catch (error) {
    return rpcError(null, -32700, error.message === "BODY_TOO_LARGE" ? "Request too large" : "Invalid JSON");
  }
  const id = message?.id;
  if (message?.jsonrpc !== "2.0" || !message.method) return rpcError(id, -32600, "Invalid Request");
  const requestedVersion = request.headers.get("mcp-protocol-version") || LEGACY_VERSIONS[0];
  if (!MCP_VERSIONS.includes(requestedVersion)) return json({ jsonrpc: "2.0", id, error: { code: -32022, message: "Unsupported protocol version", data: { supported: MCP_VERSIONS, requested: requestedVersion } } }, 400);
  const params = message.params && typeof message.params === "object" ? message.params : {};
  const requiredScope = message.method === "tools/call" && isMcpToolReadOnly(params.name)
    ? READ_SCOPE : message.method === "tools/call" ? EXECUTE_SCOPE : READ_SCOPE;
  if (!principal?.scopes?.includes(requiredScope)) {
    return mcpAuthorizationChallenge(request, { error: "insufficient_scope", scope: requiredScope });
  }
  const meta = params._meta && typeof params._meta === "object" ? params._meta : {};
  if (requestedVersion === MCP_VERSION || meta[`${META_PREFIX}protocolVersion`] === MCP_VERSION) {
    if (meta[`${META_PREFIX}protocolVersion`] !== requestedVersion || request.headers.get("mcp-method") !== message.method || !meta[`${META_PREFIX}clientCapabilities`] || typeof meta[`${META_PREFIX}clientCapabilities`] !== "object") {
      return json({ jsonrpc: "2.0", id, error: { code: -32020, message: "Request metadata/header mismatch" } }, 400);
    }
    if (["tools/call", "prompts/get", "resources/read"].includes(message.method)) {
      const supplied = request.headers.get("mcp-name");
      const expected = message.method === "resources/read" ? params.uri : params.name;
      if (typeof expected !== "string" || supplied !== expected) return json({ jsonrpc: "2.0", id, error: { code: -32020, message: "Mcp-Name does not match the request" } }, 400);
    }
  }
  if (message.method === "server/discover") {
    return json({ jsonrpc: "2.0", id, result: { supportedVersions: MCP_VERSIONS, capabilities: { tools: {} } } });
  }
  if (message.method === "tools/list") {
    return json({ jsonrpc: "2.0", id, result: { tools: listMcpTools(requestedVersion, LEGACY_VERSIONS[0]) } });
  }
  if (message.method === "tools/call") {
    try {
      const name = message.params?.name;
      const args = normalizeTrainingArguments(name, message.params?.arguments ?? {}, env);
      if (!schemas[name] || !args || typeof args !== "object" || Array.isArray(args) || !validToolArguments(name, args, env)) throw new Error("INVALID_ARGUMENTS");
      const value = envelope(name, await callTool(name, args, request, env, context, principal));
      const result = { content: [{ type: "text", text: JSON.stringify(value) }], isError: false };
      if (requestedVersion !== LEGACY_VERSIONS[0]) result.structuredContent = value;
      return json({ jsonrpc: "2.0", id, result: { ...result, ...(requestedVersion === MCP_VERSION ? { resultType: "complete", _meta: { [`${META_PREFIX}serverInfo`]: { name: "gpu-control-sites", version: "0.1.0" } } } : {}) } });
    } catch (error) {
      const known = new Set(["GITHUB_APP_NOT_CONFIGURED", "GITHUB_APP_API_FAILED", "GITHUB_APP_API_RESPONSE_INVALID",
        "GITHUB_CONNECTION_INVALID", "GITHUB_CONNECTION_REQUIRED", "GITHUB_INSTALLATION_STATE_EXPIRED",
        "GITHUB_INSTALLATION_STATE_REPLAYED", "GITHUB_INSTALLATION_ALREADY_LINKED", "GITHUB_INSTALLATION_SCOPE_INVALID",
        "GITHUB_INSTALLATION_TOKEN_SCOPE_INVALID", "GITHUB_REPOSITORY_NOT_SELECTED",
        "TRAINING_BUDGET_NOT_CONFIGURED", "TRAINING_PLAN_EXPIRED",
        "TRAINING_REGISTRATION_NOT_FOUND", "TRAINING_SOURCE_INVALID", "TRAINING_GITHUB_PRIVATE_REQUIRES_APP",
        "TRAINING_GITHUB_REPOSITORY_NOT_PUBLIC", "TRAINING_GITHUB_REPOSITORY_ARCHIVED", "TRAINING_GITHUB_RATE_LIMITED",
        "TRAINING_GITHUB_LOOKUP_FAILED", "TRAINING_GITHUB_RESPONSE_TOO_LARGE", "TRAINING_GITHUB_RESPONSE_INVALID",
        "TRAINING_GITHUB_DEFAULT_COMMIT_UNAVAILABLE", "TRAINING_GITHUB_COMMIT_UNAVAILABLE",
        "AUTHENTICATED_SITE_USER_REQUIRED", "SITE_USER_NOT_AUTHORIZED",
        "D1_NOT_CONFIGURED", "REGISTERED_WORKLOAD_OR_ARGUMENTS_INVALID", "IDEMPOTENCY_KEY_CONFLICT", "INVALID_ARGUMENTS",
        "SUBMIT_TRANSACTION_FAILED", "PLAN_EXPIRED_OR_ALREADY_USED", "RUN_NOT_FOUND", "RESULT_NOT_READY", "UNKNOWN_TOOL",
        "GOOGLE_COLAB_CONNECTION_INVALID", "GOOGLE_COLAB_CONNECTION_STATE_EXPIRED", "GOOGLE_COLAB_CONNECTION_STATE_REPLAYED",
        "GOOGLE_COLAB_OAUTH_NOT_CONFIGURED", "GOOGLE_COLAB_OAUTH_FAILED", "GOOGLE_COLAB_OAUTH_RESPONSE_INVALID",
        "GOOGLE_COLAB_OAUTH_SCOPE_INVALID", "GOOGLE_COLAB_IDENTITY_INVALID", "GOOGLE_COLAB_CONNECTION_REQUIRED",
        "GOOGLE_COLAB_CRYPTO_NOT_CONFIGURED", "GOOGLE_COLAB_CREDENTIAL_UNAVAILABLE",
        "GOOGLE_COLAB_RECONNECT_REQUIRES_DISCONNECT"]);
      const runpodProviderCodes = new Set([
        "RUNPOD_AUTHENTICATION_FAILED", "RUNPOD_PERMISSION_DENIED", "RUNPOD_PROVIDER_NOT_CONFIGURED",
        "RUNPOD_PROVIDER_TIMEOUT", "RUNPOD_PROVIDER_UNAVAILABLE", "RUNPOD_RATE_LIMITED",
        "RUNPOD_ENDPOINT_CONFIGURATION_MISMATCH", "RUNPOD_CATALOG_PRICE_INVALID_OR_ABOVE_MAXIMUM",
        "RUNPOD_NETWORK_ERROR",
      ]);
      const code = known.has(error?.message) ? error.message
        : (error?.name === "RunpodProviderError" && runpodProviderCodes.has(error?.code) ? error.code
        : (typeof error?.message === "string" && error.message.startsWith("GATEWAY_DELEGATION_")
          ? "GATEWAY_DELEGATION_FAILED" : "INTERNAL_ERROR"));
      return json({ jsonrpc: "2.0", id, result: { isError: true, content: [{ type: "text", text: JSON.stringify({ error: code }) }] } });
    }
  }
  return rpcError(id, -32601, "Method not found");
}

export { maybeDelegateRunTool, modalGpuProviderEvidence, reserveModalGpuLease };

export default {
  async fetch(request, env, context) {
    const url = new URL(request.url);
    if (url.pathname === "/.well-known/oauth-protected-resource" && request.method === "GET") {
      try { return json(mcpProtectedResourceMetadata(url.origin)); }
      catch { return json({ error: "NOT_FOUND" }, 404); }
    }
    if (url.pathname === "/.well-known/oauth-authorization-server" && request.method === "GET") {
      try { return json(mcpAuthorizationServerMetadata(url.origin)); }
      catch { return json({ error: "NOT_FOUND" }, 404); }
    }
    if (url.pathname === "/oauth/register") return handleMcpOAuthRegistration(request, env);
    if (url.pathname === "/oauth/authorize") return handleMcpOAuthAuthorization(request, env);
    if (url.pathname === "/oauth/token") return handleMcpOAuthToken(request, env);
    if (url.pathname === "/oauth/revoke") return handleMcpOAuthRevoke(request, env);
    if (url.pathname === "/" && request.method === "GET") {
      return htmlPage("GPU Control", `<p>ChatGPT Sites MCP control plane for registered GPU experiments.</p>
        <p>Viewing this page does not grant execution authority. Stateful tools require an authenticated, allowlisted Sites owner.</p>
        <p><a href="/health">Service health</a></p>`);
    }
    if (url.pathname === "/health" && request.method === "GET") return json({ ok: true, service: "gpu-control-sites", storage: !!env.DB });
    if (url.pathname === "/github/setup") return handleGithubSetup(request, env);
    if (url.pathname === "/github/oauth/callback") return handleGithubOAuthCallback(request, env);
    if (url.pathname === "/google/setup") return handleGoogleColabSetup(request, env);
    if (url.pathname === "/google/oauth/callback") return handleGoogleColabOAuthCallback(request, env);
    if (url.pathname.startsWith("/runner/")) return json({ error: "NOT_FOUND" }, 404);
    if (url.pathname === "/authorize" || url.pathname === "/authorize-training") {
      try { return await handleAuthorizationRequest(request, env); }
      catch { return htmlPage("承認処理を完了できません", "<p>チャットでplanの状態を確認してください。</p>", 500); }
    }
    if (url.pathname === "/mcp" && request.method === "POST") {
      let principal;
      try {
        principal = await authenticateMcpPrincipal(request, env);
      }
      catch { return new Response(null, { status: 503, headers: { "cache-control": "no-store" } }); }
      if (principal?.denied === "forbidden") return mcpAuthorizationChallenge(request, { error: "forbidden" });
      if (!principal) return mcpAuthorizationChallenge(request, {
        error: request.headers.has("authorization") ? "invalid_token" : null,
      });
      try { return await handleMcp(request, env, context, principal); }
      catch { return rpcError(null, -32603, "Internal error"); }
    }
    return json({ error: "NOT_FOUND" }, 404);
  },
};
