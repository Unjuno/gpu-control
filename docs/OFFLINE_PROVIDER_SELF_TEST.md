# Offline Provider Contract Self-Test

`gpu-control provider-self-test` exercises the provider-facing control-plane path without contacting any external service.

The command uses `SyntheticProviderAdapter`, a deterministic in-process adapter that:

- performs no HTTP requests;
- reads no API keys or provider credentials;
- creates no external resource;
- cannot allocate GPU compute;
- has no billable behavior.

## What it checks

The command builds synthetic evidence for a fixed non-billable test workload, creates an `ApprovedExecutionPlan`, and then follows the same provider-controller functions intended for a future live backend:

```text
synthetic source/container/pricing evidence
        -> ApprovedExecutionPlan
        -> trusted plan fingerprint check
        -> submission-time pricing freshness check
        -> SyntheticProviderAdapter.submit
        -> SubmissionReceipt
        -> running observation
        -> succeeded observation
        -> cleanup completed
        -> bounded ResultManifest
```

The synthetic result includes one small collected `metrics.json` artifact and one 2 GiB checkpoint represented as `reference_only`. This exercises the result-retention policy without creating or downloading a large file.

## Run it

From an installed development environment:

```bash
uv run gpu-control provider-self-test
```

The command can also run outside the repository directory after installation. CI executes it from `/tmp` on Python 3.11, 3.12, and 3.13 to verify that the installed package contains all required policy and provider-contract modules.

A successful response includes:

- `status: ok`;
- `dry_run: true`;
- `provider: synthetic`;
- `network_access: false`;
- `external_resources_created: false`;
- `billable_compute: false`;
- plan, submission-receipt, and result-manifest fingerprints;
- terminal state `succeeded`;
- collected/reference-only artifact dispositions.

## What it does not prove

This command does **not** verify:

- RunPod credentials;
- current RunPod price or availability;
- RunPod API request/response formats;
- GPU scheduling or CUDA execution;
- provider callbacks or real recovery behavior;
- external artifact storage.

Those require a future live-provider integration and should not be inferred from a successful synthetic test.
