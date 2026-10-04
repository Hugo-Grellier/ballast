# Contract: Draft PR merge-review summary

`run.py` renders the PR body deterministically from `run.json`, `decisions.jsonl` and `block.json` (none at publish). The same text, minus the PR-only header, is `specs/<f>/autonomous/record.md`. The body is plain Markdown and links only committed artifacts and the Issue. It never includes agent logs (spec assumption).

## Required sections, in order

1. **Header**: `Autonomous run <run-id> for #<issue> — all intermediate decisions are agent-provisional. Merging this PR is the only human approval.` (FR-014, FR-027)
2. **Mode and risk**: the mode history (each entry with time and actor), the risk level and its history, and the limits used (FR-025, AC-006).
3. **R2 notice**, only when risk is R2: `This is an R2 change. It was made without any prior human approval; the pre-change approval was agent-provisional (PD-NNNN).` It is followed by the list of R2 boundaries touched (FR-026, AC-025).
4. **Material provisional changes**: every PD with `material: true`, or an explicit `None` (FR-018).
5. **Provisional decisions**: a table with one row per PD in log order. Columns: ID, point, decision, summary, decided by (`provider/model`, role), artifact path and short digest, evidence links, superseded-by. Superseded rows stay listed (SC-002, SC-006).
6. **Reviews**: kind, verdict, reviewer `provider/model`, `cross-provider: yes|no`, and a report link. A single-provider run adds `Reduced independence: reviews used the authoring provider.` (spec edge case).
7. **Open findings**: every finding of `medium` or lower with disposition `accepted-provisionally` or `open`, with its reason.
8. **Checks**: first the `run-checks` results (`runner` provenance: command, exit status, duration), then any agent-reported checks, with their provenance label and the decision that reports them. Checks that were declared unavailable or skipped are listed explicitly. The section ends with `CI results appear on this PR.`
9. **Footer**: `Closes #<issue>` is not used. The body uses `Refs #<issue>`, so merging never closes the Issue as a side effect beyond the human's choice.

## Wording rules (tested)

- Agent-written `summary` and `basis` text is rendered escaped inside quoted blocks: HTML comments, `<!-- workflow-* -->` markers and `@mentions` are stripped or neutralized. A draft that contains a workflow marker is refused by the recorder.

- Each decision row contains `agent-provisional`.
- The body never matches `(?i)\b(human[- ]approved|approved by (the )?(human|operator|user))\b`, except the fixed phrase in the header, which states that merge is the only human approval (AC-007, SC-003).

## Size

If the body exceeds 60,000 characters, section 5 keeps ID, point and summary only and links `record.md` for the full rows. The PR still lists every decision (SC-006).
