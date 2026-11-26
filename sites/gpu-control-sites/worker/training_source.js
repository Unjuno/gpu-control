// Parse a source reference without accepting arbitrary network destinations.
export function parseTrainingSource(repository, commit) {
  if (typeof repository !== "string" || typeof commit !== "string" ||
      commit.length !== 40 || !/^[0-9a-f]{40}$/.test(commit)) {
    throw new Error("TRAINING_SOURCE_INVALID");
  }
  const slug = repository.startsWith("https://github.com/")
    ? repository.slice("https://github.com/".length)
    : repository;
  const parts = slug.split("/");
  if (parts.length !== 2 ||
      !/^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$/.test(parts[0]) ||
      !/^[A-Za-z0-9_.-]{1,100}$/.test(parts[1]) ||
      [".", ".."].includes(parts[1]) || repository.trim() !== repository) {
    throw new Error("TRAINING_SOURCE_INVALID");
  }
  return { repository: slug.toLowerCase(), commit };
}

export async function registerTrainingSource(db, owner, input) {
  const { repository, commit } = parseTrainingSource(input.repository, input.commit);
  const id = crypto.randomUUID().replaceAll("-", "");
  await db.prepare(`INSERT INTO training_registrations (id, owner_id, repository, source_sha, created_at)
    VALUES (?, ?, ?, ?, ?) ON CONFLICT(owner_id, repository, source_sha) DO NOTHING`)
    .bind(id, owner, repository, commit, Math.floor(Date.now() / 1000)).run();
  const row = await db.prepare(`SELECT id, repository, source_sha FROM training_registrations
    WHERE owner_id = ? AND repository = ? AND source_sha = ?`).bind(owner, repository, commit).first();
  let executionSpecId;
  if (input.command !== undefined) {
    const spec = JSON.stringify({ command: input.command });
    await db.prepare(`INSERT INTO training_execution_specs (id, owner_id, registration_id, spec_json, created_at)
      VALUES (?, ?, ?, ?, ?) ON CONFLICT(owner_id, registration_id, spec_json) DO NOTHING`)
      .bind(crypto.randomUUID().replaceAll("-", ""), owner, row.id, spec, Math.floor(Date.now() / 1000)).run();
    const saved = await db.prepare(`SELECT id FROM training_execution_specs
      WHERE owner_id=? AND registration_id=? AND spec_json=?`).bind(owner, row.id, spec).first();
    executionSpecId = saved.id;
  }
  return { schema_version: 2, status: "ok",
    human_summary: "学習ソースを登録しました。検証済み実行環境の設定後に実行できます。",
    machine_state: { registration_id: row.id, repository: row.repository, commit: row.source_sha,
      ...(executionSpecId ? { execution_spec_id: executionSpecId } : {}),
      state: "pending_review", executable: false },
    next_allowed_actions: [], blocking_reason: null };
}

export async function listTrainingSources(db, owner, env = {}) {
  const { results } = await db.prepare(`SELECT id AS registration_id, repository, source_sha AS "commit", created_at
    FROM training_registrations WHERE owner_id = ?
    ORDER BY created_at DESC, id DESC LIMIT 50`).bind(owner).all();
  const { results: runs } = await db.prepare(`SELECT p.id AS run_id, r.repository, r.source_sha AS "commit",
      p.dispatch_claimed_at
    FROM training_plans p JOIN training_registrations r
      ON p.registration_id=r.id AND p.owner_id=r.owner_id
    WHERE p.owner_id=? AND p.dispatch_claimed_at IS NOT NULL
    ORDER BY p.dispatch_claimed_at DESC, p.id DESC LIMIT 50`).bind(owner).all();
  const { results: specs } = await db.prepare(`SELECT id AS execution_spec_id, registration_id, spec_json, created_at
    FROM training_execution_specs WHERE owner_id=?
    ORDER BY created_at DESC, id DESC LIMIT 50`).bind(owner).all();
  return { schema_version: 2, status: "ok",
    human_summary: "登録済みソースと、送信を試行した学習計画の一覧です。実行結果は training_status で確認できます。",
    machine_state: { registrations: results.map((row) => ({
      ...row, state: "pending_review", executable: false,
      execution_profile_configured: row.repository === "unjuno/model-as-a-paper" &&
        row.commit === env.MAP_TRAINING_SOURCE_SHA &&
        Boolean(env.MAP_TRAINING_MODAL_IMAGE_ID || env.MAP_TRAINING_IMAGE_DIGEST),
    })), runs,
      execution_specs: specs.map(({ spec_json, ...item }) => ({ ...item, ...JSON.parse(spec_json) })) },
    next_allowed_actions: runs.length ? ["training_status"] : [], blocking_reason: null };
}

// Used by planning to resolve the immutable source through the caller's registration.
export async function getOwnedTrainingSource(db, owner, registrationId) {
  if (typeof registrationId !== "string" || !/^[0-9a-f]{32}$/.test(registrationId)) {
    throw new Error("TRAINING_REGISTRATION_NOT_FOUND");
  }
  const row = await db.prepare(`SELECT id AS registration_id, repository, source_sha AS "commit"
    FROM training_registrations WHERE owner_id = ? AND id = ?`)
    .bind(owner, registrationId).first();
  if (!row) throw new Error("TRAINING_REGISTRATION_NOT_FOUND");
  return row;
}

export async function findOwnedTrainingSource(db, owner, input) {
  const { repository, commit } = parseTrainingSource(input.repository, input.commit);
  const row = await db.prepare(`SELECT id AS registration_id, repository, source_sha AS "commit"
    FROM training_registrations WHERE owner_id = ? AND repository = ? AND source_sha = ?`)
    .bind(owner, repository, commit).first();
  if (!row) throw new Error("TRAINING_REGISTRATION_NOT_FOUND");
  return row;
}
