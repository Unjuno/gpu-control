import assert from "node:assert/strict";
import test from "node:test";
import { canonicalJson } from "./canonical_json.js";

test("canonical JSON sorts object keys at every depth and preserves array order", () => {
  assert.equal(canonicalJson({ z: 1, a: { y: 2, b: 3 }, list: [{ z: 4, a: 5 }] }),
    '{"a":{"b":3,"y":2},"list":[{"a":5,"z":4}],"z":1}');
});

test("canonical JSON rejects non-finite numbers with the caller's domain error", () => {
  assert.throws(() => canonicalJson({ nested: [Number.POSITIVE_INFINITY] }, "PLAN_INVALID"),
    { message: "PLAN_INVALID" });
});
