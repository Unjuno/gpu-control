import { sha256Bytes, sha256Hex as sha256 } from "./sha256.js";
import { readBoundedResponseBytes } from "./http_response_body.js";

const API_ORIGIN = "https://api.github.com";
const API_VERSION = "2022-11-28";
const INSTALL_STATE_TTL_SECONDS = 600;

function base64Url(bytes) {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/g, "");
}

function utf8(value) {
  return new TextEncoder().encode(value);
}

function validOwner(owner) {
  return typeof owner === "string" && /^[A-Za-z0-9][A-Za-z0-9_.:@-]{0,255}$/.test(owner);
}

function validSlug(slug) {
  return typeof slug === "string" && /^[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?$/.test(slug);
}

function validInstallationId(value) {
  return typeof value === "string" && /^[1-9][0-9]{0,19}$/.test(value);
}

function derLength(length) {
  if (length < 0x80) return Uint8Array.of(length);
  const bytes = [];
  for (let value = length; value; value >>>= 8) bytes.unshift(value & 0xff);
  return Uint8Array.of(0x80 | bytes.length, ...bytes);
}

function der(tag, content) {
  const length = derLength(content.length);
  const output = new Uint8Array(1 + length.length + content.length);
  output[0] = tag;
  output.set(length, 1);
  output.set(content, 1 + length.length);
  return output;
}

function concat(...arrays) {
  const output = new Uint8Array(arrays.reduce((sum, value) => sum + value.length, 0));
  let offset = 0;
  for (const value of arrays) { output.set(value, offset); offset += value.length; }
  return output;
}

function pemBytes(pem) {
  if (typeof pem !== "string" || pem.length > 16_384) throw new Error("GITHUB_APP_NOT_CONFIGURED");
  const normalized = pem.replaceAll("\\n", "\n").trim();
  const match = normalized.match(/^-----BEGIN (PRIVATE KEY|RSA PRIVATE KEY)-----\s*([A-Za-z0-9+/=\s]+)\s*-----END (?:PRIVATE KEY|RSA PRIVATE KEY)-----$/);
  if (!match || match[1] !== (match[0].includes("BEGIN RSA PRIVATE KEY") ? "RSA PRIVATE KEY" : "PRIVATE KEY")) {
    throw new Error("GITHUB_APP_NOT_CONFIGURED");
  }
  const encoded = match[2].replace(/\s/g, "");
  if (!/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(encoded)) {
    throw new Error("GITHUB_APP_NOT_CONFIGURED");
  }
  const keyBytes = Uint8Array.from(atob(encoded), (char) => char.charCodeAt(0));
  if (match[1] === "PRIVATE KEY") return keyBytes;
  const algorithm = der(0x30, Uint8Array.of(0x06, 0x09, 0x2a, 0x86, 0x48, 0x86, 0xf7, 0x0d, 0x01, 0x01, 0x01, 0x05, 0x00));
  return der(0x30, concat(Uint8Array.of(0x02, 0x01, 0x00), algorithm, der(0x04, keyBytes)));
}

export function githubAppConfigured(env) {
  return typeof env?.GITHUB_APP_ID === "string" && /^[1-9][0-9]{0,19}$/.test(env.GITHUB_APP_ID) &&
    validSlug(env.GITHUB_APP_SLUG) && typeof env.GITHUB_APP_PRIVATE_KEY === "string" &&
    env.GITHUB_APP_PRIVATE_KEY.length > 0;
}

export function githubAppOAuthConfigured(env) {
  if (!githubAppConfigured(env) || typeof env?.GITHUB_APP_CLIENT_ID !== "string" ||
      !/^[A-Za-z0-9_.-]{1,128}$/.test(env.GITHUB_APP_CLIENT_ID) ||
      typeof env?.GITHUB_APP_CLIENT_SECRET !== "string" ||
      env.GITHUB_APP_CLIENT_SECRET.length < 16 || env.GITHUB_APP_CLIENT_SECRET.length > 512 ||
      typeof env?.GITHUB_APP_OAUTH_CALLBACK_URL !== "string") return false;
  try {
    const callback = new URL(env.GITHUB_APP_OAUTH_CALLBACK_URL);
    return callback.protocol === "https:" && !callback.username && !callback.password &&
      !callback.search && !callback.hash && callback.pathname === "/github/oauth/callback";
  } catch { return false; }
}

export function githubAppTokenStorageConfigured(env) {
  try { return fromBase64Url(env?.GITHUB_APP_TOKEN_ENCRYPTION_KEY, "invalid").length === 32; }
  catch { return false; }
}

export function githubAppOwnerConnectionConfigured(env) {
  return githubAppOAuthConfigured(env) && githubAppTokenStorageConfigured(env);
}

export async function createGithubAppJwt(env, now = Math.floor(Date.now() / 1000)) {
  if (!githubAppConfigured(env) || !Number.isSafeInteger(now)) throw new Error("GITHUB_APP_NOT_CONFIGURED");
  const header = base64Url(utf8(JSON.stringify({ alg: "RS256", typ: "JWT" })));
  const payload = base64Url(utf8(JSON.stringify({ iss: env.GITHUB_APP_ID, iat: now - 60, exp: now + 540 })));
  const unsigned = `${header}.${payload}`;
  let key;
  try {
    key = await crypto.subtle.importKey("pkcs8", pemBytes(env.GITHUB_APP_PRIVATE_KEY),
      { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["sign"]);
  } catch {
    throw new Error("GITHUB_APP_NOT_CONFIGURED");
  }
  const signature = await crypto.subtle.sign("RSASSA-PKCS1-v1_5", key, utf8(unsigned));
  return `${unsigned}.${base64Url(new Uint8Array(signature))}`;
}

function randomHex(bytes = 32) {
  return [...crypto.getRandomValues(new Uint8Array(bytes))]
    .map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

function randomBase64Url(bytes = 32) {
  return base64Url(crypto.getRandomValues(new Uint8Array(bytes)));
}

function fromBase64Url(value, errorCode) {
  if (typeof value !== "string" || !/^[A-Za-z0-9_-]+$/.test(value)) throw new Error(errorCode);
  const base64 = value.replaceAll("-", "+").replaceAll("_", "/");
  try { return Uint8Array.from(atob(base64 + "=".repeat((4 - base64.length % 4) % 4)), (char) => char.charCodeAt(0)); }
  catch { throw new Error(errorCode); }
}

function githubTokenAad(owner, githubUserId, tokenType) {
  if (!validOwner(owner) || !/^[1-9][0-9]{0,19}$/.test(githubUserId || "") ||
      !["access", "refresh"].includes(tokenType)) throw new Error("GITHUB_CREDENTIAL_UNAVAILABLE");
  return utf8(`gpu-control:github-user-token:v1:${owner}:${githubUserId}:${tokenType}`);
}

async function githubTokenKey(env) {
  const bytes = fromBase64Url(env?.GITHUB_APP_TOKEN_ENCRYPTION_KEY, "GITHUB_CREDENTIAL_UNAVAILABLE");
  if (bytes.length !== 32) throw new Error("GITHUB_CREDENTIAL_UNAVAILABLE");
  return crypto.subtle.importKey("raw", bytes, { name: "AES-GCM" }, false, ["encrypt", "decrypt"]);
}

async function sealGithubUserToken(env, owner, githubUserId, tokenType, token) {
  if (typeof token !== "string" || token.length < 8 || token.length > 4096 || /\s/.test(token)) {
    throw new Error("GITHUB_USER_AUTHORIZATION_INVALID");
  }
  const key = await githubTokenKey(env);
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const ciphertext = await crypto.subtle.encrypt({ name: "AES-GCM", iv,
    additionalData: githubTokenAad(owner, githubUserId, tokenType), tagLength: 128 }, key, utf8(token));
  return { iv: base64Url(iv), ciphertext: base64Url(new Uint8Array(ciphertext)) };
}

async function openGithubUserToken(env, owner, githubUserId, tokenType, row) {
  const key = await githubTokenKey(env);
  const iv = fromBase64Url(row?.[`${tokenType}_token_iv`], "GITHUB_CREDENTIAL_UNAVAILABLE");
  const ciphertext = fromBase64Url(row?.[`${tokenType}_token_ciphertext`], "GITHUB_CREDENTIAL_UNAVAILABLE");
  if (iv.length !== 12 || ciphertext.length < 24 || ciphertext.length > 8192) {
    throw new Error("GITHUB_CREDENTIAL_UNAVAILABLE");
  }
  try {
    const clear = await crypto.subtle.decrypt({ name: "AES-GCM", iv,
      additionalData: githubTokenAad(owner, githubUserId, tokenType), tagLength: 128 }, key, ciphertext);
    return new TextDecoder("utf-8", { fatal: true }).decode(clear);
  } catch { throw new Error("GITHUB_CREDENTIAL_UNAVAILABLE"); }
}

async function pkceChallenge(verifier) {
  return base64Url(await sha256Bytes(utf8(verifier)));
}

export async function createGithubInstallationUrl(db, owner, appSlug, now = Math.floor(Date.now() / 1000)) {
  if (!validOwner(owner) || !validSlug(appSlug) || !Number.isSafeInteger(now)) {
    throw new Error("GITHUB_CONNECTION_INVALID");
  }
  const state = randomHex();
  await db.prepare(`INSERT INTO github_installation_states
    (state_hash, owner_id, created_at, expires_at, consumed_at)
    VALUES (?, ?, ?, ?, NULL)`)
    .bind(await sha256(state), owner, now, now + INSTALL_STATE_TTL_SECONDS).run();
  const url = new URL(`https://github.com/apps/${appSlug}/installations/new`);
  url.searchParams.set("state", state);
  return { authorization_url: url.toString(), expires_at: now + INSTALL_STATE_TTL_SECONDS };
}

function validInstallation(value, expectedId) {
  return value && typeof value === "object" && String(value.id) === expectedId &&
    value.suspended_at == null && value.repository_selection === "selected" &&
    typeof value.account?.login === "string" && /^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38}[A-Za-z0-9])?$/.test(value.account.login) &&
    validReadOnlyPermissions(value.permissions);
}

function validReadOnlyPermissions(value) {
  return value && typeof value === "object" && !Array.isArray(value) &&
    Object.keys(value).sort().join(",") === "contents,metadata" &&
    value.contents === "read" && value.metadata === "read";
}

export async function beginGithubInstallationOAuth(db, state, installationId, installation,
  env, now = Math.floor(Date.now() / 1000)) {
  if (typeof state !== "string" || !/^[a-f0-9]{64}$/.test(state) || !validInstallationId(installationId) ||
      !githubAppOAuthConfigured(env) || !Number.isSafeInteger(now)) {
    throw new Error("GITHUB_CONNECTION_INVALID");
  }
  if (!validInstallation(installation, installationId)) throw new Error("GITHUB_INSTALLATION_SCOPE_INVALID");
  const stateHash = await sha256(state);
  const oauthState = randomHex();
  const verifier = randomBase64Url();
  const claimed = await db.prepare(`UPDATE github_installation_states
    SET oauth_state_hash=?, pending_installation_id=?, pending_account_login=?
    WHERE state_hash=? AND consumed_at IS NULL AND expires_at>? AND oauth_state_hash IS NULL
    RETURNING owner_id`).bind(await sha256(oauthState), installationId, installation.account.login,
      stateHash, now).first();
  if (!claimed) throw new Error("GITHUB_INSTALLATION_STATE_REPLAYED");
  const url = new URL("https://github.com/login/oauth/authorize");
  url.searchParams.set("client_id", env.GITHUB_APP_CLIENT_ID);
  url.searchParams.set("redirect_uri", env.GITHUB_APP_OAUTH_CALLBACK_URL);
  url.searchParams.set("state", oauthState);
  url.searchParams.set("scope", "offline_access");
  url.searchParams.set("code_challenge", await pkceChallenge(verifier));
  url.searchParams.set("code_challenge_method", "S256");
  return { authorization_url: url.toString(),
    pkce_cookie: `__Host-gpu-control-oauth=${oauthState}.${verifier}; Max-Age=${INSTALL_STATE_TTL_SECONDS}; Path=/; Secure; HttpOnly; SameSite=Lax` };
}

async function githubApiWithUserToken(path, token, fetchImpl) {
  if (!(path === "/user" || path.startsWith("/user/")) || path.includes("..") || typeof token !== "string" ||
      token.length > 512 || !/^ghu_[A-Za-z0-9_]{16,508}$/.test(token)) {
    throw new Error("GITHUB_USER_AUTHORIZATION_INVALID");
  }
  let response;
  try {
    response = await fetchImpl(`${API_ORIGIN}${path}`, { method: "GET", redirect: "error",
      headers: { accept: "application/vnd.github+json", authorization: `Bearer ${token}`,
        "x-github-api-version": API_VERSION }, signal: AbortSignal.timeout(5_000) });
  } catch { throw new Error("GITHUB_USER_AUTHORIZATION_FAILED"); }
  if (response.status === 401 || response.status === 403) throw new Error("GITHUB_USER_AUTHORIZATION_REQUIRED");
  return githubJson(response);
}

export async function readGithubOAuthIdentity(userToken, fetchImpl = fetch) {
  const user = await githubApiWithUserToken("/user", userToken, fetchImpl);
  if (!Number.isSafeInteger(user?.id) || user.id < 1 || typeof user.login !== "string" ||
      !/^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38}[A-Za-z0-9])?$/.test(user.login)) {
    throw new Error("GITHUB_USER_IDENTITY_INVALID");
  }
  return { id: String(user.id), login: user.login };
}

export async function exchangeGithubOAuthCode(env, code, codeVerifier, options = {}) {
  if (!githubAppOAuthConfigured(env) || typeof code !== "string" ||
      !/^[A-Za-z0-9._-]{1,512}$/.test(code) || typeof codeVerifier !== "string" ||
      !/^[A-Za-z0-9._~-]{43,128}$/.test(codeVerifier)) throw new Error("GITHUB_USER_AUTHORIZATION_INVALID");
  const fetchImpl = options.fetchImpl || fetch;
  let response;
  try {
    response = await fetchImpl("https://github.com/login/oauth/access_token", { method: "POST", redirect: "error",
      headers: { accept: "application/json", "content-type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ client_id: env.GITHUB_APP_CLIENT_ID,
        client_secret: env.GITHUB_APP_CLIENT_SECRET, code, redirect_uri: env.GITHUB_APP_OAUTH_CALLBACK_URL,
        code_verifier: codeVerifier }),
      signal: AbortSignal.timeout(5_000) });
  } catch { throw new Error("GITHUB_USER_AUTHORIZATION_FAILED"); }
  const result = await githubJson(response);
  if (typeof result.access_token !== "string" || !/^ghu_[A-Za-z0-9_]{16,508}$/.test(result.access_token) ||
      typeof result.refresh_token !== "string" || !/^ghr_[A-Za-z0-9_]{16,508}$/.test(result.refresh_token) ||
      result.token_type !== "bearer" || result.scope !== "" ||
      !Number.isSafeInteger(result.expires_in) || result.expires_in < 60 || result.expires_in > 28_800 ||
      !Number.isSafeInteger(result.refresh_token_expires_in) || result.refresh_token_expires_in < 60 ||
      result.refresh_token_expires_in > 15_897_600) {
    throw new Error("GITHUB_USER_AUTHORIZATION_FAILED");
  }
  return { access_token: result.access_token, refresh_token: result.refresh_token,
    access_expires_in: result.expires_in, refresh_expires_in: result.refresh_token_expires_in };
}

async function refreshGithubOAuthToken(env, refreshToken, fetchImpl) {
  let response;
  try {
    response = await fetchImpl("https://github.com/login/oauth/access_token", { method: "POST", redirect: "error",
      headers: { accept: "application/json", "content-type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ client_id: env.GITHUB_APP_CLIENT_ID,
        client_secret: env.GITHUB_APP_CLIENT_SECRET, grant_type: "refresh_token", refresh_token: refreshToken }),
      signal: AbortSignal.timeout(5_000) });
  } catch { throw new Error("GITHUB_USER_AUTHORIZATION_REQUIRED"); }
  if (!response.ok) throw new Error("GITHUB_USER_AUTHORIZATION_REQUIRED");
  let result;
  try {
    const bytes = await readBoundedResponseBytes(response, { maxBytes: 16_384,
      tooLargeCode: "GITHUB_USER_AUTHORIZATION_REQUIRED", missingBodyCode: "GITHUB_USER_AUTHORIZATION_REQUIRED" });
    result = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
  } catch { throw new Error("GITHUB_USER_AUTHORIZATION_REQUIRED"); }
  if (typeof result.access_token !== "string" || !/^ghu_[A-Za-z0-9_]{16,508}$/.test(result.access_token) ||
      typeof result.refresh_token !== "string" || !/^ghr_[A-Za-z0-9_]{16,508}$/.test(result.refresh_token) ||
      result.token_type !== "bearer" || !Number.isSafeInteger(result.expires_in) ||
      result.expires_in < 60 || result.expires_in > 28_800 ||
      !Number.isSafeInteger(result.refresh_token_expires_in) || result.refresh_token_expires_in < 60 ||
      result.refresh_token_expires_in > 15_897_600) throw new Error("GITHUB_USER_AUTHORIZATION_REQUIRED");
  return result;
}

async function currentGithubUserToken(env, db, owner, connection, githubUserId, options = {}) {
  const now = options.now ?? Math.floor(Date.now() / 1000);
  if (connection.access_token_expires_at > now + 60) {
    return openGithubUserToken(env, owner, githubUserId, "access", connection);
  }
  if (connection.refresh_token_expires_at <= now) throw new Error("GITHUB_USER_AUTHORIZATION_REQUIRED");
  const fetchImpl = options.fetchImpl || fetch;
  let refreshToken;
  try { refreshToken = await openGithubUserToken(env, owner, githubUserId, "refresh", connection); }
  catch { throw new Error("GITHUB_USER_AUTHORIZATION_REQUIRED"); }
  let refreshed;
  try { refreshed = await refreshGithubOAuthToken(env, refreshToken, fetchImpl); }
  catch {
    // Another simultaneous request may have rotated the one-time refresh token.
    const latest = await getOwnedGithubInstallation(db, owner);
    if (latest?.access_token_expires_at > now + 60) {
      return openGithubUserToken(env, owner, githubUserId, "access", latest);
    }
    throw new Error("GITHUB_USER_AUTHORIZATION_REQUIRED");
  }
  const access = await sealGithubUserToken(env, owner, githubUserId, "access", refreshed.access_token);
  const refresh = await sealGithubUserToken(env, owner, githubUserId, "refresh", refreshed.refresh_token);
  const updated = await db.prepare(`UPDATE github_app_installations SET
    access_token_ciphertext=?, access_token_iv=?, refresh_token_ciphertext=?, refresh_token_iv=?,
    access_token_expires_at=?, refresh_token_expires_at=?
    WHERE owner_id=? AND installation_id=?`).bind(access.ciphertext, access.iv, refresh.ciphertext,
      refresh.iv, now + refreshed.expires_in, now + refreshed.refresh_token_expires_in,
      owner, connection.installation_id).run();
  if ((updated?.meta?.changes ?? updated?.changes ?? 0) !== 1) throw new Error("GITHUB_USER_AUTHORIZATION_REQUIRED");
  return refreshed.access_token;
}

export async function completeGithubInstallationOAuth(env, db, oauthState, tokens, fetchImpl = fetch,
  now = Math.floor(Date.now() / 1000)) {
  if (typeof oauthState !== "string" || !/^[a-f0-9]{64}$/.test(oauthState) ||
      !tokens || typeof tokens.access_token !== "string" || !/^ghu_[A-Za-z0-9_]{16,508}$/.test(tokens.access_token) ||
      typeof tokens.refresh_token !== "string" || !/^ghr_[A-Za-z0-9_]{16,508}$/.test(tokens.refresh_token) ||
      !Number.isSafeInteger(tokens.access_expires_in) || tokens.access_expires_in < 60 || tokens.access_expires_in > 28_800 ||
      !Number.isSafeInteger(tokens.refresh_expires_in) || tokens.refresh_expires_in < 60 ||
      tokens.refresh_expires_in > 15_897_600 ||
      !Number.isSafeInteger(now)) throw new Error("GITHUB_CONNECTION_INVALID");
  const stateHash = await sha256(oauthState);
  const intent = await db.prepare(`SELECT owner_id, pending_installation_id, pending_account_login,
      expires_at, consumed_at FROM github_installation_states WHERE oauth_state_hash=?`)
    .bind(stateHash).first();
  if (!intent || intent.expires_at <= now) throw new Error("GITHUB_INSTALLATION_STATE_EXPIRED");
  if (intent.consumed_at !== null) throw new Error("GITHUB_INSTALLATION_STATE_REPLAYED");
  if (!validInstallationId(intent.pending_installation_id)) throw new Error("GITHUB_USER_INSTALLATION_ACCESS_INVALID");
  const identity = await readGithubOAuthIdentity(tokens.access_token, fetchImpl);
  const authorizedRepositories = [];
  let totalCount = null;
  const pageSize = 25;
  for (let page = 1; page <= 20; page += 1) {
    const access = await githubApiWithUserToken(
      `/user/installations/${intent.pending_installation_id}/repositories?per_page=${pageSize}&page=${page}`,
      tokens.access_token, fetchImpl);
    if (!Number.isSafeInteger(access.total_count) || access.total_count < 0 || access.total_count > 500 ||
        !Array.isArray(access.repositories) || access.repositories.length > pageSize ||
        (totalCount !== null && totalCount !== access.total_count)) {
      throw new Error("GITHUB_USER_INSTALLATION_ACCESS_INVALID");
    }
    totalCount = access.total_count;
    for (const repository of access.repositories) {
      if (!Number.isSafeInteger(repository?.id) || repository.id < 1 ||
          typeof repository.full_name !== "string" ||
          !/^[A-Za-z0-9-]+\/[A-Za-z0-9_.-]+$/.test(repository.full_name)) {
        throw new Error("GITHUB_USER_INSTALLATION_ACCESS_INVALID");
      }
      authorizedRepositories.push({ id: String(repository.id), repository: repository.full_name.toLowerCase() });
    }
    if (authorizedRepositories.length >= totalCount || access.repositories.length === 0) break;
  }
  if (totalCount === null || authorizedRepositories.length !== totalCount ||
      new Set(authorizedRepositories.map((item) => item.id)).size !== authorizedRepositories.length) {
    throw new Error("GITHUB_USER_INSTALLATION_ACCESS_INVALID");
  }
  const owner = intent.owner_id;
  const accessToken = await sealGithubUserToken(env, owner, identity.id, "access", tokens.access_token);
  const refreshToken = await sealGithubUserToken(env, owner, identity.id, "refresh", tokens.refresh_token);
  const consumedAt = now;
  const completionNonce = randomHex();
  const results = await db.batch([
    db.prepare(`UPDATE github_installation_states SET consumed_at=?, completion_nonce=?
      WHERE oauth_state_hash=? AND pending_installation_id=? AND owner_id=?
        AND consumed_at IS NULL AND expires_at>?
        AND NOT EXISTS (SELECT 1 FROM github_owner_identities
          WHERE owner_id=? AND github_user_id<>?)
        AND NOT EXISTS (SELECT 1 FROM github_owner_identities
          WHERE github_user_id=? AND owner_id<>?) RETURNING owner_id`)
      .bind(consumedAt, completionNonce, stateHash, intent.pending_installation_id, intent.owner_id, now,
        intent.owner_id, identity.id, identity.id, intent.owner_id),
    db.prepare(`DELETE FROM github_app_installations WHERE owner_id=(
      SELECT owner_id FROM github_installation_states WHERE oauth_state_hash=? AND completion_nonce=?)`)
      .bind(stateHash, completionNonce),
    db.prepare(`INSERT INTO github_app_installations
      (owner_id, installation_id, account_login, repository_selection, user_authorized_repositories_json,
       access_token_ciphertext, access_token_iv, refresh_token_ciphertext, refresh_token_iv,
       access_token_expires_at, refresh_token_expires_at, connected_at)
      SELECT owner_id, pending_installation_id, pending_account_login, 'selected', ?, ?, ?, ?, ?, ?, ?, ?
      FROM github_installation_states WHERE oauth_state_hash=? AND completion_nonce=?
      ON CONFLICT(owner_id) DO UPDATE SET installation_id=excluded.installation_id,
        account_login=excluded.account_login, repository_selection=excluded.repository_selection,
        user_authorized_repositories_json=excluded.user_authorized_repositories_json,
        access_token_ciphertext=excluded.access_token_ciphertext, access_token_iv=excluded.access_token_iv,
        refresh_token_ciphertext=excluded.refresh_token_ciphertext, refresh_token_iv=excluded.refresh_token_iv,
        access_token_expires_at=excluded.access_token_expires_at,
        refresh_token_expires_at=excluded.refresh_token_expires_at,
        connected_at=excluded.connected_at`)
      .bind(JSON.stringify(authorizedRepositories), accessToken.ciphertext, accessToken.iv,
        refreshToken.ciphertext, refreshToken.iv, now + tokens.access_expires_in,
        now + tokens.refresh_expires_in, now, stateHash, completionNonce),
    db.prepare(`INSERT INTO github_owner_identities (owner_id, github_user_id, verified_at)
      SELECT owner_id, ?, ? FROM github_installation_states
      WHERE oauth_state_hash=? AND completion_nonce=?
      ON CONFLICT(owner_id) DO UPDATE SET verified_at=excluded.verified_at
        WHERE github_owner_identities.github_user_id=excluded.github_user_id`)
      .bind(identity.id, now, stateHash, completionNonce),
  ]);
  if (results?.[0]?.results?.length !== 1 || (results?.[2]?.meta?.changes ?? 0) !== 1 ||
      (results?.[3]?.meta?.changes ?? 0) !== 1) {
    const existing = await db.prepare(`SELECT owner_id FROM github_owner_identities
      WHERE github_user_id=?`).bind(identity.id).first();
    if (existing && existing.owner_id !== intent.owner_id) throw new Error("GITHUB_IDENTITY_ALREADY_LINKED");
    const ownerIdentity = await db.prepare(`SELECT github_user_id FROM github_owner_identities
      WHERE owner_id=?`).bind(intent.owner_id).first();
    if (ownerIdentity && ownerIdentity.github_user_id !== identity.id) {
      throw new Error("GITHUB_IDENTITY_CHANGE_REQUIRES_RELINK");
    }
    throw new Error("GITHUB_INSTALLATION_STATE_REPLAYED");
  }
  return { connected: true, account_login: intent.pending_account_login, repository_selection: "selected" };
}

export async function githubConnectionStatus(db, owner) {
  if (!validOwner(owner)) throw new Error("GITHUB_CONNECTION_INVALID");
  const row = await db.prepare(`SELECT account_login, repository_selection, connected_at
    FROM github_app_installations WHERE owner_id=?`).bind(owner).first();
  return row ? { connected: true, account_login: row.account_login,
    repository_selection: row.repository_selection, connected_at: row.connected_at }
    : { connected: false };
}

export async function disconnectGithubApp(db, owner) {
  if (!validOwner(owner)) throw new Error("GITHUB_CONNECTION_INVALID");
  await db.prepare(`DELETE FROM github_app_installations WHERE owner_id=?`).bind(owner).run();
  return { connected: false, disconnected: true };
}

async function githubJson(response) {
  if (!response.ok || response.status >= 300) throw new Error("GITHUB_APP_API_FAILED");
  const bytes = await readBoundedResponseBytes(response, {
    maxBytes: 32_768,
    tooLargeCode: "GITHUB_APP_API_RESPONSE_INVALID",
    missingBodyCode: "GITHUB_APP_API_RESPONSE_INVALID",
  });
  try { return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes)); }
  catch { throw new Error("GITHUB_APP_API_RESPONSE_INVALID"); }
}

async function appRequest(env, path, { method = "GET", body, fetchImpl = fetch, now } = {}) {
  if (!path.startsWith("/app/") || path.includes("..")) throw new Error("GITHUB_APP_API_FAILED");
  const jwt = await createGithubAppJwt(env, now);
  let response;
  try {
    response = await fetchImpl(`${API_ORIGIN}${path}`, { method, redirect: "error",
      headers: { accept: "application/vnd.github+json", authorization: `Bearer ${jwt}`,
        "x-github-api-version": API_VERSION, ...(body ? { "content-type": "application/json" } : {}) },
      ...(body ? { body: JSON.stringify(body) } : {}), signal: AbortSignal.timeout(5_000) });
  } catch {
    throw new Error("GITHUB_APP_API_FAILED");
  }
  return githubJson(response);
}

export async function verifyGithubInstallation(env, installationId, options = {}) {
  if (!validInstallationId(installationId)) throw new Error("GITHUB_CONNECTION_INVALID");
  const result = await appRequest(env, `/app/installations/${installationId}`, options);
  if (!validInstallation(result, installationId)) throw new Error("GITHUB_INSTALLATION_SCOPE_INVALID");
  return { id: String(result.id), account: { login: result.account.login },
    repository_selection: result.repository_selection, permissions: result.permissions,
    suspended_at: result.suspended_at ?? null };
}

export async function createGithubInstallationToken(env, installationId, repository, options = {}) {
  if (!validInstallationId(installationId) || typeof repository !== "string" ||
      !/^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})\/[A-Za-z0-9_.-]{1,100}$/.test(repository)) {
    throw new Error("GITHUB_CONNECTION_INVALID");
  }
  const result = await appRequest(env, `/app/installations/${installationId}/access_tokens`, {
    ...options, method: "POST", body: { repositories: [repository.split("/")[1]],
      permissions: { contents: "read", metadata: "read" } },
  });
  const expires = Date.parse(result?.expires_at);
  if (typeof result?.token !== "string" || result.token.length > 512 ||
      !Number.isFinite(expires) || expires <= Date.now() ||
      !validReadOnlyPermissions(result.permissions) ||
      !Array.isArray(result.repositories) || result.repositories.length !== 1 ||
      result.repositories[0]?.full_name?.toLowerCase() !== repository.toLowerCase()) {
    throw new Error("GITHUB_INSTALLATION_TOKEN_SCOPE_INVALID");
  }
  return { token: result.token, expires_at: Math.floor(expires / 1000) };
}

export async function listGithubInstallationRepositories(env, installationId, options = {}) {
  if (!validInstallationId(installationId)) throw new Error("GITHUB_CONNECTION_INVALID");
  const minted = await appRequest(env, `/app/installations/${installationId}/access_tokens`, {
    ...options, method: "POST", body: { permissions: { contents: "read", metadata: "read" } },
  });
  const tokenExpires = Date.parse(minted?.expires_at);
  if (typeof minted?.token !== "string" || minted.token.length > 512 ||
      !Number.isFinite(tokenExpires) || tokenExpires <= Date.now() ||
      !validReadOnlyPermissions(minted.permissions)) {
    throw new Error("GITHUB_INSTALLATION_TOKEN_SCOPE_INVALID");
  }
  const repos = [];
  for (let page = 1; page <= 20; page += 1) {
    const url = new URL(`${API_ORIGIN}/installation/repositories`);
    url.searchParams.set("per_page", "25");
    url.searchParams.set("page", String(page));
    let response;
    try {
      response = await (options.fetchImpl || fetch)(url, { method: "GET", redirect: "error",
        headers: { accept: "application/vnd.github+json", authorization: `Bearer ${minted.token}`,
          "x-github-api-version": API_VERSION }, signal: AbortSignal.timeout(5_000) });
    } catch { throw new Error("GITHUB_APP_API_FAILED"); }
    const result = await githubJson(response);
    if (!Array.isArray(result?.repositories) || result.repositories.length > 25 ||
        !Number.isSafeInteger(result.total_count) || result.total_count > 500) {
      throw new Error("GITHUB_APP_API_RESPONSE_INVALID");
    }
    for (const repo of result.repositories) {
      if (!Number.isSafeInteger(repo?.id) || repo.id < 1 ||
          typeof repo?.full_name !== "string" || !/^[A-Za-z0-9-]+\/[A-Za-z0-9_.-]+$/.test(repo.full_name) ||
          typeof repo.private !== "boolean" || typeof repo.default_branch !== "string") {
        throw new Error("GITHUB_APP_API_RESPONSE_INVALID");
      }
      repos.push({ id: String(repo.id), repository: repo.full_name.toLowerCase(), private: repo.private,
        default_branch: repo.default_branch });
    }
    if (repos.length >= result.total_count || result.repositories.length === 0) break;
  }
  return repos;
}

export async function listOwnedGithubRepositories(env, db, owner, options = {}) {
  const connection = await getOwnedGithubInstallation(db, owner);
  if (!connection) throw new Error("GITHUB_CONNECTION_REQUIRED");
  const identity = await db.prepare(`SELECT github_user_id FROM github_owner_identities WHERE owner_id=?`)
    .bind(owner).first();
  if (!identity || !/^[1-9][0-9]{0,19}$/.test(identity.github_user_id || "")) {
    throw new Error("GITHUB_USER_AUTHORIZATION_REQUIRED");
  }
  const userToken = await currentGithubUserToken(env, db, owner, connection, identity.github_user_id, options);
  const currentIdentity = await readGithubOAuthIdentity(userToken, options.fetchImpl || fetch);
  if (currentIdentity.id !== identity.github_user_id) throw new Error("GITHUB_USER_AUTHORIZATION_REQUIRED");
  let authorized;
  try { authorized = JSON.parse(connection.user_authorized_repositories_json); }
  catch { throw new Error("GITHUB_USER_AUTHORIZATION_REQUIRED"); }
  if (!Array.isArray(authorized) || authorized.length > 500 ||
      authorized.some((item) => !item || typeof item !== "object" ||
        !/^[1-9][0-9]{0,19}$/.test(item.id || "") ||
        typeof item.repository !== "string" || !/^[a-z0-9-]+\/[a-z0-9_.-]+$/.test(item.repository))) {
    throw new Error("GITHUB_USER_AUTHORIZATION_REQUIRED");
  }
  const userRepositories = [];
  let totalCount = null;
  for (let page = 1; page <= 20; page += 1) {
    const access = await githubApiWithUserToken(
      `/user/installations/${connection.installation_id}/repositories?per_page=25&page=${page}`,
      userToken, options.fetchImpl || fetch);
    if (!Number.isSafeInteger(access.total_count) || access.total_count < 0 || access.total_count > 500 ||
        !Array.isArray(access.repositories) || access.repositories.length > 25 ||
        (totalCount !== null && totalCount !== access.total_count)) {
      throw new Error("GITHUB_USER_INSTALLATION_ACCESS_INVALID");
    }
    totalCount = access.total_count;
    for (const repo of access.repositories) {
      if (!Number.isSafeInteger(repo?.id) || repo.id < 1 || typeof repo.full_name !== "string" ||
          !/^[A-Za-z0-9-]+\/[A-Za-z0-9_.-]+$/.test(repo.full_name)) {
        throw new Error("GITHUB_USER_INSTALLATION_ACCESS_INVALID");
      }
      userRepositories.push({ id: String(repo.id), repository: repo.full_name.toLowerCase() });
    }
    if (userRepositories.length >= totalCount || access.repositories.length === 0) break;
  }
  if (totalCount === null || userRepositories.length !== totalCount ||
      new Set(userRepositories.map((item) => item.id)).size !== userRepositories.length) {
    throw new Error("GITHUB_USER_INSTALLATION_ACCESS_INVALID");
  }
  const originallyAuthorizedIds = new Set(authorized.map((item) => item.id));
  const currentlyAuthorizedIds = new Set(userRepositories.map((item) => item.id));
  const installationRepositories = await listGithubInstallationRepositories(env, connection.installation_id, options);
  return installationRepositories.filter((repository) => originallyAuthorizedIds.has(repository.id) &&
    currentlyAuthorizedIds.has(repository.id));
}

export async function getOwnedGithubInstallation(db, owner) {
  if (!validOwner(owner)) throw new Error("GITHUB_CONNECTION_INVALID");
  return db.prepare(`SELECT installation_id, account_login, repository_selection, user_authorized_repositories_json,
      access_token_ciphertext, access_token_iv, refresh_token_ciphertext, refresh_token_iv,
      access_token_expires_at, refresh_token_expires_at
    FROM github_app_installations WHERE owner_id=?`).bind(owner).first();
}

/** Mint a short-lived read token only for a repository selected by this Sites owner. */
export async function createOwnedRepositoryReadToken(env, db, owner, repository, options = {}) {
  if (!githubAppConfigured(env) || !githubAppOwnerConnectionConfigured(env)) {
    throw new Error("GITHUB_APP_NOT_CONFIGURED");
  }
  const connection = await getOwnedGithubInstallation(db, owner);
  if (!connection) throw new Error("GITHUB_CONNECTION_REQUIRED");
  const repositories = await listOwnedGithubRepositories(env, db, owner, options);
  if (!repositories.some((item) => item.repository.toLowerCase() === repository.toLowerCase())) {
    throw new Error("GITHUB_REPOSITORY_NOT_SELECTED");
  }
  return createGithubInstallationToken(env, connection.installation_id, repository, options);
}

export const GITHUB_INSTALL_STATE_TTL_SECONDS = INSTALL_STATE_TTL_SECONDS;
