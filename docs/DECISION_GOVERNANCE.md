# Decision Governance

`gpu-control` distinguishes between **rejecting an action** and **abandoning an objective**.

A defensive control plane must prevent unjustified escalation, but it must not turn every uncertainty or policy failure into mission failure. The preferred behavior is to preserve the user's objective while reducing action scope, substituting a cheaper or safer method, or requesting human judgment only when necessary.

The machine-readable source of truth is `policies/decision-policy.yaml`.

## Core principle: goal-preserving restraint

The default response to an unjustified action is not "give up." It is:

```text
continue
  -> reduce scope
  -> choose a safer alternative
  -> request a human checkpoint
  -> deny the specific action
```

`deny_action` rejects one proposed action. Unless the objective has already been achieved, has become invalid, has been explicitly cancelled, or has no remaining safe and authorized path, the mission remains active.

Examples:

- A 30-minute GPU run is not economically justified: reduce to a 2-minute CUDA or one-batch smoke test.
- A paid GPU run lacks enough evidence: continue with source inspection, CPU validation, or an offline container test.
- A provider action is outside autonomous authority: preserve the plan and ask for a human checkpoint rather than inventing authorization.
- The current experiment already answered the question: stop escalation because the objective is achieved, not because the system failed.

## Decision dimensions

Before increasing action scope, evaluate the current proposal against these dimensions:

1. **Purpose** — What current objective does this action serve?
2. **Evidence** — Is there enough evidence to justify this action rather than another diagnostic step?
3. **Cheaper alternative** — Can a local, read-only, CPU, mock, smaller-data, or shorter-runtime action answer the same question?
4. **Decision value** — Will the result change the next decision?
5. **Economic value** — Is the information or outcome worth the direct and indirect cost?
6. **Reversibility** — How difficult is it to restore the prior state if the action is wrong?
7. **Blast radius** — What is the worst credible impact of a mistake?
8. **Authority** — Is this exact action authorized now, rather than merely similar to a previously authorized action?
9. **Stop condition** — What event ends the action before it drifts into open-ended work?
10. **Learning value** — If the action fails, will the failure still reduce uncertainty?
11. **Opportunity cost** — What resource, GPU capacity, human attention, or future experiment does this action displace?

These dimensions are not a scoring game where enough low-risk answers cancel one severe problem. A hard authorization or safety boundary remains binding.

## Progressive experimentation

Paid or higher-impact experimentation should be progressive:

```text
inspect
  -> local/read-only validation
  -> CPU/container smoke test
  -> smallest useful GPU smoke test
  -> bounded experiment
  -> larger experiment only if newly obtained evidence justifies it
```

Success at one stage does not automatically authorize the next stage. Failure at one stage does not justify spending more. Each expansion needs a current rationale tied to the active goal and to information obtained so far.

A remaining budget is not a reason to spend it. A cost limit is a **loss ceiling**, not a spending target.

## Mission state versus action decision

Keep these concepts separate.

Mission states:

- `active` — the objective still matters and there is useful work to do;
- `achieved` — the current objective has been answered or completed;
- `blocked` — no useful progress is currently possible without missing information, authority, or capability;
- `abandoned` — the objective was explicitly cancelled or is no longer valid.

Action outcomes:

- `continue`
- `reduce_scope`
- `safer_alternative`
- `human_checkpoint`
- `deny_action`

An action may be denied while the mission remains active. The controller or agent should then report the reason and select the cheapest safe next step that still advances the objective.

## Hard stop is a last resort

A hard stop is appropriate when:

- the human explicitly cancels the objective;
- the objective is no longer valid;
- no safe or authorized path remains; or
- the only required action has unacceptable irreversible downside.

When a hard stop occurs, preserve the reason and, where applicable, state what concrete condition would be required to resume.

## Paid-compute decision record

Before paid compute is eventually enabled, the decision record should state at least:

```text
Active goal:
Current question:
Cheapest viable alternative:
Why that alternative is insufficient:
Expected decision impact:
Maximum justified cost:
Success condition:
Stop condition:
Failure learning value:
Worst-case downside:
```

This record complements security, authorization, pricing, source, container, and cleanup evidence. It does not replace them.

## Enforcement boundary

Qualitative judgment can live in prompts and review procedures, but hard boundaries must not depend on the model talking itself into compliance.

Use prompts and agent policy for:

- purpose and decision value;
- economic rationale;
- hypothesis quality;
- alternative selection;
- opportunity-cost reasoning.

Use deterministic policy or external controls for:

- identities and permissions;
- cost/runtime/GPU-count ceilings;
- provider credentials;
- branch/environment protection;
- immutable workload and image identities;
- concurrency and provider occupancy;
- lifecycle, cleanup, and result constraints.

The intended outcome is neither reckless autonomy nor unnecessary paralysis. It is the smallest justified action that continues to make useful progress toward the active objective.
