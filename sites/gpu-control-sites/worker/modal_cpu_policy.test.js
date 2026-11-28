import assert from "node:assert/strict";
import test from "node:test";
import { modalCpuAdmissionEnabled } from "./modal_cpu_policy.js";

test("Modal CPU admission accepts only the literal enabled value", () => {
  assert.equal(modalCpuAdmissionEnabled({ CPU_WORKLOAD_ADMISSION_ENABLED: "true" }), true);
  for (const value of [undefined, null, "", "TRUE", "1", "yes", true]) {
    assert.equal(modalCpuAdmissionEnabled({ CPU_WORKLOAD_ADMISSION_ENABLED: value }), false);
  }
  assert.equal(modalCpuAdmissionEnabled({}), false);
});
