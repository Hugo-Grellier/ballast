# Timed-out or terminated worker settles through the interrupt path (#198)

Risk R2 (worker settlement and lock semantics). Implementation approved by the
operator on 2026-10-15; merge approval pending.

## Problem

At `--timeout`, `WorkerServer.poll` raised without sending `turn/interrupt`, so
every timeout ended `unknown` with the lock held. `worker.py` installed no
signal handler: SIGTERM ended the process without running `finally`, leaving
`result.json` stale, the lock held and possibly the client orphaned. Agent
harnesses stop foreground commands after 120 s by default, below the worker's
300 s default.

## Decision

One interrupt path for queue cancellation, deadline and signals.

1. `await_terminal` interrupts the turn when the queue is cancelled, a stop
   signal was received, or the deadline has passed. The reason becomes the
   settled status: `cancelled` (queue or signal) or `timeout` (deadline), and
   is recorded on the `interrupt_requested` event.
2. `WorkerServer.interrupt` sets a fresh bound of `INTERRUPT_SECONDS` from the
   request, even past the deadline. Before, a cancellation kept the earlier of
   the deadline and that bound; now every interrupt gets the same grace.
   `poll` returns `None` at the deadline until an interrupt was sent, and fails
   only once the interrupt bound has passed (still `unknown`).
3. `main` runs `execute` inside `stop_on_signals`, whose SIGTERM/SIGINT
   handlers only set a flag; the previous handlers are restored afterwards.
   Before dispatch the flag blocks the turn permit (`not_started`, lock
   released, no attempt spent); after dispatch `await_terminal` picks it up. Establishment is not cut short: it
   is bounded by the timeout and normally takes seconds.
4. Settlement is unchanged after the turn: `await_quiet`, head recording and
   review checks still gate `settled`. Missing terminal evidence, a rejected
   interrupt or survivors keep `unknown` and the lock.
5. `timeout` joins `coordinate.SETTLED`, from which `WORKER_STATUSES` and the
   dashboard status and milestone sets derive. `docs/standalone.md` describes the path and tells the coordinator to
   run the worker as a background command or keep `--timeout` about 70 s below
   the harness limit.

Signals settle as `cancelled`, not `timeout`: the worker cannot know why it was
signalled, and a stop on request is a cancellation. `MAX_RUNTIME` is unchanged.
SIGKILL still leaves `unknown`; nothing infers exit from age or PID.

## Verification

- Deadline with an interrupted terminal turn: `timeout`, lock released,
  `coordinate.worker_view` stops counting, dashboard projects `timeout`.
- Deadline without terminal turn, with a rejected interrupt, or with survivors:
  `unknown`, lock held.
- SIGTERM and SIGINT before dispatch: `not_started`, lock released, no permit,
  previous handlers restored.
- SIGTERM after dispatch: `cancelled` with terminal evidence, else `unknown`
  with the lock.
- Gate: `uv run --locked ruff check && uv run --locked ruff format --check`,
  `uv run --locked python tests/parallel.py tests/test_*.py`.
