/** Serialize JSON-compatible values with recursively sorted object keys. */
export function canonicalJson(value, errorCode = "CANONICAL_JSON_INVALID") {
  if (Array.isArray(value)) return `[${value.map((item) => canonicalJson(item, errorCode)).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) =>
      `${JSON.stringify(key)}:${canonicalJson(value[key], errorCode)}`).join(",")}}`;
  }
  if (typeof value === "number" && !Number.isFinite(value)) throw new Error(errorCode);
  return JSON.stringify(value);
}
