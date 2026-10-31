# Recovery review handoff snapshot — 2026-10-28

Status: NOT REVIEWED. This file is an implementation-author handoff aid, not independent review evidence. Review the complete worktree and do not infer PASS from the hashes.

- Branch: `codex/chatgpt-cpu-vertical`
- HEAD: `eff04c508f02c7f8206e23884f281e1edff4ddab`
- SHA-256 of `git diff HEAD --binary`: `7848e17a94b887232cb202be1ee8f5a1c0a9bb4af1562d646ae76379c030665a`
- Untracked files are listed below with SHA-256; include their contents in the review.
- This handoff file itself is excluded from the untracked-file hash list.

## Untracked review inputs

- `docs/acceptance/2026-10-28-atomic-backup-generation.md` — `be4ff7a4fb7e01618f4b1a347efc2d98beba60b18444c15b3d2fa7a2c449cd29`
- `docs/acceptance/2026-10-28-neon-first-schema-migration.md` — `ffc8c4178247dfb3a516ee5af14e8a2b4f8dd902623669bb287fe81ce1586b49`
- `docs/acceptance/2026-10-28-owner-issuer-migration.md` — `8ff161185694f96dc87bb707c2cca7e4524c82b6c2c727d6e9f507df2740a01a`
- `docs/acceptance/2026-10-28-paired-artifact-restore.md` — `93dd484a9faf03c70b02a52333bf1baf962ca172cfe47df2a95a5a71f5513486`
- `docs/decisions/2026-10-28-p3-deployment-topology.md` — `405ccb2942ce13aaccef2aebf8c59d7488e58bdf0646908baa572455d290dd7a`
- `gateway/deploy/backup_generation.py` — `19bdb77a36becd0a579c367903792a17187a5215a74fa4de857b9b8f81a91d9a`
- `gateway/deploy/check_artifact_capacity.py` — `1c23c7dca772e2892105c9d0bef5077439812effe8430ccc6989fd1bec8525a8`
- `gateway/deploy/gpu-control-api.service` — `27baae1f3ff157880d4f911a61cc7fb010911b44ad755e3b34918a6d0e92500b`
- `gateway/deploy/gpu-control-artifact-capacity.service` — `ae87229379e339c008be71c42c93aa83214b85cb7ceb5b5fcfdd28689c113569`
- `gateway/deploy/gpu-control-artifact-capacity.timer` — `a346c49f5813df91f961f712e863d8545952ca229949df5350fc36ab382f4b61`
- `gateway/deploy/gpu-control-db-migrate.service` — `182b58fe3163be74b15cc44c1071a2c1242f4ed62da1e615a78d4f3852c5c886`
- `gateway/gpu_gateway/owner_migration.py` — `82a623f56b6ad6bfd987b44fac2d35ac0bdf2f89941f048835960c84a70789b2`
- `gateway/tests/test_backup_generation.py` — `da3b21bc46d7284840edaa03d4efaab33b5a4f8f88407a5f53ae4bc0ef835958`
- `gateway/tests/test_deploy_units.py` — `5ccb8155c3826dfb684eff890c7111ac595606cbbc131331a3ab66d9530011ef`
- `gateway/tests/test_external_auth.py` — `993810d8719ede81b81c9898d931dbc1ba653c180866aba9b15a8f2aab33ecf5`
- `gateway/tests/test_owner_migration.py` — `217a9c6d4f0aa2e0e242a11a0e1f2e481780c7c379d8f392033ef360a5dc5ebb`
- `src/gpu_control/http_security.py` — `b66a0bce74b592358954c7ee5be40dc279caa61e8a26ae397bc57a4a3633feaa`
- `tests/test_http_security.py` — `c664d039cc6bc126d173d3485cf5fe67647d431f7a9fe1c7fa2d1afb222ccb63`

## Required reviewer action

Refresh the branch, HEAD, tracked diff, and untracked file hashes before starting. Inspect all changed files, follow `RECOVERY_REVIEW_CHECKLIST.md`, and fill its reviewer record only as the independent reviewer. Any follow-up code change requires a fresh review target.
