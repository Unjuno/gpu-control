import { mapTrainingConfiguration } from "./map_training_configuration.js";
import { readBoundedResponseBytes } from "./http_response_body.js";

export const MAP_TRAINING_REPOSITORY = "unjuno/model-as-a-paper";

// Parse a source reference without accepting arbitrary network destinations.
export function parseTrainingRepository(repository) {
  if (typeof repository !== "string") throw new Error("TRAINING_SOURCE_INVALID");
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
  return slug.toLowerCase();
}

export function parseTrainingSource(repository, commit) {
  const slug = parseTrainingRepository(repository);
  if (typeof commit !== "string" || commit.length !== 40 || !/^[0-9a-f]{40}$/.test(commit)) {
    throw new Error("TRAINING_SOURCE_INVALID");
  }
  return { repository: slug.toLowerCase(), commit };
}

async function readGithubJson(response) {
  if (response.status === 404) throw new Error("TRAINING_GITHUB_REPOSITORY_NOT_PUBLIC");
  if (response.status === 403 || response.status === 429) throw new Error("TRAINING_GITHUB_RATE_LIMITED");
  if (!response.ok) throw new Error("TRAINING_GITHUB_LOOKUP_FAILED");
  const bytes = await readBoundedResponseBytes(response, {
    maxBytes: 16_384, tooLargeCode: "TRAINING_GITHUB_RESPONSE_TOO_LARGE",
    missingBodyCode: "TRAINING_GITHUB_RESPONSE_INVALID",
  });
  try {
    return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
  } catch {
    throw new Error("TRAINING_GITHUB_RESPONSE_INVALID");
  }
}

function validGithubBranch(branch) {
  return typeof branch === "string" && branch.length <= 255 &&
    /^[A-Za-z0-9._/-]+$/.test(branch) && !branch.startsWith("/") &&
    !branch.endsWith("/") && !branch.endsWith(".") && !branch.includes("..") &&
    !branch.includes("//") && !branch.includes("@{") &&
    branch.split("/").every((part) => part && part !== "." && part !== ".." && !part.endsWith(".lock"));
}

// Resolve a public repository anonymously or a private repository only with
// the exact-repository installation token minted by the owner's GitHub App.
// The ChatGPT GitHub connector's OAuth token is not available to this Worker.
export async function resolvePublicDefaultBranchCommit(repository, fetchImpl = fetch, installationToken = null) {
  const slug = parseTrainingRepository(repository);
  const headers = { accept: "application/vnd.github+json", "x-github-api-version": "2022-11-28",
    ...(installationToken ? { authorization: `Bearer ${installationToken}` } : {}) };
  const request = async (url) => {
    let response;
    try {
      response = await fetchImpl(url, { method: "GET", headers, redirect: "error",
        signal: AbortSignal.timeout(5_000) });
    } catch {
      throw new Error("TRAINING_GITHUB_LOOKUP_FAILED");
    }
    return readGithubJson(response);
  };
  const metadata = await request(`https://api.github.com/repos/${slug}`);
  if (!metadata || typeof metadata.private !== "boolean" || (metadata.private && !installationToken) || metadata.archived === true ||
      !validGithubBranch(metadata.default_branch)) {
    throw new Error(metadata?.archived === true ? "TRAINING_GITHUB_REPOSITORY_ARCHIVED"
      : metadata?.private === true ? "TRAINING_GITHUB_PRIVATE_REQUIRES_APP"
        : "TRAINING_GITHUB_RESPONSE_INVALID");
  }
  const commitsUrl = new URL(`https://api.github.com/repos/${slug}/commits`);
  commitsUrl.searchParams.set("sha", metadata.default_branch);
  commitsUrl.searchParams.set("per_page", "1");
  const commits = await request(commitsUrl.toString());
  const commit = Array.isArray(commits) ? commits[0]?.sha : null;
  if (typeof commit !== "string" || !/^[0-9a-f]{40}$/.test(commit)) {
    throw new Error("TRAINING_GITHUB_DEFAULT_COMMIT_UNAVAILABLE");
  }
  return { repository: slug, commit, default_branch: metadata.default_branch,
    visibility: metadata.private ? "private" : "public" };
}

export async function verifyGithubCommit(repository, commit, fetchImpl = fetch, installationToken = null) {
  const source = parseTrainingSource(repository, commit);
  let response;
  try {
    response = await fetchImpl(`https://api.github.com/repos/${source.repository}/git/commits/${source.commit}`, {
      method: "GET", redirect: "error", headers: { accept: "application/vnd.github+json",
        "x-github-api-version": "2022-11-28",
        ...(installationToken ? { authorization: `Bearer ${installationToken}` } : {}) },
      signal: AbortSignal.timeout(5_000),
    });
  } catch { throw new Error("TRAINING_GITHUB_LOOKUP_FAILED"); }
  const value = await readGithubJson(response);
  if (value?.sha !== source.commit) throw new Error("TRAINING_GITHUB_COMMIT_UNAVAILABLE");
  return { ...source, visibility: value.repository?.private === true ? "private" : "public" };
}

export async function registerTrainingSource(db, owner, input, { resolveCommit = resolvePublicDefaultBranchCommit } = {}) {
  const repository = parseTrainingRepository(input.repository);
  const hasMapOverrides = input.dataset !== undefined || input.run_name !== undefined || input.steps !== undefined;
  if (hasMapOverrides && repository !== MAP_TRAINING_REPOSITORY) return {
    schema_version: 2, status: "blocked",
    human_summary: "dataset、run_name、stepsの登録設定は現在MAP-44Mでのみ利用できます。",
    machine_state: { repository, ...(input.commit ? { commit: input.commit } : {}) }, next_allowed_actions: [],
    blocking_reason: "TRAINING_PROFILE_UNAVAILABLE",
  };
  const resolved = input.commit === undefined
    ? await resolveCommit(repository)
    : { repository, commit: input.commit, visibility: "unspecified" };
  const { commit } = parseTrainingSource(repository, resolved.commit);
  const id = crypto.randomUUID().replaceAll("-", "");
  await db.prepare(`INSERT INTO training_registrations (id, owner_id, repository, source_sha, created_at)
    VALUES (?, ?, ?, ?, ?) ON CONFLICT(owner_id, repository, source_sha) DO NOTHING`)
    .bind(id, owner, repository, commit, Math.floor(Date.now() / 1000)).run();
  const row = await db.prepare(`SELECT id, repository, source_sha FROM training_registrations
    WHERE owner_id = ? AND repository = ? AND source_sha = ?`).bind(owner, repository, commit).first();
  let executionSpecId;
  const execution = repository === MAP_TRAINING_REPOSITORY
    ? { dataset: input.dataset ?? "papers", run_name: input.run_name ?? "map44m", steps: input.steps ?? 100000 }
    : {};
  if (Object.keys(execution).length) {
    const spec = JSON.stringify(execution);
    await db.prepare(`INSERT INTO training_execution_specs (id, owner_id, registration_id, spec_json, created_at)
      VALUES (?, ?, ?, ?, ?) ON CONFLICT(owner_id, registration_id, spec_json) DO NOTHING`)
      .bind(crypto.randomUUID().replaceAll("-", ""), owner, row.id, spec, Math.floor(Date.now() / 1000)).run();
    const saved = await db.prepare(`SELECT id FROM training_execution_specs
      WHERE owner_id=? AND registration_id=? AND spec_json=?`).bind(owner, row.id, spec).first();
    executionSpecId = saved.id;
  }
  return { schema_version: 2, status: "ok",
    human_summary: executionSpecId
      ? "MAP-44Mの学習ソースと固定学習設定を登録しました。training_listで実行プロファイルを確認できます。"
      : resolved.visibility === "public"
        ? "GitHub repositoryの既定ブランチからimmutable commitを固定しました。登録だけでは実行できません。次はtraining_previewで実験契約、GPU、runtime、見積もりをまとめて確認します。"
        : "学習ソースを登録しました。登録だけでは実行できません。次はtraining_previewで実験契約、GPU、runtime、見積もりをまとめて確認します。",
    machine_state: { registration_id: row.id, repository: row.repository, commit: row.source_sha,
      ...(resolved.visibility === "public" ? { visibility: resolved.visibility, default_branch: resolved.default_branch } : {}),
      ...(executionSpecId ? { execution_spec_id: executionSpecId } : {}),
      state: "registered" },
    next_allowed_actions: executionSpecId ? ["training_list"] : ["training_preview"], blocking_reason: null };
}

function hasConfiguredExecutionProfile(row, env) {
  const config = mapTrainingConfiguration(env);
  if (row.repository !== MAP_TRAINING_REPOSITORY || row.commit !== config.source_sha) return false;
  const imageId = config.image_id;
  if (imageId) return /^im-[A-Za-z0-9]{8,128}$/.test(imageId);
  return /^sha256:[0-9a-f]{64}$/.test(config.image_digest || "");
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
  const registrations = results.map((row) => {
    const executionProfileConfigured = hasConfiguredExecutionProfile(row, env);
    return { ...row, state: "registered", execution_profile_configured: executionProfileConfigured,
      can_prepare: executionProfileConfigured };
  });
  // Preview performs the same manifest/lock checks as inspect and adds current
  // runtime, GPU, quote and budget readiness. Keep inspect available as an
  // explicitly requested diagnostic, not a mandatory extra hop.
  const nextActions = registrations.length ? ["training_preview"] : [];
  if (runs.length) nextActions.push("training_status");
  return { schema_version: 2, status: "ok",
    human_summary: "登録済みソースと送信済み学習計画の一覧です。can_prepare=trueのソースはtraining_previewで条件と費用を確認できます。実行結果はtraining_statusで確認できます。",
    machine_state: { registrations, runs,
      execution_specs: specs.map(({ spec_json, ...item }) => ({ ...item, ...JSON.parse(spec_json) })) },
    next_allowed_actions: nextActions, blocking_reason: null };
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
