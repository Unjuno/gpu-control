import {
  beginGithubInstallationOAuth,
  completeGithubInstallationOAuth,
  exchangeGithubOAuthCode,
  githubAppOAuthConfigured,
  verifyGithubInstallation,
} from "./github_app_connection.js";
import { completeMcpOAuthGitHubLogin, isMcpOAuthGitHubState } from "./mcp_oauth.js";

function finish(response, oauthKind = "github") {
  response.headers.append("set-cookie", "__Host-gpu-control-oauth=; Max-Age=0; Path=/; Secure; HttpOnly; SameSite=Lax");
  if (oauthKind === "mcp") {
    response.headers.append("set-cookie", "__Host-gpu-control-mcp-oauth=; Max-Age=0; Path=/; Secure; HttpOnly; SameSite=Lax");
  }
  response.headers.set("cache-control", "no-store");
  response.headers.set("referrer-policy", "no-referrer");
  return response;
}

function cookieValue(request, name) {
  const prefix = `${name}=`;
  const cookie = request.headers.get("cookie") || "";
  return cookie.split(";").map((item) => item.trim())
    .find((item) => item.startsWith(prefix))?.slice(prefix.length) || "";
}

/** Compose GitHub App connection and external MCP owner-proof OAuth routes. */
export function createGithubOAuthRoutes({ htmlPage, escapeHtml }) {
  async function setup(request, env) {
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

  async function callback(request, env) {
    if (request.method !== "GET") return htmlPage("GitHub接続", "<p>このcallbackはGETのみ受け付けます。</p>", 405);
    if (!env.DB || !githubAppOAuthConfigured(env)) return htmlPage("GitHub接続を確認できません",
      "<p>GPU Control側のGitHub App設定がまだ完了していません。</p>", 503);
    const url = new URL(request.url);
    const callbackUrl = new URL(env.GITHUB_APP_OAUTH_CALLBACK_URL);
    if (`${url.origin}${url.pathname}` !== `${callbackUrl.origin}${callbackUrl.pathname}`) {
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
    const [cookieState, codeVerifier, ...extra] = cookieValue(request,
      mcpOAuth ? "__Host-gpu-control-mcp-oauth" : "__Host-gpu-control-oauth").split(".");
    if (!(mcpOAuth ? /^[A-Za-z0-9_-]{43}$/.test(state) : /^[a-f0-9]{64}$/.test(state)) ||
        cookieState !== state || extra.length !== 0 || !/^[A-Za-z0-9._~-]{43,128}$/.test(codeVerifier || "")) {
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

  return { setup, callback };
}
