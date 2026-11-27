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

async function sha256(value) {
  const digest = await crypto.subtle.digest("SHA-256", utf8(value));
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

function randomHex(bytes = 32) {
  return [...crypto.getRandomValues(new Uint8Array(bytes))]
    .map((byte) => byte.toString(16).padStart(2, "0")).join("");
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

export async function bindGithubInstallation(db, state, installationId, verifyInstallation,
  now = Math.floor(Date.now() / 1000)) {
  if (typeof state !== "string" || !/^[a-f0-9]{64}$/.test(state) || !validInstallationId(installationId) ||
      typeof verifyInstallation !== "function" || !Number.isSafeInteger(now)) {
    throw new Error("GITHUB_CONNECTION_INVALID");
  }
  const stateHash = await sha256(state);
  const intent = await db.prepare(`SELECT owner_id, expires_at, consumed_at FROM github_installation_states
    WHERE state_hash=?`).bind(stateHash).first();
  if (!intent || intent.expires_at <= now) {
    throw new Error("GITHUB_INSTALLATION_STATE_EXPIRED");
  }
  if (intent.consumed_at !== null) throw new Error("GITHUB_INSTALLATION_STATE_REPLAYED");
  const installation = await verifyInstallation(installationId);
  if (!validInstallation(installation, installationId)) throw new Error("GITHUB_INSTALLATION_SCOPE_INVALID");

  // Consume the browser callback state before saving its installation binding.
  // Competing callbacks can produce at most one successful claim.
  const claimed = await db.prepare(`UPDATE github_installation_states SET consumed_at=?
    WHERE state_hash=? AND owner_id=? AND consumed_at IS NULL AND expires_at>?
    RETURNING owner_id`).bind(now, stateHash, intent.owner_id, now).first();
  if (!claimed) throw new Error("GITHUB_INSTALLATION_STATE_REPLAYED");
  const existing = await db.prepare(`SELECT owner_id FROM github_app_installations WHERE installation_id=?`)
    .bind(installationId).first();
  if (existing && existing.owner_id !== intent.owner_id) throw new Error("GITHUB_INSTALLATION_ALREADY_LINKED");
  await db.batch([
    db.prepare(`DELETE FROM github_app_installations WHERE owner_id=?`).bind(intent.owner_id),
    db.prepare(`INSERT INTO github_app_installations
      (owner_id, installation_id, account_login, repository_selection, connected_at)
      VALUES (?, ?, ?, 'selected', ?)
      ON CONFLICT(owner_id) DO UPDATE SET installation_id=excluded.installation_id,
        account_login=excluded.account_login, repository_selection=excluded.repository_selection,
        connected_at=excluded.connected_at`)
      .bind(intent.owner_id, installationId, installation.account.login, now),
  ]);
  return { connected: true, account_login: installation.account.login, repository_selection: "selected" };
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
  const length = Number(response.headers.get("content-length"));
  if (Number.isFinite(length) && length > 32_768) throw new Error("GITHUB_APP_API_RESPONSE_INVALID");
  if (!response.body) throw new Error("GITHUB_APP_API_RESPONSE_INVALID");
  const reader = response.body.getReader();
  let size = 0;
  const chunks = [];
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > 32_768) {
        await reader.cancel();
        throw new Error("GITHUB_APP_API_RESPONSE_INVALID");
      }
      chunks.push(value);
    }
  } finally { reader.releaseLock(); }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
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
    ...options, method: "POST", body: { repositories: [repository],
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
  for (let page = 1; page <= 5; page += 1) {
    const url = new URL(`${API_ORIGIN}/installation/repositories`);
    url.searchParams.set("per_page", "100");
    url.searchParams.set("page", String(page));
    let response;
    try {
      response = await (options.fetchImpl || fetch)(url, { method: "GET", redirect: "error",
        headers: { accept: "application/vnd.github+json", authorization: `Bearer ${minted.token}`,
          "x-github-api-version": API_VERSION }, signal: AbortSignal.timeout(5_000) });
    } catch { throw new Error("GITHUB_APP_API_FAILED"); }
    const result = await githubJson(response);
    if (!Array.isArray(result?.repositories) || result.repositories.length > 100 ||
        !Number.isSafeInteger(result.total_count) || result.total_count > 500) {
      throw new Error("GITHUB_APP_API_RESPONSE_INVALID");
    }
    for (const repo of result.repositories) {
      if (typeof repo?.full_name !== "string" || !/^[A-Za-z0-9-]+\/[A-Za-z0-9_.-]+$/.test(repo.full_name) ||
          typeof repo.private !== "boolean" || typeof repo.default_branch !== "string") {
        throw new Error("GITHUB_APP_API_RESPONSE_INVALID");
      }
      repos.push({ repository: repo.full_name.toLowerCase(), private: repo.private,
        default_branch: repo.default_branch });
    }
    if (repos.length >= result.total_count || result.repositories.length === 0) break;
  }
  return repos;
}

export async function getOwnedGithubInstallation(db, owner) {
  if (!validOwner(owner)) throw new Error("GITHUB_CONNECTION_INVALID");
  return db.prepare(`SELECT installation_id, account_login, repository_selection
    FROM github_app_installations WHERE owner_id=?`).bind(owner).first();
}

export const GITHUB_INSTALL_STATE_TTL_SECONDS = INSTALL_STATE_TTL_SECONDS;
