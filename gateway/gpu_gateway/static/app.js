import { registerWebMCP } from "./webmcp.js";
const $ = (id) => document.getElementById(id);
let csrf = "", selected = null;
const registrations = new AbortController();
const showError = (error) => { $("error").textContent = error.message; };
async function api(path, data) {
  const response = await fetch(path, { method: data === undefined ? "GET" : "POST", credentials: "same-origin",
    headers: data === undefined ? {} : { "Content-Type": "application/json", "X-CSRF-Token": csrf },
    body: data === undefined ? undefined : JSON.stringify(data) });
  const result = await response.json();
  if (!response.ok) throw new Error(result.message || `HTTP ${response.status}`);
  return result;
}
async function invoke(name, input = {}) {
  const value = await api(`/api/tools/${encodeURIComponent(name)}`, input);
  if (value.id) select(value);
  return value;
}
function select(run) {
  selected = run;
  $("plan").textContent = JSON.stringify({ id: run.id, state: run.state, fingerprint: run.fingerprint, ...run.plan }, null, 2);
  $("result").textContent = JSON.stringify(run.result || { state: run.state, error: run.error, cancel_requested: run.cancel_requested }, null, 2);
  $("approve").disabled = !["awaiting_approval", "approved"].includes(run.state);
  $("submit").disabled = run.state !== "approved";
  $("cancel").disabled = ["succeeded", "failed", "cancelled", "expired"].includes(run.state);
}
async function refresh() {
  const data = await invoke("experiments_list");
  const holder = $("runs"); holder.replaceChildren();
  $("worker").textContent = data.worker_last_seen_at ? `worker 最終確認: ${new Date(data.worker_last_seen_at * 1000).toLocaleString()}` : "worker: 未接続。投入前に独立workerを起動してください。";
  for (const run of data.experiments) {
    const row = document.createElement("div"); row.className = "run";
    const text = document.createElement("span"); text.textContent = `${run.workload} · ${run.state} · ${run.id.slice(0, 10)}`;
    const button = document.createElement("button"); button.textContent = "表示";
    button.addEventListener("click", () => invoke("experiments_get", { run_id: run.id }).catch(showError)); row.append(text, button); holder.append(row);
    if (selected?.id === run.id) await invoke("experiments_get", { run_id: run.id });
  }
}
$("prepare").addEventListener("submit", async (event) => {
  event.preventDefault(); $("error").textContent = "";
  const button = $("prepare-button"); button.disabled = true;
  try {
    await invoke("experiments_prepare", { workload: $("workload").value,
      runtime_seconds: Number($("runtime").value), max_cost_usd: $("cost").value,
      parameters: JSON.parse($("parameters").value), idempotency_key: crypto.randomUUID() });
    await refresh();
  } catch (error) { showError(error); } finally { button.disabled = false; }
});
$("approve").addEventListener("click", async (event) => {
  if (!event.isTrusted || !selected) return; // UX guard; server auth+CSRF remain authoritative.
  try { select(await api(`/api/approvals/${selected.id}`, { fingerprint: selected.fingerprint })); }
  catch (error) { showError(error); }
});
$("submit").addEventListener("click", async () => {
  try { await invoke("experiments_submit", { run_id: selected.id }); await refresh(); }
  catch (error) { showError(error); }
});
$("cancel").addEventListener("click", async () => {
  try { await invoke("experiments_cancel", { run_id: selected.id }); await refresh(); }
  catch (error) { showError(error); }
});
$("refresh").addEventListener("click", () => refresh().catch(showError));
$("logout").addEventListener("click", async () => {
  try { await api("/auth/logout", {}); registrations.abort(); location.reload(); }
  catch (error) { showError(error); }
});
async function boot() {
  const supported = Boolean(document.modelContext?.registerTool);
  $("webmcp-status").textContent = supported ? "WebMCP: ログイン後に登録" : "WebMCP: このブラウザでは未対応。通常のWeb操作とRemote MCPは利用できます。";
  try {
    const session = await api("/api/session"); csrf = session.csrf;
    $("connection").textContent = "認証済み · 実験はサーバー側で所有者を検証します。";
    $("logout").hidden = false; $("prepare-button").disabled = false; $("refresh").disabled = false;
    const data = await invoke("integrations_list");
    $("workload").replaceChildren();
    for (const workload of data.workloads) {
      const option = document.createElement("option"); option.value = workload.id;
      option.textContent = `${workload.id} (${workload.provider})`; $("workload").append(option);
    }
    const { tools } = await api("/api/tools");
    if (supported) {
      try {
        await registerWebMCP({ context: document.modelContext, definitions: tools, invoke, signal: registrations.signal });
        $("webmcp-status").textContent = "WebMCP: 登録済み。承認操作はツールに公開していません。";
      } catch (error) { $("webmcp-status").textContent = `WebMCP登録失敗: ${error.message}`; }
    }
    await refresh();
  } catch (error) { $("connection").textContent = `ログインまたは初期設定が必要です: ${error.message}`; }
}
window.addEventListener("pagehide", () => registrations.abort(), { once: true });
boot();
