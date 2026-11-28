import assert from "node:assert/strict";
import test from "node:test";
import { readBoundedResponseBytes } from "./http_response_body.js";

function response(body, headers = {}) {
  return { headers: new Headers(headers), body };
}

test("bounded response reader returns bytes across chunks", async () => {
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(new Uint8Array([1, 2]));
      controller.enqueue(new Uint8Array([3]));
      controller.close();
    },
  });
  assert.deepEqual(await readBoundedResponseBytes(response(stream), {
    maxBytes: 3, tooLargeCode: "TOO_LARGE", missingBodyCode: "MISSING",
  }), new Uint8Array([1, 2, 3]));
});

test("bounded response reader rejects declared and streamed oversize bodies", async () => {
  await assert.rejects(readBoundedResponseBytes(response(new ReadableStream(), {
    "content-length": "9",
  }), { maxBytes: 4, tooLargeCode: "TOO_LARGE", missingBodyCode: "MISSING" }),
  { message: "TOO_LARGE" });

  let cancelled = false;
  const stream = new ReadableStream({
    pull(controller) { controller.enqueue(new Uint8Array([1, 2, 3])); },
    cancel() { cancelled = true; },
  });
  await assert.rejects(readBoundedResponseBytes(response(stream), {
    maxBytes: 2, tooLargeCode: "TOO_LARGE", missingBodyCode: "MISSING",
  }), { message: "TOO_LARGE" });
  assert.equal(cancelled, true);
});

test("bounded response reader preserves explicit empty-body and missing-body policies", async () => {
  assert.deepEqual(await readBoundedResponseBytes(response(null), {
    maxBytes: 2, tooLargeCode: "TOO_LARGE", missingBodyCode: "MISSING", allowEmptyBody: true,
  }), new Uint8Array());
  await assert.rejects(readBoundedResponseBytes(response(null), {
    maxBytes: 2, tooLargeCode: "TOO_LARGE", missingBodyCode: "MISSING",
  }), { message: "MISSING" });
});

test("bounded response reader cancels an aborted stream and preserves AbortError", async () => {
  let cancelled = false;
  const stream = new ReadableStream({
    pull() { return new Promise(() => {}); },
    cancel() { cancelled = true; },
  });
  const controller = new AbortController();
  const pending = readBoundedResponseBytes(response(stream), {
    maxBytes: 2, tooLargeCode: "TOO_LARGE", missingBodyCode: "MISSING", signal: controller.signal,
  });
  controller.abort();
  await assert.rejects(pending, (error) => error?.name === "AbortError");
  assert.equal(cancelled, true);
});
