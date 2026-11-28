import { issueTrainingChallenge, confirmTrainingChallenge } from "./training_authorization.js";
import { sha256Hex as sha256 } from "./sha256.js";
import { MODAL_PRICING_CHECKED_AT, estimateModalSandboxCostUsd } from "./modal_cpu_policy.js";
import { HUMAN_AUTHORIZATION_TTL_SECONDS } from "./human_authorization_policy.js";
import { sitesOwnerFromRequest, sitesPlatformIdentityPresent } from "./mcp_request_auth.js";
import { trainingControlPlaneSha } from "./training_security_configuration.js";
import { readUrlEncodedFormRequest } from "./http_request_body.js";

export function createTrainingAuthorizationRoutes({ htmlPage, escapeHtml, sitePublicOrigin, authorizationUrl }) {
  function randomHex(byteLength) {
    const bytes = crypto.getRandomValues(new Uint8Array(byteLength));
    return [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
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
    const returnTo = new URL(url.pathname, sitePublicOrigin);
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
    if (url.origin !== sitePublicOrigin || origin !== sitePublicOrigin || (fetchSite && fetchSite !== "same-origin") ||
        !request.headers.get("content-type")?.toLowerCase().startsWith("application/x-www-form-urlencoded")) {
      return htmlPage("リクエストを確認できません", "<p>Siteの確認ページから操作してください。</p>", 403);
    }
    let form;
    try { form = await readUrlEncodedFormRequest(request); }
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

  return { handleAuthorizationRequest };
}
