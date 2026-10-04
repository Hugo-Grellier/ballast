# Contract: agent decision drafts

Location: `specs/<f>/autonomous/drafts/`. Drafts are untrusted, and the recorder (`artifacts.py record-decision`) validates each one strictly. Any violation fails the step as a `postcondition` block that names the field. The recorder deletes the draft after it appends the entry.

## Decision draft: `<point>.json`, or `<point>-<n>.json` for multi-entry points

```json
{
  "point": "plan",
  "decision": "accept",
  "summary": "Plan covers FR-001..FR-030 with one workflow per mode",
  "basis": "Why the plan is acceptable, citing the spec and review",
  "evidence": ["specs/27-autonomous-core/plan.md", "specs/27-autonomous-core/reviews/plan.md"],
  "artifact": "specs/27-autonomous-core/plan.md",
  "model": "claude-opus-5-5",
  "material": false,
  "supersedes": null,
  "risk": "R1",
  "boundaries": [],
  "privileged_actions": [],
  "review": null,
  "assumption": null
}
```

| Field | Rule |
| --- | --- |
| `point` | Must equal the recorder's `--point`. Multi-entry points are `clarification`, `decision-resolution` and `specialist-review`. |
| `decision` | `accept` (gates), `assume` (clarification), `resolve` (decision resolution), `accept-finding` (review points) |
| `summary`, `basis` | Non-empty, length-bounded (data model). The summary is one line. |
| `evidence` | Existing repository-relative paths inside the checkout, or `https://` URLs. Symlinks and `..` are refused. |
| `artifact` | Existing repository-relative path, not a symlink (the same applies to a review `report`). The recorder hashes it, so the draft carries no digest. |
| `model` | Optional, agent-reported. It is recorded as `unreported` when absent. |
| `risk` | Optional. A level above the recorded risk raises it and triggers the eligibility re-check. A lower level is ignored. |
| `boundaries` | Optional R2 boundary names; merged into the risk record |
| `privileged_actions` | Required list (may be empty) of privileged actions the change now needs before merge (FR-006 vocabulary). A non-empty list triggers the eligibility re-check; an unauthorized action records an `ineligible` block. Review entries carry the same field. `run.py` re-checks the union before publication (research R-03). |
| `review` | Required for review points (data model: Review entry, without `cross_provider` and `author_provider`, which the runner fills). The findings section of the `report` file is rendered by the recorder from the validated `findings` (plan review round 3): the structured draft is the only source of findings, and the reviewer's own file holds narrative only. The recorder refuses a narrative that contains a findings heading or a severity tag (`critical`, `high`, `medium`, `low` as a label), so a finding cannot live only in prose. Test: a narrative carrying a `high` finding absent from the draft is refused. |
| `assumption` | Required for `clarification`: `question`, `default`, and `reversible: true`. A `false` value is refused; that case must be a block. |
| Wording | `summary` and `basis` must not match `(?i)\b(human[- ]approved|approved by (the )?(human|operator|user))\b` (AC-007). |

Fields the runner owns (`id`, `prev`, `at`, `provider`, `step_id`, `role`) are ignored when present.

## Block draft: `block.json`

```json
{
  "category": "decision",
  "condition": "Spec requires both X and not-X for archived items",
  "options": [
    {"option": "Keep X", "consequence": "..."},
    {"option": "Drop X", "consequence": "..."}
  ],
  "recovery": "Choose an option and record it in spec.md, then continue human-gated",
  "evidence": ["specs/27-autonomous-core/spec.md"]
}
```

`category` is `decision` or `contradiction`. Two or more options are required. A `decision` block also needs a reason why no safe, reversible default exists. `run.py` adds the `command` field and moves the block into `block.json` in operator state. No provisional decision is recorded for the blocked point (AC-011). A clarification that finds several independent outcomes uses `category: decision` and recommends decomposition. It never creates Issues.

## Provisional decision resolution in `decisions.md` (Autonomous only)

```text
## DEC-0003 — Resolution

- **Status**: agent-provisional (PD-0012), not human-approved
- **Resolution**: ...
- **Material**: yes|no
```

`check_decisions` in an Autonomous run accepts a resolution only when its `PD-NNNN` exists in the log with `point: decision-resolution`. In a human-gated run, a resolution whose status says `agent-provisional` does not count as resolved.
