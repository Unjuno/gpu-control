import assert from "node:assert/strict";
import test from "node:test";
import worker from "./index.js";

const sourceSha = "b".repeat(40);
const siteOrigin = "https://gpu-control-sites.unjuno.chatgpt.site";

test("Site confirmation binds one exact plan to the authenticated owner and consumes the CSRF challenge", async () => {
  const runId = "1".repeat(32);
  const fingerprint = "2".repeat(64);
  const now = Math.floor(Date.now() / 1000);
  const plan = { id: runId, owner_id: "test-owner", fingerprint, workload: "tiny-stories-inference-v1",
    repository: "Unjuno/gpu-control", source_sha: sourceSha,
    parameters_json: JSON.stringify({ prompt: "<script>alert(1)</script>", max_new_tokens: 3, seed: 42 }),
    runtime_seconds: 15, max_cost_usd: "0.01", state: "prepared", expires_at: now + 300 };
  const challenges = new Map();
  const authorizations = new Map();
  const env = { GPU_CONTROL_ALLOWED_USER_IDS: "test-owner,other-owner", DB: {} };
  env.DB.prepare = (sql) => ({ bind(...values) { return {
    values,
    async first() {
      if (sql.includes("FROM plans WHERE id=?")) {
        return values[0] === runId && values[1] === "test-owner" && values[2] === fingerprint ? plan : null;
      }
      if (sql.includes("FROM human_authorizations")) return authorizations.get(values[1]) || null;
      throw new Error(`unexpected confirmation query: ${sql}`);
    },
    async run() {
      assert.match(sql, /INSERT OR REPLACE INTO authorization_challenges/);
      const [id, owner, planId, planFingerprint, tokenHash, createdAt, expiresAt] = values;
      challenges.set(tokenHash, { id, owner_id: owner, plan_id: planId, fingerprint: planFingerprint,
        token_hash: tokenHash, created_at: createdAt, expires_at: expiresAt, consumed_at: null });
      return { success: true };
    },
  }; } });
  env.DB.batch = async (statements) => {
    const [consume, create] = statements;
    const consumeValues = consume.values;
    const [consumedAt, tokenHash, owner, planId, planFingerprint, currentTime] = consumeValues;
    const challenge = challenges.get(tokenHash);
    if (!challenge || challenge.consumed_at !== null || challenge.owner_id !== owner || challenge.plan_id !== planId ||
        challenge.fingerprint !== planFingerprint || challenge.expires_at < currentTime || plan.state !== "prepared" ||
        plan.expires_at < currentTime) return [{ meta: { changes: 0 } }, { meta: { changes: 0 } }];
    challenge.consumed_at = consumedAt;
    const [authorizationId, authorizedAt, insertTokenHash, insertOwner, insertPlanId, insertFingerprint] = create.values;
    assert.equal(insertTokenHash, tokenHash);
    assert.equal(insertOwner, owner);
    assert.equal(insertPlanId, planId);
    assert.equal(insertFingerprint, planFingerprint);
    if (authorizations.has(planId)) return [{ meta: { changes: 1 } }, { meta: { changes: 0 } }];
    authorizations.set(planId, { id: authorizationId, owner_id: owner, plan_id: planId, fingerprint: planFingerprint,
      authorization_reference: challenge.id, authorized_at: authorizedAt,
      expires_at: Math.min(challenge.expires_at, plan.expires_at), consumed_at: null });
    return [{ meta: { changes: 1 } }, { meta: { changes: 1 } }];
  };

  const url = `${siteOrigin}/authorize?run_id=${runId}&plan_fingerprint=${fingerprint}`;
  const originalPrepare = env.DB.prepare;
  env.DB.prepare = () => { throw new Error("non-owner confirmation request reached D1"); };
  const anonymous = await worker.fetch(new Request(url), env);
  const anonymousHtml = await anonymous.text();
  assert.equal(anonymous.status, 401);
  assert.match(anonymousHtml, /target="_top"/);
  assert.match(anonymousHtml, new RegExp(encodeURIComponent(`/authorize?run_id=${runId}&plan_fingerprint=${fingerprint}`)));
  assert.match(anonymousHtml, /ChatGPTでサインイン/);
  const nonOwner = await worker.fetch(new Request(url, { headers: { "oai-authenticated-user-id": "other-user" } }), env);
  assert.equal(nonOwner.status, 403);
  env.DB.prepare = originalPrepare;
  const page = await worker.fetch(new Request(url, { headers: { "oai-authenticated-user-id": "test-owner" } }), env);
  const html = await page.text();
  assert.equal(page.status, 200);
  assert.equal(page.headers.get("cache-control"), "no-store");
  assert.match(page.headers.get("content-security-policy"), /frame-ancestors 'none'/);
  assert.match(html, /Modal制御関数料金はこの上限に含まれず/);
  assert.match(html, /CPU request\/limit: 1 physical core \/ memory request\/limit: 512 MiB/);
  assert.match(html, /CPUは上限を超えて使えず、超過時はthrottleされます/);
  assert.match(html, /メモリ上限超過時はSandboxがOOM終了/);
  assert.match(html, /このplanを1回承認する/);
  assert.doesNotMatch(html, /<script>alert\(1\)<\/script>/);
  const token = html.match(/name="challenge" value="([0-9a-f]{64})"/)[1];
  const formBody = new URLSearchParams({ run_id: runId, plan_fingerprint: fingerprint, challenge: token, confirm: "yes" });
  const crossSite = await worker.fetch(new Request(`${siteOrigin}/authorize`, {
    method: "POST", headers: { "oai-authenticated-user-id": "test-owner", origin: "https://attacker.invalid",
      "sec-fetch-site": "cross-site", "content-type": "application/x-www-form-urlencoded" }, body: formBody,
  }), env);
  assert.equal(crossSite.status, 403);
  assert.equal(authorizations.size, 0);

  const wrongOrigin = await worker.fetch(new Request("https://site.invalid/authorize", {
    method: "POST", headers: { "oai-authenticated-user-id": "test-owner", origin: "https://site.invalid",
      "sec-fetch-site": "same-origin", "content-type": "application/x-www-form-urlencoded" }, body: formBody,
  }), env);
  assert.equal(wrongOrigin.status, 403);
  assert.equal(authorizations.size, 0);

  const duplicateBody = new URLSearchParams(formBody);
  duplicateBody.append("confirm", "no");
  const duplicate = await worker.fetch(new Request(`${siteOrigin}/authorize`, {
    method: "POST", headers: { "oai-authenticated-user-id": "test-owner", origin: siteOrigin,
      "sec-fetch-site": "same-origin", "content-type": "application/x-www-form-urlencoded" }, body: duplicateBody,
  }), env);
  assert.equal(duplicate.status, 400);
  assert.equal(authorizations.size, 0);

  const approved = await worker.fetch(new Request(`${siteOrigin}/authorize`, {
    method: "POST", headers: { "oai-authenticated-user-id": "test-owner", origin: siteOrigin,
      "sec-fetch-site": "same-origin", "content-type": "application/x-www-form-urlencoded" }, body: formBody,
  }), env);
  assert.equal(approved.status, 200);
  assert.match(await approved.text(), /チャットに戻り/);
  const authorization = authorizations.get(runId);
  assert.equal(authorization.owner_id, "test-owner");
  assert.equal(authorization.fingerprint, fingerprint);
  assert.equal(authorization.expires_at, plan.expires_at);
  assert.ok(authorization.expires_at > authorization.authorized_at);
  assert.equal(authorization.consumed_at, null);

  const replay = await worker.fetch(new Request(`${siteOrigin}/authorize`, {
    method: "POST", headers: { "oai-authenticated-user-id": "test-owner", origin: siteOrigin,
      "sec-fetch-site": "same-origin", "content-type": "application/x-www-form-urlencoded" }, body: formBody,
  }), env);
  assert.equal(replay.status, 409);
  assert.equal(authorizations.size, 1);
});

