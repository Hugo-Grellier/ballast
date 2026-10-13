# Research: Autonomous PR completion policy

Phase 0 for [plan.md](plan.md). Every decision here is agent-provisional; merging the PR is the only human approval. Sources are the current code at `81d39fc` and the documents cited in [spec.md](spec.md).

## R1. Where the completion step runs

- **Decision**: `run.py` runs a new `_complete(run_id, checkpoint_outcome)` step after the Draft PR checkpoint and acceptance packet (`_checkpoint`), and only in an invocation whose `_publish` succeeded. `_publish` leaves the publication (repository, PR number, URL, pushed commit) in an in-process holder keyed by run ID, and `_complete` consumes it. Nothing about it is persisted. If the process dies between publication and completion, nothing happens and the PR stays a Draft.
- **Rationale**: FR-007 requires evaluation after the packet attempt. Today the packet runs in `_checkpoint`, which `_run_autonomous` and `_resume_engine` call in their `finally` blocks after `_finish` → `_publish` (`tools/spec_workflow/run.py:872-876`, `2093-2097`). An in-process hand-off adds no operator-state field, so with no configuration the run record stays byte-identical (FR-013), and a stale "pending" record can never make a later command mark a PR ready.
- **Alternatives considered**: (a) Mark ready inside `autonomy.publish`. That runs before the packet exists, so condition (9) could never hold. (b) Persist a `completion_pending` field in the run record. That changes `run.json` for every run and adds a state that a later command could act on (D-08: only the publication's own invocation evaluates).

## R2. `ballast run publish` retry runs the checkpoint when the outcome is reported

- **Decision**: After a successful `_publish` in `_publish_command`, and only when the run's trusted snapshot has `completion_configured = "ready"`, the retry also runs `_checkpoint(run_id)` (Draft PR checkpoint and packet), then `_complete`. With no key, `draft` or an unknown value, the retry's output stays exactly today's.
- **Rationale**: Today's Autonomous publish retry runs no checkpoint (`run.py:1297-1333`), so no packet would exist for the pushed commit and condition (9) would always fail. FR-007 names the retry as a publication that evaluates eligibility. Adding the checkpoint only when the outcome is reported keeps FR-013.
- **Alternatives considered**: Run the checkpoint after every publish retry. That changes the no-configuration output (FR-013, SC-003). Use the latest recorded `acceptance_packet` event instead. Its head is an earlier commit, so condition (9) fails and the retry could never succeed.

## R3. Policy snapshot fields and narrowing

- **Decision**: `autonomy.parse_policy` recognizes `completion` and `completion_max_severity` (added to `POLICY_KEYS`). When the table sets them, the snapshot gains:
  - `completion_configured`: `ready` or `draft`. An unknown value yields `draft` and the warning ``ignored [autonomous] completion 'X': cannot widen eligibility``.
  - `completion_max_severity`: `low`, `info` or `none`. An unknown value yields `low` and the same warning shape.
  The start adds `completion_flag` when `--completion` is given, and `completion`, the effective value, from one function `completion_policy(configured, flag)`. A flag wider than the configured value refuses the start before any record is written. `--refresh-policy` takes the new `completion_configured` and `completion_max_severity` from the `ballast trust` baseline, keeps the recorded `completion_flag`, and recomputes `completion` with the same function. With no key and no flag, the snapshot has none of these fields, so the run record and the record's policy text are unchanged.
- **Rationale**: FR-003 asks for the effective value in the snapshot, and FR-004 asks that the start flag still narrow after a refresh. That only works if the flag is recorded separately from the configured value. Leaving the keys out when they are unset keeps existing snapshots and the tests that compare them unchanged (FR-013).
- **Alternatives considered**: Always add the keys with defaults. That changes every run record and existing `parse_policy` assertions for no benefit. Store only the effective value. A refresh could not then tell a flag-narrowed `draft` from a configured `draft` (AC-018).

## R4. When the outcome is reported

- **Decision**: The outcome is evaluated, printed and recorded only when the run's snapshot has `completion_configured == "ready"` and the run is an Autonomous (`ballast-autonomous`) run. Otherwise `_complete` returns at once, prints nothing and records nothing. This is PD-0007's reading of FR-009/FR-010/FR-013.
- **Rationale**: This reproduces today's behavior exactly for unconfigured projects, and still reports the AC-016 case, where the flag narrowed a configured `ready`.

## R5. Eligibility as a pure function over operator records

- **Decision**: A new trusted module `tools/spec_workflow/completion.py` exposes `evaluate(inputs) -> list[Reason]`. It is a pure function over a frozen `Inputs` value that the I/O layer collects:

  | # | Condition | Operator record read |
  | --- | --- | --- |
  | 1 | Autonomous at publication | `autonomy.effective_mode(run) == "autonomous"` and `run["workflow"] == "ballast-autonomous"` |
  | 2 | Effective policy `ready` | `run["eligibility"]["policy"]["completion"]` |
  | 3 | Risk R0/R1 | `run["risk"]["level"]` (scope record, raised only by recorders) |
  | 4 | No privileged action | `autonomy.privileged_union(run, decisions)` is empty, authorized or not |
  | 5 | Final acceptance | `autonomy.current(decisions, "final-acceptance")` is not empty |
  | 6 | Spec reconciliation converged | the current `spec-reconciliation` decision's review verdict is `approved` (see R6) |
  | 7 | No open finding above the threshold | findings with disposition `open` or `accepted-provisionally` in `current_decisions`, compared with `completion_max_severity` |
  | 8 | `[checks]` passed on the published tree | `autonomy.read_checks` is a non-empty list, every result exits 0 without timing out, and `run["checked_tree"]` is set (publish already refused any other tree) |
  | 9 | Packet published, every criterion verified | the in-process `PacketOutcome` from this invocation's checkpoint: state `published`, `updated` or `unchanged`; `head` equal to the pushed commit; `verified` ≥ 1 and `failed`, `not_run`, `stale` and `missing` all 0 |
  | 10 | No material provisional change | no current decision has `material: true` |
  | 11 | No block resolved | no human decision of kind `block-resolution` |
  | 12 | PR head is the published commit | one read-back of the PR: `autonomy._pr_problem(...)` is `None` (open draft, right base and head branch) and `head.sha` equals the pushed commit |

  The function returns every failed condition in this order (AC-006). Condition (12) needs one forge read, which the I/O layer makes before calling `evaluate`, so the result stays pure. A failed read is a condition (12) failure with the fixed cause code.
- **Rationale**: Purity makes each condition testable alone (SC-002) without GitHub. Every input comes from operator state, the Git common directory, or a trusted step's in-memory result, and none of them can be written by an agent step (ADR-0004, ADR-0018).
- **Alternatives considered**: Stop at the first failure. The spec requires every failure to be listed. Read `reviews/convergence.md` for condition (6). It is agent-written.

## R6. What "spec reconciliation is CONVERGED" reads

- **Decision**: Condition (6) reads the current `spec-reconciliation` decision's recorded review verdict (`approved`). The literal `- Verdict: CONVERGED` line lives in the agent-written `reviews/convergence.md`, and the trusted `validate-convergence` step (`artifacts.py convergence`) requires it before `final-acceptance` can be recorded (`templates/spec-kit/workflows/autonomous/workflow.yml:338-355`). So conditions (5) and (6) together mean that a trusted validator accepted a CONVERGED verdict and a trusted recorder recorded an approved reconciliation review.
- **Rationale**: This satisfies AC-014. An agent can edit `convergence.md` after the fact, but that cannot change the result.

## R7. Agent-derived values inside operator records

- **Finding (security note)**: Conditions (6), (7) and (10) read decisions that trusted recorders validated and appended, but whose content (verdict, finding severity and disposition, the `material` flag) began as an agent draft. This is the provenance every Autonomous decision already has (ADR-0004). An agent cannot write the log directly, and it cannot lower risk: `raise_risk` only raises. The operator chose these conditions at intake. The merge reviewer still sees every decision in the PR. The plan adds no new trust in agent text: drafts and artifacts written after the recorder ran cannot change the result (AC-014).

## R8. The forge action and its verification

- **Decision**: Mark ready with `gh pr ready <number> --repo <OWNER/NAME>`. The program is resolved and run as `autonomy._gh` and the Draft PR checkpoint do: `draft_pr._resolve` outside working trees, `draft_pr._command` from an empty directory with the hardened environment, and the token variables withheld from agents as today. The completion module calls `draft_pr._command` directly and classifies a failure with `draft_pr._classify`. It records and prints only the fixed cause code (`gh-missing`, `gh-unauthenticated`, `gh-forbidden`, `github-unreachable`, `github-error`, `gh-untrusted`), never `gh` output (Draft PR authority rule). After the call, one more read-back must show `draft: false` and the same `head.sha`. Otherwise the outcome is `unverified` with reason `forge-unverified`: the runner cannot tell whether the PR is still a Draft, so it does not claim one (plan-review F-001).
- **Rationale**: BL-INV-005 (postconditions over exit codes). This is the same pattern as `_create_verified`.
- **Residual race**: GitHub's ready-for-review mutation takes no expected head. A push that lands between the read-back and `gh pr ready` leaves a ready PR whose head is not the published commit. The post-ready read-back detects this and records the outcome `unverified` with `forge-unverified`. The PR stays ready, because converting it back would be a further forge write that the spec does not ask for. Marking ready approves nothing, and branch protection and the human merge still gate the change. This mirrors #17 DEC-0007's accepted body race.
- **Alternatives considered**: `gh api graphql` with `markPullRequestReadyForReview`. This adds a GraphQL call path and gives no stronger guarantee. `gh pr ready --undo` on a post-ready mismatch. This is an extra forge write and widens the R2 surface.

## R9. Ledger record: a new `pr_completion` event kind

- **Decision**: Add a runner-only `pr_completion` kind with fields `outcome` (`ready`, `draft` or `unverified`), `pr_number`, `commit` (`oid`), `reasons?` (an ordered list of fixed reason codes, required for `draft` and `unverified`, exactly `["forge-unverified"]` for `unverified`, and forbidden for `ready`) and `cause?` (a Draft PR `failed-retryable` code, only with `forge-failed` or `pr-unreadable`; plan-review F-005). The ledger has no list type, so add a `labels` value type: a list of 1 to 16 unique `label` strings. The ENUM check is applied per element.
- **Rationale**: The existing `pull_request` event's `outcome` enum describes checkpoint states (`created`, `reused` and so on). Mixing completion outcomes into it would blur two different records and change its validation. Either choice is rejected by an older pinned Ballast reading the stream (a new kind, or a new field in `pull_request`), as ADR-0018 records for `runner-recorded`. With no configuration no such event is written, so an unconfigured stream stays readable by older versions (FR-013).
- **Alternatives considered**: Extend `pull_request` with optional fields. Same compatibility cost, muddier semantics. Store reasons as one joined label. This loses per-reason validation.

## R10. Output line

- **Decision**: One new line, printed right after the `Draft PR:` and `Acceptance packet:` lines: `PR completion: <state> #<number> <url>[: <reason>; <reason>…]`. `<state>` is `ready-for-review`, `draft` or `unverified`. Reasons are fixed wording filled only with validated values (risk level, mode name, severity, privileged-action kinds, PD or HD IDs, counts, cause codes). A ready line adds `; merging stays the only human approval`.
- **Rationale**: The spec says "the Draft PR line" and "the PR line" (FR-009, AC-004). The completion outcome must come after the packet line (R1), so it cannot be the publisher's `Draft PR: <url>` line. A distinct prefix, in the same grammar as the checkpoint line (`draft_pr.format_line`), keeps existing `Draft PR:` parsers and tests exact. This is a wording clarification, not a behavior change. It is listed under Review notes in the plan.

## R11. AC-003 and FR-012 against current status transitions

- **Finding (spec ambiguity, wording only)**: A run is set to `published` before `_complete` runs, and `ballast run publish` refuses a `published` run (`run.py:1319`, `TRANSITIONS["published"] == {"continued"}`). So no publish retry ever reaches a PR this run marked ready. The Draft PR checkpoint (`draft_pr._Checkpoint.decide`/`reuse`), the packet (`packet._publish`) and `ballast run demo` never check the draft state. Only `autonomy._pr_problem`, which is used by publication alone, rejects a non-draft PR.
- **Decision**: No change to `_pr_problem`. FR-012 holds by construction. Tests pin it: a checkpoint after `ready` reuses the PR and makes no `pr ready` call, and a publish retry of the published run refuses as today with no forge call. AC-003's "publish retry … updates that PR" clause is vacuous. The plan lists this for the spec reconciliation step rather than changing behavior.

## R12. `--completion` CLI surface

- **Decision**: `ballast run start --mode autonomous --completion draft|ready`. `_split_mode` takes the flag out. It is refused with a non-autonomous mode ("--completion needs --mode autonomous"), with any other value, and when given twice. In `_start_autonomous`, after `parse_policy` and before `check_eligibility` writes anything, `--completion ready` with `completion_configured` other than `ready` refuses with `--completion ready cannot widen ballast.toml [autonomous] completion (<configured>)`. `resume` and `continue` do not accept the flag: they already refuse unknown options.
- **Rationale**: Fail closed, before any agent step (AC-015). This matches how `--wall-time` is checked.

## R13. Threshold semantics

- **Decision**: Severity rank uses `autonomy.SEVERITIES` (`critical` > `high` > `medium` > `low` > `info`). Threshold `low` allows open `low` and `info`, `info` allows only `info`, and `none` allows none. A finding counts when its disposition is `open` or `accepted-provisionally` in a current (non-superseded) decision, the same set the record's "Open findings" section lists.
- **Rationale**: The default never lets through more than the fix loop does (`artifacts._open_to_fix`). PD-0003.

## R14. Risk recheck against the R2 boundaries

R2 stays. The trusted runner gains a forge write (`gh pr ready`), which changes "what `ballast` executes" and the launcher's trust model (`docs/policies/project/workflow.md`). Agent authority does not change: `mark-ready` stays a never-authorizable kind (`autonomy.NEVER_AUTHORIZED`, ADR-0016), agents still cannot run `gh`, and the policy comes only from protected `ballast.toml` through the start snapshot or a `ballast trust` baseline. No installed-path or ignore rule changes. Nothing new is downloaded.

## R15. Compatibility for projects pinning earlier versions

Projects that pin an earlier Ballast see nothing. After upgrading, with no `completion` key, they get identical output, ledger and run records. Setting `completion` on an older pinned version gives today's "ignored [autonomous] completion: cannot widen eligibility" warning and a Draft PR, so the key is safe to commit before upgrading. A ledger stream holding a `pr_completion` event is rejected by an older pinned version (R9), as with ADR-0018.
