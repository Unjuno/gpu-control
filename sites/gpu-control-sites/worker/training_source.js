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
  return { schema_version: 2, status: "ok",
    human_summary: "学習ソースを登録しました。検証済み実行環境の設定後に実行できます。",
    machine_state: { registration_id: row.id, repository: row.repository, commit: row.source_sha,
      state: "pending_review", executable: false },
    next_allowed_actions: [], blocking_reason: null };
}

export async function listTrainingSources(db, owner) {
  const { results } = await db.prepare(`SELECT id AS registration_id, repository, source_sha AS "commit", created_at
    FROM training_registrations WHERE owner_id = ?
    ORDER BY created_at DESC, id DESC LIMIT 50`).bind(owner).all();
  return { schema_version: 2, status: "ok",
    human_summary: "あなたが登録した学習ソースの一覧です。",
    machine_state: { registrations: results.map((row) => ({
      ...row, state: "pending_review", executable: false,
    })) },
    next_allowed_actions: [], blocking_reason: null };
}
