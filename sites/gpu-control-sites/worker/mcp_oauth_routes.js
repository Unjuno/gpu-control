import {
  beginMcpOAuthGitHubLogin,
  createMcpOAuthConsent,
  exchangeMcpOAuthToken,
  mcpAuthorizationServerMetadata,
  mcpOAuthError,
  mcpProtectedResourceMetadata,
  registerMcpOAuthClient,
  revokeMcpOAuthToken,
} from "./mcp_oauth.js";

function json(data, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store",
    pragma: "no-cache",
    "x-content-type-options": "nosniff",
  } });
}

function hasMediaType(request, expected) {
  return (request.headers.get("content-type") || "").split(";", 1)[0].trim().toLowerCase() === expected;
}

/** Compose the external MCP client's OAuth and discovery HTTP surface. */
export function createMcpOAuthRoutes({ htmlPage, escapeHtml, readJson, readUrlEncodedForm }) {
  async function authorization(request, env) {
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
      const response = htmlPage("GPU Controlへの接続を完了できません", `<p>${detail}</p>`, 400);
      response.headers.append("set-cookie", "__Host-gpu-control-mcp-consent=; Max-Age=0; Path=/; Secure; HttpOnly; SameSite=Lax");
      return response;
    }
  }

  async function registration(request, env) {
    if (request.method !== "POST") return json({ error: "invalid_request" }, 405);
    if (!env.DB || !hasMediaType(request, "application/json")) return json({ error: "invalid_client_metadata" }, 400);
    try {
      const body = await readJson(request, 16 * 1024);
      const result = await registerMcpOAuthClient(env.DB, body, request.headers.get("cf-connecting-ip"));
      return json(result, 201);
    } catch (error) {
      const code = mcpOAuthError(error);
      const status = code === "MCP_OAUTH_REGISTRATION_RATE_LIMITED" ? 429
        : ["MCP_OAUTH_REGISTRATION_RATE_LIMIT_UNAVAILABLE", "MCP_OAUTH_REGISTRATION_STORAGE_UNAVAILABLE"].includes(code) ? 503 : 400;
      return json({ error: status === 429 ? "temporarily_unavailable" : "invalid_client_metadata" }, status);
    }
  }

  async function token(request, env) {
    if (request.method !== "POST") return json({ error: "invalid_request" }, 405);
    if (!env.DB || request.headers.has("authorization") || !hasMediaType(request, "application/x-www-form-urlencoded")) {
      return json({ error: "invalid_request" }, 400);
    }
    try { return await exchangeMcpOAuthToken(env.DB, await readUrlEncodedForm(request), new URL(request.url).origin); }
    catch { return json({ error: "server_error" }, 500); }
  }

  async function revoke(request, env) {
    if (request.method !== "POST") return json({ error: "invalid_request" }, 405);
    if (!env.DB || request.headers.has("authorization") || !hasMediaType(request, "application/x-www-form-urlencoded")) {
      return json({ error: "invalid_request" }, 400);
    }
    try { return await revokeMcpOAuthToken(env.DB, await readUrlEncodedForm(request)); }
    catch { return json({ error: "server_error" }, 500); }
  }

  return {
    authorization,
    registration,
    token,
    revoke,
    protectedResourceMetadata(request) {
      try { return json(mcpProtectedResourceMetadata(new URL(request.url).origin)); }
      catch { return json({ error: "NOT_FOUND" }, 404); }
    },
    authorizationServerMetadata(request) {
      try { return json(mcpAuthorizationServerMetadata(new URL(request.url).origin)); }
      catch { return json({ error: "NOT_FOUND" }, 404); }
    },
  };
}
