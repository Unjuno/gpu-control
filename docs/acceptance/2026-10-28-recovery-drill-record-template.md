# Production recovery drill record

Status: **TEMPLATE ONLY — no production or timed drill has been run.**

Use one copy per drill. The operator performing the restore and the independent
observer must record times in UTC and retain the private command/output
evidence. Do not put credentials, OAuth tokens, token hashes, private owner IDs,
or database URLs in this record.

## Scope and authorization

| Field | Value |
| --- | --- |
| Environment / deployment revision | NOT RUN |
| Incident or planned-drill identifier | NOT RUN |
| Drill type (isolated / production) | NOT RUN |
| Approval/reference and date | NOT RUN |
| Restore operator | NOT RUN |
| Independent observer | NOT RUN |
| Selected recovery generation ID | NOT RUN |
| Source schema and PostgreSQL version | NOT RUN |
| Artifact volume identity / filesystem size | NOT RUN |
| Data classes in scope (runs, OAuth state, artifacts) | NOT RUN |

## Clock definitions

- **RPO incident start:** the UTC timestamp when the disruption began, based
  on monitoring or request evidence. Record this separately from the last
  successful write before the disruption.
- **RPO recovered-through:** the timestamp of the latest acknowledged Gateway
  write at or before `RPO incident start` whose run, result, OAuth state (where
  in scope), and paired artifact bytes are all present and verified after
  recovery. A DB timestamp alone is insufficient.
- **Measured RPO:** elapsed time from `RPO incident start` back to `RPO
  recovered-through`. If the latest acknowledged pre-incident write is fully
  recovered, record that point; if any acknowledged pre-incident writes are
  missing, use the latest earlier write whose full state was recovered and list
  every missing acknowledged write. A drill with no acknowledged writes must
  state that RPO could not be measured from workload data. An incident with all
  pre-incident writes recovered can still have a nonzero time interval since
  the latest write; it has no acknowledged-write loss.
- **RTO start:** first observed user-visible outage or planned recovery start,
  whichever begins the recovery event. Record the source signal and timestamp.
- **RTO end:** the timestamp when ingress is restored and the independent
  observer confirms readiness, owner-scoped run/result/artifact reads, cleanup
  accounting, and operator-visible alerts. A successful `pg_restore` alone is
  not recovery completion.
- **Measured RTO:** elapsed UTC time from `RTO start` to `RTO end`. State
  whether the two-hour target was met; do not stop the clock for investigation,
  waiting on an operator, or correcting a failed verification.

Use synchronized UTC clocks and preserve raw timestamps with timezone. Record
the exact target and source state before the drill; do not choose a favorable
start point after observing the result. For an isolated rehearsal, report
measured durations but do not claim production RPO/RTO acceptance.

## Timeline and verification

| Event | UTC timestamp | Evidence reference / result |
| --- | --- | --- |
| Impact or planned recovery begins (`RTO start`) | NOT RUN | NOT RUN |
| Last acknowledged write before disruption | NOT RUN | NOT RUN |
| Ingress/admissions stopped | NOT RUN | NOT RUN |
| Paired generation selected and checksums verified | NOT RUN | NOT RUN |
| Database restore completed | NOT RUN | NOT RUN |
| Artifact volume restore completed | NOT RUN | NOT RUN |
| Schema, run, OAuth and cleanup reconciliation completed | NOT RUN | NOT RUN |
| Owner-scoped artifact digest/size checks completed | NOT RUN | NOT RUN |
| Independent observer accepts readiness and reads | NOT RUN | NOT RUN |
| Ingress restored (`RTO end`) | NOT RUN | NOT RUN |
| Latest acknowledged write at/before disruption fully recovered (`RPO recovered-through`) | NOT RUN | NOT RUN |

## Results and disposition

| Measure | Result |
| --- | --- |
| Measured RPO | NOT RUN |
| RPO target (24 hours) met? | NOT RUN |
| Acknowledged-write loss? / missing writes | NOT RUN |
| Missing acknowledged runs/writes | NOT RUN |
| Measured RTO | NOT RUN |
| RTO target (2 hours) met? | NOT RUN |
| Run/result/OAuth parity evidence | NOT RUN |
| Source / manifest / restored schema-version match (include `unversioned` if applicable) | NOT RUN |
| Private source and restored table-count evidence references | NOT RUN |
| Artifact manifest count and digest verification | NOT RUN |
| `active_count`, nonterminal runs, and external resource reconciliation | NOT RUN |
| Owner-isolation check | NOT RUN |
| Alert delivery / recovery notification | NOT RUN |
| Deviations, unresolved risks, corrective actions | NOT RUN |
| Independent observer decision and UTC time | NOT RUN |

Acceptance requires the independent observer to verify the evidence and the
recorded measurements to meet the predeclared targets. Any missing acknowledged
state, unknown external resource outcome, digest mismatch, or owner-boundary
failure is a failed drill regardless of elapsed time. Preserve the source
generation and drill evidence until the corrective action is reviewed.
