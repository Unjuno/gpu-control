/** SHA-256 over text or bytes, returning the fixed-size digest bytes. */
export async function sha256Bytes(value) {
  const bytes = typeof value === "string" ? new TextEncoder().encode(value) : value;
  if (!(bytes instanceof Uint8Array)) throw new TypeError("SHA256_INPUT_INVALID");
  return new Uint8Array(await crypto.subtle.digest("SHA-256", bytes));
}

/** Return the canonical lowercase SHA-256 hex representation for text or bytes. */
export async function sha256Hex(value) {
  return [...await sha256Bytes(value)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}
