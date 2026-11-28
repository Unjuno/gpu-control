import { completeGoogleColabOAuth, beginGoogleColabOAuth,
  googleColabOAuthConfigured } from "./google_colab_connection.js";

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

/** Create provider-specific HTTP routes using the Site's shared HTML renderer. */
export function createGoogleColabOAuthRoutes({ htmlPage, escapeHtml }) {
  async function setup(request, env) {
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

  async function callback(request, env) {
    if (request.method !== "GET") return clearGoogleColabOAuthCookie(
      htmlPage("Google Colab接続", "<p>このcallbackはGETのみ受け付けます。</p>", 405));
    if (!env.DB || !googleColabOAuthConfigured(env)) return clearGoogleColabOAuthCookie(
      htmlPage("Google Colab接続を確認できません", "<p>GPU Control側のGoogle OAuth設定がまだ完了していません。</p>", 503));
    const url = new URL(request.url);
    let callbackUrl;
    try { callbackUrl = new URL(env.GOOGLE_COLAB_OAUTH_CALLBACK_URL); } catch { callbackUrl = null; }
    if (!callbackUrl || url.origin + url.pathname !== callbackUrl.origin + callbackUrl.pathname) {
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

  return { setup, callback };
}
