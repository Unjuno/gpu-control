import assert from "node:assert/strict";
import test from "node:test";
import { readBoundedRequestText, readJsonRequest, readUrlEncodedFormRequest } from "./http_request_body.js";

function request(body, headers = {}) {
  return new Request("https://gpu-control.example/", { method: "POST", headers, body });
}

test("bounded request readers decode JSON and URL-encoded forms", async () => {
  assert.deepEqual(await readJsonRequest(request('{"ok":true}')), { ok: true });
  const form = await readUrlEncodedFormRequest(request("name=GPU+Control&scope=read%3Aexperiments"));
  assert.equal(form.get("name"), "GPU Control");
  assert.equal(form.get("scope"), "read:experiments");
});

test("bounded request readers preserve format-specific empty-body errors", async () => {
  await assert.rejects(readJsonRequest(new Request("https://gpu-control.example/", { method: "POST" })),
    { message: "INVALID_JSON" });
  await assert.rejects(readUrlEncodedFormRequest(new Request("https://gpu-control.example/", { method: "POST" })),
    { message: "INVALID_FORM" });
});

test("declared and streamed overages preserve format-specific errors", async () => {
  await assert.rejects(readJsonRequest(request("{}", { "content-length": "9" }), 8), { message: "BODY_TOO_LARGE" });
  await assert.rejects(readUrlEncodedFormRequest(request("name=long"), 4), { message: "FORM_TOO_LARGE" });
});

test("oversized streams are cancelled and UTF-8 decoding stays strict", async () => {
  let cancelled = false;
  const body = new ReadableStream({
    start(controller) { controller.enqueue(new Uint8Array([1, 2, 3])); },
    cancel() { cancelled = true; },
  });
  const streamed = new Request("https://gpu-control.example/", { method: "POST", body, duplex: "half" });
  await assert.rejects(readBoundedRequestText(streamed, 2, {
    tooLargeCode: "BODY_TOO_LARGE", missingBodyCode: "INVALID_JSON",
  }), { message: "BODY_TOO_LARGE" });
  assert.equal(cancelled, true);

  const invalidUtf8 = request(new Uint8Array([0xff]));
  await assert.rejects(readJsonRequest(invalidUtf8), TypeError);
});
