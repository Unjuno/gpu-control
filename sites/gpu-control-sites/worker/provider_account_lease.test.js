import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync, readdirSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";
import {
  deriveProviderAccountScopeHash,
  ProviderAccountLeaseError,
  reserveProviderAccountLease,
  transitionProviderAccountLease,
} from "./provider_account_lease.js";

const MIGRATION_DIR = new URL("../drizzle/", import.meta.url);
const SCOPE_HASH = "a".repeat(64);
const PLAN_A = "b".repeat(64);
const PLAN_B = "c".repeat(64);
const CHALLENGE_A = "d".repeat(64);
const CHALLENGE_B = "e".repeat(64);
const EVIDENCE = "f".repeat(64);
const AUTH_KEY = Buffer.from(Array.from({ length: 32 }, (_, index) => index)).toString("base64");

class SqliteD1 {
  constructor(database) { this.database = database; }
  prepare(sql) {
    const database = this.database;
    let params = [];
    const statement = {
      sql,
      get params() { return params; },
      bind(...values) { params = values; return statement; },
      first() { return database.prepare(sql).get(...params) ?? null; },
      all() { return { results: database.prepare(sql).all(...params) }; },
      run() { return { meta: database.prepare(sql).run(...params) }; },
    };
    return statement;
  }
  batch(statements) {
    this.database.exec("BEGIN IMMEDIATE");
    try {
      const results = statements.map((statement) => ({
        results: this.database.prepare(statement.sql).all(...statement.params),
      }));
      this.database.exec("COMMIT");
      return results;
    } catch (error) {
      this.database.exec("ROLLBACK");
      throw error;
    }
  }
}

function database() {
  const value = new DatabaseSync(":memory:");
  value.exec("PRAGMA foreign_keys = ON");
  for (const name of readdirSync(MIGRATION_DIR).filter((entry) => entry.endsWith(".sql")).sort()) {
    value.exec(readFileSync(new URL(name, MIGRATION_DIR), "utf8"));
  }
  return value;
}

function insertIntent(db, { suffix, fingerprint, challenge, now = 10 }) {
  const planId = `plan-${suffix}`;
  const runId = `run-${suffix}`;
  const ownerId = "site-owner";
  const authorizationId = `authorization-${suffix}`;
  db.prepare(`INSERT INTO plans (
      id, owner_id, idempotency_key, fingerprint, workload, repository, source_sha,
      image_digest, parameters_json, runtime_seconds, max_cost_usd, state, created_at, expires_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'queued', ?, ?)`)
    .run(planId, ownerId, `key-${suffix}`, fingerprint, "registered-workload", "Unjuno/orbitune",
      "1".repeat(40), `sha256:${"2".repeat(64)}`, "{}", 1, "0.01", now, now + 300);
  db.prepare(`INSERT INTO human_authorizations (
      id, owner_id, plan_id, fingerprint, authorization_reference, authorized_at, expires_at, consumed_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)`)
    .run(authorizationId, ownerId, planId, fingerprint, `authorization-ref-${suffix}`, now, now + 600, now + 1);
  db.prepare(`INSERT INTO runs (id, owner_id, plan_id, state, created_at, updated_at)
    VALUES (?, ?, ?, 'queued', ?, ?)`)
    .run(runId, ownerId, planId, now, now);
  return { planId, runId, ownerId, authorizationId, fingerprint, challenge };
}

function leaseInput(intent, { accountScopeSha256 = SCOPE_HASH, now = 20 } = {}) {
  return {
    accountScopeSha256,
    runId: intent.runId,
    ownerId: intent.ownerId,
    planId: intent.planId,
    planFingerprint: intent.fingerprint,
    authorizationId: intent.authorizationId,
    challengeSha256: intent.challenge,
    now,
  };
}

test("RunPod account scope is keyed, stable, and does not expose the raw scope id", async () => {
  const first = await deriveProviderAccountScopeHash({ scopeId: "unjuno-primary", hmacKeyB64: AUTH_KEY });
  const repeat = await deriveProviderAccountScopeHash({ scopeId: "unjuno-primary", hmacKeyB64: AUTH_KEY });
  const other = await deriveProviderAccountScopeHash({ scopeId: "unjuno-secondary", hmacKeyB64: AUTH_KEY });
  assert.match(first, /^[0-9a-f]{64}$/);
  assert.equal(repeat, first);
  assert.notEqual(other, first);
  assert.notEqual(first, "unjuno-primary");
  await assert.rejects(deriveProviderAccountScopeHash({ scopeId: "unjuno-primary", hmacKeyB64: "c2hvcnQ=" }),
    (error) => error instanceof ProviderAccountLeaseError && error.code === "INVALID_ACCOUNT_SCOPE_HMAC_KEY");
});

test("RunPod account lease is idempotent, serialized, fenced, and held through cleanup", async () => {
  const raw = database();
  const db = new SqliteD1(raw);
  try {
    const firstIntent = insertIntent(raw, { suffix: "one", fingerprint: PLAN_A, challenge: CHALLENGE_A });
    const [first, replay] = await Promise.all([
      reserveProviderAccountLease(db, leaseInput(firstIntent)),
      reserveProviderAccountLease(db, leaseInput(firstIntent)),
    ]);
    assert.equal(first.lease_token, replay.lease_token);
    assert.equal(first.generation, 1);
    assert.equal(first.state, "reserved");

    await transitionProviderAccountLease(db, {
      accountScopeSha256: SCOPE_HASH, leaseToken: first.lease_token, generation: 1, revision: 1,
      toState: "released", evidenceType: "provider_create_not_started", evidenceSha256: EVIDENCE, now: 21,
    });
    raw.prepare("UPDATE runs SET state='failed', cleanup_state='confirmed', cleanup_receipt_json=? WHERE id=?")
      .run('{"kind":"not_started"}', firstIntent.runId);
    const secondIntent = insertIntent(raw, { suffix: "two", fingerprint: PLAN_B, challenge: CHALLENGE_B, now: 30 });
    const second = await reserveProviderAccountLease(db, leaseInput(secondIntent, { now: 31 }));
    assert.equal(second.generation, 2);
    assert.equal(second.state, "reserved");

    await assert.rejects(reserveProviderAccountLease(db, leaseInput(firstIntent, { now: 32 })),
      (error) => error instanceof ProviderAccountLeaseError && error.code === "PROVIDER_ACCOUNT_LEASE_BUSY");

    await assert.rejects(transitionProviderAccountLease(db, {
      accountScopeSha256: SCOPE_HASH, leaseToken: first.lease_token, generation: 1, revision: 2,
      toState: "submitting", evidenceType: "stale_worker", evidenceSha256: EVIDENCE, now: 33,
    }), (error) => error instanceof ProviderAccountLeaseError && error.code === "STALE_PROVIDER_ACCOUNT_LEASE");

    const submitting = await transitionProviderAccountLease(db, {
      accountScopeSha256: SCOPE_HASH, leaseToken: second.lease_token, generation: 2, revision: 1,
      toState: "submitting", evidenceType: "create_intent_persisted", evidenceSha256: CHALLENGE_B, now: 34,
    });
    await assert.rejects(Promise.resolve().then(() => raw.prepare(`UPDATE provider_account_lease_events
      SET evidence_type='rewritten' WHERE account_scope_sha256=?`).run(SCOPE_HASH)), /append-only/);
    await assert.rejects(Promise.resolve().then(() => raw.prepare(`DELETE FROM provider_account_lease_events
      WHERE account_scope_sha256=?`).run(SCOPE_HASH)), /append-only/);
    const uncertain = await transitionProviderAccountLease(db, {
      accountScopeSha256: SCOPE_HASH, leaseToken: second.lease_token, generation: 2, revision: submitting.revision,
      toState: "uncertain", evidenceType: "ambiguous_create_outcome", evidenceSha256: EVIDENCE, now: 35,
    });
    await assert.rejects(transitionProviderAccountLease(db, {
      accountScopeSha256: SCOPE_HASH, leaseToken: second.lease_token, generation: 2, revision: uncertain.revision,
      toState: "released", evidenceType: "provider_inventory_absent", evidenceSha256: EVIDENCE, now: 36,
    }), (error) => error instanceof ProviderAccountLeaseError && error.code === "PROVIDER_ACCOUNT_LEASE_TRANSITION_DENIED");
    assert.equal(raw.prepare("SELECT state FROM provider_account_leases WHERE account_scope_sha256=?").get(SCOPE_HASH).state, "uncertain");

    const active = await transitionProviderAccountLease(db, {
      accountScopeSha256: SCOPE_HASH, leaseToken: second.lease_token, generation: 2, revision: uncertain.revision,
      toState: "active", providerJobId: "pod-123", evidenceType: "validated_provider_receipt", evidenceSha256: EVIDENCE, now: 37,
    });
    const cleanup = await transitionProviderAccountLease(db, {
      accountScopeSha256: SCOPE_HASH, leaseToken: second.lease_token, generation: 2, revision: active.revision,
      toState: "cleanup_pending", providerJobId: "pod-123", evidenceType: "cleanup_started", evidenceSha256: EVIDENCE, now: 38,
    });
    raw.prepare(`UPDATE runs SET state='failed', cleanup_state='confirmed', cleanup_receipt_json=? WHERE id=?`)
      .run('{"provider":"runpod","pod_id":"pod-123","terminated":true}', secondIntent.runId);
    const released = await transitionProviderAccountLease(db, {
      accountScopeSha256: SCOPE_HASH, leaseToken: second.lease_token, generation: 2, revision: cleanup.revision,
      toState: "released", evidenceType: "pod_termination_confirmed", evidenceSha256: EVIDENCE, now: 39,
    });
    assert.equal(released.state, "released");
    assert.equal(released.provider_job_id, "pod-123");
    assert.equal(released.release_evidence_sha256, EVIDENCE);
    assert.equal(raw.prepare("SELECT COUNT(*) AS count FROM provider_account_lease_events").get().count, 8);
  } finally {
    raw.close();
  }
});
