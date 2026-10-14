# Contract: `ballast` command surface for agent sessions and operators

Covers FR-005 to FR-012, FR-015 to FR-017, and AC-007 to AC-028. The rationale is in [research R7 to R14](../research.md#r7-who-did-it-operator-at-a-terminal-or-a-relaying-agent-session-fr-010-fr-011).

## Agent command matrix

"Agent session" means the operator's own Claude Code or Codex session, outside any `ballast run` step. An agent inside a step can run no `ballast` command (the `in-progress` marker; defence in depth: `BALLAST_AGENT_STEP`).

| Command | Agent session | Recorded actor | Human-gated run | Chat run | Autonomous run |
| --- | --- | --- | --- | --- | --- |
| `ballast setup`, `ballast intake`, `ballast run status` | may run | none | yes | yes | yes |
| `ballast run start` (human-gated), `ballast run resume` (human-gated) | may run, with `--relayed-by` | none: a human-gated run has no operator run record; `--relayed-by` is validated, and its engine gates stay terminal-only (plan-review F-002) | yes | n/a | n/a |
| `ballast run start --mode chat` | may run, with `--relayed-by` | relayed mode start | n/a | yes | n/a |
| `ballast run start --mode autonomous` | relays after a yes in chat, with `--relayed-by` | relayed mode start | n/a | n/a | yes, when eligible |
| `ballast run resume` (block carries no decision) | may run, with `--relayed-by` | relayed block resolution | see above | n/a (Chat continues with `step`) | yes |
| `ballast run resume` (block carries a decision) | relays after the operator's answer in chat, with `--relayed-by` and `--ref` | relayed block resolution, with the ref | see above | n/a | yes |
| `ballast run continue` (Autonomous source only: stopped, completed or published) | relays with `--relayed-by` and `--ref` (required for every category today) | relayed block resolution or mode change, with the ref | n/a | n/a | yes |
| `ballast run step RUN PHASE --headless` | may run | none (step records) | n/a | yes | n/a |
| `ballast run step RUN PHASE` (interactive) | no terminal: refused | none | n/a | operator | n/a |
| `ballast run publish` | may run | none | n/a | yes, after a current final approval | runner publishes |
| `ballast run approve RUN GATE... \| --through GATE` | relays after a yes in chat, with `--relayed-by` | relayed gate approval | **refused** | yes | **refused** |
| `ballast run reject`, `ballast run resolve`, `ballast run mode` | **refused** (terminal only) | operator | operator | operator | n/a |
| `ballast trust` | may run outside a step, on a checkout the session set up; refused inside a step (the `in-progress` marker, and `BALLAST_AGENT_STEP`) (D-09) | none (trust provenance `source: trust`, as today) | | | |
| `ballast discard-runs` | may run | none | | | |
| `ballast ledger ...` | may run | as today | | | |

A command that records a decision with neither a terminal nor `--relayed-by` is refused before anything is written:

```text
ballast: refusing: without a terminal, name the relaying agent session with --relayed-by SESSION; nothing was recorded
```

## `--relayed-by SESSION`

- Accepted by `run start`, `resume`, `continue` and `approve`. Refused by every other command (`--relayed-by is not accepted by COMMAND`).
- `SESSION` matches `[A-Za-z0-9][A-Za-z0-9._:-]{0,79}`, for example `claude-code:5f0c2a`. It is refused when it matches the human-approval wording guard.
- Where the matrix refuses a relay:
  - Human-gated run: `ballast: refusing: a human-gated run takes approvals only from the operator at a terminal; nothing was recorded` (AC-011).
  - Autonomous run: `ballast: refusing: an Autonomous run has no human gate before merge; nothing was recorded` (AC-012).
  - A decision-carrying block without `--ref`: `ballast: refusing: the CATEGORY block carries a decision; relay it only with --ref naming the operator's answer; nothing was recorded` (AC-028).

## Relayed `resume` and `continue` by block category

Operator decision D-08 (Issue #147). The category is the `block.category` of the stopped run.

| Block category | Carries a decision | Relayed `resume` or `continue` |
| --- | --- | --- |
| `upstream-sync`, `interrupted` (including a usage limit), `postcondition` | no | `--relayed-by` only; the agent session need not ask |
| `decision`, `contradiction`, `review-finding`, `limit`, `ineligible` | yes | `--relayed-by` and `--ref TEXT` naming the operator's in-chat answer |
| `tamper`, `unfinished-step`, `permission`, `forge`, `credential`, any later category | yes (fail closed, agent inference) | same as above |

- The decision-free set is data in `actor.py`; every other category needs `--ref`.
- The `ref` passes the `HUMAN_APPROVAL` wording guard. It names the answer (for example `Issue #147 comment, option 2`) and never quotes approval words.
- `continue` takes only an Autonomous source and already requires `--ref` for every category, so D-08 adds a requirement to Autonomous `resume` only. A relayed `continue` without `--ref` is refused by today's argument rule; the test asserts that text, not the D-08 one (plan-review F-003). `continue --mode chat` and `continue --mode human-gated` follow the same rule.
- Today's preconditions still apply first: `tamper` and `unfinished-step` cannot resume in Autonomous, and `limit` is never raised by resume.

## Batch approval

```text
ballast run approve RUN GATE [GATE ...] [--relayed-by SESSION]
ballast run approve RUN --through GATE [--relayed-by SESSION]
```

- Gates are named in the order scope, intent, plan, tasks, implementation, spec-reconciliation, final, with no duplicates. `--through` and explicit gates are mutually exclusive.
- At a terminal it prints one block, then reads one line:

  ```text
  Approving 4 decisions in run RUN:
    scope    .specify/feature.json                     sha256:…
    intent   specs/N-slug/spec.md                      sha256:…
    plan     specs/N-slug/plan.md                      sha256:…
    tasks    specs/N-slug/tasks.md                     sha256:…
  Type `approve scope intent plan tasks` to confirm:
  ```

- The command records all gates or none. It refuses, recording nothing, with `GATE is not pending`, `GATE: <precondition failure>`, `the typed text did not match`, `an agent step is active`, or a changed digest between display and record.
- Relayed: no prompt. The same validation runs, and one relayed `gate-approval` is written per gate.
- A single-gate `approve RUN GATE` keeps today's prompt text, `approve GATE`.

## Headless Chat step

```text
ballast run step RUN PHASE --headless [--kind KIND]
```

The step runs under Autonomous confinement (bwrap, systemd scope, confined allow and deny lists, self-test). A missing `bwrap` refuses, as Autonomous start does. The phase-graph preconditions are unchanged, so the step runs only when its upstream approvals are current. Afterwards it prints the run's next pending gates and `ballast run approve RUN --through GATE`. Without `--headless` and without a terminal:

```text
ballast: refusing: a Chat step needs a terminal; run it headless with --headless, or switch the run to human-gated at a terminal
```

## `ballast run mode`

`ballast run mode RUN chat|human-gated --reason TEXT` now needs a terminal and the typed text `mode RUN TARGET`. Without a terminal it is refused, and it never accepts `--relayed-by`.

## `ballast discard-runs`

- `ballast discard-runs --help` or `-h` prints usage to stdout and exits 0. It takes no lock and changes nothing (AC-021).
- `ballast discard-runs ARG...` with anything else prints `ballast: refusing: discard-runs takes no arguments (see --help)` and exits 2, changing nothing (AC-022).
- After a discard, the `Next:` line is chosen as follows (AC-023):
  - Protected inputs equal the baseline: `Next: protected inputs are unchanged since the trust baseline; no ballast trust is needed. …`
  - They differ: `Next: review the checkout, then run ballast trust. …`
  - A tamper marker exists: the tamper recovery as today.

## Autonomous start on a branch not named for the Issue

At a terminal:

```text
autonomous needs a feature branch named for Issue #N; this checkout is on BRANCH.
Type `switch feat-N-slug` to run `git switch -c feat-N-slug` and continue, or anything else to stop:
```

When exactly one local branch carries the Issue number, the proposal is that branch and the command is `git switch`. Without a terminal, or with `--relayed-by`, it prints the following and exits 2 (AC-027):

```text
ballast: refusing: not eligible for autonomous: autonomous needs a feature branch named for the Issue without an open PR
Switch first: git switch -c feat-N-slug
Then rerun: ballast run start --mode autonomous -i issue=N -i feature_directory=specs/N-slug ...
```

## Resume and stop categories

- `ballast run resume RUN` after a `postcondition` block at `validate-implementation` re-enters at `implement` (AC-024).
- An agent step whose CLI hit its provider usage limit, and whose wrapper confirmed its processes stopped, stops as `interrupted` with the recovery `wait for the usage limit to reset, then ballast run resume RUN` (Chat: `ballast run step RUN PHASE`). No `discard-runs` and no `trust` are needed (AC-025).
- A dead wrapper keeps `unfinished-step` (AC-026).
