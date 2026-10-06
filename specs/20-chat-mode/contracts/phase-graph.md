# Contract: Chat phase graph

The trusted runner evaluates each entry condition and precondition **when it is requested**, and records each evaluation as a `check` event ([data-model.md](../data-model.md)). Check names are the existing `artifacts.py` checks. A Chat run evaluates them with the run's feature and operator record. "Current" means the human decision's bound digest equals the artifact's digest now.

Every phase entry, and the `implementation` and `final` preconditions, also run `open-write-scope`: it fails while a path that an earlier step changed outside its write scope still holds what that step left ([DEC-0003](../decisions.md)).

Identifiers reuse `ballast-feature` step and gate IDs (`templates/spec-kit/workflows/feature/workflow.yml`), so the ledger reports both kinds of run against one definition.

## Phases

| Phase | `ballast-feature` step | Command (Claude `/`, Codex `$`) | Entry condition | Postcondition at close | Write scope |
| --- | --- | --- | --- | --- | --- |
| `specify` | `specify` | `speckit-specify` with the stored idea and `SPECIFY_FEATURE_DIRECTORY` | `scope` approval current | `spec` | `specs/<f>/` |
| `clarify` | `clarify` | `speckit-clarify` | `spec` | `clarified-spec` | `specs/<f>/` |
| `plan` | `plan` | `speckit-plan` | `intent` (registered human block, current digest) and no later `reject intent` | `plan` | `specs/<f>/` |
| `tasks` | `tasks` | `speckit-tasks` | `plan`, `plan` approval current | `tasks` | `specs/<f>/` |
| `analyze` | `analyze` | `speckit-analyze` | `tasks` | `tasks` | `specs/<f>/` |
| `implement` | `implement` | `speckit-intent-implement` | `tasks`, `tasks` approval current, baseline recorded | `implementation` (against the operator-state baseline) | worktree minus protected inputs |
| `reconcile-intent` | `reconcile-intent` | `speckit-intent-decisions` | `implementation`, `implementation` approval current | `decisions` (structure only) | worktree minus protected inputs |
| `converge` | `converge` | `speckit-converge` | `implementation`, `implementation` approval current, then `decisions` with every resolution humanly confirmed | `plan`, `tasks` (no pending task), `decisions` | worktree minus protected inputs |
| `review` | review handoff of the matching gate | the matching shipped review skill (see below) | the kind's artifact check | report exists at the kind's path, changed in this step, last `- Verdict:` in the enum | `specs/<f>/reviews/` |

The checks are cumulative, as in `ballast-feature`: `plan` re-verifies `intent`, `tasks` re-verifies `plan`, and so on.

Review kinds:

| Kind | Entry | Report path | Skill named in the prompt |
| --- | --- | --- | --- |
| `plan` | `plan` | `reviews/plan-review.md` | `ballast-engineering-review` (plan scope) |
| `implementation` | `implementation` | `reviews/implementation-review.md` | `ballast-engineering-review` |
| `security` | `implementation` | `reviews/security-review.md` | `ballast-security-review` |
| `test` | `implementation` | `reviews/test-review.md` | `ballast-test-review` |
| `documentation` | `implementation` | `reviews/documentation-review.md` | `ballast-documentation-review` |
| `spec-reconciliation` | `decisions` with confirmed resolutions, `tasks` with no pending task | `reviews/convergence.md` | `ballast-spec-reconciliation` |

Verdict enum: `approved`, `changes-requested` (plan and implementation kinds), `CONVERGED`, `PARTIAL`, `FAILED` (spec reconciliation). The verdict is evidence only; no gate opens on it.

## Gates

| Gate | `ballast-feature` gate | Precondition for `approve` | Bound digest |
| --- | --- | --- | --- |
| `scope` | `scope-gate` | Run active, feature directory matches the pinned Issue | Issue and feature |
| `intent` | `approve-intent` | `clarified-spec` | spec digest |
| `plan` | `review-plan` | `plan` | `plan.md` |
| `tasks` | `review-tasks` | `tasks`, `intent` and `plan` approvals current | `tasks.md` |
| `implementation` | `review-implementation` | `implementation`, `tasks` approval current | tree |
| `spec-reconciliation` | `spec-reconciliation` | `convergence` (`- Verdict: CONVERGED`) | `reviews/convergence.md` |
| `final` | `final-acceptance` | `convergence`, `spec-reconciliation` approval current, project checks passed or `unavailable` for the current tree, every earlier gate approval current and no open write-scope violation ([DEC-0002](../decisions.md), [DEC-0003](../decisions.md)) | tree, `reviews/` included |

`reject` has the same precondition. A rejection keeps the gate closed until a later approval at a current digest.

## Allowed next actions

`status` and each step's last lines list, in this order:

1. every phase whose entry condition passes now;
2. every gate whose precondition passes and that is not approved at a current digest;
3. `checks` when `implementation` passes;
4. `publish` when `final` is current and its precondition still passes ([DEC-0002](../decisions.md));
5. `mode`.

A phase or gate missing from the list is refused when requested, and the refusal names the first failing check and its `E-NNNN`.
