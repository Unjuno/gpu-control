import { issueTrainingChallenge, confirmTrainingChallenge } from "./training_authorization.js";
import { sha256Hex as sha256 } from "./sha256.js";
import { isMcpToolReadOnly, listMcpTools, OUTPUT_SCHEMA, schemas } from "./mcp_tool_contract.js";
import { normalizeTrainingArguments, validToolArguments } from "./experiment_input_contract.js";
import { beginGithubInstallationOAuth, completeGithubInstallationOAuth,
  exchangeGithubOAuthCode, githubAppOAuthConfigured,
  verifyGithubInstallation } from "./github_app_connection.js";
import { MODAL_PRICING_CHECKED_AT, estimateModalSandboxCostUsd } from "./modal_cpu_policy.js";
import { executionOrigin } from "./execution_origin.js";
import { HUMAN_AUTHORIZATION_TTL_SECONDS } from "./human_authorization_policy.js";
import { beginMcpOAuthGitHubLogin, completeMcpOAuthGitHubLogin,
  createMcpOAuthConsent, exchangeMcpOAuthToken, isMcpOAuthGitHubState, mcpAuthorizationServerMetadata,
  mcpOAuthError, mcpProtectedResourceMetadata, registerMcpOAuthClient, revokeMcpOAuthToken,
  READ_SCOPE, EXECUTE_SCOPE } from "./mcp_oauth.js";
import { authenticateMcpPrincipal, mcpAuthorizationChallenge, sitesOwnerFromRequest,
  sitesPlatformIdentityPresent } from "./mcp_request_auth.js";
import { trainingControlPlaneSha } from "./training_security_configuration.js";
import { dispatchMcpTool, modalGpuProviderEvidence } from "./mcp_tool_dispatch.js";
import { createGoogleColabOAuthRoutes } from "./google_colab_oauth_routes.js";

const LEGACY_VERSIONS = ["2025-03-26", "2025-06-18", "2025-11-25"];
const MCP_VERSION = "2026-07-28";
const MCP_VERSIONS = [...LEGACY_VERSIONS, MCP_VERSION];
const META_PREFIX = "io.modelcontextprotocol/";
const MAX_BODY_BYTES = 16 * 1024;
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

const { setup: handleGoogleColabSetup, callback: handleGoogleColabOAuthCallback } =
  createGoogleColabOAuthRoutes({ htmlPage, escapeHtml });

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
    trainingControlPlaneSha(env), now);
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
  const owner = sitesOwnerFromRequest(request, env);
  if (!sitesPlatformIdentityPresent(request)) {
    const signInPath = chatGPTSignInPath(authorizationReturnPath(request));
    return htmlPage("ChatGPT Sitesへのサインインが必要です",
      `<p>あなたのChatGPTアカウントでサインインして、このplanの確認に戻ってください。</p><p><a href="${escapeHtml(signInPath)}" target="_top" rel="noreferrer">ChatGPTでサインイン</a></p>`, 401);
  }
  if (!owner) return htmlPage("このアカウントは許可されていません", "<p>GPU Controlを許可したChatGPTアカウントで開いてください。</p>", 403);
  if (!env.DB) return htmlPage("データベースを利用できません", "<p>このSiteでは承認を記録できません。</p>", 503);
  const training = new URL(request.url).pathname === "/authorize-training";
  if (training && !/^[0-9a-f]{40}$/.test(trainingControlPlaneSha(env) || "")) {
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
      trainingControlPlaneSha(env), token, now);
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
      const value = envelope(name, await dispatchMcpTool(name, args, request, env, context, principal, {
        modalGpuProviderEvidence, randomHex, authorizationUrl, submitSummary,
      }));
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

export { modalGpuProviderEvidence };

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
