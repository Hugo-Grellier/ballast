# ADR-0018: An Autonomous run records per-criterion checks from the agent-proposed manifest

- Status: proposed (2026-10-07, with the change for [#117](https://github.com/Hugo-Grellier/ballast/issues/117)). Resolved by the driving agent under the operator's standing authority for v1.0 issues (2026-10-05), listed for merge review; merging the PR is the human approval that accepts it.
- Risk: R2 (what Ballast executes).
- Extends: [ADR-0006](0006-review-packet-reads.md), whose rejected alternative "running the manifest's mapped tests from `run-checks`" this decision takes up, and [ADR-0017](0017-deferred-operator-tasks-and-unmapped-criteria.md), which left it to #117.

## Context

The acceptance packet shows a criterion `verified` only from a per-criterion `verification` event bound to the head commit's implementation tree, the spec and the manifest. Only `ballast ledger check` wrote one, so every mapped criterion of an Autonomous PR read `not run` until the operator ran one command per mapped test on a clean checkout of the pushed commit, then `ballast run checkpoint`. The run had already executed the same tests as part of its `[checks]` suites, but those run whole suites and record no criterion.

Running the mapped tests from the trusted runner is a new execution path: the runner executes agent-written test code and records the result as evidence. `ledger check` runs `.venv/bin/python` directly, unconfined, which is acceptable for an operator at a terminal and not for an unattended runner.

## Decision

- **Where.** The Autonomous `run-checks` step (`artifacts.py`), after its `[checks]` commands passed on the tree frozen at the final implementation review, runs each distinct test that a valid `acceptance-evidence.json` maps. `run-checks --feedback`, Chat and human-gated runs run none.
- **Confinement.** Each test runs as `.venv/bin/python -X pycache_prefix=/tmp/... -c <ACCEPTANCE_CHECK> <test> ...` (a passed test must exit with a per-run code the harness reads from stdin before any test code is imported, so an import-time exit is failed; a test name is at most 300 characters; bytecode only from a fresh cache in the sandbox's private /tmp, never an agent-writable `__pycache__`; the test is refused, and recorded failed, unless every module along its name was loaded from an allowed published file of the checkout) through the same bubblewrap argv as the check commands (`confined_argv`, no agent integration and so no login, secret-named variables dropped, credential paths hidden, the host read-only), with one difference: the whole checkout is bound read-only (`writable_checkout=False`), git-ignored outputs included. The test name must match `tests.test_….test_…`, the pattern `ledger check` accepts, and is passed through `shlex.join`, so a manifest cannot add a command.
- **Published tests only.** A test runs only when every file Python could import along its dotted name (each `.py` module and package `__init__.py`) is tracked or unignored and not reached through a symlink, so `git add --all` publishes it; a test in an ignored or missing file would pass locally and be absent at the PR head, so it is listed as not run and records nothing. Other ignored files a test imports stay visible to it, as the run record already notes for `run-checks`.
- **Limits.** At most 100 mapped (AC, test) pairs (`ACCEPTANCE_TESTS`), so at most 100 test runs and 100 recorded results, and a manifest of at most 1 MiB, checked before it is read; more runs none. Each test has the `[checks]` timeout and none runs past the run's remaining wall time; when it runs out, the rest are listed as not run.
- **Evidence.** The step takes `ledger.artifact_digests` before the tests, then, only after the existing tamper and tree checks passed and the digests are unchanged, appends, in one write (all or none), a `runner` `snapshot` and one `verification` per mapped (AC, test) with the new source `runner-recorded`, bound to that snapshot's implementation tree, spec digest and manifest digest. The tree is the one `publish` commits: it refuses a tree that differs from the one that passed `run-checks`, and `git add --all` of that tree has the same implementation fingerprint (`commit_tree`) as the checked worktree, so the evidence is not stale on arrival.
- **Source label.** `runner-recorded` is valid only on a bound criterion `verification`; `ledger record` does not offer it, and an AC verification through `record` is still refused. The ledger report and the packet count it like `operator-attested` for a criterion's state, the report lists `ac_sources`, and the packet and the run record label each such result `runner-recorded`. Gate recovery still needs an `operator-attested` check.
- **Reported, never skipped.** No manifest, an ignored one (the PR head would not carry it), a malformed one, one bound to another spec or AC set, one over the limit, or no `.venv/bin/python` runs nothing and is named in the run record's "Acceptance checks (runner-recorded)" section, as is a refused ledger write, which records nothing; a criterion mapped to `[]` is listed as missing. A failing test is recorded `failed`, not a block: the `[checks]` commands remain the gate.
- **Agents.** An agent step cannot write the ledger (the Git common directory is read-only in its sandbox) or the operator records, and the manifest stays a proposal: it chooses which agent-written tests run, never their result.

## Consequences

- An Autonomous PR's packet shows its mapped criteria `verified` or `failed` without an operator step, labeled as the runner's check of agent-written tests. The merge reviewer still judges whether those tests check the criterion.
- A project without `.venv/bin/python` (one that runs its tests through another launcher) gets no runner evidence, as with `ballast ledger check`.
- A stream holding a `runner-recorded` event is rejected by an older pinned Ballast, as with any unknown value.

## Rejected alternatives

- Running the tests unconfined with `ledger check`'s code path: the runner would execute agent-written code with the operator's credentials.
- Labeling the results `operator-attested` or `runner`: the first claims an operator check that did not happen; the second already marks Chat runs' suite-wide checks and would not tell a reviewer the result came from agent-written tests.
- Running the tests with the writable checkout of the check commands: a test could change the tree; the post-run tree check would catch it, but a read-only bind removes the case.
- Blocking the run on a failed acceptance test: the `[checks]` commands already gate the run; a failed criterion is shown to the merge reviewer instead.
- Running a subset when over the limit: partial evidence reads as complete; the record names the refusal instead.
