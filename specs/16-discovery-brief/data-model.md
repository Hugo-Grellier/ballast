# Data model: Source-backed discovery brief

Entities from the spec's Key Entities, with the fields and rules the validator enforces. The file format itself is in [contracts/discovery-brief.md](contracts/discovery-brief.md).

## Discovery brief (`specs/<N>-<slug>/discovery.md`)

| Field | Form | Rule |
| --- | --- | --- |
| Evidence marker | `<!-- ballast-discovery: input evidence -->` as the first line | Required (FR-013, AC-018). |
| Authority note | One paragraph linking `spec.md` and `intent.md` | Required; must contain both links. |
| Mode | `**Mode**: human-gated` or `**Mode**: autonomous` | In a run, must equal the run's mode (Autonomous when an operator run record exists). |
| Sources | `## Sources` list | Each entry is a cited source or `unavailable: <what> — <why>`. Repository paths must exist. |
| Need | `## Need` with `User`, `Job to be done`, `Current pain`, `Intended outcome` items | Each item carries a provenance marker. |
| Examples | `## Examples` list | At least one item; each carries a marker. |
| Scope, Non-goals, Constraints, Permissions and data authority, Success evidence | One `##` section each | Non-empty; each list item carries a marker. |
| Issue acceptance criteria | `## Issue acceptance criteria`, items `IAC-n: <text>` | Must equal the snapshot's criteria (R-05) when the snapshot has them. |
| Edge, failure and permission cases | `## Edge, failure and permission cases` | Each item carries a marker; the spec must cover or reject each (FR-014, reviewed). |
| Known / Inferred / Undecided | `## Known`, `## Inferred`, `## Undecided` | Known items use `[S:]` or `[O:]`; Inferred items use `[I]` or `[P:]`; Undecided items reference a `D-NN`. |
| Decisions | `## Decisions`, one `### D-NN: <title>` each | See High-impact decision. |
| Question metrics | `## Question metrics`: `Rounds`, `Questions asked`, `Assumptions adopted` | Integers. In a human-gated run `validate-discovery` rewrites this section from operator state; in an Autonomous run it requires the agent's counts to equal the recorded ones (FR-015). |
| Changes | `## Changes` (optional) | Present only when an existing brief was updated (`Continue #N`). |

Provenance markers are defined in [research R-04](research.md#r-04-traceability-marker-syntax). A list item with no marker fails validation and the message names the section and item (AC-002).

## Provenance

| Kind | Marker | Allowed in |
| --- | --- | --- |
| Cited source | `[S: …]` | Brief and spec |
| Agent inference | `[I]` | Brief and spec |
| Operator answer | `[O: D-NN]` | Brief and spec, human-gated only; `D-NN` must be `answered` |
| Agent-provisional assumption | `[P: D-NN]` | Brief and spec, Autonomous only; `D-NN` must be `assumed` |
| Brief item | `[B: …]` | Spec only |

## High-impact decision (`### D-NN` in the brief)

| Field | Rule |
| --- | --- |
| `Status` | One of `settled`, `open`, `answered`, `assumed`, `blocking`. |
| `Question` | One line. |
| `Why it matters` | Which implementation or acceptance outcome changes. |
| `Sources` | Markers for the evidence considered; a contradiction names both sources (FR-006). |
| `Options` | At least two, each with a consequence, unless `settled`. |
| `Recommended default` | Required unless `settled`. |
| `Answer` | Empty unless `answered`; set only by the operator. |
| `Resolution` | For `settled`: the source that answers it (FR-007, AC-005). For `assumed`: the adopted default and why it is safe and reversible. |

State transitions:

```text
human-gated:  settled                       (repository answered it; never asked)
              open ──(round recorded, operator fills Answer, resume)──▶ answered
autonomous:   settled
              assumed   (safe, reversible default; recorded as PD-NNNN at point clarification)
              blocking  (block.json written; run stops)
```

Rules:

- A human-gated brief from the agent step has no `answered` decision and no non-empty `Answer` (AC-008).
- An Autonomous brief has no `open` and no `answered` decision (AC-012); `blocking` only appears together with a block draft, so a recorded brief never reaches validation with it.
- A contradiction about product behavior, scope, data authority, a security boundary or accepted architecture is never `assumed` (FR-009); the command must block. The validator cannot judge the category, so review checks it.
- Contradictions between sources are `open` (human-gated) or `blocking` (Autonomous), never silently `settled` (AC-004).

## Clarification round (operator state)

Stored by `validate-discovery` under `launcher.state_dir()/discovery/<sha256(feature)>.json`, which agents cannot write:

| Field | Meaning |
| --- | --- |
| `feature` | `specs/<N>-<slug>` |
| `rounds` | List of `{asked: [D-NN, …], questions_digest, at}` in order. |
| `answered` | `{D-NN: answer_digest}` accepted on resume. |
| `ran` | `true` once discovery validated for this feature; makes the spec traceability check mandatory (R-06). |

Derived metrics (written into the brief in human-gated runs, compared in Autonomous runs): `Rounds = len(rounds)`, `Questions asked = sum(len(asked))`, `Assumptions adopted = count(assumed)`. In an Autonomous run `Rounds` and `Questions asked` are 0, and `Assumptions adopted` equals the number of `clarification` entries recorded by `record-discovery`, each naming its `D-NN` in `assumption.question`.

## Spec traceability (checked on `spec.md`)

| Rule | Applies when | Failure names |
| --- | --- | --- |
| Every `**AC-NNN**` line carries a provenance marker | discovery ran (R-06) | the AC ID (AC-015) |
| Every `IAC-n` in the brief appears in `spec.md`, in an AC marker or under a non-goal heading | discovery ran | the `IAC-n` and its text (AC-016) |
| `[O: D-NN]` / `[P: D-NN]` refer to `answered` / `assumed` decisions of the brief | discovery ran | the marker |

Functional-requirement markers and failure/permission/edge coverage (AC-014 for FRs, AC-019) are checked by the plan and spec reconciliation reviews, as the spec's Assumptions state.
