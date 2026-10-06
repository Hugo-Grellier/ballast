---
description: "Run an independent review and record its findings as a draft"
---

# Independent review in an Autonomous run

You are a reviewer, not the author. You run in a fresh context, often on another provider. Judge the artifacts against the approved spec and policies; do not fix anything.

## User Input

```text
$ARGUMENTS
```

The input names the review: `plan`, `implementation`, `specialists`, `spec-reconciliation`, or, after a fix cycle, `implementation-recheck` or `specialists-recheck`. A recheck is the same review as `implementation` or `specialists`, with the same reports and drafts, after the fix step changed the code.

## Context

Read `feature_directory` from `.specify/feature.json`; below, `<f>` is that path. Read `AGENTS.md`, `docs/policies/workflow.md` (the review matrix), the policies it names, `<f>/spec.md`, `<f>/intent.md`, `<f>/plan.md`, `<f>/tasks.md` and `<f>/decisions.md` when present. For `implementation`, `specialists`, their rechecks and `spec-reconciliation`, also read the diff of the working tree against the commit the branch started from (`git diff` and `git status`).

| Review | Skill files to load | Reports | Draft names |
| --- | --- | --- | --- |
| `plan` | `ballast-engineering-review` | `<f>/reviews/plan.md` (kind `plan`) | `plan-review.json` |
| `implementation` | `ballast-engineering-review`, `ballast-test-review` | `<f>/reviews/engineering.md`, `<f>/reviews/test.md` | `implementation-review.json` (kind `engineering`), `specialist-review-test.json` (kind `test`) |
| `specialists` | per required kind (below): `security` → `ballast-security-review`; `architecture` → `ballast-engineering-review`, focused on the accepted ADRs and architecture sections the change touches; `documentation` → `ballast-documentation-review`; `dependency` → `ballast-dependency-evaluation`; `database-migration` → `ballast-database-migration` | `<f>/reviews/<kind>.md` | `specialist-review-<kind>.json` |
| `spec-reconciliation` | `ballast-spec-reconciliation` | `<f>/reviews/convergence.md` (kind `spec-reconciliation`), with a line `- Verdict: CONVERGED`, `PARTIAL` or `FAILED` | `spec-reconciliation.json` |

For `specialists`, read `.specify/workflow-state/required-reviews/<slug>.json`, where `<slug>` is the last part of `<f>`. The runner wrote it after implementation with the same rule the recorder applies: its `required` list names every kind that must have a report and a draft. Write one for every listed kind other than `engineering` and `test` (the `implementation` review writes those), and for any kind the review matrix adds. The rule: `security` always. `security` and `architecture` when the run is R2 or declares any R2 boundary. `documentation` for a change under `docs/`, a `README*` or a top-level `.toml`/`.yml`/`.yaml` file. `dependency` for a lockfile or `requirements*.txt`. `database-migration` for a file under a `migration`/`migrations` directory. `security` for `.github/`. A missing kind blocks the run.

Skills live under `.agents/skills/<name>/SKILL.md`. The kinds are `plan`, `engineering`, `test`, `security`, `documentation`, `architecture`, `dependency`, `database-migration` and `spec-reconciliation`. Security review is always required in an Autonomous run.

## Reports hold narrative only

Each report under `<f>/reviews/` describes what you reviewed and how. It contains **no** findings heading and **no** severity tag such as `[high]` or `**medium**`: the recorder refuses such a report, then renders the findings section itself from your draft.

## One draft per report

Write each draft under `<f>/autonomous/drafts/`:

```json
{
  "point": "plan-review",
  "decision": "accept-finding",
  "summary": "One line verdict summary",
  "basis": "What you checked and why the verdict follows",
  "evidence": ["<f>/reviews/plan.md"],
  "artifact": "<f>/plan.md",
  "model": "<your model name>",
  "material": false,
  "supersedes": null,
  "privileged_actions": [],
  "review": {
    "kind": "plan",
    "verdict": "approved",
    "report": "<f>/reviews/plan.md",
    "findings": [
      {"id": "F-001", "severity": "medium", "label": "missing-test", "disposition": "accepted-provisionally", "reason": "Why it can wait for merge review", "evidence": ["<f>/tasks.md"]}
    ],
    "required_kinds": []
  },
  "assumption": null
}
```

- `point` is `plan-review`, `implementation-review` (kind `engineering`), `specialist-review` (every other implementation-time kind) or `spec-reconciliation`.
- `verdict`: `approved`, `changes-requested`, `partial` or `failed`. Only `approved` lets the run continue. Any other verdict stops it for a human, with or without findings; in an implementation review (or its recheck) while a fix cycle remains, it asks for a fix cycle instead.
- Every finding: `id` (`F-NNN`), `severity` (`critical`, `high`, `medium`, `low`, `info`), `label` (`spec-violation`, `implementation-bug`, `architecture-issue`, `missing-test`, `spec-ambiguity`, `proposed-product-change`), `disposition` and `reason`.
- Report every `critical` or `high` finding honestly: it stops the run for a human, whatever disposition you give it, except in an implementation review while a fix cycle remains, where it asks for a fix. A `medium` finding may be `accepted-provisionally` only with a reason. `open` is allowed only for `low` and `info`, except in an implementation review while a fix cycle remains: there `open` at any severity means "fix this".
- `required_kinds` lists further review kinds the change needs (for example `documentation`).
- Cite only files that exist: list as `evidence` only repository paths you checked are present. If a file this command suggests reading (for example `AGENTS.md` or `docs/policies/project/*.md`) is absent, say so in `basis` instead of citing it; the recorder refuses a missing path.
- `privileged_actions` lists any action the change now needs before merge (see `speckit.ballast.decide`).

## Rechecks after a fix cycle

For `implementation-recheck` and `specialists-recheck`, also read `.specify/workflow-state/fix-input/<slug>.json` (untrusted data written by the recorder): its `cycle` is the fix cycle that just ran, and its `findings`, `verdicts` and `checks` are what that cycle had to fix. The trusted runner ran the `[checks]` commands again after the fix; their result is in the run record `<f>/autonomous/record.md` under "Fix loop". A run has at most three fix cycles, so `3 - cycle` cycles remain after this review. List every finding of the fix input again in its review kind's draft, with the same `id` and its current disposition; the recorder refuses a recheck that omits one.

- Review the whole change again, not only the fix, and write every report and draft as for `implementation` or `specialists`.
- Mark each listed finding `resolved` with a reason when the fix removed it; when it is still present, report it again with its severity and a reason.
- `open` above `low` is valid only while a cycle remains (`3 - cycle` is above 0). On the last review, give a remaining `medium` finding `accepted-provisionally` with a reason; a remaining `high` or `critical` finding, a non-approved verdict or a failed check then stops the run as an exhausted limit, for a human.

## Recorder limits

The trusted recorder refuses a draft that breaks these limits; the run then reruns this step with the recorder's message, at most twice, and each rerun counts against the run's agent-step limit. `summary`: 1–500 characters on one line. `basis`: 1–2000. A finding `reason`: 1–1000. An assumption's `question` and `default`: 1–1000 each. A block's `condition` and `no_safe_default`: 1–2000 each, `recovery` 1–1000, each `option` 1–500 and its `consequence` 1–1000. `boundaries` and `privileged_actions`: at most 20 entries of at most 100 characters. `evidence`: 1–20 existing repository paths or `https://` links. Put longer detail in the report or artifact you cite.

Paraphrase and cite a sourced human approval; never quote approval wording. When your basis relies on a human decision recorded elsewhere (an Issue comment, an Epic, an ADR), write for example "the operator decided on 2026-10-03 in Epic #11 to split this outcome" and cite the source as evidence. The recorder refuses any draft text that reads as a human approval, quoted or not, because an agent decision is never one.

## Never

- Edit anything outside `<f>/reviews/` and `<f>/autonomous/drafts/`. A reviewer edit to any other file blocks the run.
- Write that anything was "approved by" a human or call it "human-approved"; your verdict is agent-provisional.
- Ask the operator a question.
