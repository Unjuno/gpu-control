# Orbitune RunPod canary acceptance

The first Orbitune RunPod workload has three distinct success layers. They must not be collapsed into one boolean.

```text
authenticated process success
        ↓
Orbitune result-side canary acceptance
        ↓
provider-finalized canary acceptance
```

## 1. Authenticated process success

`authenticate_runpod_log_result(...)` establishes that bounded result bytes and completion evidence belong to the same completion challenge and agree with the trusted process exit outcome. A `pass` result plus exit code 0 becomes `JobState.SUCCEEDED`.

That state does **not** prove that the paid GPU canary met its experiment criteria. A local CPU smoke can legitimately complete successfully and must still fail the paid-canary acceptance gate.

## 2. Orbitune result-side canary acceptance

`validate_orbitune_canary_result(...)` is the trusted workload-specific gate for the currently selected Orbitune canary source:

```text
repository  Unjuno/orbitune
source SHA  38594057d1b118a7acf6c843e39d7d8a25571316
workload    orbitune-runpod-training-canary-v1
```

The function requires trusted control-plane values for the selected source SHA, approved execution-plan fingerprint, and approved immutable image digest. Those values must agree with the authenticated completion evidence and the authenticated result bytes.

The result-side acceptance criteria are intentionally exact:

- authenticated process state is `succeeded` with exit code 0;
- the immutable authenticated payload must reparse to the same JSON value as the exact authenticated `result_bytes`;
- schema version is the actual integer `1`;
- workload id and frozen source SHA match the selected canary;
- completion evidence is bound to the exact approved-plan fingerprint and immutable image digest;
- completion `result_sha256` matches the authenticated result bytes;
- architecture is `orbitune-midi-gpt-v0`;
- tokenizer is `theory-remi-v0`;
- parameter count is the actual integer `10,200,960`;
- training steps, batch size, and sequence length are actual integers equal to 250, 8, and 256;
- processed-token count is the actual integer `512,000`;
- device is CUDA, CUDA is reported available, GPU name and CUDA runtime version are present;
- positive CUDA peak-VRAM evidence is present;
- validation occurs exactly at steps 50, 100, 150, 200, and 250;
- all validation losses are finite and the final validation loss is below the first;
- exactly one `canary-base.pt` checkpoint metadata entry exists;
- checkpoint size is positive and at most 64 MiB;
- checkpoint digest is a canonical lowercase SHA-256 digest;
- checkpoint transport remains `container-local-only` at this stage.

The returned `OrbituneCanaryResultAcceptance` is result-side evidence only. It retains the completion `execution_name`, full per-run nonce, and authenticated `result_sha256` in addition to source/plan/image identity, so a later provider-finalization layer can correlate the acceptance with one exact execution and one exact result even when the same approved plan is submitted more than once.

It deliberately does not claim cleanup, cost, pricing, image publication, or final provider lifecycle success.

## 3. Provider-finalized canary acceptance

A future final acceptance layer must additionally bind the result-side evidence to provider lifecycle facts, including at minimum:

- the exact submission receipt and provider job identity;
- the retained completion execution identity and result digest;
- fresh approved pricing/cost bounds;
- successful collection through a production-supported transport;
- terminal lifecycle correlation;
- cleanup completion and reconciliation;
- the final bounded result manifest.

RunPod production Pod-log SSE is currently not treated as an available production collection transport. Result-side acceptance therefore remains offline/testable without implying that the repository is ready for a paid live run.

## Security boundary

Authentication, workload acceptance, and authorization are different properties. Signed workload output may prove provenance and result integrity, but it cannot authorize paid compute, change control-plane policy, select secrets, increase resource limits, or bypass provider cleanup requirements.
