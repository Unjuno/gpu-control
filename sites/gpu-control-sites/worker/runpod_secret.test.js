import assert from "node:assert/strict";
import test from "node:test";
import { openCompletionKey, RunpodSecretError, sealCompletionKey } from "./runpod_secret.js";

const stateKey = Buffer.from(Array.from({ length: 32 }, (_, index) => index)).toString("base64");
const binding = { runId: "a".repeat(32), ownerId: "owner-1", planFingerprint: "b".repeat(64), keyId: "c".repeat(32) };

test("completion key round trips only under the exact run binding", async () => {
  const plaintext = Uint8Array.from(Array.from({ length: 32 }, (_, index) => 255 - index));
  const sealed = await sealCompletionKey({ stateEncryptionKeyB64: stateKey, completionKeyBytes: plaintext, binding });
  assert.notEqual(sealed.ciphertextB64, Buffer.from(plaintext).toString("base64"));
  const opened = await openCompletionKey({ stateEncryptionKeyB64: stateKey, ...sealed, binding });
  assert.deepEqual(opened, plaintext);
  opened.fill(0);
});

test("cross-owner, cross-plan, and modified ciphertext fail authentication", async () => {
  const plaintext = crypto.getRandomValues(new Uint8Array(32));
  const sealed = await sealCompletionKey({ stateEncryptionKeyB64: stateKey, completionKeyBytes: plaintext, binding });
  await assert.rejects(openCompletionKey({ stateEncryptionKeyB64: stateKey, ...sealed,
    binding: { ...binding, ownerId: "owner-2" } }), (error) => error.code === "RUNPOD_SECRET_AUTHENTICATION_FAILED");
  await assert.rejects(openCompletionKey({ stateEncryptionKeyB64: stateKey, ...sealed,
    binding: { ...binding, planFingerprint: "d".repeat(64) } }), (error) => error.code === "RUNPOD_SECRET_AUTHENTICATION_FAILED");
  const bytes = Buffer.from(sealed.ciphertextB64, "base64");
  bytes[0] ^= 1;
  await assert.rejects(openCompletionKey({ stateEncryptionKeyB64: stateKey, ivB64: sealed.ivB64,
    ciphertextB64: bytes.toString("base64"), binding }), (error) => error instanceof RunpodSecretError &&
      error.code === "RUNPOD_SECRET_AUTHENTICATION_FAILED");
  plaintext.fill(0);
});

test("state key and completion key lengths are exact", async () => {
  await assert.rejects(sealCompletionKey({ stateEncryptionKeyB64: Buffer.from("short").toString("base64"),
    completionKeyBytes: new Uint8Array(32), binding }), (error) => error.code === "RUNPOD_STATE_ENCRYPTION_KEY_INVALID");
  await assert.rejects(sealCompletionKey({ stateEncryptionKeyB64: stateKey,
    completionKeyBytes: new Uint8Array(31), binding }), (error) => error.code === "RUNPOD_COMPLETION_KEY_INVALID");
});
