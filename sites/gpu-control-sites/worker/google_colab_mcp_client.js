import { googleColabAccessToken } from "./google_colab_connection.js";
import { validGoogleColabToolCall } from "./google_colab_mcp_contract.js";
import { readBoundedResponseBytes } from "./http_response_body.js";

const COLAB_MCP_ENDPOINT = "https://colaboratory.googleapis.com/mcp";
// execute_code accepts up to 256 KiB of UTF-8 source. Leave room for JSON
// escaping and MCP envelope fields while retaining one bounded request cap.
const MAX_REQUEST_BYTES = 2 * 1024 * 1024;
const MAX_RESPONSE_BYTES = 64 * 1024;
const SHORT_TOOL_TIMEOUT_MS = 30_000;
const LONG_TOOL_TIMEOUT_MS = 600_000;
const LONG_RUNNING_TOOLS = new Set(["create_runtime", "execute_code"]);

/** Colab's documented execution ceiling is 600 seconds; short reads stay bounded. */
export function googleColabToolTimeoutMs(name) {
  return LONG_RUNNING_TOOLS.has(name) ? LONG_TOOL_TIMEOUT_MS : SHORT_TOOL_TIMEOUT_MS;
}
async function readBoundedText(response) {
  const bytes = await readBoundedResponseBytes(response, {
    maxBytes: MAX_RESPONSE_BYTES, tooLargeCode: "GOOGLE_COLAB_RESPONSE_TOO_LARGE",
    missingBodyCode: "GOOGLE_COLAB_RESPONSE_INVALID", allowEmptyBody: true,
  });
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
  if (!validGoogleColabToolCall(name, argumentsValue, options)) {
    throw new Error("GOOGLE_COLAB_TOOL_INVALID");
  }
  const timeoutMs = options.timeoutMs ?? googleColabToolTimeoutMs(name);
  if (!Number.isSafeInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > LONG_TOOL_TIMEOUT_MS) {
    throw new Error("GOOGLE_COLAB_TIMEOUT_INVALID");
  }
  const auth = await googleColabAccessToken(env.DB, env, owner, { fetchImpl: options.fetchImpl });
  const id = crypto.randomUUID();
  const body = JSON.stringify({ jsonrpc: "2.0", id, method: "tools/call", params: { name, arguments: argumentsValue } });
  if (new TextEncoder().encode(body).byteLength > MAX_REQUEST_BYTES) throw new Error("GOOGLE_COLAB_REQUEST_TOO_LARGE");
  const fetchImpl = options.fetchImpl || fetch;
  let response;
  try {
    response = await fetchImpl(COLAB_MCP_ENDPOINT, { method: "POST", redirect: "error",
      signal: AbortSignal.timeout(timeoutMs), headers: { authorization: "Bearer " + auth.access_token,
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
