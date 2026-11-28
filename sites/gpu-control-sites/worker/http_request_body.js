/** Read a request body once with a byte limit before decoding its format. */
export async function readBoundedRequestText(request, limit, { tooLargeCode, missingBodyCode }) {
  const declared = Number(request.headers.get("content-length") || 0);
  if (declared > limit) throw new Error(tooLargeCode);
  if (!request.body) throw new Error(missingBodyCode);

  const reader = request.body.getReader();
  const chunks = [];
  let size = 0;
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > limit) {
        await reader.cancel();
        throw new Error(tooLargeCode);
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }

  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
}

export async function readJsonRequest(request, limit = 16 * 1024) {
  return JSON.parse(await readBoundedRequestText(request, limit, {
    tooLargeCode: "BODY_TOO_LARGE", missingBodyCode: "INVALID_JSON",
  }));
}

export async function readUrlEncodedFormRequest(request, limit = 4096) {
  return new URLSearchParams(await readBoundedRequestText(request, limit, {
    tooLargeCode: "FORM_TOO_LARGE", missingBodyCode: "INVALID_FORM",
  }));
}
