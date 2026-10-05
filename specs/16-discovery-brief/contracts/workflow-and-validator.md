# Contract: workflow steps, validator checks and runner snapshot

## Workflow steps

`ballast-feature` (version 1.1.0 → 1.2.0), between `scope-gate` and `specify`:

| Step | Kind | Runs |
| --- | --- | --- |
| `discover` | command | `speckit.ballast.discover`, `input.args: human-gated` |
| `validate-discovery` | shell | `python3 -I -S .ballast/spec_workflow/artifacts.py discovery --run {{ context.run_id }}` |

`ballast-autonomous` (version 1.0.0 → 1.1.0), between `record-scope` and `specify`:

| Step | Kind | Runs |
| --- | --- | --- |
| `discover` | command | `speckit.ballast.discover`, `input.args: autonomous` |
| `record-discovery` | shell | `artifacts.py record-decision --run {{ context.run_id }} --point clarification` |
| `validate-discovery` | shell | `artifacts.py discovery --run {{ context.run_id }}` |

In both workflows the `specify` step's `input.args` gain: write `spec.md` from `{{ inputs.feature_directory }}/discovery.md`; put a provenance marker on every functional requirement and acceptance criterion; cite every `IAC-n` or list it under non-goals. The `clarify` step gains: do not reopen a decision the brief settled, answered or assumed. `ballast-continue` is unchanged (gate-only, starts after implementation).

## `artifacts.py discovery`

```text
artifacts.py discovery (--run RUN_ID | --feature specs/<N>-<slug>)
```

Exit 0 when the brief satisfies [discovery-brief.md](discovery-brief.md) and [data-model.md](../data-model.md); otherwise exit non-zero with `workflow contract failed: <reason>` on stderr, like every other check.

| Context | Additional behavior |
| --- | --- |
| Human-gated run, no `open` decision | Pass; set `ran` in operator state. No question shown. |
| Human-gated run, `open` decisions, no round recorded for this question set | Refuse any filled `Answer`; record the round; fail with one message listing every open decision (question, options with consequences, recommended default) and the instruction: fill each `Answer` line in `<f>/discovery.md`, then `ballast run resume <run>`. |
| Human-gated run, round recorded | Require the asked questions unchanged and every asked decision `answered` with a non-empty `Answer`; refuse an answer to a decision not asked; record the answer digests; pass. |
| Autonomous run | Refuse `open` and `answered` decisions; require each `assumed` decision to match one `clarification` entry recorded by `record-discovery`; refuse a change outside `<f>/` in `git status`; check `Mode: autonomous`. |
| `--feature` (no run) | Structure, markers and coverage only; no operator-state attribution. |

In a human-gated run, a passing check rewrites the brief's `## Question metrics` section from the counts in operator state ([data-model.md](../data-model.md#clarification-round-operator-state)); this is the only edit a validator makes to the brief. In an Autonomous run the check does not edit the brief (its digest is already in the recorded decisions); it requires `Rounds: 0`, `Questions asked: 0` and `Assumptions adopted` equal to the recorded discovery assumptions.

## `artifacts.py spec` (extended)

When discovery ran for the feature (brief present or operator state `ran`), `check_spec` also enforces the spec traceability rules in [data-model.md](../data-model.md#spec-traceability-checked-on-specmd). A missing brief after `ran` fails. Features without either keep today's check (PD-0002). The rules are cumulative: `clarified-spec`, `intent`, `plan` and later checks call `check_spec` and so re-verify them.

`check_intent` is unchanged: intent binds only the `spec.md` digest, so editing `discovery.md` after intent neither invalidates nor changes it (AC-017, SC-006).

## Issue snapshot (`.specify/workflow-state/issues/<N>.md`)

`render_issue_snapshot(issue, scope_comment, comments)` adds, after the intake scope comment:

```markdown
## Comments

### <login> (<author_association>), <created_at>

> <body, every line quoted>
```

Comments appear oldest first. Each body is quoted line by line, so a comment cannot forge another author's header or a section (security review SEC-001). The intake scope comment stays in its own section and is not repeated. Budget within the existing 60,000-character cap: body first, then scope comment, then comments, each truncated with the existing marker; a truncated or omitted comment is announced as such.

| Start | When the Issue cannot be read |
| --- | --- |
| `ballast run start --mode autonomous` | Unchanged: the start is refused (fails closed). |
| `ballast run start` (human-gated) | Writes a snapshot whose body is `Issue #<N> could not be read: <reason>` and continues; discovery lists the Issue under `unavailable`. |

The human-gated start reads only `repos/<repo>/issues/<N>` and its comments for the `[github] repository` in `ballast.toml`, through the same `gh` resolution the Draft PR checkpoint uses, and passes no token to any agent step.
