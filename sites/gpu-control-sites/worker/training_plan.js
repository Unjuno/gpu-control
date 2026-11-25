import { findOwnedTrainingSource, getOwnedTrainingSource } from "./training_source.js";

const MAP_REPOSITORY = "unjuno/model-as-a-paper";

export async function previewTrainingPlan(env, owner, args) {
  const source = args.registration_id
    ? await getOwnedTrainingSource(env.DB, owner, args.registration_id)
    : await findOwnedTrainingSource(env.DB, owner, args);
  const machine = { ...source, executable: false };
  // These values are set by the operator after reviewing the commit and building
  // the image. A registration alone never gives a commit execution authority.
  if (source.repository !== MAP_REPOSITORY ||
      source.commit !== env.MAP_TRAINING_SOURCE_SHA ||
      !/^sha256:[0-9a-f]{64}$/.test(env.MAP_TRAINING_IMAGE_DIGEST || "")) {
    return { schema_version: 2, status: "blocked",
      human_summary: "このコミットに対応する検証済みの学習イメージが設定されていません。",
      machine_state: machine, next_allowed_actions: [], blocking_reason: "TRAINING_PROFILE_UNAVAILABLE" };
  }
  const now = Math.floor(Date.now() / 1000);
  const hourlyRate = Number(env.MAP_TRAINING_HOURLY_MICROUSD);
  const quoteExpires = Number(env.MAP_TRAINING_QUOTE_EXPIRES_AT);
  if (!Number.isSafeInteger(hourlyRate) || hourlyRate <= 0 || hourlyRate > 1000000000 ||
      !Number.isSafeInteger(quoteExpires) || quoteExpires <= now || quoteExpires > now + 3600) {
    return { schema_version: 2, status: "blocked",
      human_summary: "有効な学習料金の見積もりが設定されていません。",
      machine_state: machine, next_allowed_actions: [], blocking_reason: "TRAINING_QUOTE_UNAVAILABLE" };
  }
  // The source app allows up to 600 seconds of startup. Reserve that
  // separately and apply the source policy's 10 percent budget margin.
  const estimatedCost = Math.ceil(hourlyRate * (args.runtime_seconds + 600) / 3240);
  if (estimatedCost > args.max_cost_microusd) {
    return { schema_version: 2, status: "blocked",
      human_summary: "指定された予算上限では、この実行時間の見積もりをカバーできません。",
      machine_state: { ...machine, estimated_cost_microusd: estimatedCost },
      next_allowed_actions: [], blocking_reason: "TRAINING_BUDGET_TOO_LOW" };
  }
  return { schema_version: 2, status: "ok",
    human_summary: "学習条件を確認しました。実行受付は別途必要です。",
    machine_state: { ...machine, image_digest: env.MAP_TRAINING_IMAGE_DIGEST,
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
  const admission = env.MAP_TRAINING_ADMISSION_ENABLED === "true" &&
    Number(env.MAP_TRAINING_RUNTIME_SECONDS) === plan.runtime_seconds;
  const actions = state === "prepared" ? ["training_status", "training_cancel"] : ["training_status"];
  if (state === "prepared" && admission) actions.unshift("training_submit");
  return { ...preview, approved_plan: plan, next_allowed_actions: actions,
    human_summary: "認証済みの所有者に紐づく学習計画を保存しました。",
    machine_state: { ...plan, executable, run_id: existing.id,
      plan_fingerprint: fingerprint, expires_at: existing.expires_at, state } };
}

export async function trainingPlanState(db, owner, runId, cancel = false) {
  const now = Math.floor(Date.now() / 1000);
  if (cancel) {
    await db.prepare(`UPDATE training_plans SET cancelled_at=?
      WHERE owner_id=? AND id=? AND cancelled_at IS NULL AND dispatch_claimed_at IS NULL AND expires_at>?`)
      .bind(now, owner, runId, now).run();
  }
  const row = await db.prepare(`SELECT fingerprint, expires_at, cancelled_at, dispatch_claimed_at
    FROM training_plans WHERE owner_id=? AND id=?`).bind(owner, runId).first();
  if (!row) throw new Error("RUN_NOT_FOUND");
  const state = row.cancelled_at !== null ? "cancelled"
    : row.dispatch_claimed_at !== null ? "dispatching" : row.expires_at <= now ? "expired" : "prepared";
  return { schema_version: 2, status: "ok", human_summary: "保存済みの学習計画の状態です。",
    machine_state: { run_id: runId, state, plan_fingerprint: row.fingerprint,
      expires_at: row.expires_at, cancelled_at: row.cancelled_at },
    next_allowed_actions: state === "prepared" ? ["training_cancel"] : [], blocking_reason: null };
}

// Authorization must already be established. This single write reserves the
// whole plan ceiling and prevents concurrent or duplicate dispatch claims.
export async function claimTrainingDispatch(db, owner, runId, fingerprint, now, monthlyLimit) {
  if (!Number.isSafeInteger(monthlyLimit) || monthlyLimit < 1) {
    throw new Error("TRAINING_BUDGET_NOT_CONFIGURED");
  }
  const date = new Date(now * 1000);
  const monthStart = Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), 1) / 1000;
  return db.prepare(`UPDATE training_plans SET dispatch_claimed_at=?
    WHERE owner_id=? AND id=? AND fingerprint=?
      AND cancelled_at IS NULL AND dispatch_claimed_at IS NULL AND expires_at>?
      AND json_extract(plan_json, '$.max_cost_microusd') +
        COALESCE((SELECT SUM(json_extract(p.plan_json, '$.max_cost_microusd'))
          FROM training_plans p WHERE p.dispatch_claimed_at>=?), 0) <= ?
    RETURNING plan_json`).bind(now, owner, runId, fingerprint, now, monthStart, monthlyLimit).first();
}

export async function submitTrainingPlan(env, owner, args, delegate, isConfigured) {
  const { run_id: runId, plan_fingerprint: fingerprint, approved_plan: approved } = args;
  const row = await env.DB.prepare(`SELECT plan_json, dispatch_claimed_at FROM training_plans
    WHERE owner_id=? AND id=? AND fingerprint=?`).bind(owner, runId, fingerprint).first();
  if (!row) throw new Error("RUN_NOT_FOUND");
  const plan = JSON.parse(row.plan_json);
  if (Object.keys(approved).length !== Object.keys(plan).length ||
      Object.entries(plan).some(([key, value]) => !Object.hasOwn(approved, key) || approved[key] !== value)) {
    throw new Error("INVALID_ARGUMENTS");
  }
  if (row.dispatch_claimed_at !== null) return trainingPlanState(env.DB, owner, runId);
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
  const claimed = await claimTrainingDispatch(env.DB, owner, runId, fingerprint, now,
    Number(env.MAP_TRAINING_MONTHLY_MICROUSD));
  if (!claimed) return { schema_version: 2, status: "blocked", human_summary: "計画または予算枠を確保できませんでした。",
    machine_state: { run_id: runId }, next_allowed_actions: ["training_status"], blocking_reason: "TRAINING_DISPATCH_NOT_RESERVED" };
  let state = "uncertain";
  try {
    const response = await delegate(env, owner, "training_submit", {
      run_id: runId, plan_fingerprint: fingerprint, plan: { ...plan, run_id: runId },
    });
    if (response?.state === "running") state = "running";
  } catch {
    // The provider may have accepted the call. Recover by status, never respawn.
  }
  return { schema_version: 2, status: "pending", human_summary: "学習の送信状態を確認してください。",
    machine_state: { run_id: runId, state }, next_allowed_actions: ["training_status"], blocking_reason: null };
}
