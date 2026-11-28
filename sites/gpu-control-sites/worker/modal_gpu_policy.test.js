import assert from "node:assert/strict";
import test from "node:test";
import { modalGpuWorkloadAdmissionEnabled } from "./modal_gpu_policy.js";

test("Modal GPU admission accepts only the literal enabled value", () => {
  assert.equal(modalGpuWorkloadAdmissionEnabled({ MODAL_GPU_WORKLOAD_ADMISSION_ENABLED: "true" }), true);
  for (const value of [undefined, null, "", "TRUE", "1", "yes", true]) {
    assert.equal(modalGpuWorkloadAdmissionEnabled({ MODAL_GPU_WORKLOAD_ADMISSION_ENABLED: value }), false);
  }
  assert.equal(modalGpuWorkloadAdmissionEnabled({}), false);
});
