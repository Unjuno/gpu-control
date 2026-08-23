# Decision Failure Catalog

`policies/failure-catalog.yaml` is a catalog of recurring ways an otherwise capable agent can make a poor execution decision.

It is not a list of forbidden words and it is not an authority source. It is a set of recognizable patterns that should trigger reconsideration before a high-impact action proceeds.

## Why keep a catalog

Abstract rules such as "minimize risk" are easy to agree with but easy to misapply. Concrete failure patterns give agents and reviewers examples of what policy violations look like in practice.

The catalog is especially useful as few-shot context because it contains:

- the bad pattern;
- observable signals;
- the relevant constitutional articles;
- the required corrective response.

## Categories

The initial catalog covers objective drift, unjustified scope escalation, economic mistakes, evidence quality, authorization inheritance, stale rationale, approval fatigue, defensive paralysis, lifecycle bounds, resource occupancy, cleanup, few-shot misuse, hidden scope, and experiments that fail without producing useful information.

Important examples include:

- `F003 sunk_cost_escalation` — prior spending is used to justify more spending;
- `F006 authorization_inheritance` — earlier approval is reused for a materially different action;
- `F009 defensive_paralysis` — one denied action is incorrectly treated as failure of the entire objective;
- `F011 resource_hoarding` — scarce compute remains occupied without current value;
- `F013 example_laundering` — a prior example or template is treated as current authorization or evidence;
- `F014 scope_laundering` — a consequential action is described as a harmless substep so stricter gates appear not to apply.

## How an agent should use it

Before escalating a consequential action, compare the proposed rationale against the catalog. A match is a signal to reassess; it is not automatically proof that the action is wrong.

When a pattern is detected:

1. identify the concrete signal;
2. re-check the current objective, evidence, authority, cost, and downside;
3. apply the catalog's required response;
4. preserve safe progress when possible;
5. use a human checkpoint when the remaining issue is judgment or authority.

Hard stops remain a last resort under the Action Constitution.

## Maintenance

New failure modes should be added when they represent a recurring class of decision error rather than one isolated implementation bug. Each entry must have a stable ID, a concise pattern, observable signals, constitutional article references, and a corrective response.

A failure entry must never weaken deterministic security, authorization, cleanup, pricing, or repository-state gates.
