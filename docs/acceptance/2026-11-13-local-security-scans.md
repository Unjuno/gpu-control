# Supplemental local security scans — 2026-11-13

These machine scans supplement, but do not replace, the requested independent
repository-wide Codex Security Deep Scan. They ran against the tracked
repository tree including the Sign-in fix at PR #68 code commit
`f49988a96e4a65657f67041b90862da6d3aa1319`; later edits were documentation-only.

## Semgrep

- Version: 1.161.0
- Command: `semgrep scan --config p/security-audit --metrics=off --json .`
- Coverage: 277 tracked files, 110 rules, approximately 100% parsed lines;
  51 files matching `.semgrepignore` were skipped.
- Result: one WARNING, `python.lang.security.insecure-hash-algorithms.insecure-hash-algorithm-sha1`, at `project_control/runner.py:147`.
- Triage: this code reproduces GitHub's Git blob object ID (`SHA-1("blob " + length + NUL + bytes)`) for source-integrity matching. The call sets `usedforsecurity=False`; nearby comments explicitly state it is not a signature or security token. The finding is an intentional compatibility use, not evidence of a signing/credential weakness. It remains a static analyzer warning.

## Gitleaks

- Version: 8.30.1
- Command: `gitleaks dir --redact=100 --no-banner --exit-code 0 --report-format json --report-path /tmp/gpu-control-gitleaks-redacted.json .`
- Coverage: current filesystem tree, approximately 15.34 MB; this was not a full Git history scan.
- Result: five `generic-api-key` matches, with all report contents redacted.
- Triage: four matches are the fixed `TOKENIZER_SHA256` model asset checksum in source and its generated bundle copy. One match is an `oai-authenticated-user-id` header in documentation describing a forged-identity denial probe. No live credential was verified from these matches.

## Limits and next action

The Codex Security Deep Scan coordinator refused to start because the current
parent session does not provide the managed filesystem permission profile
required for read-only workers. It returned: `Deep Scan cannot safely start a
read-only worker: the parent must provide a managed filesystem permission
profile.` No replacement scan was started. Repository-wide semantic audit,
full-history secret validation, independent review, actual authenticated
cross-account testing, and hosted provider acceptance remain open.
