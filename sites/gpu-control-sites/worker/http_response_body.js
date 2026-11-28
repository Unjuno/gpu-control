/** Collect a response body once, enforcing a byte bound before callers decode it. */
export async function readBoundedResponseBytes(response, {
  maxBytes,
  tooLargeCode,
  missingBodyCode,
  allowEmptyBody = false,
  cancelDeclaredOversize = false,
  signal = null,
}) {
  const declared = Number(response.headers.get("content-length"));
  if (Number.isFinite(declared) && declared > maxBytes) {
    if (cancelDeclaredOversize) {
      try { await response.body?.cancel(); } catch { /* Preserve the size error. */ }
    }
    throw new Error(tooLargeCode);
  }
  if (!response.body) {
    if (allowEmptyBody) return new Uint8Array();
    throw new Error(missingBodyCode);
  }

  const reader = response.body.getReader();
  const chunks = [];
  let size = 0;
  try {
    for (;;) {
      let onAbort;
      const read = reader.read();
      const next = signal === null ? read : Promise.race([read, new Promise((_, reject) => {
        onAbort = () => reject(new DOMException("The operation was aborted", "AbortError"));
        if (signal.aborted) onAbort();
        else signal.addEventListener("abort", onAbort, { once: true });
      })]);
      let chunk;
      try { chunk = await next; }
      finally { if (onAbort) signal.removeEventListener("abort", onAbort); }
      if (chunk.done) break;
      size += chunk.value.byteLength;
      if (size > maxBytes) {
        try { await reader.cancel(); } catch { /* Preserve the size error. */ }
        throw new Error(tooLargeCode);
      }
      chunks.push(chunk.value);
    }
  } catch (error) {
    if (error?.name === "AbortError") {
      try { await reader.cancel(); } catch { /* Abort remains the public outcome. */ }
    }
    throw error;
  } finally {
    reader.releaseLock();
  }

  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return bytes;
}
