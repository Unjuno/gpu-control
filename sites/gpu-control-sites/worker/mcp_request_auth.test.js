import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import test from "node:test";

import { authenticateMcpPrincipal, mcpAuthorizationChallenge, mcpOwnerAllowlistStatus,
  sitesOwnerFromRequest } from "./mcp_request_auth.js";

const request = (headers = {}) => new Request("https://gpu-control.example/mcp", { headers });

test("Sites identity resolves only an exact allowlisted owner within the header bound", () => {
  const env = { GPU_CONTROL_ALLOWED_USER_IDS: "owner-a, owner-b" };
  assert.equal(sitesOwnerFromRequest(request({ "oai-authenticated-user-id": "owner-a" }), env), "owner-a");
  assert.equal(sitesOwnerFromRequest(request({ "oai-authenticated-user-id": "owner-a,owner-b" }), env), null);
  assert.equal(sitesOwnerFromRequest(request({ "oai-authenticated-user-id": "x".repeat(257) }), env), null);
  assert.equal(sitesOwnerFromRequest(request({ "oai-authenticated-user-id": "owner-a" }), {}), null);
});

test("owner allowlist status exposes only a count and scope, never identities", () => {
  assert.deepEqual(mcpOwnerAllowlistStatus({}), {
    configured: false, allowed_owner_count: 0, scope: "closed",
  });
  assert.deepEqual(mcpOwnerAllowlistStatus({ GPU_CONTROL_ALLOWED_USER_IDS: "owner-a, owner-a" }), {
    configured: true, allowed_owner_count: 1, scope: "single_owner",
  });
  assert.deepEqual(mcpOwnerAllowlistStatus({ GPU_CONTROL_ALLOWED_USER_IDS: "owner-a,owner-b" }), {
    configured: true, allowed_owner_count: 2, scope: "multiple_owners",
  });
});

test("ChatGPT Sites principal receives the existing read and execute scopes", async () => {
  const principal = await authenticateMcpPrincipal(
    request({ "oai-authenticated-user-id": "owner-a" }),
    { GPU_CONTROL_ALLOWED_USER_IDS: "owner-a" });
  assert.deepEqual(principal, { owner_id: "owner-a", auth_method: "chatgpt_sites",
    scopes: ["experiments:read", "experiments:execute"] });
});

test("unallowlisted platform identity is denied and malformed bearer never touches storage", async () => {
  assert.deepEqual(await authenticateMcpPrincipal(
    request({ "oai-authenticated-user-id": "owner-a" }),
    { GPU_CONTROL_ALLOWED_USER_IDS: "owner-b" }), { denied: "forbidden" });
  assert.equal(await authenticateMcpPrincipal(request({ authorization: "Bearer invalid" }), {
    DB: { prepare() { throw new Error("must not inspect storage"); } },
  }), null);
});

test("OAuth bearer access is revoked immediately when its owner leaves the current allowlist", async () => {
  const token = `gpc_at_${"a".repeat(43)}`;
  const tokenHash = createHash("sha256").update(token).digest("hex");
  const DB = {
    prepare(sql) {
      return { bind(...values) {
        return { first: async () => {
          if (!sql.includes("FROM mcp_oauth_tokens") || values[0] !== tokenHash) return null;
          return { owner_id: "owner-a", client_id: "client", scope: "experiments:read experiments:execute",
            resource: "https://gpu-control.example/mcp", expires_at: 2_000_000_000 };
        } };
      } };
    },
  };
  const bearerRequest = request({ authorization: `Bearer ${token}` });
  assert.equal((await authenticateMcpPrincipal(bearerRequest,
    { DB, GPU_CONTROL_ALLOWED_USER_IDS: "owner-a" })).owner_id, "owner-a");
  assert.deepEqual(await authenticateMcpPrincipal(bearerRequest,
    { DB, GPU_CONTROL_ALLOWED_USER_IDS: "owner-b" }), { denied: "forbidden" });
  assert.deepEqual(await authenticateMcpPrincipal(bearerRequest, { DB }), { denied: "forbidden" });
});

test("authorization challenges preserve resource discovery, scope and status semantics", () => {
  const unauthenticated = mcpAuthorizationChallenge(request());
  assert.equal(unauthenticated.status, 401);
  assert.match(unauthenticated.headers.get("www-authenticate"), /scope="experiments:read"/);
  const forbidden = mcpAuthorizationChallenge(request(), { error: "forbidden" });
  assert.equal(forbidden.status, 403);
  assert.match(forbidden.headers.get("www-authenticate"), /oauth-protected-resource/);
  const scope = mcpAuthorizationChallenge(request(), { error: "insufficient_scope", scope: "experiments:execute" });
  assert.equal(scope.status, 403);
  assert.match(scope.headers.get("www-authenticate"), /scope="experiments:execute"/);
});
