import { createGithubInstallationUrl, disconnectGithubApp, githubAppConfigured, githubAppOAuthConfigured,
  githubConnectionStatus, getOwnedGithubInstallation, listOwnedGithubRepositories } from "./github_app_connection.js";

const GITHUB_TOOLS = new Set([
  "github_connection_start", "github_connection_status",
  "github_connection_disconnect", "github_repositories",
]);

export function isGithubTool(name) {
  return GITHUB_TOOLS.has(name);
}

/** Handle the owner-scoped GitHub source connection tools. */
export async function handleGithubTool(name, env, owner) {
  if (!isGithubTool(name)) return null;
  if (name === "github_connection_start") {
    if (!githubAppOAuthConfigured(env)) return { schema_version: 2, status: "blocked",
      human_summary: "GitHub App接続の初期設定が完了していません。GPU実験は開始していません。",
      machine_state: { configured: false }, next_allowed_actions: [], blocking_reason: "GITHUB_APP_NOT_CONFIGURED" };
    const link = await createGithubInstallationUrl(env.DB, owner, env.GITHUB_APP_SLUG);
    return { schema_version: 2, status: "ok", human_summary: "GitHub Appの接続リンクを作成しました。選択リポジトリ限定でinstall後、GitHub利用者本人の確認を完了してください。",
      machine_state: { connected: false, authorization_url: link.authorization_url,
        expires_at: link.expires_at, requested_repository_permissions: { contents: "read", metadata: "read" },
        repository_selection: "selected" }, next_allowed_actions: ["github_connection_status"], blocking_reason: null };
  }
  if (name === "github_connection_status") {
    if (!githubAppConfigured(env)) return { schema_version: 2, status: "blocked",
      human_summary: "GPU Control側のGitHub App設定がまだ完了していません。管理者設定後に接続できます。",
      machine_state: { configured: false, connected: false }, next_allowed_actions: [],
      blocking_reason: "GITHUB_APP_NOT_CONFIGURED" };
    const connection = await githubConnectionStatus(env.DB, owner);
    const setupConfigured = githubAppOAuthConfigured(env);
    return { schema_version: 2, status: "ok", human_summary: !setupConfigured && !connection.connected
      ? "GitHub接続を開始するためのOAuth設定が未完了です。"
      : "GitHub repository connection state.",
      machine_state: { configured: true, setup_configured: setupConfigured, ...connection },
      next_allowed_actions: connection.connected ? ["github_repositories", "github_connection_disconnect"]
        : setupConfigured ? ["github_connection_start"] : [], blocking_reason: null };
  }
  if (name === "github_connection_disconnect") return { schema_version: 2, status: "ok",
    human_summary: "GPU ControlからGitHub repository connectionを削除しました。GitHub App自体のuninstallはGitHub側で行ってください。",
    machine_state: await disconnectGithubApp(env.DB, owner), next_allowed_actions: ["github_connection_start"], blocking_reason: null };
  if (!githubAppConfigured(env)) return { schema_version: 2, status: "blocked",
    human_summary: "GitHub App接続の初期設定が完了していません。",
    machine_state: { repositories: [] }, next_allowed_actions: ["github_connection_start"],
    blocking_reason: "GITHUB_APP_NOT_CONFIGURED" };
  const connection = await getOwnedGithubInstallation(env.DB, owner);
  if (!connection) return { schema_version: 2, status: "blocked",
    human_summary: "GitHub accountがまだGPU Controlへ接続されていません。",
    machine_state: { repositories: [] }, next_allowed_actions: ["github_connection_start"],
    blocking_reason: "GITHUB_CONNECTION_REQUIRED" };
  const repositories = await listOwnedGithubRepositories(env, env.DB, owner);
  return { schema_version: 2, status: "ok", human_summary: `接続済みGitHub accountから${repositories.length}件の選択済みrepositoryを取得しました。`,
    machine_state: { account_login: connection.account_login, repositories },
    next_allowed_actions: ["training_register"], blocking_reason: null };
}
