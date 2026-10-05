# End-to-end runs (T044)

- Date: 2026-10-05
- Host: Linux, systemd user session, Spec Kit CLI 1.0.11, bwrap; Claude integration (`-i integration=claude`; Codex quota exhausted until 2026-10-10)
- Scratch project: private disposable GitHub repository with a small Python package, installed with `BALLAST_STANDARD_DIR=<this worktree> ballast setup` and trusted.
- Test Issue #8 "Add a word-count helper": a three-line body, a `## Acceptance criteria` list of three items, and one owner comment ("Punctuation attached to a word ("hello,") should still count as one word.").

## Findings fixed on the way

1. **Stale `.specify/feature.json`** (first human-gated attempt): discovery runs before `speckit.specify` writes the pointer, so it read `specs/4-admin-token` from an earlier run and blocked `BLOCKED_DECISION`. `run.py` now points `.specify/feature.json` at the run's validated feature on every human-gated `start` and `resume`, as an Autonomous start already did (`54171bc`, test `BranchSyncCallTests.test_start_points_feature_json_at_the_run_before_the_engine`).
2. **Issue snapshot before the branch check** (after rebasing onto #18): the snapshot is a new file under `.specify/workflow-state/`, which the branch check counts as dirty in a checkout that does not ignore `.specify/`. The snapshot is now written after the check (`3716a3f`, caught by `BranchSyncEndToEndTests.test_start_synchronizes_before_the_first_step`).
3. The first attempt also failed because the default integration (Codex) was out of quota; not a Ballast defect.

## Scenario 1: human-gated (AC-001, AC-006, AC-007, AC-009)

`ballast run start -i idea="Issue #8: …" -i feature_directory=specs/8-word-count -i integration=claude`, scope gate approved.

- The discover step wrote `specs/8-word-count/discovery.md` before any `spec.md`, citing the Issue body, the owner comment, `src/pilot/text.py` and the engineering policy, and listing the missing constitution, product and technical specs as unavailable.
- `validate-discovery` stopped the run once with both open decisions bundled (question round 1): D-01 punctuation-only tokens, D-02 non-string input, each with options, consequences and a recommended default.
- Both answered A in `discovery.md` (Status `answered`), then `ballast run resume 6a6d7a1b`.
- specify and clarify ran without asking again; the run reached the `approve-intent` gate, whose summary lists D-01 and D-02 as operator answers recorded in the brief. The run was stopped at that gate (nothing further is in this scenario's scope).

```
  ▸ [validate-discovery] shell …

Status: failed
Run ID: 6a6d7a1b
Error: Shell command exited with code 1.

Run 6a6d7a1b: failed at step validate-discovery
stderr: workflow contract failed [discovery]: discovery needs your answers (question round 1); the repository and the Issue do not settle these decisions:

D-01: Does a whitespace-separated token made only of punctuation (e.g. `"-"` in `"a - b"`, or `"..."`) count as a word?
  Why it matters: It changes the expected result of acceptance tests (`"a - b"` → 3 or 2) and whether the implementation is a plain whitespace split or needs a character test per token.
  Options:
    - A — Count every whitespace-separated token, punctuation-only included. Consequence: implementation is `len(text.split())`; `"a - b"` returns 3; simplest and consistent with `slugify`.
    - B — Count only tokens containing at least one letter or digit. Consequence: `"a - b"` returns 2; adds a per-token `any(ch.isalnum() ...)` check and a test for the excluded case.
  Recommended default: A, because the Issue defines words purely by whitespace separation and the comment only addresses punctuation attached to a word.

D-02: What should `count_words` do when given a non-string argument such as `None`?
  Why it matters: It decides whether a validation path and its negative test are part of acceptance.
  Options:
    - A — No explicit validation; rely on the `str` type hint, as `slugify` does, so `None` raises the natural `AttributeError`. Consequence: no extra code or test; matches the module's existing style.
    - B — Raise `TypeError` explicitly for non-`str` input. Consequence: one guard and one negative test; clearer error for callers.
    - C — Return 0 for `None`. Consequence: silently accepts missing input, which the engineering policy discourages ("a failed operation must not appear successful").
  Recommended default: A, because it matches the existing module and the Issue asks for nothing more.

For each decision above, edit specs/8-word-count/discovery.md: set **Status** to answered and write your choice on its **Answer** line (the recommended default is fine). Leave the questions unchanged, then run `ballast run resume 6a6d7a1b`.
error: Shell command exited with code 1.
Agent logs: .specify/workflow-state/6a6d7a1b/agents/
Draft PR: pending (not-published): publish the branch, e.g. git push -u origin feat/8-word-count
```

## Scenario 2: Autonomous (AC-010, AC-012, AC-013)

`ballast run start --mode autonomous -i issue=8 -i idea="Issue #8: …" -i feature_directory=specs/8-word-count-auto -i integration=claude`, from a fresh feature branch, after an intake scope comment with `Autonomous: yes`.

- No prompt at any step; the run completed (`Status: completed`, run `d3076a2c`) and opened the scratch project's Draft PR #9.
- The PR's files include `specs/8-word-count-auto/discovery.md`.
- The discovery assumption D-05 (no runtime validation of non-`str` input) is PD-0002, kind `clarification`, decision `assume (agent-provisional)`, in both `autonomous/record.md` and the PR body's provisional-decision table; the intent decision PD-0003 cites it.

```
- **Same-provider reviews:** every review ran on Claude, the same provider that wrote the code (DEC-0004 in the run record). They are independent only because each ran in a separate context.
- **Blocked command:** one shell command was denied because it needed approval and nobody could answer. I read the same files with the Read tool instead, so nothing was skipped.
  ▸ [record-final] shell …

Status: completed
Run ID: d3076a2c

Run d3076a2c: completed at step record-final
Agent logs: .specify/workflow-state/d3076a2c/agents/
Draft PR: <scratch project>/pull/9
Every intermediate decision is agent-provisional; merging the PR is the only human approval.
Draft PR: reused #9 <scratch project>/pull/9
```

- Verdict: PASS
