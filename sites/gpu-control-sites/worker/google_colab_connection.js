const GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth";
const GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token";
const GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke";
const GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo";
const SITE_PUBLIC_ORIGIN = "https://gpu-control-sites.unjuno.chatgpt.site";
const COLAB_SCOPE = "https://www.googleapis.com/auth/colaboratory";
const CONNECTION_TTL_SECONDS = 600;
const MAX_GOOGLE_RESPONSE_BYTES = 16 * 1024;

const utf8 = (value) => new TextEncoder().encode(value);
const base64Url = (bytes) => {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/g, "");
};
function fromBase64Url(value) {
  if (typeof value !== "string" || !/^[A-Za-z0-9_-]+$/.test(value)) throw new Error("GOOGLE_COLAB_CRYPTO_NOT_CONFIGURED");
  const base64 = value.replaceAll("-", "+").replaceAll("_", "/");
  try { return Uint8Array.from(atob(base64 + "=".repeat((4 - base64.length % 4) % 4)), (char) => char.charCodeAt(0)); }
  catch { throw new Error("GOOGLE_COLAB_CRYPTO_NOT_CONFIGURED"); }
}
function randomHex(bytes = 32) {
  return [...crypto.getRandomValues(new Uint8Array(bytes))].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}
function randomBase64Url(bytes = 32) { return base64Url(crypto.getRandomValues(new Uint8Array(bytes))); }
async function sha256(value) {
  return [...new Uint8Array(await crypto.subtle.digest("SHA-256", utf8(value)))]
    .map((byte) => byte.toString(16).padStart(2, "0")).join("");
}
async function pkceChallenge(verifier) { return base64Url(new Uint8Array(await crypto.subtle.digest("SHA-256", utf8(verifier)))); }
function validOwner(owner) { return typeof owner === "string" && /^[A-Za-z0-9][A-Za-z0-9_.:@-]{0,255}$/.test(owner); }
function validText(value, min = 1, max = 512) { return typeof value === "string" && value.length >= min && value.length <= max; }

export function googleColabOAuthConfigured(env) {
  if (!validText(env?.GOOGLE_COLAB_OAUTH_CLIENT_ID, 8, 256) ||
      !validText(env?.GOOGLE_COLAB_OAUTH_CLIENT_SECRET, 16, 512) ||
      typeof env?.GOOGLE_COLAB_OAUTH_CALLBACK_URL !== "string") return false;
  try {
    const callback = new URL(env.GOOGLE_COLAB_OAUTH_CALLBACK_URL);
    return callback.protocol === "https:" && !callback.username && !callback.password &&
      callback.origin === SITE_PUBLIC_ORIGIN && !callback.search && !callback.hash &&
      callback.pathname === "/google/oauth/callback";
  } catch { return false; }
}

export function googleColabConnectionConfigured(env) {
  if (!googleColabOAuthConfigured(env)) return false;
  try { return fromBase64Url(env.GOOGLE_COLAB_TOKEN_ENCRYPTION_KEY).length === 32; }
  catch { return false; }
}

async function encryptionKey(env) {
  if (typeof env?.GOOGLE_COLAB_TOKEN_ENCRYPTION_KEY !== "string") throw new Error("GOOGLE_COLAB_CRYPTO_NOT_CONFIGURED");
  const bytes = fromBase64Url(env.GOOGLE_COLAB_TOKEN_ENCRYPTION_KEY);
  if (bytes.length !== 32) throw new Error("GOOGLE_COLAB_CRYPTO_NOT_CONFIGURED");
  return crypto.subtle.importKey("raw", bytes, { name: "AES-GCM" }, false, ["encrypt", "decrypt"]);
}

async function encryptRefreshToken(env, token) {
  if (!validText(token, 8, 4096) || /\s/.test(token)) throw new Error("GOOGLE_COLAB_OAUTH_FAILED");
  const key = await encryptionKey(env);
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const encrypted = await crypto.subtle.encrypt({ name: "AES-GCM", iv, tagLength: 128 }, key, utf8(token));
  return { ciphertext: base64Url(new Uint8Array(encrypted)), iv: base64Url(iv) };
}

async function decryptRefreshToken(env, row) {
  const key = await encryptionKey(env);
  const iv = fromBase64Url(row?.refresh_token_iv);
  const ciphertext = fromBase64Url(row?.refresh_token_ciphertext);
  if (iv.length !== 12 || ciphertext.length < 24 || ciphertext.length > 4096) throw new Error("GOOGLE_COLAB_CREDENTIAL_UNAVAILABLE");
  try {
    const clear = await crypto.subtle.decrypt({ name: "AES-GCM", iv, tagLength: 128 }, key, ciphertext);
    return new TextDecoder("utf-8", { fatal: true }).decode(clear);
  } catch { throw new Error("GOOGLE_COLAB_CREDENTIAL_UNAVAILABLE"); }
}

async function googleJson(response) {
  const declaredLength = Number(response.headers.get("content-length"));
  if (Number.isFinite(declaredLength) && declaredLength > MAX_GOOGLE_RESPONSE_BYTES) {
    throw new Error("GOOGLE_COLAB_OAUTH_RESPONSE_INVALID");
  }
  let text;
  try {
    if (!response.body) text = "";
    else {
      const reader = response.body.getReader();
      const chunks = [];
      let size = 0;
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        size += value.byteLength;
        if (size > MAX_GOOGLE_RESPONSE_BYTES) {
          await reader.cancel();
          throw new Error("GOOGLE_COLAB_OAUTH_RESPONSE_INVALID");
        }
        chunks.push(value);
      }
      const bytes = new Uint8Array(size);
      let offset = 0;
      for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
      text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
    }
  } catch (error) {
    if (error?.message === "GOOGLE_COLAB_OAUTH_RESPONSE_INVALID") throw error;
    throw new Error("GOOGLE_COLAB_OAUTH_FAILED");
  }
  let value;
  try { value = JSON.parse(text); } catch { throw new Error("GOOGLE_COLAB_OAUTH_RESPONSE_INVALID"); }
  if (!response.ok) throw new Error("GOOGLE_COLAB_OAUTH_FAILED");
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("GOOGLE_COLAB_OAUTH_RESPONSE_INVALID");
  return value;
}
async function googleFetch(fetchImpl, url, init) {
  try { return await fetchImpl(url, { ...init, redirect: "error", signal: AbortSignal.timeout(5_000) }); }
  catch { throw new Error("GOOGLE_COLAB_OAUTH_FAILED"); }
}

export async function createGoogleColabConnectionUrl(db, owner, now = Math.floor(Date.now() / 1000)) {
  if (!db || !validOwner(owner) || !Number.isSafeInteger(now)) throw new Error("GOOGLE_COLAB_CONNECTION_INVALID");
  // Expired/consumed setup attempts have no remaining authority. Bound their
  // retention so repeated connection requests cannot grow this table forever.
  await db.prepare("DELETE FROM google_colab_oauth_states WHERE expires_at<=? OR (consumed_at IS NOT NULL AND consumed_at<?)")
    .bind(now, now - CONNECTION_TTL_SECONDS).run();
  const setupState = randomHex();
  const expiresAt = now + CONNECTION_TTL_SECONDS;
  await db.prepare("INSERT INTO google_colab_oauth_states (setup_state_hash, owner_id, oauth_state_hash, created_at, expires_at, consumed_at) VALUES (?, ?, NULL, ?, ?, NULL)")
    .bind(await sha256(setupState), owner, now, expiresAt).run();
  const url = new URL("/google/setup", SITE_PUBLIC_ORIGIN);
  url.searchParams.set("state", setupState);
  return { authorization_url: url.toString(), expires_at: expiresAt };
}

export async function beginGoogleColabOAuth(db, setupState, env, now = Math.floor(Date.now() / 1000)) {
  if (!db || typeof setupState !== "string" || !/^[a-f0-9]{64}$/.test(setupState) ||
      !googleColabOAuthConfigured(env) || !Number.isSafeInteger(now)) throw new Error("GOOGLE_COLAB_CONNECTION_INVALID");
  const oauthState = randomHex();
  const verifier = randomBase64Url(32);
  const claimed = await db.prepare("UPDATE google_colab_oauth_states SET oauth_state_hash=? WHERE setup_state_hash=? AND consumed_at IS NULL AND expires_at>? AND oauth_state_hash IS NULL RETURNING owner_id")
    .bind(await sha256(oauthState), await sha256(setupState), now).first();
  if (!claimed) throw new Error("GOOGLE_COLAB_CONNECTION_STATE_EXPIRED");
  const url = new URL(GOOGLE_AUTH_URL);
  url.searchParams.set("client_id", env.GOOGLE_COLAB_OAUTH_CLIENT_ID);
  url.searchParams.set("redirect_uri", env.GOOGLE_COLAB_OAUTH_CALLBACK_URL);
  url.searchParams.set("response_type", "code");
  url.searchParams.set("scope", "openid email " + COLAB_SCOPE);
  url.searchParams.set("access_type", "offline");
  url.searchParams.set("include_granted_scopes", "true");
  url.searchParams.set("prompt", "consent");
  url.searchParams.set("state", oauthState);
  url.searchParams.set("code_challenge", await pkceChallenge(verifier));
  url.searchParams.set("code_challenge_method", "S256");
  return { authorization_url: url.toString(), pkce_cookie: "__Host-gpu-control-colab-oauth=" +
    oauthState + "." + verifier + "; Max-Age=" + CONNECTION_TTL_SECONDS + "; Path=/; Secure; HttpOnly; SameSite=Lax" };
}

async function exchangeCode(env, code, verifier, fetchImpl) {
  if (!googleColabOAuthConfigured(env) || !validText(code, 1, 2048) || /\s/.test(code) ||
      typeof verifier !== "string" || !/^[A-Za-z0-9_-]{43,128}$/.test(verifier)) throw new Error("GOOGLE_COLAB_OAUTH_FAILED");
  const response = await googleFetch(fetchImpl, GOOGLE_TOKEN_URL, { method: "POST",
    headers: { accept: "application/json", "content-type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ code, client_id: env.GOOGLE_COLAB_OAUTH_CLIENT_ID,
      client_secret: env.GOOGLE_COLAB_OAUTH_CLIENT_SECRET, redirect_uri: env.GOOGLE_COLAB_OAUTH_CALLBACK_URL,
      grant_type: "authorization_code", code_verifier: verifier }) });
  const value = await googleJson(response);
  if (!validText(value.access_token, 8, 4096) || !validText(value.refresh_token, 8, 4096) ||
      typeof value.scope !== "string" || !value.scope.split(/\s+/).includes(COLAB_SCOPE) ||
      !Number.isSafeInteger(value.expires_in) || value.expires_in < 60 || value.expires_in > 86_400) {
    throw new Error("GOOGLE_COLAB_OAUTH_SCOPE_INVALID");
  }
  return value;
}

async function fetchGoogleIdentity(accessToken, fetchImpl) {
  const response = await googleFetch(fetchImpl, GOOGLE_USERINFO_URL, { method: "GET",
    headers: { accept: "application/json", authorization: "Bearer " + accessToken } });
  const value = await googleJson(response);
  if (typeof value.sub !== "string" || !/^[A-Za-z0-9_-]{1,255}$/.test(value.sub) ||
      typeof value.email !== "string" || value.email.length > 320 ||
      !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.email) || value.email_verified !== true) {
    throw new Error("GOOGLE_COLAB_IDENTITY_INVALID");
  }
  return { subject: value.sub, email: value.email };
}

export async function completeGoogleColabOAuth(db, env, oauthState, verifier, code, options = {}) {
  const now = options.now ?? Math.floor(Date.now() / 1000);
  if (!db || typeof oauthState !== "string" || !/^[a-f0-9]{64}$/.test(oauthState) ||
      typeof verifier !== "string" || !/^[A-Za-z0-9_-]{43,128}$/.test(verifier) || !Number.isSafeInteger(now)) {
    throw new Error("GOOGLE_COLAB_CONNECTION_INVALID");
  }
  const stateHash = await sha256(oauthState);
  const claimed = await db.prepare("UPDATE google_colab_oauth_states SET consumed_at=? WHERE oauth_state_hash=? AND consumed_at IS NULL AND expires_at>? RETURNING owner_id")
    .bind(now, stateHash, now).first();
  if (!claimed) throw new Error("GOOGLE_COLAB_CONNECTION_STATE_REPLAYED");
  const fetchImpl = options.fetchImpl || fetch;
  const tokens = await exchangeCode(env, code, verifier, fetchImpl);
  const identity = await fetchGoogleIdentity(tokens.access_token, fetchImpl);
  const sealed = await encryptRefreshToken(env, tokens.refresh_token);
  const existing = await db.prepare("SELECT google_subject_id, connected_at FROM google_colab_accounts WHERE owner_id=?")
    .bind(claimed.owner_id).first();
  if (existing && existing.google_subject_id !== identity.subject) {
    throw new Error("GOOGLE_COLAB_RECONNECT_REQUIRES_DISCONNECT");
  }
  const connectedAt = existing?.google_subject_id === identity.subject ? existing.connected_at : now;
  await db.prepare("INSERT INTO google_colab_accounts (owner_id, google_subject_id, account_email, refresh_token_ciphertext, refresh_token_iv, connected_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(owner_id) DO UPDATE SET google_subject_id=excluded.google_subject_id, account_email=excluded.account_email, refresh_token_ciphertext=excluded.refresh_token_ciphertext, refresh_token_iv=excluded.refresh_token_iv, connected_at=excluded.connected_at, updated_at=excluded.updated_at")
    .bind(claimed.owner_id, identity.subject, identity.email, sealed.ciphertext, sealed.iv, connectedAt, now).run();
  return { connected: true, account_email: identity.email, connected_at: connectedAt };
}

export async function googleColabConnectionStatus(db, owner) {
  if (!validOwner(owner)) throw new Error("GOOGLE_COLAB_CONNECTION_INVALID");
  const row = await db.prepare("SELECT account_email, connected_at FROM google_colab_accounts WHERE owner_id=?").bind(owner).first();
  return row ? { connected: true, account_email: row.account_email, connected_at: row.connected_at } : { connected: false };
}

export async function googleColabAccessToken(db, env, owner, options = {}) {
  if (!validOwner(owner)) throw new Error("GOOGLE_COLAB_CONNECTION_INVALID");
  const row = await db.prepare("SELECT refresh_token_ciphertext, refresh_token_iv, google_subject_id FROM google_colab_accounts WHERE owner_id=?").bind(owner).first();
  if (!row) throw new Error("GOOGLE_COLAB_CONNECTION_REQUIRED");
  if (!googleColabOAuthConfigured(env)) throw new Error("GOOGLE_COLAB_OAUTH_NOT_CONFIGURED");
  const refreshToken = await decryptRefreshToken(env, row);
  const response = await googleFetch(options.fetchImpl || fetch, GOOGLE_TOKEN_URL, { method: "POST",
    headers: { accept: "application/json", "content-type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ client_id: env.GOOGLE_COLAB_OAUTH_CLIENT_ID,
      client_secret: env.GOOGLE_COLAB_OAUTH_CLIENT_SECRET, refresh_token: refreshToken, grant_type: "refresh_token" }) });
  const value = await googleJson(response);
  if (!validText(value.access_token, 8, 4096) ||
      (value.scope !== undefined && (typeof value.scope !== "string" || !value.scope.split(/\s+/).includes(COLAB_SCOPE)))) {
    throw new Error("GOOGLE_COLAB_OAUTH_SCOPE_INVALID");
  }
  return { access_token: value.access_token, expires_in: Number.isSafeInteger(value.expires_in) ? value.expires_in : null,
    google_subject_id: row.google_subject_id };
}

export async function disconnectGoogleColab(db, env, owner, options = {}) {
  if (!validOwner(owner)) throw new Error("GOOGLE_COLAB_CONNECTION_INVALID");
  const row = await db.prepare("SELECT refresh_token_ciphertext, refresh_token_iv FROM google_colab_accounts WHERE owner_id=?").bind(owner).first();
  if (!row) return { disconnected: false, remote_revoked: false };
  let remoteRevoked = false;
  try {
    const token = await decryptRefreshToken(env, row);
    const response = await googleFetch(options.fetchImpl || fetch, GOOGLE_REVOKE_URL, { method: "POST",
      headers: { "content-type": "application/x-www-form-urlencoded" }, body: new URLSearchParams({ token }) });
    remoteRevoked = response.ok;
  } catch { remoteRevoked = false; }
  await db.prepare("DELETE FROM google_colab_accounts WHERE owner_id=?").bind(owner).run();
  await db.prepare("DELETE FROM google_colab_oauth_states WHERE owner_id=?").bind(owner).run();
  return { disconnected: true, remote_revoked: remoteRevoked };
}
