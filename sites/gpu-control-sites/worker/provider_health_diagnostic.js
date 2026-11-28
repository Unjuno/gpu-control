import { modalConfigured, providerHealth } from "./modal_http_client.js";
import { MODAL_HEALTH_CHECK_COOLDOWN_SECONDS } from "./provider_health_policy.js";
import { modalCpuAdmissionEnabled } from "./modal_cpu_policy.js";

async function runProviderHealthDiagnostic(env, owner, runId, fingerprint, authorizationValidated) {
  if (!env.DB) return {
    schema_version: 2, status: "blocked", human_summary: "D1 database is not configured; the health-check budget cannot be enforced.",
    machine_state: { configured: false, sandbox_started: false },
    next_allowed_actions: [], blocking_reason: "D1_NOT_CONFIGURED",
  };
  if (!modalConfigured(env)) return {
    schema_version: 2, status: "blocked", human_summary: "Modal接続設定が不足しています。Sandboxは起動していません。",
    machine_state: { configured: false, sandbox_started: false, admission_enabled: modalCpuAdmissionEnabled(env) },
    next_allowed_actions: [], blocking_reason: "MODAL_PROVIDER_NOT_CONFIGURED",
  };
  const now = Math.floor(Date.now() / 1000);
  if (!authorizationValidated) {
    let authorization;
    try {
      authorization = await env.DB.prepare(`SELECT p.id FROM plans p JOIN human_authorizations a
        ON a.plan_id=p.id AND a.owner_id=p.owner_id AND a.fingerprint=p.fingerprint
        WHERE p.id=? AND p.owner_id=? AND p.fingerprint=? AND p.state='prepared' AND p.expires_at>=?
          AND a.expires_at>=? AND a.consumed_at IS NULL`)
        .bind(runId, owner, fingerprint, now, now).first();
    } catch {
      return {
        schema_version: 2, status: "blocked", human_summary: "承認状態を確認できません。Modalには接続していません。",
        machine_state: { configured: true, sandbox_started: false, inference_started: false },
        next_allowed_actions: [], blocking_reason: "HUMAN_AUTHORIZATION_STORE_UNAVAILABLE",
      };
    }
    if (!authorization) return {
      schema_version: 2, status: "blocked", human_summary: "この正確なplanはSites確認ページでまだ承認されていないか、期限切れです。Modalには接続していません。",
      machine_state: { configured: true, sandbox_started: false, inference_started: false },
      next_allowed_actions: [], blocking_reason: "HUMAN_AUTHORIZATION_REQUIRED",
    };
  }
  if (!modalCpuAdmissionEnabled(env)) return {
    schema_version: 2, status: "blocked", human_summary: "CPU Admissionは停止中です。Modal healthには接続していません。",
    machine_state: { configured: true, admission_enabled: false, sandbox_started: false, inference_started: false },
    next_allowed_actions: [], blocking_reason: "CPU_WORKLOAD_ADMISSION_DISABLED",
  };
  let reservation;
  try {
    reservation = await env.DB.prepare(`INSERT INTO modal_health_check_limits (scope, last_checked_at)
      VALUES ('workspace', ?) ON CONFLICT(scope) DO UPDATE SET last_checked_at=excluded.last_checked_at
      WHERE modal_health_check_limits.last_checked_at <= ?`)
      .bind(now, now - MODAL_HEALTH_CHECK_COOLDOWN_SECONDS).run();
  } catch {
    return {
      schema_version: 2, status: "blocked", human_summary: "Modal health check budget could not be reserved; no provider request was sent.",
      machine_state: { configured: true, sandbox_started: false, inference_started: false },
      next_allowed_actions: [], blocking_reason: "MODAL_HEALTH_CHECK_LIMIT_UNAVAILABLE",
    };
  }
  if (reservation?.meta?.changes !== 1) return {
    schema_version: 2, status: "blocked", human_summary: "Modal health check was recently used. Wait before checking again.",
    machine_state: { configured: true, sandbox_started: false, inference_started: false, cooldown_seconds: MODAL_HEALTH_CHECK_COOLDOWN_SECONDS },
    next_allowed_actions: [], blocking_reason: "MODAL_HEALTH_CHECK_RATE_LIMITED",
  };
  let planCheck;
  try {
    planCheck = await env.DB.prepare(`INSERT INTO modal_authorized_health_checks (plan_id, owner_id, fingerprint, checked_at)
      SELECT p.id, p.owner_id, p.fingerprint, ? FROM plans p JOIN human_authorizations a
        ON a.plan_id=p.id AND a.owner_id=p.owner_id AND a.fingerprint=p.fingerprint
      WHERE p.id=? AND p.owner_id=? AND p.fingerprint=? AND p.state='prepared' AND p.expires_at>=?
        AND a.expires_at>=? AND a.consumed_at IS NULL
      ON CONFLICT(plan_id) DO NOTHING`)
      .bind(now, runId, owner, fingerprint, now, now).run();
  } catch {
    return {
      schema_version: 2, status: "blocked", human_summary: "plan単位のhealth利用枠を確保できません。Modalには接続していません。",
      machine_state: { configured: true, sandbox_started: false, inference_started: false },
      next_allowed_actions: [], blocking_reason: "MODAL_PLAN_HEALTH_LIMIT_UNAVAILABLE",
    };
  }
  if (planCheck?.meta?.changes !== 1) return {
    schema_version: 2, status: "blocked", human_summary: "このplanのModal health確認はすでに使われています。再確認には新しいplanの確認が必要です。",
    machine_state: { configured: true, sandbox_started: false, inference_started: false },
    next_allowed_actions: [], blocking_reason: "MODAL_PLAN_HEALTH_ALREADY_CHECKED",
  };
  const result = await providerHealth(env);
  const ready = !!result.provider;
  try {
    const persisted = await env.DB.prepare(`UPDATE modal_authorized_health_checks SET ready=?
      WHERE plan_id=? AND owner_id=? AND fingerprint=? AND checked_at=?`)
      .bind(ready ? 1 : 0, runId, owner, fingerprint, now).run();
    if (persisted?.meta?.changes !== 1) throw new Error("MODAL_HEALTH_RESULT_ROW_MISSING");
  } catch {
    return {
      schema_version: 2, status: "blocked",
      human_summary: "Modal health確認結果を安全に保存できませんでした。Sandboxは起動していません。",
      machine_state: { configured: true, sandbox_started: false, inference_started: false },
      next_allowed_actions: [], blocking_reason: "MODAL_HEALTH_RESULT_PERSISTENCE_FAILED",
    };
  }
  return {
    schema_version: 2, status: ready ? "ok" : "blocked",
    human_summary: ready
      ? "Modalの認証済みhealth応答と登録済みworkload identityが一致しました。Sandboxと推論は開始していません。"
      : "Modalのhealth確認に失敗したか、登録済みworkload identityと一致しません。Sandboxと推論は開始していません。",
    machine_state: {
      configured: true, ready, checks: result.checks,
      admission_enabled: modalCpuAdmissionEnabled(env),
      sandbox_started: false, inference_started: false,
      control_function_cost_included_in_sandbox_ceiling: false,
    },
    next_allowed_actions: [], blocking_reason: ready ? null : "MODAL_PROVIDER_HEALTH_MISMATCH",
  };
}



/** Health-tool entry: verify the exact owner-bound human authorization here. */
export function providerHealthDiagnostic(env, owner, runId, fingerprint) {
  return runProviderHealthDiagnostic(env, owner, runId, fingerprint, false);
}

/** Submit entry: use only after the caller has validated this exact authorization. */
export function providerHealthDiagnosticForAuthorizedSubmit(env, owner, runId, fingerprint) {
  return runProviderHealthDiagnostic(env, owner, runId, fingerprint, true);
}
