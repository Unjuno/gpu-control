import { authenticateMcpAccessToken, EXECUTE_SCOPE, READ_SCOPE } from "./mcp_oauth.js";

export function sitesOwnerFromRequest(request, env) {
  const id = request.headers.get("oai-authenticated-user-id");
  if (!id || id.length > 256) return null;
  return isMcpOwnerAllowed(id, env) ? id : null;
}

export function isMcpOwnerAllowed(owner, env) {
  if (typeof owner !== "string" || owner.length > 256) return false;
  return configuredMcpOwners(env).has(owner);
}

export function mcpOwnerAllowlistStatus(env) {
  const owners = configuredMcpOwners(env);
  return {
    configured: owners.size > 0,
    allowed_owner_count: owners.size,
    scope: owners.size === 0 ? "closed" : owners.size === 1 ? "single_owner" : "multiple_owners",
  };
}

function configuredMcpOwners(env) {
  return new Set(typeof env?.GPU_CONTROL_ALLOWED_USER_IDS === "string"
    ? env.GPU_CONTROL_ALLOWED_USER_IDS.split(",").map((value) => value.trim()).filter(Boolean)
    : []);
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
  const principal = await authenticateMcpAccessToken(env.DB, match[1], `${new URL(request.url).origin}/mcp`);
  if (!principal) return null;
  return isMcpOwnerAllowed(principal.owner_id, env) ? principal : { denied: "forbidden" };
}

export function mcpAuthorizationChallenge(request, { error = null, scope = READ_SCOPE } = {}) {
  const resourceMetadata = `${new URL(request.url).origin}/.well-known/oauth-protected-resource`;
  const challenge = [`Bearer resource_metadata="${resourceMetadata}"`, `scope="${scope}"`];
  if (error) challenge.push(`error="${error}"`);
  return new Response(null, { status: ["insufficient_scope", "forbidden"].includes(error) ? 403 : 401, headers: {
    "www-authenticate": challenge.join(", "), "cache-control": "no-store", "content-length": "0",
  } });
}
