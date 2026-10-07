# Data Model: Chat mode

Entities from the spec's Key Entities, with where each one is stored and who may write it. "Operator state" means `$XDG_STATE_HOME/ballast/<checkout-key>/runs/<run>/` (`autonomy.run_dir`). While a step is active the launcher refuses every `ballast` command. What else bounds an agent depends on the step's driver:

- **Interactive Chat steps** run under bwrap, which hides operator state from the step.
- **Headless steps of a run switched to human-gated** (D-5) run through `agent.py` without bwrap. They are bound only by the headless permission model: Claude `acceptEdits` with no prompts and the narrow Bash allow list, Codex `workspace-write` with no extra writable roots. The human-gated intent registration under `state_dir/approvals` (#29) already relies on this same bound.

The hash chain detects a broken or edited log, but it does not authenticate who wrote a line. Every log below is append-only. Logs marked "chained" carry `prev` = SHA-256 of the previous raw line and are read with `autonomy.read_log`.

## Chat run (`run.json`)

It extends the existing operator run record (`autonomy.new_run` / `validate_run`).

| Field | Type | Rule |
| --- | --- | --- |
| `version` | int | `1`, unchanged. |
| `run_id` | string | `[A-Za-z0-9_-]{1,64}`; 8 hex characters from `uuid4` at start. |
| `feature` | string | `specs/<N>-<slug>`, matching `autonomy.FEATURE`; fixed for the run. |
| `issue` | int | Equals `<N>`. |
| `workflow` | string | New value `ballast-chat` added to `WORKFLOWS`. |
| `mode_history` | list | See "Mode change". The effective mode is the last entry: `chat` or `human-gated`. |
| `status` | string | `active`, `completed` (final approval current) or `published`. Existing `TRANSITIONS`, plus `completed → active` and `published → active` when a later change makes final approval stale; publication then needs a new final approval. |
| `integration` | string | `claude` or `codex`: the authoring integration chosen at start. A step may override it; each step records its own. |
| `review_integration` | string | The other provider when its CLI is on `PATH` and confinable, else the same. |
| `cross_provider` | bool | Existing field, same rule. |
| `continues` | string or null | The source run ID for a continuation from Autonomous or from a `ballast-feature` run. |
| `start_head` | string | Commit at start (publication diff base, as Autonomous `head`). |
| `baseline` | object or null | `{tree, at, approval: HD-id}`, written when `tasks` is approved. It is the trusted implementation baseline, kept in operator state. |
| `active_step` | object or null | `{step, phase, unit, started_at}` from step start until step close. Non-null means a step is in progress. |
| `last_manifest` | string | SHA-256 of the latest stored tree manifest (`manifests/<digest>.json`). |
| `started_at` | string | UTC ISO timestamp. |

No `risk`, `eligibility` or `limits` (Chat has no wall-time or attempt limit; Assumptions). The `validate_run` rule that requires them stays scoped to `ballast-autonomous`.

## Chat step (`steps.jsonl`)

Two entries per step, both written by the trusted runner: `start` before the agent starts, and `close` after the scope is confirmed gone and the checks have run. A `start` without a `close` is an unfinished step, closed as `interrupted` by the next invocation (R10).

| Field | Entry | Rule |
| --- | --- | --- |
| `step` | both | `<stamp>-<phase>-<integration>`; also names the log directory and the scope unit. |
| `entry` | both | `start` or `close`. |
| `phase` | both | One of the phase-graph phases ([contracts/phase-graph.md](contracts/phase-graph.md)). |
| `review_kind` | both | For `review` only. |
| `driver` | start | `interactive` (Chat) or `headless` (human-gated, through `agent.py`). |
| `integration`, `model`, `role` | start | Provider, the `--model` Ballast passed or `unreported`, and `author` or `reviewer`. |
| `tree_before` | start | Manifest digest before the agent starts. |
| `started_at` / `ended_at` | start / close | UTC ISO timestamps. |
| `outcome` | close | `completed`, `failed`, `interrupted` or `tampered`. A step `refused` before any agent ran has no entries here; it is an `events.jsonl` refusal. |
| `exit_code` | close | The agent CLI's exit, or `null` when it was interrupted. |
| `scope_stopped` | close | `true` only when systemd confirmed the unit gone and the subreaper reaped every descendant. |
| `protected_changes` | close | Paths; non-empty means `tampered` and the tamper marker is written. |
| `write_scope_violations` | close | Paths outside the phase's write scope. |
| `postcondition` | close | `E-NNNN` IDs of the check events run at close. |
| `tree_after` | close | Manifest digest after the step. |
| `log` | close | `.specify/workflow-state/<run>/agents/<step>/`, local only. |
| `late_close` | close | `true` when a later invocation closed a step whose wrapper died (step-runner lifecycle step 2), else `false`. |
| `attribution` | close | `"uncertain"` for a late close: every change since `tree_before` is attributed to the step, including any operator edit made after the wrapper died. Otherwise `"step"`. |
| `protected_compared` | close | `false` for a late close: the protected-state snapshot lived only in the dead wrapper's memory. Otherwise `true`. |

## Check result, review, refusal and out-of-step change (`events.jsonl`, chained, `E-NNNN`)

| Kind | Fields | Written when |
| --- | --- | --- |
| `check` | `check` (the `artifacts.py` name: `spec`, `clarified-spec`, `intent`, `plan`, `tasks`, `implementation`, `decisions`, `convergence`, `write-scope`, `project-checks`), `purpose` (`entry`, `postcondition`, `gate`, `operator`), `passed`, `detail` (≤ 2,000 characters, the `ContractError` text), `digests` (artifact digests the check read), `tree`, `step` or null | Every evaluation by the runner. Failures are kept forever, and nothing overwrites them (FR-010). |
| `project-checks` | `results` (`[{command, exit, seconds, timed_out, provenance: "runner"}]`), `unavailable` (bool), `tree`, `protected_changes` (a non-empty list never counts as passing, #66) | `ballast run checks`. |
| `review` | `kind`, `step`, `reviewer` (`{provider, model, role}`), `cross_provider`, `report` (path), `report_digest`, `verdict` (enum) | Close of a `review` step whose report exists and changed in that step. |
| `out-of-step-change` | `actor: "operator"` (or `"sync"` for what a branch synchronization brought in, #66), `paths` (sorted, ≤ 500, then a count), `from_manifest`, `to_manifest`, `stale` (HD IDs whose digests no longer match) | The first invocation after a change made between steps (FR-011). |
| `refusal` | `command`, `phase` or `gate`, `reason`, `failed_check` (`E-NNNN`) or null | A refused `step`, `approve`, `publish` or `mode`, when a run record exists. |
| `sync` | `outcome`, `cause`, `ledger_event` | Each `step`'s branch check. A pointer only; the full event stays in the ledger. |

## Human decision (`human-decisions.jsonl`, chained, `HD-NNNN`)

It extends `autonomy.HUMAN_DECISION_KINDS`, which today holds `mode-change`, `block-resolution` and `merge-feedback`.

| Kind | Extra fields | Rule |
| --- | --- | --- |
| `gate-approval` | `gate`, `artifact`, `digest`, `supersedes_provisional` (PD IDs of a continued Autonomous source, or `[]`) | Only through `approve`, with no active step and TTY confirmation. Current while `digest` matches. |
| `gate-rejection` | `gate`, `artifact`, `digest`, `ref` (reason) | Through `reject`. The gate stays closed until a later `gate-approval` at a current digest. |
| `decision-resolution` | `decision` (`DEC-NNNN`), `digest` (normalized text of its Resolution section) | Through `resolve`. Current while the resolution text matches. |
| `mode-change` | `from`, `to`, `ref` (reason) | Through `mode` or `continue --mode chat`. |

Common fields, unchanged: `id`, `prev`, `at`, `by: "operator"`, `kind`, `ref`.

**Gate digest binding**:

| Gate | Artifact | Digest |
| --- | --- | --- |
| `scope` | Issue `#N` and the feature directory | SHA-256 of `"<N>\n<feature>"` |
| `intent` | `spec.md` | `artifacts.spec_digest`; also the registered block in `intent.md` |
| `plan` | `plan.md` | SHA-256 of normalized text |
| `tasks` | `tasks.md` | SHA-256 of normalized text, with every task checkbox read as unchecked: implementing marks tasks done without making the tasks approval stale, while a changed or added task does |
| `implementation` | worktree | tree digest (`autonomy.tree_digest`, excluding `specs/<f>/reviews/`) |
| `spec-reconciliation` | `reviews/convergence.md` | SHA-256 of normalized text |
| `final` | worktree | tree digest including `specs/<f>/reviews/` ([DEC-0002](decisions.md)), so a review changed after final approval makes it stale |

## Mode change (`run.json.mode_history`)

| Field | Rule |
| --- | --- |
| `mode` | `human-gated`, `autonomous` or `chat` (`MODES` gains `chat`). |
| `action` | `start` (first entry only), `lower` (`autonomous → human-gated` or `autonomous → chat`), `switch` (`chat ⇄ human-gated` only). |
| `at`, `by` | UTC timestamp; `operator` only. |
| `reason`, `decision_id` | The operator's reason and the `mode-change` or continuation HD. |

`_validate_mode_history` and `change_mode` refuse every other transition. Any move to `autonomous` after `start` is refused ("never raised"). A Chat continuation's first entry is `{mode: chat, action: start}` and its `continues` field links the source. The source records its own `lower`.

## Out-of-step change (manifest)

`manifests/<sha256>.json` in operator state is `{path: sha256}` for every tracked and unignored file. It is computed operator-side with hooks, fsmonitor and filter drivers disabled and `hash-object --no-filters`. Content-addressed, deduplicated, and never trusted from the checkout.

## Handoff summary (derived, never stored)

Built by `chat.summary(run)` from `run.json`, `steps.jsonl`, `events.jsonl`, `human-decisions.jsonl` and, for a continuation, the source's decision log. Fields, in display order:

1. Mode (with history), run ID, Issue, feature directory, branch (from the pin), status, and the source run when continued.
2. Completed steps: phase, provider/model/role, start, end, outcome.
3. Failed checks: the latest result per check that is still failing, with its `E-NNNN` and detail.
4. Gates: approved (current), approved (stale, with the change that made it stale), rejected, pending.
5. Open decisions: `DEC-NNNN` proposals without a current human resolution, and agent-provisional decisions carried from an Autonomous source and not yet superseded.
6. Out-of-step changes since the last step.
7. Allowed next actions: each phase whose entry condition passes, each gate whose precondition passes, plus `checks`, `mode`, `publish` (when allowed) and `stop`.

It never reads a conversation log (FR-019).

## State transitions

```text
start --mode chat ─▶ active ──step/approve/...──▶ active
                       │  approve final (current)
                       ▼
                   completed ──publish──▶ published
                       │ a later change makes final stale
                       ▼
                     active
active|completed ──mode chat⇄human-gated──▶ (same status, mode_history += switch)
```

Stopping a Chat run between steps needs no command and changes no status: the run stays `active` with no active step until the operator's next invocation (FR-018).

A step: `start` entry (active_step set, marker written) → `close` entry (`completed`, `failed`, `interrupted` or `tampered`; marker removed unless the scope could not be confirmed stopped or the step was tampered).
