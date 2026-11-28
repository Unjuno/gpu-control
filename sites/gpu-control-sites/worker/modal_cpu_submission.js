import { normalizeTrainingArguments, validToolArguments } from "./experiment_input_contract.js";
import { HUMAN_AUTHORIZATION_TTL_SECONDS } from "./human_authorization_policy.js";
import { estimateModalSandboxCostUsd } from "./modal_cpu_policy.js";
import { prepareModalComputeBudgetReservation, utcMonthKey } from "./provider_budget_policy.js";
import { providerHealthDiagnosticForAuthorizedSubmit } from "./provider_health_diagnostic.js";
import { modalConfigured } from "./modal_http_client.js";
import { WORKLOADS } from "./workload_registry.js";

const WORKLOAD = WORKLOADS.tiny_stories.id;

export async function submitModalCpuRun(env, owner, args, request, services) {
  if (!validToolArguments("experiment_submit", args, env)) throw new Error("INVALID_ARGUMENTS");
    const now = Math.floor(Date.now() / 1000);
    const existing = await env.DB.prepare("SELECT id, state, created_at FROM runs WHERE owner_id=? AND plan_id=?")
      .bind(owner, args.run_id).first();
    if (existing) return { schema_version: 2, status: "ok", human_summary: services.submitSummary(existing.state), run_id: existing.id,
      machine_state: { state: existing.state, created_at: existing.created_at }, next_allowed_actions: ["experiment_status"], blocking_reason: null };
    const plan = await env.DB.prepare(`SELECT id, owner_id, fingerprint, workload, repository, source_sha,
        parameters_json, runtime_seconds, max_cost_usd, image_digest, state, expires_at
      FROM plans WHERE id=? AND owner_id=? AND fingerprint=?`).bind(args.run_id, owner, args.plan_fingerprint).first();
    let parameters;
    try { parameters = plan ? JSON.parse(plan.parameters_json) : null; } catch { parameters = null; }
    const approved = args.approved_plan;
    if (!plan || plan.state !== "prepared" || plan.expires_at <= now || plan.image_digest !== env.CPU_WORKLOAD_IMAGE_DIGEST ||
        !parameters || plan.workload !== approved.workload || plan.repository !== approved.repository || plan.source_sha !== approved.commit ||
        parameters.prompt !== approved.prompt || parameters.max_new_tokens !== approved.max_new_tokens || parameters.seed !== approved.seed ||
        plan.runtime_seconds !== approved.runtime_seconds || plan.max_cost_usd !== approved.max_cost_usd ||
        estimateModalSandboxCostUsd(plan.runtime_seconds) !== approved.estimated_sandbox_cost_usd) {
      return { schema_version: 2, status: "blocked", human_summary: "ChatGPTの確認内容が、このownerの現在有効なplanと完全一致しません。新しいplanを準備して内容を確認してください。",
        machine_state: { run_id: args.run_id, plan_valid: false, authorization_required: true, sandbox_started: false },
        next_allowed_actions: [], blocking_reason: "APPROVED_PLAN_MISMATCH_OR_EXPIRED" };
    }
    let authorization = await env.DB.prepare(`SELECT id, fingerprint, expires_at, consumed_at FROM human_authorizations
      WHERE owner_id=? AND plan_id=? AND fingerprint=?`).bind(owner, args.run_id, args.plan_fingerprint).first();
    if (!authorization) {
      const authorizationId = services.randomHex(16);
      const authorizationReference = `chatgpt-tool:${services.randomHex(16)}`;
      try {
        await env.DB.prepare(`INSERT INTO human_authorizations
            (id, owner_id, plan_id, fingerprint, authorization_reference, authorized_at, expires_at, consumed_at, authorization_source)
          SELECT ?, p.owner_id, p.id, p.fingerprint, ?, ?, MIN(?, p.expires_at), NULL, 'chatgpt_mcp_write_confirmation'
          FROM plans p
          WHERE p.id=? AND p.owner_id=? AND p.fingerprint=? AND p.workload=? AND p.repository=? AND p.source_sha=?
            AND json_extract(p.parameters_json, '$.prompt')=?
            AND json_extract(p.parameters_json, '$.max_new_tokens')=?
            AND json_extract(p.parameters_json, '$.seed')=?
            AND p.runtime_seconds=? AND p.max_cost_usd=? AND p.image_digest=?
            AND p.state='prepared' AND p.expires_at>?
          ON CONFLICT(plan_id) DO NOTHING`)
          .bind(authorizationId, authorizationReference, now, now + HUMAN_AUTHORIZATION_TTL_SECONDS,
            args.run_id, owner, args.plan_fingerprint, approved.workload, approved.repository, approved.commit,
            approved.prompt, approved.max_new_tokens, approved.seed, approved.runtime_seconds,
            approved.max_cost_usd, env.CPU_WORKLOAD_IMAGE_DIGEST, now).run();
      } catch {
        return { schema_version: 2, status: "blocked", human_summary: "ChatGPT承認をplanに安全に記録できませんでした。Sandboxは起動していません。",
          machine_state: { run_id: args.run_id, authorization_valid: false, sandbox_started: false },
          next_allowed_actions: [], blocking_reason: "CHATGPT_AUTHORIZATION_PERSISTENCE_FAILED" };
      }
      authorization = await env.DB.prepare(`SELECT id, fingerprint, expires_at, consumed_at FROM human_authorizations
        WHERE owner_id=? AND plan_id=? AND fingerprint=?`).bind(owner, args.run_id, args.plan_fingerprint).first();
    }
    if (!authorization || authorization.fingerprint !== args.plan_fingerprint) {
      return { schema_version: 2, status: "blocked", human_summary: "このplanのowner-bound承認を確認できません。新しいplanを準備し、ChatGPTで再確認してください。",
        machine_state: { run_id: args.run_id, authorization_required: true, authorization_valid: false },
        next_allowed_actions: [], blocking_reason: "HUMAN_AUTHORIZATION_REQUIRED" };
    }
    if (authorization.expires_at < now) return { schema_version: 2, status: "blocked",
      human_summary: "実験の承認が期限切れです。新しいplanを準備し、内容をもう一度確認してください。",
      machine_state: { run_id: args.run_id, authorization_required: true, authorization_valid: false },
      next_allowed_actions: [], blocking_reason: "HUMAN_AUTHORIZATION_EXPIRED" };
    if (authorization.consumed_at !== null) return { schema_version: 2, status: "blocked",
      human_summary: "この承認はすでに使用済みです。新しいplanを準備し、内容をもう一度確認してください。",
      machine_state: { run_id: args.run_id, authorization_required: true, authorization_valid: false },
      next_allowed_actions: [], blocking_reason: "HUMAN_AUTHORIZATION_ALREADY_USED" };
    if (!modalConfigured(env)) return { schema_version: 2, status: "blocked",
      human_summary: "Modal接続設定が不足しています。Sandboxは起動していません。",
      machine_state: { run_id: args.run_id, available: false, sandbox_started: false },
      next_allowed_actions: [], blocking_reason: "MODAL_PROVIDER_NOT_CONFIGURED" };
    if (env.CPU_WORKLOAD_ADMISSION_ENABLED !== "true") return { schema_version: 2, status: "blocked",
      human_summary: "CPU実行Admissionは停止中です。Modalには接続していません。",
      machine_state: { run_id: args.run_id, admission_enabled: false, sandbox_started: false },
      next_allowed_actions: [], blocking_reason: "CPU_WORKLOAD_ADMISSION_DISABLED" };
    // The standalone health tool owns the one-use workspace and plan health
    // reservations as well. A successful prior diagnostic can be reused.
    let priorPlanHealth;
    try {
      priorPlanHealth = await env.DB.prepare(`SELECT ready FROM modal_authorized_health_checks
        WHERE plan_id=? AND owner_id=? AND fingerprint=?`)
        .bind(args.run_id, owner, args.plan_fingerprint).first();
    } catch {
      return { schema_version: 2, status: "blocked",
        human_summary: "このplanのhealth確認状態を安全に読み取れないため、Modalには接続していません。",
        machine_state: { run_id: args.run_id, sandbox_started: false },
        next_allowed_actions: [], blocking_reason: "MODAL_PLAN_HEALTH_STATE_UNAVAILABLE" };
    }
    if (priorPlanHealth && priorPlanHealth.ready !== 1) return { schema_version: 2, status: "blocked",
      human_summary: "このplanのModal health確認は成功していません。接続を復旧して新しいplanを確認してください。",
      machine_state: { run_id: args.run_id, sandbox_started: false },
      next_allowed_actions: [], blocking_reason: "MODAL_PLAN_HEALTH_ALREADY_CHECKED" };
    if (!priorPlanHealth) {
      const health = await providerHealthDiagnosticForAuthorizedSubmit(env, owner, args.run_id, args.plan_fingerprint);
      if (health.status !== "ok") {
        const blockingReason = health.blocking_reason === "MODAL_PROVIDER_HEALTH_MISMATCH"
          ? "MODAL_PROVIDER_HEALTH_FAILED" : health.blocking_reason;
        const { checks, ...healthState } = health.machine_state || {};
        return { ...health,
          machine_state: { run_id: args.run_id, provider: "modal_cpu", workload: WORKLOAD,
            ...healthState, ...(checks ? { provider_health_checks: checks } : {}), sandbox_started: false },
          blocking_reason: blockingReason,
        };
      }
    }
    const reservationAt = Math.floor(Date.now() / 1000);
    if (authorization.expires_at < reservationAt) return { schema_version: 2, status: "blocked",
      human_summary: "実験の承認が有効期限を過ぎました。新しいplanを準備して確認してください。",
      machine_state: { run_id: args.run_id, authorization_required: true, authorization_valid: false },
      authorization_url: services.authorizationUrl(request, args.run_id, args.plan_fingerprint), next_allowed_actions: [], blocking_reason: "HUMAN_AUTHORIZATION_EXPIRED" };
    try {
      const providerReservation = prepareModalComputeBudgetReservation(env.DB, {
        runId: args.run_id, source: "modal_cpu", fingerprint: args.plan_fingerprint,
        periodKey: utcMonthKey(reservationAt), requestedMicrousd: 10000, now: reservationAt,
      });
      const submissionBatch = await env.DB.batch([
        providerReservation,
        env.DB.prepare(`UPDATE human_authorizations SET consumed_at=?
          WHERE id=? AND owner_id=? AND plan_id=? AND fingerprint=? AND expires_at>=? AND consumed_at IS NULL
            AND EXISTS (SELECT 1 FROM plans p WHERE p.id=? AND p.owner_id=? AND p.fingerprint=? AND p.state='prepared' AND p.expires_at>=?)
            AND EXISTS (SELECT 1 FROM modal_compute_budget_reservations r WHERE r.run_id=? AND r.source='modal_cpu'
              AND r.plan_fingerprint=? AND r.period_key=? AND r.reserved_microusd=10000)`)
          .bind(reservationAt, authorization.id, owner, args.run_id, args.plan_fingerprint, reservationAt,
            args.run_id, owner, args.plan_fingerprint, reservationAt, args.run_id, args.plan_fingerprint,
            utcMonthKey(reservationAt)),
        env.DB.prepare(`UPDATE plans SET state = 'queued' WHERE id = ? AND owner_id = ? AND fingerprint = ? AND image_digest = ? AND state = 'prepared' AND expires_at >= ?
          AND EXISTS (SELECT 1 FROM human_authorizations a WHERE a.id=? AND a.owner_id=? AND a.plan_id=? AND a.fingerprint=? AND a.consumed_at=?)`)
          .bind(args.run_id, owner, args.plan_fingerprint, env.CPU_WORKLOAD_IMAGE_DIGEST, reservationAt, authorization.id, owner, args.run_id, args.plan_fingerprint, reservationAt),
        env.DB.prepare(`INSERT INTO runs (id, owner_id, plan_id, state, created_at, updated_at)
          SELECT p.id, p.owner_id, p.id, 'queued', ?, ? FROM plans p
          WHERE p.id = ? AND p.owner_id = ? AND p.fingerprint = ? AND p.image_digest = ? AND p.state = 'queued' AND p.expires_at >= ?
            AND EXISTS (SELECT 1 FROM human_authorizations a WHERE a.id=? AND a.owner_id=? AND a.plan_id=? AND a.fingerprint=? AND a.consumed_at=?)`)
          .bind(reservationAt, reservationAt, args.run_id, owner, args.plan_fingerprint, env.CPU_WORKLOAD_IMAGE_DIGEST, reservationAt, authorization.id, owner, args.run_id, args.plan_fingerprint, reservationAt),
        env.DB.prepare(`DELETE FROM modal_compute_budget_reservations WHERE run_id=? AND source='modal_cpu'
          AND plan_fingerprint=? AND period_key=? AND reserved_microusd=10000
          AND NOT EXISTS (SELECT 1 FROM runs r WHERE r.plan_id=?)`)
          .bind(args.run_id, args.plan_fingerprint, utcMonthKey(reservationAt), args.run_id),
      ]);
      if (submissionBatch?.[0]?.meta?.changes === 0) {
        const existingRun = await env.DB.prepare(`SELECT id, state, created_at FROM runs WHERE owner_id=? AND plan_id=?`)
          .bind(owner, args.run_id).first();
        if (existingRun) return { schema_version: 2, status: "ok", human_summary: services.submitSummary(existingRun.state),
          run_id: existingRun.id, machine_state: { state: existingRun.state, created_at: existingRun.created_at },
          next_allowed_actions: ["experiment_status"], blocking_reason: null };
        return { schema_version: 2, status: "blocked",
          human_summary: "Modal計算ルート共通の予算上限を確保できないか、予約状態が一致しません。Modalには接続していません。",
          machine_state: { run_id: args.run_id, provider: "modal_cpu", sandbox_started: false },
          next_allowed_actions: ["experiment_status"], blocking_reason: "PROVIDER_BUDGET_EXHAUSTED" };
      }
    } catch {
      const active = await env.DB.prepare("SELECT id, state FROM runs WHERE state IN ('queued', 'running') LIMIT 1").first();
      if (active) return { schema_version: 2, status: "blocked", human_summary: "実行枠は使用中です。", blocking_reason: "PROVIDER_SLOT_BUSY", run_id: null };
      throw new Error("SUBMIT_TRANSACTION_FAILED");
    }
    const run = await env.DB.prepare(`SELECT r.id, r.state, r.created_at, r.cancel_requested, p.workload, p.repository,
        p.source_sha, p.image_digest, p.fingerprint, p.parameters_json, p.runtime_seconds
      FROM runs r JOIN plans p ON p.id=r.plan_id WHERE r.owner_id=? AND r.plan_id=?`).bind(owner, args.run_id).first();
    if (!run) throw new Error("PLAN_EXPIRED_OR_ALREADY_USED");
    if (run.state === "queued") {
      const providerSubmitAt = Math.floor(Date.now() / 1000);
      if (authorization.expires_at < providerSubmitAt) {
        await env.DB.prepare(`UPDATE runs SET state='failed', failure_code='HUMAN_AUTHORIZATION_EXPIRED', cleanup_state='confirmed', updated_at=?
          WHERE id=? AND owner_id=? AND state='queued'`).bind(providerSubmitAt, run.id, owner).run();
        return { schema_version: 2, status: "blocked", human_summary: "Modal呼び出し前に承認の有効期限が切れました。新しいplanを準備して確認してください。",
          machine_state: { run_id: run.id, state: "failed", cleanup_state: "confirmed", authorization_valid: false },
          next_allowed_actions: ["experiment_status"], blocking_reason: "HUMAN_AUTHORIZATION_EXPIRED" };
      }
      await env.DB.prepare("UPDATE runs SET state='running', lease_expires_at=?, updated_at=? WHERE id=? AND owner_id=? AND state='queued'")
        .bind(providerSubmitAt + run.runtime_seconds + 30, providerSubmitAt, run.id, owner).run();
      await services.synchronizeModalRun(env, run.id, owner, { submit: true, authorizationExpiresAt: authorization.expires_at });
    }
    const updated = await env.DB.prepare("SELECT state, created_at, updated_at, cleanup_state, failure_code FROM runs WHERE id=? AND owner_id=?").bind(run.id, owner).first();
    return { schema_version: 2, status: updated?.state === "running" ? "pending" : "ok", human_summary: services.submitSummary(updated?.state), run_id: run.id,
      machine_state: { state: updated?.state, created_at: updated?.created_at, updated_at: updated?.updated_at, cleanup_state: updated?.cleanup_state, failure_code: updated?.failure_code },
      next_allowed_actions: updated?.state === "running" ? ["experiment_status", "experiment_cancel"] : ["experiment_status"], blocking_reason: null };
}
