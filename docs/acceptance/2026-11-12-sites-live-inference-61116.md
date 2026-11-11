# Sites live inference acceptance — 2026-11-12

## Result

ChatGPT completed one additional registered TinyStories CPU inference through
the owner-private Sites MCP path. The run was free; paid providers remained
parked.

| Field | Value |
| --- | --- |
| Run ID | `5148ce027ba143d8ae75cc1df34a1ad5` |
| Workload | `tiny-stories-inference-v1` |
| Registered repository/source | `Unjuno/gpu-control` / `3cc7a765cbcbeb7abdfa0d607e8a44e4cdff2288` |
| Image | `sha256:f0e1bbd44e0bd475dc2f19a548a96e041fc9cb48fc4160d4c0c4de02b0e00541` |
| Seed / generated tokens | `61116` / `8` |
| Runtime / cost ceiling | `249 ms` / `$0.00` |
| GPU used | `false` |
| Final state / cleanup | `succeeded` / `confirmed` |
| Artifact | `result.json`, 979 bytes |
| Artifact SHA-256 | `855511d428a2db88d904d99e7c3523d50fb7e83f0e719c21d3883cb6fed4100d` |

The run passed source identity, parameter bounds, model digest, inference,
non-root, no-secret-environment, no-Docker-socket, read-only-rootfs and
network-disabled checks. ChatGPT retrieved the complete artifact. An independent
local digest check confirmed the returned 979 bytes match the artifact SHA-256.

This is another CPU vertical acceptance, not GPU, multi-owner isolation,
recovery, long-duration operation or paid-execution evidence.
