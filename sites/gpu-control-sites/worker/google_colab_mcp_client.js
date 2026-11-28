import { googleColabAccessToken } from "./google_colab_connection.js";

const COLAB_MCP_ENDPOINT = "https://colaboratory.googleapis.com/mcp";
const MAX_REQUEST_BYTES = 64 * 1024;
const MAX_RESPONSE_BYTES = 64 * 1024;
// The current product surface is read-only. Runtime creation and code
// execution stay unreachable until the owner-bound run lifecycle is wired.
const READ_ONLY_MCP_TOOLS = new Set([
  "get_subscription", "list_runtimes", "list_runtime_specs",
]);

async function readBoundedText(response) {
  const declared = Number(response.headers.get("content-length"));
  if (Number.isFinite(declared) && declared > MAX_RESPONSE_BYTES) throw new Error("GOOGLE_COLAB_RESPONSE_TOO_LARGE");
  if (!response.body) return "";
  const reader = response.body.getReader();
  const chunks = [];
  let size = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > MAX_RESPONSE_BYTES) {
      await reader.cancel();
      throw new Error("GOOGLE_COLAB_RESPONSE_TOO_LARGE");
    }
    chunks.push(value);
  }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
  try { return new TextDecoder("utf-8", { fatal: true }).decode(bytes); }
  catch { throw new Error("GOOGLE_COLAB_RESPONSE_INVALID"); }
}

function parseMcpResponse(text, contentType, id) {
  let payload;
  try {
    if (contentType.includes("text/event-stream")) {
      const matches = text.split(/\r?\n\r?\n/).flatMap((event) => {
        const data = event.split(/\r?\n/).filter((line) => line.startsWith("data:"))
          .map((line) => line.slice(5).trim()).join("\n");
        if (!data || data === "[DONE]") return [];
        try {
          const message = JSON.parse(data);
          return message?.jsonrpc === "2.0" && message.id === id ? [message] : [];
        } catch { return []; }
      });
      if (matches.length !== 1) throw new Error("missing or duplicate response event");
      payload = matches[0];
    } else payload = JSON.parse(text);
  } catch { throw new Error("GOOGLE_COLAB_RESPONSE_INVALID"); }
  if (!payload || typeof payload !== "object" || Array.isArray(payload) || payload.jsonrpc !== "2.0" || payload.id !== id) {
    throw new Error("GOOGLE_COLAB_RESPONSE_INVALID");
  }
  if (payload.error) {
    const code = Number.isInteger(payload.error.code) ? payload.error.code : null;
    const data = payload.error.data;
    const status = typeof data?.status === "string" && /^[A-Z][A-Z0-9_]{0,63}$/.test(data.status) ? data.status : null;
    throw new Error("GOOGLE_COLAB_PROVIDER_ERROR:" + (status || (code === -32602 ? "INVALID_ARGUMENT" : "REQUEST_FAILED")));
  }
  if (!payload.result || typeof payload.result !== "object" || Array.isArray(payload.result)) {
    throw new Error("GOOGLE_COLAB_RESPONSE_INVALID");
  }
  return payload.result;
}

/** Call only the fixed Google Colab hosted MCP endpoint and its fixed tool set. */
export async function callGoogleColabMcpTool(env, owner, name, argumentsValue = {}, options = {}) {
  if (!READ_ONLY_MCP_TOOLS.has(name) || !argumentsValue || typeof argumentsValue !== "object" || Array.isArray(argumentsValue)) {
    throw new Error("GOOGLE_COLAB_TOOL_INVALID");
  }
  const auth = await googleColabAccessToken(env.DB, env, owner, { fetchImpl: options.fetchImpl });
  const id = crypto.randomUUID();
  const body = JSON.stringify({ jsonrpc: "2.0", id, method: "tools/call", params: { name, arguments: argumentsValue } });
  if (new TextEncoder().encode(body).byteLength > MAX_REQUEST_BYTES) throw new Error("GOOGLE_COLAB_REQUEST_TOO_LARGE");
  const fetchImpl = options.fetchImpl || fetch;
  let response;
  try {
    response = await fetchImpl(COLAB_MCP_ENDPOINT, { method: "POST", redirect: "error",
      signal: AbortSignal.timeout(30_000), headers: { authorization: "Bearer " + auth.access_token,
        "content-type": "application/json", accept: "application/json, text/event-stream" }, body });
  } catch { throw new Error("GOOGLE_COLAB_PROVIDER_UNAVAILABLE"); }
  const contentType = response.headers.get("content-type") || "";
  if (!response.ok) throw new Error("GOOGLE_COLAB_PROVIDER_HTTP_" + response.status);
  if (!contentType.includes("application/json") && !contentType.includes("text/event-stream")) {
    throw new Error("GOOGLE_COLAB_RESPONSE_INVALID");
  }
  return parseMcpResponse(await readBoundedText(response), contentType, id);
}

/** Normalize a Google MCP tool result without passing arbitrary text onward. */
export function googleColabStructuredResult(result) {
  if (result?.isError === true) throw new Error("GOOGLE_COLAB_PROVIDER_TOOL_FAILED");
  if (result?.structuredContent && typeof result.structuredContent === "object" && !Array.isArray(result.structuredContent)) {
    return result.structuredContent;
  }
  if (!Array.isArray(result?.content) || result.content.length !== 1 || result.content[0]?.type !== "text") {
    throw new Error("GOOGLE_COLAB_RESPONSE_INVALID");
  }
  try {
    const parsed = JSON.parse(result.content[0].text);
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) return parsed;
  } catch { /* Text-only provider responses are not interpreted as control data. */ }
  throw new Error("GOOGLE_COLAB_RESPONSE_INVALID");
}
