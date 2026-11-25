# ChatGPT Sites live inference refresh — 2026-11-12

Status: **PASS for one bounded, free, registered CPU inference and full result
artifact retrieval through the currently connected ChatGPT Sites tools.** This
does not establish GPU execution, broad model quality, separate-account owner
isolation, or backup/restore acceptance.

Before submission, `experiment_capabilities` returned `available=true`,
`runner_ready=true`, `admission_enabled=true`, `provider=local_cpu`,
`free=true`, and `paid_execution=parked`.

ChatGPT prepared and submitted run
`585e1ce77c07498fbf87e317dfc3c22a` using the registered `tiny-stories-inference-v1`
workload, repository `Unjuno/gpu-control`, source SHA
`3cc7a765cbcbeb7abdfa0d607e8a44e4cdff2288`, and image digest
`sha256:f0e1bbd44e0bd475dc2f19a548a96e041fc9cb48fc4160d4c0c4de02b0e00541`.
The request used prompt `A tiny orange cat watched the rain.`, seed `61121`, an
8-token limit, 30-second runtime limit, and `$0.00` maximum cost.

The run reached `succeeded` with result `passed` in 254 ms, generated 8 tokens,
reported `gpu_used=false`, and returned `cleanup_state=confirmed`. The output
was `A tiny orange cat watched the rain. The cat was scared of the rain`.
`experiment_result` returned the same owner-bound result. ChatGPT then fetched
the complete `result.json` from R2 in one bounded chunk: 989 bytes, EOF true,
SHA-256 `e0568f621c0fc7093331a962dcad2644bcd5aef83066850b75f52934ddb291ae`,
matching the D1 artifact reference. The inference result checksum was
`442ee60c4e219363c540ab835e7ad50d3feae17b2a5e60d6eb66c6875f3367bc`.

This is a live end-to-end CPU inference and artifact retrieval observation. It
does not substitute for distinct-account authorization, D1/R2 recovery, or
GPU/provider acceptance. Paid execution remained parked.
