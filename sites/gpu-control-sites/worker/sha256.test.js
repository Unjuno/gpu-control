import test from "node:test";
import assert from "node:assert/strict";
import { sha256Bytes, sha256Hex } from "./sha256.js";

test("SHA-256 hex has one canonical representation for text and bytes", async () => {
  assert.equal(await sha256Hex("abc"), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
  assert.equal(await sha256Hex(new TextEncoder().encode("abc")),
    "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
  assert.equal(await sha256Hex(new Uint8Array()), "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
  assert.deepEqual([...await sha256Bytes("abc")], [...Buffer.from("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad", "hex")]);
});

test("SHA-256 rejects values outside the text-or-byte contract", async () => {
  await assert.rejects(sha256Hex({}), { name: "TypeError", message: "SHA256_INPUT_INVALID" });
  await assert.rejects(sha256Hex(null), { name: "TypeError", message: "SHA256_INPUT_INVALID" });
});
