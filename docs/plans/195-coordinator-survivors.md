# Coordinator processes in an issue checkout (#195)

Risk R2 (worker settlement). Plan approved by the operator on 2026-10-15.

## Problem

`await_quiet` treats any process whose working directory is inside the checkout
as a worker survivor. A coordinator process there (the dashboard during #193)
turns a completed worker into `unknown`, with an anonymous reason and no kept
output.

## Decision

Processes that do not descend from the worker's client are **not** ignored for
settlement. Sandboxed commands start their own session and are reparented once
the client exits, so descent cannot be proven after the fact. A subreaper would
help, but work handed to a daemon (`systemd-run`, a container engine) would
still look foreign. Settlement stays `unknown`; the operator acts on named
processes.

## Changes

1. `worker.describe`: the block reason lists survivors as `PID (comm)` from
   `/proc/PID/comm`, never the command line, capped at ten.
2. `worktree.inside_checkout`: the worker, dashboard and queue commands refuse
   to start when their own working directory is under `ballast-v2/` (path
   only, no Git call through a worker-writable gitfile). The worker would
   otherwise be its own survivor.
3. `worker.keep_output`: a backend-confirmed completed turn writes `output.txt`
   and `turn: completed` before the quiet check, so the work survives an
   `unknown` settlement. Status and lock semantics are unchanged.
4. `docs/standalone.md` states the rule.

## Verification

- Unrelated `sleep` in the checkout (the #193 case): the block names its PID and
  `sleep`, `result.json` is `unknown` with `turn: completed`, `output.txt` is
  kept and the lock is held.
- The worker, dashboard and queue commands refuse to start from inside a checkout.
- Existing quiet-checkout, survivor and `unknown` tests stay green.
- Gate: `uv run --locked ruff check && uv run --locked ruff format --check`,
  `uv run --locked python tests/parallel.py tests/test_*.py`.
