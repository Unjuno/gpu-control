# P5 account-lease working-tree Security Review — 2026-10-31

## Scope

- Repository: `Unjuno/gpu-control`
- Base and head: `a794438f42bd7246f463eaaa40d963af0aae9d13`
- Frozen working-tree digest:
  `codex-security-snapshot/v1:sha256:68c2ace3c86596fe7c7547fafac24ee328320ce0ae6380b3d4edc0598a8b2f20`
- Codex Security scan: `2087f03f-3369-44bf-af49-0eea97eefb67`
- Coverage: all 18 generated source/policy review items; five reviewed security
  surfaces; two non-overlapping source-discovery passes and a fresh
  source-backed architecture map.

## Result

The completed scan found **zero plausible security candidates** in the frozen
diff. Reviewed areas were Gateway authentication/owner checks, RunPod account
lease creation and recovery, paid/credit authorization gates, backup integrity,
and repository execution policy. Report and SARIF are retained in the Codex
Security scan directory for the scan ID above.

Paid and credit authorization verifier functions remain unconnected to a direct
Gateway caller in the reviewed source. Default RunPod registration does not opt
into candidate/paid/credit execution, and the Worker continues to reject paid
and credit RunPod plans while durable authorization persistence is unavailable.
This is an implementation gap, not evidence of an exploitable path in the
reviewed snapshot.

## Limits

This was static diff review; it did not run the application or verify a live
provider, production host, authenticated ChatGPT session, real GPU, billing, or
resource cleanup. It does not replace an independent GitHub PR review. It does
not establish P1 ChatGPT or P3/P4/P5 release acceptance. Preserve repository
mode `parked` and all spending gates.
