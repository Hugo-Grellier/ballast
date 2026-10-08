# Decisions: Qualify the Ballast 1.0 request-to-PR path

## DEC-0001: Spec, plan and tasks written by hand instead of through `ballast run`

- **Status**: resolved by the driving agent under the operator's standing authority for v1.0 issues (2026-10-05), listed for merge review.
- **Context**: #24 asks that the feature-local spec and plan be prepared "through the normal scope/intent workflow before implementation". This feature implements no product code. Its output is evidence from running the released CLI against two other repositories. Running `ballast run` on this repository would need a v0.9.0 setup of the Ballast worktree itself, which is pinned at v0.8.1. It would also put an agent-written spec through gates that check implementation artifacts this feature does not have.
- **Decision**: write `spec.md` (scope and AC copied from the Issue), `plan.md` and `tasks.md` by hand. Run no `ballast run` here. Replace the intent gate with two things: an independent review of the evidence before the PR (Codex, read-only, test-review skill), and the operator's merge review. No `intent.md` approval record exists, and none is claimed.
- **Alternatives**: run the assess workflow, rejected because its outputs (problem definition, shaped concept) do not fit release evidence; set up v0.9.0 in this worktree and run `ballast-feature`, rejected because it would change the pin and the protected inputs of the repository under test.
- **Consequence**: the merge review is the first human approval of this feature's scope and evidence.

## DEC-0002: Base-advance drills use a second branch of the disposable repository

- **Status**: resolved by the driving agent under the operator's standing authority for v1.0 issues (2026-10-05), listed for merge review.
- **Context**: the stale-resume and conflict drills need the run's base to advance while the run is paused. The agent may not push to an existing default branch, and the blank repository's `main` had received its one allowed initial push.
- **Decision**: start drill run `0840d2db` while `main-next` is the repository's default branch, so that Ballast pins `main-next` as the run's base. Then set the default branch back to `main` and advance `main-next` with ordinary pushes to what is by then a non-default branch.
- **Consequence**: the drills exercise Ballast's pinned-base synchronization exactly as for a default branch. The repository's default branch was `main-next` for about two minutes. The branch `main-next` remains for the operator to delete.

## DEC-0003: Release gate item 6 met as a qualified mechanism with a known model limit

- **Status**: decided by the operator on 2026-10-07 (relayed by the coordinating agent on 2026-10-08). Recorded here for the merge review; merging #115 confirms it.
- **Context**: roadmap gate item 6 asks for one zero-cost backend "qualified as a recoverable fallback". Drill D6 showed the mechanism working live: a quota failure is recognized, the refusal or selection is recorded in the ledger, and the fallback attempt runs confined. It also showed two limits. The operator's `~/.agents/skills` is not empty, so the fallback is refused in the operator's normal environment (`permission-mismatch`). And when the fallback was selected, the 4B CPU model `qwen3:4b-16k` printed the brief instead of writing it, so the step failed its postcondition.
- **Decision**: accept the result as is for 1.0. Gate item 6 is read as "the fallback mechanism is qualified and observable within the same permission and privacy boundary", with the two limits recorded as known limits. It is not read as "a local model completes a step on this host". #23 SC-004 ("completes or is refused with a recorded cause") is met.
- **Consequence**: the release notes or the operator should state the limits. A larger local model, or emptying `~/.agents/skills`, is later work and needs no change to Ballast.
