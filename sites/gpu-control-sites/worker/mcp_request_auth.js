import { authenticateMcpAccessToken, EXECUTE_SCOPE, READ_SCOPE } from "./mcp_oauth.js";

export function sitesOwnerFromRequest(request, env) {
  const id = request.headers.get("oai-authenticated-user-id");
  if (!id || id.length > 256) return null;
  const allowed = new Set(typeof env.GPU_CONTROL_ALLOWED_USER_IDS === "string"
    ? env.GPU_CONTROL_ALLOWED_USER_IDS.split(",").map((value) => value.trim()).filter(Boolean)
    : []);
  return allowed.has(id) ? id : null;
}

export function sitesPlatformIdentityPresent(request) {
  return Boolean(request.headers.get("oai-authenticated-user-id"));
}

export async function authenticateMcpPrincipal(request, env) {
  if (sitesPlatformIdentityPresent(request)) {
    const owner = sitesOwnerFromRequest(request, env);
    return owner ? { owner_id: owner, auth_method: "chatgpt_sites", scopes: [READ_SCOPE, EXECUTE_SCOPE] }
      : { denied: "forbidden" };
  }
  const authorization = request.headers.get("authorization") || "";
  const match = authorization.match(/^Bearer (gpc_at_[A-Za-z0-9_-]{43})$/);
  if (!match || !env.DB) return null;
  return authenticateMcpAccessToken(env.DB, match[1], `${new URL(request.url).origin}/mcp`);
}

export function mcpAuthorizationChallenge(request, { error = null, scope = READ_SCOPE } = {}) {
  const resourceMetadata = `${new URL(request.url).origin}/.well-known/oauth-protected-resource`;
  const challenge = [`Bearer resource_metadata="${resourceMetadata}"`, `scope="${scope}"`];
  if (error) challenge.push(`error="${error}"`);
  return new Response(null, { status: ["insufficient_scope", "forbidden"].includes(error) ? 403 : 401, headers: {
    "www-authenticate": challenge.join(", "), "cache-control": "no-store", "content-length": "0",
  } });
}
