import { githubAppOAuthConfigured, readGithubOAuthIdentity } from "./github_app_connection.js";

const READ_SCOPE = "experiments:read";
const EXECUTE_SCOPE = "experiments:execute";
const AUTHORIZATION_TTL_SECONDS = 600;
const CODE_TTL_SECONDS = 120;
const ACCESS_TTL_SECONDS = 900;
const REFRESH_TTL_SECONDS = 30 * 24 * 60 * 60;

function bytesToBase64Url(bytes) {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/g, "");
}

function randomBase64Url(length = 32) {
  return bytesToBase64Url(crypto.getRandomValues(new Uint8Array(length)));
}

function randomHex(length = 16) {
  return [...crypto.getRandomValues(new Uint8Array(length))]
    .map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function sha256(value) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function pkceChallenge(verifier) {
  return bytesToBase64Url(new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier))));
}

function validOrigin(origin) {
  try {
    const url = new URL(origin);
    return url.protocol === "https:" && url.origin === origin && !url.username && !url.password;
  } catch { return false; }
}

function canonicalResource(origin) {
  if (!validOrigin(origin)) throw new Error("MCP_OAUTH_ORIGIN_INVALID");
  return `${origin}/mcp`;
}

function validRedirectUri(value) {
  if (typeof value !== "string" || value.length > 2048 || value.includes("#")) return false;
  try {
    const uri = new URL(value);
    if (uri.username || uri.password || uri.hash || uri.href !== value ||
        ["code", "state", "error", "iss"].some((name) => uri.searchParams.has(name))) return false;
    if (uri.protocol === "https:") return true;
    return uri.protocol === "http:" && ["localhost", "127.0.0.1", "[::1]"].includes(uri.hostname);
  } catch { return false; }
}

function validClientId(value) {
  return typeof value === "string" && /^gpc_client_[A-Za-z0-9_-]{32}$/.test(value);
}

function parseScopes(value) {
  if (typeof value !== "string" || value.length > 128) return null;
  const scopes = [...new Set(value.split(/\s+/).filter(Boolean))].sort();
  if (scopes.length < 1 || scopes.some((scope) => ![READ_SCOPE, EXECUTE_SCOPE].includes(scope))) return null;
  if (scopes.includes(EXECUTE_SCOPE) && !scopes.includes(READ_SCOPE)) scopes.push(READ_SCOPE);
  return [...new Set(scopes)].sort();
}

function oauthJson(value, status = 200) {
  return new Response(JSON.stringify(value), { status, headers: {
    "content-type": "application/json; charset=utf-8", "cache-control": "no-store",
    pragma: "no-cache", "x-content-type-options": "nosniff",
  } });
}

function html(value, status = 200, headers = {}) {
  return new Response(value, { status, headers: { "content-type": "text/html; charset=utf-8",
    "cache-control": "no-store", "content-security-policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'",
    "referrer-policy": "no-referrer", "x-content-type-options": "nosniff", ...headers } });
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;" })[character]);
}

export function mcpProtectedResourceMetadata(origin) {
  return { resource: canonicalResource(origin), authorization_servers: [origin], bearer_methods_supported: ["header"],
    scopes_supported: [READ_SCOPE, EXECUTE_SCOPE] };
}

export function mcpAuthorizationServerMetadata(origin) {
  if (!validOrigin(origin)) throw new Error("MCP_OAUTH_ORIGIN_INVALID");
  return { issuer: origin, authorization_endpoint: `${origin}/oauth/authorize`, token_endpoint: `${origin}/oauth/token`,
    registration_endpoint: `${origin}/oauth/register`, revocation_endpoint: `${origin}/oauth/revoke`,
    response_types_supported: ["code"], grant_types_supported: ["authorization_code", "refresh_token"],
    code_challenge_methods_supported: ["S256"], registration_endpoint_auth_methods_supported: ["none"],
    token_endpoint_auth_methods_supported: ["none"],
    scopes_supported: [READ_SCOPE, EXECUTE_SCOPE], client_id_metadata_document_supported: false };
}

export async function registerMcpOAuthClient(db, body, remoteAddress, now = Math.floor(Date.now() / 1000)) {
  const name = body?.client_name;
  const redirects = body?.redirect_uris;
  if (!db || !Number.isSafeInteger(now) || typeof name !== "string" || name.trim() !== name ||
      name.length < 1 || name.length > 100 || !Array.isArray(redirects) || redirects.length < 1 || redirects.length > 10 ||
      redirects.some((uri) => !validRedirectUri(uri)) || new Set(redirects).size !== redirects.length ||
      (body.grant_types !== undefined && (!Array.isArray(body.grant_types) || body.grant_types.length < 1 ||
        !body.grant_types.includes("authorization_code") ||
        body.grant_types.some((grant) => !["authorization_code", "refresh_token"].includes(grant)))) ||
      (body.response_types !== undefined && (!Array.isArray(body.response_types) ||
        body.response_types.length !== 1 || body.response_types[0] !== "code")) ||
      (body.token_endpoint_auth_method !== undefined && body.token_endpoint_auth_method !== "none")) {
    throw new Error("MCP_OAUTH_CLIENT_METADATA_INVALID");
  }
  if (typeof remoteAddress !== "string" || remoteAddress.length < 1 || remoteAddress.length > 128) {
    throw new Error("MCP_OAUTH_REGISTRATION_RATE_LIMIT_UNAVAILABLE");
  }
  const ipHash = await sha256(`gpu-control-mcp-client-registration:${remoteAddress}`);
  const day = new Date(now * 1000).toISOString().slice(0, 10);
  const globalHash = await sha256("gpu-control-mcp-client-registration:global");
  const retentionDay = new Date((now - 30 * 24 * 60 * 60) * 1000).toISOString().slice(0, 10);
  let globalLimit;
  let limit;
  try {
    await Promise.all([
      db.prepare("DELETE FROM mcp_oauth_registration_limits WHERE period_day<?").bind(retentionDay).run(),
      db.prepare("DELETE FROM mcp_oauth_authorization_requests WHERE expires_at<=?").bind(now).run(),
      db.prepare("DELETE FROM mcp_oauth_authorization_codes WHERE expires_at<=?").bind(now).run(),
      db.prepare("DELETE FROM mcp_oauth_tokens WHERE expires_at<=?").bind(now).run(),
    ]);
    globalLimit = await db.prepare(`INSERT INTO mcp_oauth_registration_limits (ip_hash, period_day, registration_count)
      VALUES (?, ?, 1) ON CONFLICT(ip_hash, period_day) DO UPDATE SET registration_count=registration_count+1
      WHERE registration_count<200 RETURNING registration_count`).bind(globalHash, day).first();
  } catch { throw new Error("MCP_OAUTH_REGISTRATION_STORAGE_UNAVAILABLE"); }
  if (!globalLimit) throw new Error("MCP_OAUTH_REGISTRATION_RATE_LIMITED");
  try {
    limit = await db.prepare(`INSERT INTO mcp_oauth_registration_limits (ip_hash, period_day, registration_count)
      VALUES (?, ?, 1) ON CONFLICT(ip_hash, period_day) DO UPDATE SET registration_count=registration_count+1
      WHERE registration_count<10 RETURNING registration_count`).bind(ipHash, day).first();
  } catch { throw new Error("MCP_OAUTH_REGISTRATION_STORAGE_UNAVAILABLE"); }
  if (!limit) throw new Error("MCP_OAUTH_REGISTRATION_RATE_LIMITED");
  const clientId = `gpc_client_${randomBase64Url(24)}`;
  try {
    await db.prepare(`INSERT INTO mcp_oauth_clients (client_id, client_name, redirect_uris_json, created_at, revoked_at)
      VALUES (?, ?, ?, ?, NULL)`).bind(clientId, name, JSON.stringify(redirects), now).run();
  } catch { throw new Error("MCP_OAUTH_REGISTRATION_STORAGE_UNAVAILABLE"); }
  return { client_id: clientId, client_name: name, redirect_uris: redirects,
    grant_types: ["authorization_code", "refresh_token"], response_types: ["code"], token_endpoint_auth_method: "none" };
}

export async function createMcpOAuthConsent(db, params, origin, now = Math.floor(Date.now() / 1000)) {
  if (!db || !Number.isSafeInteger(now) || params?.response_type !== "code" || !validClientId(params.client_id) ||
      typeof params.redirect_uri !== "string" || !validRedirectUri(params.redirect_uri) ||
      typeof params.state !== "string" || params.state.length < 1 || params.state.length > 512 ||
      typeof params.code_challenge !== "string" || !/^[A-Za-z0-9_-]{43}$/.test(params.code_challenge) ||
      params.code_challenge_method !== "S256" || params.resource !== canonicalResource(origin)) {
    throw new Error("MCP_OAUTH_AUTHORIZATION_REQUEST_INVALID");
  }
  const scopes = parseScopes(params.scope || READ_SCOPE);
  if (!scopes) throw new Error("MCP_OAUTH_SCOPE_INVALID");
  const client = await db.prepare(`SELECT client_name, redirect_uris_json FROM mcp_oauth_clients
    WHERE client_id=? AND revoked_at IS NULL`).bind(params.client_id).first();
  if (!client) throw new Error("MCP_OAUTH_CLIENT_UNKNOWN");
  let registeredRedirects;
  try { registeredRedirects = JSON.parse(client.redirect_uris_json); } catch { registeredRedirects = null; }
  if (!Array.isArray(registeredRedirects) || !registeredRedirects.includes(params.redirect_uri)) {
    throw new Error("MCP_OAUTH_REDIRECT_URI_INVALID");
  }
  const csrf = randomBase64Url(32);
  const consentHash = await sha256(csrf);
  await db.prepare(`INSERT INTO mcp_oauth_authorization_requests
    (consent_hash, client_id, redirect_uri, client_state, code_challenge, scope, resource, created_at, expires_at, github_state_hash, consumed_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)`)
    .bind(consentHash, params.client_id, params.redirect_uri, params.state, params.code_challenge,
      scopes.join(" "), params.resource, now, now + AUTHORIZATION_TTL_SECONDS).run();
  const scopeLabels = scopes.map((scope) => scope === READ_SCOPE ? "実験と結果の閲覧" : "実験計画の作成と実行操作");
  const page = `<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>GPU Controlへの接続</title><main style="font:16px/1.6 system-ui,sans-serif;max-width:640px;margin:3rem auto;padding:1.5rem;border:1px solid #ddd;border-radius:12px"><h1>GPU Controlへの接続</h1><p><strong>${escapeHtml(client.client_name)}</strong> がGPU Controlに接続しようとしています。</p><p>許可する操作:</p><ul>${scopeLabels.map((label) => `<li>${escapeHtml(label)}</li>`).join("")}</ul><p>この許可だけでprovider設定や実験が変更されることはありません。実験の実行には、GPU Controlの個別plan・予算・admissionルールが引き続き適用されます。</p><form method="post" action="/oauth/authorize"><input type="hidden" name="csrf" value="${csrf}"><button type="submit" style="font:inherit;padding:.75rem 1rem">GitHubで本人確認して接続</button></form></main></html>`;
  return { response: html(page, 200, { "set-cookie": `__Host-gpu-control-mcp-consent=${csrf}; Max-Age=${AUTHORIZATION_TTL_SECONDS}; Path=/; Secure; HttpOnly; SameSite=Lax` }) };
}

export async function beginMcpOAuthGitHubLogin(db, csrf, env, now = Math.floor(Date.now() / 1000)) {
  if (!db || !githubAppOAuthConfigured(env) || typeof csrf !== "string" || !/^[A-Za-z0-9_-]{43}$/.test(csrf) ||
      !Number.isSafeInteger(now)) throw new Error("MCP_OAUTH_LOGIN_NOT_CONFIGURED");
  const consentHash = await sha256(csrf);
  const request = await db.prepare(`SELECT client_id, redirect_uri, client_state, code_challenge, scope, resource
    FROM mcp_oauth_authorization_requests WHERE consent_hash=? AND consumed_at IS NULL AND expires_at>? AND github_state_hash IS NULL`)
    .bind(consentHash, now).first();
  if (!request) throw new Error("MCP_OAUTH_AUTHORIZATION_REQUEST_EXPIRED");
  const githubState = randomBase64Url(32);
  const githubStateHash = await sha256(githubState);
  const verifier = randomBase64Url(32);
  const challenge = await pkceChallenge(verifier);
  const claimed = await db.prepare(`UPDATE mcp_oauth_authorization_requests SET github_state_hash=?
    WHERE consent_hash=? AND consumed_at IS NULL AND expires_at>? AND github_state_hash IS NULL RETURNING consent_hash`)
    .bind(githubStateHash, consentHash, now).first();
  if (!claimed) throw new Error("MCP_OAUTH_AUTHORIZATION_REQUEST_REPLAYED");
  const authorizationUrl = new URL("https://github.com/login/oauth/authorize");
  authorizationUrl.searchParams.set("client_id", env.GITHUB_APP_CLIENT_ID);
  authorizationUrl.searchParams.set("redirect_uri", env.GITHUB_APP_OAUTH_CALLBACK_URL);
  authorizationUrl.searchParams.set("state", githubState);
  authorizationUrl.searchParams.set("code_challenge", challenge);
  authorizationUrl.searchParams.set("code_challenge_method", "S256");
  return { authorization_url: authorizationUrl.toString(),
    cookie: `__Host-gpu-control-mcp-oauth=${githubState}.${verifier}; Max-Age=${AUTHORIZATION_TTL_SECONDS}; Path=/; Secure; HttpOnly; SameSite=Lax` };
}

export function isMcpOAuthGitHubState(db, state) {
  if (typeof state !== "string" || !/^[A-Za-z0-9_-]{43}$/.test(state)) return Promise.resolve(false);
  return sha256(state).then(async (hash) => Boolean(await db.prepare(`SELECT consent_hash
    FROM mcp_oauth_authorization_requests WHERE github_state_hash=? AND consumed_at IS NULL`)
    .bind(hash).first()));
}

export async function completeMcpOAuthGitHubLogin(db, state, userToken, fetchImpl = fetch,
  now = Math.floor(Date.now() / 1000)) {
  if (!db || typeof state !== "string" || !/^[A-Za-z0-9_-]{43}$/.test(state) ||
      typeof userToken !== "string" || !Number.isSafeInteger(now)) throw new Error("MCP_OAUTH_LOGIN_INVALID");
  const githubStateHash = await sha256(state);
  const request = await db.prepare(`SELECT r.consent_hash, r.client_id, r.redirect_uri, r.client_state,
      r.code_challenge, r.scope, r.resource, r.expires_at, r.consumed_at
    FROM mcp_oauth_authorization_requests r
    JOIN mcp_oauth_clients c ON c.client_id=r.client_id AND c.revoked_at IS NULL
    WHERE r.github_state_hash=?`).bind(githubStateHash).first();
  if (!request || request.expires_at <= now || request.consumed_at !== null) {
    throw new Error("MCP_OAUTH_AUTHORIZATION_REQUEST_EXPIRED");
  }
  const identity = await readGithubOAuthIdentity(userToken, fetchImpl);
  const owner = await db.prepare("SELECT owner_id FROM github_owner_identities WHERE github_user_id=?")
    .bind(identity.id).first();
  if (!owner) throw new Error("MCP_OAUTH_OWNER_LINK_REQUIRED");
  const code = `gpc_code_${randomBase64Url(32)}`;
  const codeHash = await sha256(code);
  const consumedAt = now;
  const results = await db.batch([
    db.prepare(`UPDATE mcp_oauth_authorization_requests SET consumed_at=?
      WHERE github_state_hash=? AND consumed_at IS NULL AND expires_at>? AND EXISTS
        (SELECT 1 FROM mcp_oauth_clients c WHERE c.client_id=mcp_oauth_authorization_requests.client_id AND c.revoked_at IS NULL)
      RETURNING consent_hash`).bind(consumedAt, githubStateHash, now),
    db.prepare(`INSERT INTO mcp_oauth_authorization_codes
      (code_hash, client_id, owner_id, redirect_uri, code_challenge, scope, resource, created_at, expires_at, consumed_at, exchange_id)
      SELECT ?, r.client_id, ?, r.redirect_uri, r.code_challenge, r.scope, r.resource, ?, ?, NULL, NULL
      FROM mcp_oauth_authorization_requests r WHERE r.github_state_hash=? AND r.consumed_at=?`)
      .bind(codeHash, owner.owner_id, now, now + CODE_TTL_SECONDS, githubStateHash, consumedAt),
  ]);
  if (results?.[0]?.results?.length !== 1 || (results?.[1]?.meta?.changes ?? 0) !== 1) {
    throw new Error("MCP_OAUTH_AUTHORIZATION_REQUEST_REPLAYED");
  }
  const redirect = new URL(request.redirect_uri);
  redirect.searchParams.set("code", code);
  redirect.searchParams.set("state", request.client_state);
  return { redirect_uri: redirect.toString(), response: new Response(null, { status: 302, headers: {
    location: redirect.toString(), "cache-control": "no-store", "referrer-policy": "no-referrer",
    "set-cookie": "__Host-gpu-control-mcp-oauth=; Max-Age=0; Path=/; Secure; HttpOnly; SameSite=Lax",
  } }) };
}

function createTokenPair() {
  return { accessToken: `gpc_at_${randomBase64Url(32)}`, refreshToken: `gpc_rt_${randomBase64Url(32)}`,
    familyId: randomHex(16), rotationId: randomHex(16) };
}

function tokenResponse(pair, scope) {
  return { access_token: pair.accessToken, token_type: "Bearer", expires_in: ACCESS_TTL_SECONDS,
    refresh_token: pair.refreshToken, scope };
}

function invalidGrant() {
  return oauthJson({ error: "invalid_grant" }, 400);
}

function oneParameter(params, name, { required = false, maxLength = 4096 } = {}) {
  const values = params.getAll(name);
  if (values.length > 1 || (required && values.length !== 1) || (values[0]?.length ?? 0) > maxLength) return null;
  return values[0] ?? null;
}

export async function exchangeMcpOAuthToken(db, params, origin, now = Math.floor(Date.now() / 1000)) {
  if (!db || !Number.isSafeInteger(now) || !params || params.has("client_secret") ||
      oneParameter(params, "resource", { required: true, maxLength: 512 }) !== canonicalResource(origin)) {
    return oauthJson({ error: "invalid_request" }, 400);
  }
  const clientId = oneParameter(params, "client_id", { required: true, maxLength: 64 });
  if (!validClientId(clientId)) return oauthJson({ error: "invalid_client" }, 401);
  const grantType = oneParameter(params, "grant_type", { required: true, maxLength: 32 });
  if (!grantType) return oauthJson({ error: "invalid_request" }, 400);
  if (grantType === "authorization_code") {
    const code = oneParameter(params, "code", { required: true, maxLength: 64 });
    const redirectUri = oneParameter(params, "redirect_uri", { required: true, maxLength: 2048 });
    const verifier = oneParameter(params, "code_verifier", { required: true, maxLength: 128 });
    if (typeof code !== "string" || !/^gpc_code_[A-Za-z0-9_-]{43}$/.test(code) ||
        typeof verifier !== "string" || !/^[A-Za-z0-9._~-]{43,128}$/.test(verifier) ||
        typeof redirectUri !== "string" || !validRedirectUri(redirectUri)) {
      return oauthJson({ error: "invalid_grant" }, 400);
    }
    const codeHash = await sha256(code);
    const challenge = await pkceChallenge(verifier);
    const record = await db.prepare(`SELECT scope FROM mcp_oauth_authorization_codes
      WHERE code_hash=? AND client_id=? AND redirect_uri=? AND resource=? AND code_challenge=?
        AND consumed_at IS NULL AND expires_at>?`).bind(codeHash, clientId, redirectUri,
      canonicalResource(origin), challenge, now).first();
    if (!record) return invalidGrant();
    const pair = createTokenPair();
    const [accessHash, refreshHash] = await Promise.all([sha256(pair.accessToken), sha256(pair.refreshToken)]);
    const results = await db.batch([
      db.prepare(`UPDATE mcp_oauth_authorization_codes SET consumed_at=?, exchange_id=?
        WHERE code_hash=? AND client_id=? AND redirect_uri=? AND resource=? AND code_challenge=?
          AND consumed_at IS NULL AND expires_at>?
          AND EXISTS (SELECT 1 FROM mcp_oauth_clients c WHERE c.client_id=mcp_oauth_authorization_codes.client_id AND c.revoked_at IS NULL)
        RETURNING code_hash`).bind(now, pair.rotationId, codeHash, clientId, redirectUri,
        canonicalResource(origin), challenge, now),
      db.prepare(`INSERT INTO mcp_oauth_tokens
        (token_hash, token_type, client_id, owner_id, scope, resource, family_id, created_at, expires_at, consumed_at, revoked_at, rotation_id)
        SELECT ?, 'access', client_id, owner_id, scope, resource, ?, ?, ?, NULL, NULL, NULL
        FROM mcp_oauth_authorization_codes WHERE code_hash=? AND exchange_id=?`)
        .bind(accessHash, pair.familyId, now, now + ACCESS_TTL_SECONDS, codeHash, pair.rotationId),
      db.prepare(`INSERT INTO mcp_oauth_tokens
        (token_hash, token_type, client_id, owner_id, scope, resource, family_id, created_at, expires_at, consumed_at, revoked_at, rotation_id)
        SELECT ?, 'refresh', client_id, owner_id, scope, resource, ?, ?, ?, NULL, NULL, NULL
        FROM mcp_oauth_authorization_codes WHERE code_hash=? AND exchange_id=?`)
        .bind(refreshHash, pair.familyId, now, now + REFRESH_TTL_SECONDS, codeHash, pair.rotationId),
    ]);
    if (results?.[0]?.results?.length !== 1 || (results?.[1]?.meta?.changes ?? 0) !== 1 ||
        (results?.[2]?.meta?.changes ?? 0) !== 1) return invalidGrant();
    return oauthJson(tokenResponse(pair, record.scope));
  }
  if (grantType !== "refresh_token") return oauthJson({ error: "unsupported_grant_type" }, 400);
  const refreshToken = oneParameter(params, "refresh_token", { required: true, maxLength: 64 });
  if (typeof refreshToken !== "string" || !/^gpc_rt_[A-Za-z0-9_-]{43}$/.test(refreshToken)) return invalidGrant();
  const refreshHash = await sha256(refreshToken);
  const record = await db.prepare(`SELECT owner_id, client_id, scope, resource, family_id, expires_at, consumed_at, revoked_at
    FROM mcp_oauth_tokens WHERE token_hash=? AND token_type='refresh'`).bind(refreshHash).first();
  if (!record || record.client_id !== clientId || record.resource !== canonicalResource(origin) ||
      record.revoked_at !== null || record.expires_at <= now) return invalidGrant();
  if (record.consumed_at !== null) {
    await db.prepare("UPDATE mcp_oauth_tokens SET revoked_at=COALESCE(revoked_at, ?) WHERE family_id=?")
      .bind(now, record.family_id).run();
    return invalidGrant();
  }
  const pair = createTokenPair();
  const [accessHash, newRefreshHash] = await Promise.all([sha256(pair.accessToken), sha256(pair.refreshToken)]);
  const results = await db.batch([
    db.prepare(`UPDATE mcp_oauth_tokens SET consumed_at=?, rotation_id=?
      WHERE token_hash=? AND token_type='refresh' AND client_id=? AND resource=? AND consumed_at IS NULL
        AND revoked_at IS NULL AND expires_at>? RETURNING family_id`)
      .bind(now, pair.rotationId, refreshHash, clientId, canonicalResource(origin), now),
    db.prepare(`INSERT INTO mcp_oauth_tokens
      (token_hash, token_type, client_id, owner_id, scope, resource, family_id, created_at, expires_at, consumed_at, revoked_at, rotation_id)
      SELECT ?, 'access', client_id, owner_id, scope, resource, family_id, ?, ?, NULL, NULL, NULL
      FROM mcp_oauth_tokens WHERE token_hash=? AND rotation_id=? AND consumed_at=?`)
      .bind(accessHash, now, now + ACCESS_TTL_SECONDS, refreshHash, pair.rotationId, now),
    db.prepare(`INSERT INTO mcp_oauth_tokens
      (token_hash, token_type, client_id, owner_id, scope, resource, family_id, created_at, expires_at, consumed_at, revoked_at, rotation_id)
      SELECT ?, 'refresh', client_id, owner_id, scope, resource, family_id, ?, ?, NULL, NULL, NULL
      FROM mcp_oauth_tokens WHERE token_hash=? AND rotation_id=? AND consumed_at=?`)
      .bind(newRefreshHash, now, now + REFRESH_TTL_SECONDS, refreshHash, pair.rotationId, now),
  ]);
  if (results?.[0]?.results?.length !== 1 || (results?.[1]?.meta?.changes ?? 0) !== 1 ||
      (results?.[2]?.meta?.changes ?? 0) !== 1) {
    const current = await db.prepare(`SELECT consumed_at, family_id FROM mcp_oauth_tokens
      WHERE token_hash=? AND token_type='refresh'`).bind(refreshHash).first();
    if (current?.consumed_at !== null && current?.family_id) {
      await db.prepare("UPDATE mcp_oauth_tokens SET revoked_at=COALESCE(revoked_at, ?) WHERE family_id=?")
        .bind(now, current.family_id).run();
    }
    return invalidGrant();
  }
  return oauthJson(tokenResponse(pair, record.scope));
}

export async function revokeMcpOAuthToken(db, params, now = Math.floor(Date.now() / 1000)) {
  if (!db || !Number.isSafeInteger(now) || !params || params.has("client_secret")) return oauthJson({ error: "invalid_request" }, 400);
  const token = oneParameter(params, "token", { required: true, maxLength: 128 });
  const clientId = oneParameter(params, "client_id", { required: true, maxLength: 64 });
  if (!validClientId(clientId) || typeof token !== "string" || token.length > 128) {
    return oauthJson({ error: "invalid_request" }, 400);
  }
  const hash = await sha256(token);
  const record = await db.prepare(`SELECT family_id FROM mcp_oauth_tokens
    WHERE token_hash=? AND client_id=? AND revoked_at IS NULL`).bind(hash, clientId).first();
  if (record) await db.prepare("UPDATE mcp_oauth_tokens SET revoked_at=COALESCE(revoked_at, ?) WHERE family_id=?")
    .bind(now, record.family_id).run();
  return oauthJson({});
}

export async function authenticateMcpAccessToken(db, token, resource, now = Math.floor(Date.now() / 1000)) {
  if (!db || typeof token !== "string" || !/^gpc_at_[A-Za-z0-9_-]{43}$/.test(token) ||
      typeof resource !== "string" || !Number.isSafeInteger(now)) return null;
  const tokenHash = await sha256(token);
  const row = await db.prepare(`SELECT owner_id, client_id, scope, resource, expires_at
    FROM mcp_oauth_tokens WHERE token_hash=? AND token_type='access' AND revoked_at IS NULL
      AND expires_at>?`).bind(tokenHash, now).first();
  if (!row || row.resource !== resource) return null;
  const scopes = parseScopes(row.scope);
  if (!scopes) return null;
  return { owner_id: row.owner_id, client_id: row.client_id, scopes, auth_method: "mcp_oauth" };
}

export function mcpOAuthError(error) {
  const codes = new Set(["MCP_OAUTH_CLIENT_METADATA_INVALID", "MCP_OAUTH_REGISTRATION_RATE_LIMIT_UNAVAILABLE",
    "MCP_OAUTH_REGISTRATION_RATE_LIMITED", "MCP_OAUTH_REGISTRATION_STORAGE_UNAVAILABLE",
    "MCP_OAUTH_AUTHORIZATION_REQUEST_INVALID", "MCP_OAUTH_SCOPE_INVALID",
    "MCP_OAUTH_CLIENT_UNKNOWN", "MCP_OAUTH_REDIRECT_URI_INVALID", "MCP_OAUTH_LOGIN_NOT_CONFIGURED",
    "MCP_OAUTH_AUTHORIZATION_REQUEST_EXPIRED", "MCP_OAUTH_AUTHORIZATION_REQUEST_REPLAYED",
    "MCP_OAUTH_LOGIN_INVALID", "MCP_OAUTH_OWNER_LINK_REQUIRED", "GITHUB_USER_IDENTITY_INVALID",
    "GITHUB_USER_AUTHORIZATION_INVALID", "GITHUB_USER_AUTHORIZATION_FAILED", "GITHUB_APP_API_FAILED",
    "GITHUB_APP_API_RESPONSE_INVALID"]);
  return codes.has(error?.message) ? error.message : "MCP_OAUTH_REQUEST_FAILED";
}

export function parseMcpScopes(scope) {
  return parseScopes(scope);
}

export { EXECUTE_SCOPE, READ_SCOPE };
