import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import test from "node:test";
import { GOOGLE_COLAB_MAX_FILE_BYTES, readGoogleColabRuntimeFile } from "./google_colab_runtime_files.js";
import { GOOGLE_COLAB_MAX_ARTIFACT_BYTES } from "./google_colab_execution_limits.js";

const bytes = new TextEncoder().encode("immutable checkpoint bytes");
const runtime = { name: "runtimes/gpu-control-run", runtimeSpec: {
  variant: "VARIANT_GPU", accelerator: "T4", shape: "SHAPE_STANDARD",
}, connectionInfo: { token: "short-lived-runtime-proxy-token", expireTime: "2026-11-28T12:00:00Z",
  url: "https://colab.googleusercontent.com/runtime-proxy" } };
const artifact = { path: "checkpoints/model.pt", size_bytes: bytes.byteLength,
  sha256: createHash("sha256").update(bytes).digest("hex") };

test("Colab runtime file retrieval is run-bound, fixed-origin, bounded, and checksum verified", async () => {
  const result = await readGoogleColabRuntimeFile(runtime, artifact, { expectedRuntimeName: runtime.name,
    fetchImpl: async (url, init) => {
      assert.equal(url.origin, "https://colab.googleusercontent.com");
      assert.equal(url.pathname, "/runtime-proxy/files/checkpoints/model.pt");
      assert.equal(init.method, "GET");
      assert.equal(init.redirect, "error");
      assert.equal(init.headers["X-Colab-Runtime-Proxy-Token"], runtime.connectionInfo.token);
      return new Response(bytes, { status: 200 });
    } });
  assert.deepEqual(result, bytes);
  await assert.rejects(readGoogleColabRuntimeFile(runtime, artifact, { expectedRuntimeName: "runtimes/other",
    fetchImpl: async () => { throw new Error("must not fetch"); } }),
  { message: "GOOGLE_COLAB_RUNTIME_FILE_INVALID" });
  await assert.rejects(readGoogleColabRuntimeFile(runtime, { ...artifact, path: "../secret" }, {
    expectedRuntimeName: runtime.name, fetchImpl: async () => { throw new Error("must not fetch"); } }),
  { message: "GOOGLE_COLAB_ARTIFACT_INVALID" });
  await assert.rejects(readGoogleColabRuntimeFile(runtime, { ...artifact, sha256: "0".repeat(64) }, {
    expectedRuntimeName: runtime.name, fetchImpl: async () => new Response(bytes) }),
  { message: "GOOGLE_COLAB_ARTIFACT_CHECKSUM_MISMATCH" });
});

test("Colab runtime file retrieval enforces the 50 MiB API bound and refuses redirects", async () => {
  assert.equal(GOOGLE_COLAB_MAX_FILE_BYTES, GOOGLE_COLAB_MAX_ARTIFACT_BYTES);
  await assert.rejects(readGoogleColabRuntimeFile(runtime, { ...artifact,
    size_bytes: GOOGLE_COLAB_MAX_FILE_BYTES + 1 }, { expectedRuntimeName: runtime.name }),
  { message: "GOOGLE_COLAB_ARTIFACT_INVALID" });
  await assert.rejects(readGoogleColabRuntimeFile(runtime, artifact, { expectedRuntimeName: runtime.name,
    fetchImpl: async () => { throw new TypeError("redirect blocked"); } }),
  { message: "GOOGLE_COLAB_RUNTIME_FILE_UNAVAILABLE" });
});
