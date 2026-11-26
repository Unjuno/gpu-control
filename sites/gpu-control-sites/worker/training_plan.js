import { findOwnedTrainingSource, getOwnedTrainingSource } from "./training_source.js";
import { getTrainingAuthorization } from "./training_authorization.js";

const MAP_REPOSITORY = "unjuno/model-as-a-paper";
const SITE_PUBLIC_ORIGIN = "https://gpu-control-sites.unjuno.chatgpt.site";
const MAX_PRICING_AGE_SECONDS = 30 * 24 * 60 * 60;
const DEFAULT_MAP_EXECUTION = Object.freeze({ dataset: "papers", run_name: "map44m", steps: 100000 });

function trainingAuthorizationUrl(runId, fingerprint) {
  const url = new URL("/authorize-training", SITE_PUBLIC_ORIGIN);
  url.searchParams.set("run_id", runId);
  url.searchParams.set("plan_fingerprint", fingerprint);
  return url.toString();
}

function validMapExecution(value) {
  return value && typeof value === "object" && !Array.isArray(value) &&
    Object.keys(value).sort().join(",") === "dataset,run_name,steps" &&
    typeof value.dataset === "string" && /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/.test(value.dataset) &&
    typeof value.run_name === "string" && /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/.test(value.run_name) &&
    Number.isSafeInteger(value.steps) && value.steps >= 1 && value.steps <= 100000;
}

export async function previewTrainingPlan(env, owner, args) {
  const source = args.registration_id
    ? await getOwnedTrainingSource(env.DB, owner, args.registration_id)
    : await findOwnedTrainingSource(env.DB, owner, args);
  const machine = { ...source, executable: false };
  let execution = DEFAULT_MAP_EXECUTION;
  let executionSpecId = args.execution_spec_id;
  if (!executionSpecId) {
    const { results = [] } = await env.DB.prepare(`SELECT id AS execution_spec_id, spec_json
      FROM training_execution_specs WHERE owner_id=? AND registration_id=?
      ORDER BY created_at DESC, id DESC LIMIT 2`).bind(owner, source.registration_id).all();
    if (results.length > 1) return { schema_version: 2, status: "blocked",
      human_summary: "このソースには複数の学習設定があります。training_listから実行設定を選んでください。",
      machine_state: { ...machine, execution_specs: results.map(({ execution_spec_id, spec_json }) => ({
        execution_spec_id, ...JSON.parse(spec_json),
      })) }, next_allowed_actions: [], blocking_reason: "TRAINING_CONFIGURATION_SELECTION_REQUIRED" };
    if (results.length === 1) {
      executionSpecId = results[0].execution_spec_id;
      execution = JSON.parse(results[0].spec_json);
    }
  } else {
    const spec = await env.DB.prepare(`SELECT spec_json FROM training_execution_specs
      WHERE owner_id=? AND registration_id=? AND id=?`)
      .bind(owner, source.registration_id, executionSpecId).first();
    if (!spec) throw new Error("TRAINING_REGISTRATION_NOT_FOUND");
    execution = JSON.parse(spec.spec_json);
  }
  if (!validMapExecution(execution)) return { schema_version: 2, status: "blocked",
    human_summary: "MAP-44Mの学習設定が不正です。登録済み設定を確認してください。",
    machine_state: { ...machine, ...(executionSpecId ? { execution_spec_id: executionSpecId } : {}) },
    next_allowed_actions: [], blocking_reason: "TRAINING_PROFILE_INVALID" };
  const imageId = env.MAP_TRAINING_MODAL_IMAGE_ID;
  const imageIdentity = imageId || env.MAP_TRAINING_IMAGE_DIGEST;
  const imagePattern = imageId ? /^im-[A-Za-z0-9]{8,128}$/ : /^sha256:[0-9a-f]{64}$/;
  // These values are set by the operator after reviewing the commit and building
  // the image. A registration alone never gives a commit execution authority.
  if (source.repository !== MAP_REPOSITORY ||
      source.commit !== env.MAP_TRAINING_SOURCE_SHA ||
      !imagePattern.test(imageIdentity || "")) {
    return { schema_version: 2, status: "blocked",
      human_summary: "このコミットに対応する検証済みの学習イメージが設定されていません。",
      machine_state: { ...machine, ...execution,
        ...(executionSpecId ? { execution_spec_id: executionSpecId } : {}) },
      next_allowed_actions: [], blocking_reason: "TRAINING_PROFILE_UNAVAILABLE" };
  }
  const now = Math.floor(Date.now() / 1000);
  const hourlyRate = Number(env.MAP_TRAINING_HOURLY_MICROUSD);
  const quoteExpires = Number(env.MAP_TRAINING_QUOTE_EXPIRES_AT);
  if (!Number.isSafeInteger(hourlyRate) || hourlyRate <= 0 || hourlyRate > 1000000000 ||
      !Number.isSafeInteger(quoteExpires) || quoteExpires <= now || quoteExpires > now + MAX_PRICING_AGE_SECONDS) {
    return { schema_version: 2, status: "blocked",
      human_summary: "有効な学習料金の見積もりが設定されていません。",
      machine_state: { ...machine, ...execution,
        ...(executionSpecId ? { execution_spec_id: executionSpecId } : {}) },
      next_allowed_actions: [], blocking_reason: "TRAINING_QUOTE_UNAVAILABLE" };
  }
  // The source app allows up to 600 seconds of startup. Reserve that
  // separately and apply the source policy's 10 percent budget margin.
  const estimatedCost = Math.ceil(hourlyRate * (args.runtime_seconds + 600) / 3240);
  if (estimatedCost > args.max_cost_microusd) {
    return { schema_version: 2, status: "blocked",
      human_summary: "指定された予算上限では、この実行時間の見積もりをカバーできません。",
      machine_state: { ...machine, ...execution,
        ...(executionSpecId ? { execution_spec_id: executionSpecId } : {}),
        estimated_cost_microusd: estimatedCost },
      next_allowed_actions: [], blocking_reason: "TRAINING_BUDGET_TOO_LOW" };
  }
  return { schema_version: 2, status: "ok",
    human_summary: "MAP-44Mの学習条件を確認しました。実行計画を準備できます。",
    machine_state: { ...machine, ...(executionSpecId ? { execution_spec_id: executionSpecId } : {}),
      ...execution, image_digest: imageIdentity, provider: "modal",
      provider_resource_id: "gpu-control-map-training/train_map",
      gpu: "L4", gpu_count: 1, runtime_seconds: args.runtime_seconds,
      estimated_cost_microusd: estimatedCost, hourly_microusd: hourlyRate, quote_expires_at: quoteExpires,
      max_cost_microusd: args.max_cost_microusd, checkpoint_visibility: "owner_private" },
    next_allowed_actions: [], blocking_reason: null };
}

export async function prepareTrainingPlan(env, owner, args) {
  const { idempotency_key: key, ...inputs } = args;
  const preview = await previewTrainingPlan(env, owner, inputs);
  if (preview.status !== "ok") return preview;

  const { executable, ...plan } = preview.machine_state;
  const json = JSON.stringify(plan);
  const bytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(JSON.stringify([owner, json])));
  const fingerprint = [...new Uint8Array(bytes)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
  const now = Math.floor(Date.now() / 1000);
  const expires = Math.min(now + 600, plan.quote_expires_at);
  if (expires <= now) throw new Error("TRAINING_PLAN_EXPIRED");
  await env.DB.prepare(`INSERT INTO training_plans
    (id, owner_id, registration_id, idempotency_key, fingerprint, plan_json, created_at, expires_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(owner_id, idempotency_key) DO NOTHING`)
    .bind(crypto.randomUUID().replaceAll("-", ""), owner, plan.registration_id, key, fingerprint, json, now, expires).run();
  const existing = await env.DB.prepare(`SELECT id, fingerprint, expires_at, cancelled_at, dispatch_claimed_at FROM training_plans
    WHERE owner_id=? AND idempotency_key=?`).bind(owner, key).first();
  if (existing?.fingerprint !== fingerprint) throw new Error("IDEMPOTENCY_KEY_CONFLICT");
  if (existing.expires_at <= now) throw new Error("TRAINING_PLAN_EXPIRED");
  const state = existing.cancelled_at !== null ? "cancelled"
    : existing.dispatch_claimed_at !== null ? "dispatching" : "prepared";
  const authorization = await getTrainingAuthorization(env.DB, owner, existing.id, fingerprint);
  const authorized = state === "prepared" && authorization?.authorized_at !== null &&
    authorization?.authorized_at !== undefined && authorization?.expires_at > now &&
    authorization?.consumed_at === null;
  const admission = env.MAP_TRAINING_ADMISSION_ENABLED === "true" &&
    Number(env.MAP_TRAINING_RUNTIME_SECONDS) === plan.runtime_seconds;
  const actions = state === "prepared" ? ["training_status", "training_cancel"] : ["training_status"];
  const executableNow = state === "prepared" && admission && authorized;
  if (executableNow) actions.unshift("training_submit");
  return { ...preview, approved_plan: plan, next_allowed_actions: actions,
    human_summary: !admission
      ? "学習計画は保存しましたが、現在この条件の実行受付は停止中です。"
      : authorized
      ? "学習計画を保存しました。所有者確認済みなので、このplanを送信できます。"
      : "学習計画を保存しました。送信前にauthorization_urlを開き、このplanの有料実行を確認してください。Modalへのログインは不要です。",
    machine_state: { ...plan, executable: executableNow, run_id: existing.id,
      plan_fingerprint: fingerprint, expires_at: existing.expires_at, state,
      authorization_state: !admission ? "unavailable" : authorized ? "authorized" : "required",
      ...(admission && !authorized && state === "prepared"
        ? { authorization_url: trainingAuthorizationUrl(existing.id, fingerprint) } : {}) } };
}

export async function trainingPlanState(env, owner, runId, cancel = false) {
  const db = env.DB;
  const now = Math.floor(Date.now() / 1000);
  if (cancel) {
    await db.prepare(`UPDATE training_plans SET cancelled_at=?
      WHERE owner_id=? AND id=? AND cancelled_at IS NULL AND dispatch_claimed_at IS NULL AND expires_at>?`)
      .bind(now, owner, runId, now).run();
  }
  const row = await db.prepare(`SELECT fingerprint, expires_at, cancelled_at, dispatch_claimed_at, dispatch_rejection
    FROM training_plans WHERE owner_id=? AND id=?`).bind(owner, runId).first();
  if (!row) throw new Error("RUN_NOT_FOUND");
  const authorization = await getTrainingAuthorization(db, owner, runId, row.fingerprint);
  const state = row.cancelled_at !== null ? "cancelled"
    : row.dispatch_rejection ? "blocked"
    : row.dispatch_claimed_at !== null ? "dispatching" : row.expires_at <= now ? "expired" : "prepared";
  const authorized = state === "prepared" && authorization?.authorized_at !== null &&
    authorization?.authorized_at !== undefined && authorization?.expires_at > now &&
    authorization?.consumed_at === null;
  const admission = env.MAP_TRAINING_ADMISSION_ENABLED === "true";
  return { schema_version: 2, status: "ok", human_summary: "保存済みの学習計画の状態です。",
    machine_state: { run_id: runId, state, plan_fingerprint: row.fingerprint,
      expires_at: row.expires_at, cancelled_at: row.cancelled_at,
      authorization_state: state !== "prepared" ? "none" : !admission ? "unavailable" : authorized ? "authorized" : "required",
      ...(admission && !authorized && state === "prepared"
        ? { authorization_url: trainingAuthorizationUrl(runId, row.fingerprint) } : {}),
      ...(row.dispatch_rejection ? { reason: row.dispatch_rejection } : {}) },
    next_allowed_actions: state === "prepared"
      ? [...(admission && authorized ? ["training_submit"] : []), "training_cancel"] : [], blocking_reason: null };
}

// Authorization must already be established. This single write reserves the
// whole plan ceiling and prevents concurrent or duplicate dispatch claims.
export async function claimTrainingDispatch(db, owner, runId, fingerprint, now, monthlyLimit, authorization) {
  if (!Number.isSafeInteger(monthlyLimit) || monthlyLimit < 1) {
    throw new Error("TRAINING_BUDGET_NOT_CONFIGURED");
  }
  if (!authorization || authorization.authorization_source !== "site_owner_plan_confirmation" ||
      authorization.authorized_by !== owner || authorization.decision_record_id !== `training-plan:${runId}:${fingerprint}` ||
      !/^[0-9a-f]{40}$/.test(authorization.control_plane_sha || "") ||
      !/^[0-9a-f]{32}$/.test(authorization.authorization_id || "") ||
      !/^[0-9a-f]{64}$/.test(authorization.authorization_reference || "")) {
    throw new Error("TRAINING_AUTHORIZATION_INVALID");
  }
  const date = new Date(now * 1000);
  const monthStart = Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), 1) / 1000;
  const results = await db.batch([
    db.prepare(`UPDATE training_plans SET dispatch_claimed_at=?
    WHERE owner_id=? AND id=? AND fingerprint=?
      AND cancelled_at IS NULL AND dispatch_claimed_at IS NULL AND expires_at>?
      AND EXISTS (SELECT 1 FROM training_authorizations a WHERE a.plan_id=training_plans.id
        AND a.owner_id=training_plans.owner_id AND a.fingerprint=training_plans.fingerprint
        AND a.authorization_id=? AND a.authorization_reference=? AND a.control_plane_sha=?
        AND a.authorization_source='site_owner_plan_confirmation' AND a.authorized_by=?
        AND a.decision_record_id=? AND a.authorized_at IS NOT NULL
        AND a.consumed_at IS NULL AND a.expires_at>?)
      AND json_extract(plan_json, '$.max_cost_microusd') +
        COALESCE((SELECT SUM(json_extract(p.plan_json, '$.max_cost_microusd'))
          FROM training_plans p WHERE p.dispatch_claimed_at>=?), 0) <= ?
    RETURNING plan_json`).bind(now, owner, runId, fingerprint, now, authorization.authorization_id,
      authorization.authorization_reference, authorization.control_plane_sha, owner,
      authorization.decision_record_id, now, monthStart, monthlyLimit),
    db.prepare(`UPDATE training_authorizations SET consumed_at=?
      WHERE plan_id=? AND owner_id=? AND fingerprint=? AND control_plane_sha=?
        AND authorization_id=? AND authorization_reference=?
        AND authorization_source='site_owner_plan_confirmation' AND authorized_by=?
        AND decision_record_id=? AND authorized_at IS NOT NULL AND expires_at>?
        AND consumed_at IS NULL AND EXISTS (SELECT 1 FROM training_plans p
          WHERE p.id=training_authorizations.plan_id AND p.owner_id=training_authorizations.owner_id
            AND p.fingerprint=training_authorizations.fingerprint AND p.dispatch_claimed_at=?)`)
      .bind(now, runId, owner, fingerprint, authorization.control_plane_sha,
        authorization.authorization_id, authorization.authorization_reference, owner,
        authorization.decision_record_id, now, now),
  ]);
  return results?.[0]?.results?.[0] || null;
}

export async function submitTrainingPlan(env, owner, args, delegate, isConfigured) {
  const { run_id: runId, plan_fingerprint: fingerprint, approved_plan: approved } = args;
  const row = await env.DB.prepare(`SELECT plan_json, dispatch_claimed_at, expires_at FROM training_plans
    WHERE owner_id=? AND id=? AND fingerprint=?`).bind(owner, runId, fingerprint).first();
  if (!row) throw new Error("RUN_NOT_FOUND");
  const plan = JSON.parse(row.plan_json);
  const { admission_token: _admissionToken, ...approvedPlan } = approved;
  if (Object.keys(approvedPlan).length !== Object.keys(plan).length ||
      Object.entries(plan).some(([key, value]) => !Object.hasOwn(approvedPlan, key) || approvedPlan[key] !== value)) {
    throw new Error("INVALID_ARGUMENTS");
  }
  if (row.dispatch_claimed_at !== null) return trainingPlanState(env, owner, runId);
  const controlPlaneSha = env.MAP_TRAINING_CONTROL_PLANE_SHA;
  if (typeof controlPlaneSha !== "string" || !/^[0-9a-f]{40}$/.test(controlPlaneSha)) {
    return { schema_version: 2, status: "blocked", human_summary: "学習の認証境界が設定されていません。",
      machine_state: { run_id: runId }, next_allowed_actions: ["training_status"],
      blocking_reason: "TRAINING_AUTHORIZATION_NOT_CONFIGURED" };
  }
  if (env.MAP_TRAINING_ADMISSION_ENABLED !== "true" || !isConfigured(env)) {
    return { schema_version: 2, status: "blocked", human_summary: "学習の実行受付は停止中です。",
      machine_state: { run_id: runId }, next_allowed_actions: [], blocking_reason: "TRAINING_ADMISSION_DISABLED" };
  }
  if (Number(env.MAP_TRAINING_RUNTIME_SECONDS) !== plan.runtime_seconds) {
    return { schema_version: 2, status: "blocked",
      human_summary: "計画の時間上限がModalに設定された上限と一致しません。",
      machine_state: { run_id: runId }, next_allowed_actions: [], blocking_reason: "TRAINING_RUNTIME_MISMATCH" };
  }
  const current = await previewTrainingPlan(env, owner, plan);
  const { executable, ...currentPlan } = current.machine_state;
  if (current.status !== "ok" || JSON.stringify(currentPlan) !== row.plan_json) {
    throw new Error("TRAINING_PLAN_EXPIRED");
  }
  const now = Math.floor(Date.now() / 1000);
  const authorization = await getTrainingAuthorization(env.DB, owner, runId, fingerprint);
  const expectedAuthorization = authorization && authorization.authorization_source === "site_owner_plan_confirmation" &&
    authorization.authorized_by === owner && authorization.control_plane_sha === controlPlaneSha &&
    authorization.decision_record_id === `training-plan:${runId}:${fingerprint}` &&
    authorization.target_repository === plan.repository && authorization.target_sha === plan.commit &&
    authorization.image_digest === plan.image_digest && authorization.provider === plan.provider &&
    authorization.provider_resource_id === plan.provider_resource_id && authorization.gpu_count === plan.gpu_count &&
    authorization.runtime_seconds === plan.runtime_seconds && authorization.max_cost_microusd === plan.max_cost_microusd &&
    authorization.authorized_at !== null && authorization.expires_at > now && authorization.consumed_at === null;
  if (!expectedAuthorization) return { schema_version: 2, status: "blocked",
    human_summary: "このplanはまだSite上で有料実行の確認が済んでいません。authorization_urlを開いて確認してください。",
    machine_state: { run_id: runId, authorization_state: "required",
      authorization_url: trainingAuthorizationUrl(runId, fingerprint) }, next_allowed_actions: ["training_status"],
    blocking_reason: "TRAINING_AUTHORIZATION_REQUIRED" };
  const claimed = await claimTrainingDispatch(env.DB, owner, runId, fingerprint, now,
    Number(env.MAP_TRAINING_MONTHLY_MICROUSD), authorization);
  if (!claimed) return { schema_version: 2, status: "blocked", human_summary: "計画または予算枠を確保できませんでした。",
    machine_state: { run_id: runId }, next_allowed_actions: ["training_status"], blocking_reason: "TRAINING_DISPATCH_NOT_RESERVED" };
  const delegatedAuthorization = {
    authorization_id: authorization.authorization_id,
    authorization_source: authorization.authorization_source,
    authorization_reference: authorization.authorization_reference,
    decision_record_id: authorization.decision_record_id,
    authorized_by: authorization.authorized_by,
    control_plane_sha: authorization.control_plane_sha,
    target_repository: authorization.target_repository,
    target_sha: authorization.target_sha,
    image_digest: authorization.image_digest,
    provider: authorization.provider,
    provider_resource_id: authorization.provider_resource_id,
    gpu_count: authorization.gpu_count,
    runtime_seconds: authorization.runtime_seconds,
    max_cost_microusd: authorization.max_cost_microusd,
    authorized_at: authorization.authorized_at,
    expires_at: authorization.expires_at,
    owner,
    run_id: runId,
    plan_fingerprint: fingerprint,
  };
  let state = "uncertain";
  try {
    const response = await delegate(env, owner, "training_submit", {
      run_id: runId, plan_fingerprint: fingerprint, plan: { ...plan, run_id: runId },
      authorization: delegatedAuthorization,
      authorization_expires_at: authorization.expires_at,
    });
    if (response?.state === "blocked" &&
        ["TRAINING_ADMISSION_DISABLED", "TRAINING_AUTHORIZATION_EXPIRED"].includes(response.reason)) {
      await env.DB.prepare(`UPDATE training_plans SET dispatch_rejection=?
        WHERE owner_id=? AND id=? AND fingerprint=? AND dispatch_claimed_at IS NOT NULL`)
        .bind(response.reason, owner, runId, fingerprint).run();
      return { schema_version: 2, status: "blocked",
        human_summary: "プロバイダーは学習の受付を拒否しました。",
        machine_state: { run_id: runId, state: "blocked" },
        next_allowed_actions: ["training_status"], blocking_reason: response.reason };
    }
    if (response?.state === "running") state = "running";
  } catch {
    // The provider may have accepted the call. Recover by status, never respawn.
  }
  return { schema_version: 2, status: "pending", human_summary: "学習の送信状態を確認してください。",
    machine_state: { run_id: runId, state }, next_allowed_actions: ["training_status"], blocking_reason: null };
}
