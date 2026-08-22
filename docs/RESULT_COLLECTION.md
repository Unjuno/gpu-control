# Result Collection Contract

Provider output is untrusted and potentially large. `gpu-control` therefore treats collection as a bounded metadata-and-small-artifact operation rather than an instruction to download everything produced by a GPU job.

## Core rule

A finalized provider job may produce two classes of artifacts:

1. **collected** — small artifacts that the control plane is allowed to retain directly;
2. **reference_only** — large artifacts that remain in provider/object storage and are represented only by metadata plus a required SHA-256 digest.

Large checkpoints should normally be `reference_only`. A result reference is opaque metadata. The control plane must not automatically fetch it merely because it appears in a manifest.

## Default bounds

The bundled and published result policy currently sets:

- retained logs: at most 1 MiB;
- artifact entries: at most 32;
- one collected artifact: at most 64 MiB;
- all collected artifacts combined: at most 128 MiB;
- one declared artifact, including reference-only artifacts: at most 1 TiB;
- artifact names: at most 160 characters;
- artifact references: at most 2048 characters.

These are control-plane retention limits, not workload output limits. A workload may create a larger checkpoint if it stays external and is represented as `reference_only`.

## OutputArtifact

`src/gpu_control/results.py` defines `OutputArtifact` with:

- a safe relative POSIX name;
- lowercase `sha256:` digest;
- declared size in bytes;
- media type;
- opaque provider/storage reference;
- disposition (`collected` or `reference_only`).

Names such as `../secret`, absolute paths, and backslash-separated paths are rejected. Duplicate names in one manifest are rejected.

The digest is required for both collected and reference-only artifacts so later consumers can verify content identity independently of the storage reference.

## ResultManifest

A result manifest is created only after the asynchronous lifecycle has reached a finalized state: the provider job is terminal and cleanup is recorded as completed.

The manifest binds the collected result to:

- provider;
- provider job id;
- approved-plan fingerprint;
- submission-receipt fingerprint;
- final-observation fingerprint;
- terminal job state;
- collection timestamp;
- retained log byte count and truncation state;
- bounded artifact metadata.

`build_result_manifest(...)` rejects collection before finalization, collection timestamps that predate the final observation, oversized logs, oversized collected files, excessive collected totals, excessive artifact counts, malformed artifact metadata, and unsafe artifact names.

## Durable result state

`ResultManifest` has deterministic JSON serialization and a `sha256:` fingerprint. `ResultManifest.from_json(...)` uses strict restoration and rejects unknown fields, missing fields, duplicate JSON keys, unsupported schema versions, malformed states, malformed digests, and policy violations.

After restoration, `validate_manifest_against_lifecycle(...)` must re-bind the manifest to the trusted submission receipt and final observation. Parsing successfully is not sufficient to establish trust.

## Security properties

The collector must not:

- automatically fetch reference-only artifacts;
- execute generated files;
- interpret an artifact reference as authorization;
- retain unbounded logs;
- retain unbounded artifacts;
- accept path traversal in artifact names;
- trust provider result metadata without lifecycle correlation;
- treat cleanup failure as a completed result.

## Provider independence

This contract contains no RunPod-specific API shape. A future RunPod collector should translate provider output into `OutputArtifact` values and a `ResultManifest`, subject to the same policy limits.

That keeps provider-specific transport separate from the control-plane trust and retention rules.
