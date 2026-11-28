const UUID_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const RESOURCE_ID = "[a-z][a-z0-9-]{0,62}";
const RUNTIME_NAME = new RegExp(`^runtimes/${RESOURCE_ID}$`);
const SESSION_NAME = new RegExp(`^runtimes/${RESOURCE_ID}/sessions/${RESOURCE_ID}$`);

const TOOL_ARGUMENTS = {
  get_subscription: (args) => exactKeys(args, []),
  list_runtime_specs: (args) => exactKeys(args, []),
  list_runtimes: (args) => exactKeys(args, []),
  create_runtime: (args) => (exactKeys(args, ["runtime", "requestId"]) ||
      exactKeys(args, ["runtime", "requestId", "runtimeId"])) && UUID_V4.test(args.requestId) &&
    (args.runtimeId === undefined || /^[a-z][a-z0-9-]{0,62}$/.test(args.runtimeId)) &&
    exactKeys(args.runtime, ["runtimeSpec"]) && validRuntimeSpec(args.runtime.runtimeSpec),
  execute_code: (args) => exactKeys(args, ["code", "executionId", "session"]) &&
    typeof args.code === "string" && args.code.length > 0 && new TextEncoder().encode(args.code).byteLength <= 256 * 1024 &&
    UUID_V4.test(args.executionId) && SESSION_NAME.test(args.session),
  get_runtime: (args) => exactKeys(args, ["name"]) && RUNTIME_NAME.test(args.name),
};

function exactKeys(value, expected) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const actual = Object.keys(value).sort();
  return actual.length === expected.length && actual.every((key, index) => key === [...expected].sort()[index]);
}

function validRuntimeSpec(spec) {
  return exactKeys(spec, ["variant", "accelerator", "shape"]) &&
    ["VARIANT_CPU", "VARIANT_GPU", "VARIANT_TPU"].includes(spec.variant) &&
    typeof spec.accelerator === "string" && /^[A-Z0-9]{2,16}$/.test(spec.accelerator) &&
    ["SHAPE_STANDARD", "SHAPE_HIGHMEM"].includes(spec.shape) &&
    (spec.variant !== "VARIANT_GPU" || spec.accelerator !== "NONE");
}

/** Validate the narrow Google Colab MCP surface required by the shared run lifecycle. */
export function validGoogleColabToolCall(name, args, options = {}) {
  if (name === "create_session") {
    return exactKeys(args, ["parent", "sessionId"]) && RUNTIME_NAME.test(args.parent) &&
      new RegExp(`^${RESOURCE_ID}$`).test(args.sessionId) &&
      options.expectedRuntimeName === args.parent && options.expectedSessionId === args.sessionId;
  }
  if (name === "list_sessions") {
    return exactKeys(args, ["parent"]) && RUNTIME_NAME.test(args.parent) &&
      typeof options.expectedRuntimeName === "string" && options.expectedRuntimeName === args.parent;
  }
  if (name === "delete_session") {
    return exactKeys(args, ["name"]) && SESSION_NAME.test(args.name) &&
      typeof options.expectedSessionName === "string" && options.expectedSessionName === args.name;
  }
  if (name === "delete_runtime") {
    return (exactKeys(args, ["name"]) || exactKeys(args, ["name", "allowMissing"])) &&
      RUNTIME_NAME.test(args.name) && (args.allowMissing === undefined || args.allowMissing === true) &&
      typeof options.expectedRuntimeName === "string" && options.expectedRuntimeName === args.name;
  }
  if (name === "get_runtime") {
    return exactKeys(args, ["name"]) && RUNTIME_NAME.test(args.name) &&
      typeof options.expectedRuntimeName === "string" && options.expectedRuntimeName === args.name;
  }
  if (name === "execute_code") {
    return TOOL_ARGUMENTS[name]?.(args) === true &&
      typeof options.expectedSessionName === "string" && options.expectedSessionName === args.session &&
      typeof options.expectedExecutionId === "string" && options.expectedExecutionId === args.executionId;
  }
  return TOOL_ARGUMENTS[name]?.(args) === true;
}

/** Validate private runtime handles before they enter the owner-scoped run record. */
export function validGoogleColabRuntime(value) {
  if (!value || typeof value !== "object" || Array.isArray(value) ||
      !RUNTIME_NAME.test(value.name || "") || !validRuntimeSpec(value.runtimeSpec) ||
      !value.connectionInfo || typeof value.connectionInfo !== "object" || Array.isArray(value.connectionInfo)) return false;
  const info = value.connectionInfo;
  if (typeof info.token !== "string" || info.token.length < 16 || info.token.length > 8192 ||
      typeof info.expireTime !== "string" || !Number.isFinite(Date.parse(info.expireTime)) ||
      typeof info.url !== "string" || info.url.length > 2048) return false;
  try {
    const url = new URL(info.url);
    return isGoogleColabRuntimeProxyUrl(url);
  } catch { return false; }
}

/** Accept only Google's documented Colab runtime proxy origin, never a caller URL. */
export function isGoogleColabRuntimeProxyUrl(value) {
  const url = value instanceof URL ? value : new URL(value);
  return url.protocol === "https:" && url.hostname === "colab.googleusercontent.com" &&
    url.port === "" && !url.username && !url.password && !url.hash && !url.search;
}

export function validGoogleColabSession(value, expectedRuntime) {
  return Boolean(value && typeof value === "object" && !Array.isArray(value) &&
    typeof expectedRuntime === "string" && RUNTIME_NAME.test(expectedRuntime) &&
    typeof value.name === "string" && SESSION_NAME.test(value.name) &&
    value.name.startsWith(expectedRuntime + "/sessions/"));
}

export function validGoogleColabExecution(value, expectedSession, expectedExecutionId) {
  return Boolean(value && typeof value === "object" && !Array.isArray(value) &&
    value.session === expectedSession && value.executionId === expectedExecutionId &&
    Number.isSafeInteger(value.executionCount) && value.executionCount >= 0 &&
    typeof value.stdout === "string" && typeof value.stderr === "string" &&
    typeof value.result === "string" && typeof value.outputTruncated === "boolean" &&
    (value.executionError === undefined || value.executionError === null ||
      (typeof value.executionError === "object" && !Array.isArray(value.executionError) &&
       typeof value.executionError.name === "string" && typeof value.executionError.value === "string" &&
       Array.isArray(value.executionError.traceback) && value.executionError.traceback.every((line) => typeof line === "string"))));
}
