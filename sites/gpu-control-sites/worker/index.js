import { listMcpTools, OUTPUT_SCHEMA, schemas } from "./mcp_tool_contract.js";
import { normalizeTrainingArguments, validToolArguments } from "./experiment_input_contract.js";
import { executionOrigin } from "./execution_origin.js";
import { authenticateMcpPrincipal, mcpAuthorizationChallenge } from "./mcp_request_auth.js";
import { dispatchMcpTool, modalGpuProviderEvidence } from "./mcp_tool_dispatch.js";
import { createGoogleColabOAuthRoutes } from "./google_colab_oauth_routes.js";
import { createMcpOAuthRoutes } from "./mcp_oauth_routes.js";
import { createGithubOAuthRoutes } from "./github_oauth_routes.js";
import { mcpToolErrorCode } from "./mcp_tool_errors.js";
import { CURRENT_MCP_VERSION, LEGACY_MCP_VERSIONS, SUPPORTED_MCP_VERSIONS,
  mcpRpcError, parseMcpProtocolRequest } from "./mcp_protocol.js";
import { mcpToolErrorResponse, mcpToolSuccessResponse } from "./mcp_tool_result.js";
import { readJsonRequest } from "./http_request_body.js";
import { createTrainingAuthorizationRoutes } from "./training_authorization_routes.js";

const SITE_PUBLIC_ORIGIN = "https://gpu-control-sites.unjuno.chatgpt.site";

function json(data, status = 200, headers = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", ...headers },
  });
}

function hasMediaType(request, expected) {
  return (request.headers.get("content-type") || "").split(";", 1)[0].trim().toLowerCase() === expected;
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
const mcpOAuthRoutes = createMcpOAuthRoutes({ htmlPage, escapeHtml });
const githubOAuthRoutes = createGithubOAuthRoutes({ htmlPage, escapeHtml });

function authorizationUrl(_request, runId, fingerprint) {
  const url = new URL("/authorize", SITE_PUBLIC_ORIGIN);
  url.searchParams.set("run_id", runId);
  url.searchParams.set("plan_fingerprint", fingerprint);
  return url.toString();
}

const trainingAuthorizationRoutes = createTrainingAuthorizationRoutes({ htmlPage, escapeHtml,
  sitePublicOrigin: SITE_PUBLIC_ORIGIN, authorizationUrl });

async function handleMcp(request, env, context = null, principal = null) {
  const parsed = await parseMcpProtocolRequest(request, principal, readJsonRequest);
  if (parsed.response) return parsed.response;
  const { message, id, requestedVersion, params } = parsed;
  if (message.method === "server/discover") {
    return json({ jsonrpc: "2.0", id, result: { supportedVersions: SUPPORTED_MCP_VERSIONS, capabilities: { tools: {} } } });
  }
  if (message.method === "tools/list") {
    return json({ jsonrpc: "2.0", id, result: { tools: listMcpTools(requestedVersion, LEGACY_MCP_VERSIONS[0]) } });
  }
  if (message.method === "tools/call") {
    try {
      const name = message.params?.name;
      const args = normalizeTrainingArguments(name, message.params?.arguments ?? {}, env);
      if (!schemas[name] || !args || typeof args !== "object" || Array.isArray(args) || !validToolArguments(name, args, env)) throw new Error("INVALID_ARGUMENTS");
      const value = await dispatchMcpTool(name, args, request, env, context, principal, {
        modalGpuProviderEvidence, randomHex, authorizationUrl, submitSummary,
      });
      return mcpToolSuccessResponse(id, name, value, requestedVersion);
    } catch (error) {
      const code = mcpToolErrorCode(error);
      return mcpToolErrorResponse(id, code);
    }
  }
  return mcpRpcError(id, -32601, "Method not found");
}

export { modalGpuProviderEvidence };

export default {
  async fetch(request, env, context) {
    const url = new URL(request.url);
    if (url.pathname === "/.well-known/oauth-protected-resource" && request.method === "GET") {
      return mcpOAuthRoutes.protectedResourceMetadata(request);
    }
    if (url.pathname === "/.well-known/oauth-authorization-server" && request.method === "GET") {
      return mcpOAuthRoutes.authorizationServerMetadata(request);
    }
    if (url.pathname === "/oauth/register") return mcpOAuthRoutes.registration(request, env);
    if (url.pathname === "/oauth/authorize") return mcpOAuthRoutes.authorization(request, env);
    if (url.pathname === "/oauth/token") return mcpOAuthRoutes.token(request, env);
    if (url.pathname === "/oauth/revoke") return mcpOAuthRoutes.revoke(request, env);
    if (url.pathname === "/" && request.method === "GET") {
      return htmlPage("GPU Control", `<p>ChatGPT Sites MCP control plane for registered GPU experiments.</p>
        <p>Viewing this page does not grant execution authority. Stateful tools require an authenticated, allowlisted Sites owner.</p>
        <p><a href="/health">Service health</a></p>`);
    }
    if (url.pathname === "/health" && request.method === "GET") return json({ ok: true, service: "gpu-control-sites", storage: !!env.DB });
    if (url.pathname === "/github/setup") return githubOAuthRoutes.setup(request, env);
    if (url.pathname === "/github/oauth/callback") return githubOAuthRoutes.callback(request, env);
    if (url.pathname === "/google/setup") return handleGoogleColabSetup(request, env);
    if (url.pathname === "/google/oauth/callback") return handleGoogleColabOAuthCallback(request, env);
    if (url.pathname.startsWith("/runner/")) return json({ error: "NOT_FOUND" }, 404);
    if (url.pathname === "/authorize" || url.pathname === "/authorize-training") {
      try { return await trainingAuthorizationRoutes.handleAuthorizationRequest(request, env); }
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
      catch { return mcpRpcError(null, -32603, "Internal error"); }
    }
    return json({ error: "NOT_FOUND" }, 404);
  },
};
