# Codex client kept out of group-wide signals (#231)

Risk R2 (what the worker launches and how it stops). Implementation approved by
the operator, relayed on the
[issue](https://github.com/Hugo-Grellier/ballast/issues/231); merge approval
pending.

## Problem

`AppServer` started the Codex client without `start_new_session`, so it shared
the worker's process group. A signal to the whole group (terminal Ctrl-C, a
harness stopping the group) also stopped the client: the worker saw EOF/EPIPE
and ended `unknown` with its lock held. #198 handled SIGTERM/SIGINT sent to the
worker process only.

## Decision

1. `WorkerServer` starts its client in its own session (`start_new_session`).
   A SIGTERM/SIGINT to the worker's PID or process group reaches only the
   worker, which takes the #198 interrupt path and settles `cancelled` with
   terminal evidence. The task-free probe (`codex.py`) is unchanged: it keeps
   sharing its caller's signals.
2. Out of the worker's group, a group-wide SIGKILL would no longer reach the
   client and could leave it running a turn unwatched. The worker therefore
   sets the Linux parent-death signal (`prctl(PR_SET_PDEATHSIG, SIGKILL)`
   through `ctypes`, in `preexec_fn`): if the worker dies first, even by
   SIGKILL, the kernel SIGKILLs the client. A `getppid` check in the child
   closes the race where the worker dies before `prctl` takes effect. The
   signal is bound to the forking thread; `execute` starts the client from the
   main thread. SIGKILL rather than SIGTERM: a dead worker settles nothing, so
   a graceful client shutdown buys no evidence.
3. Host support narrows to Linux. Without `prctl` the worker refuses before
   starting a client (fixed reason, `not_started`, reservation released). The
   worker already needed Linux `/proc` to settle, so no settling host is lost.
4. Not covered, documented: a signal to the client's own PID or session, and a
   recursive tree kill that signals each descendant PID, still reach the
   client and end the worker `unknown` with its lock. Commands the client
   started in their own sessions can outlive a SIGKILLed worker; that worker
   stays `unknown` with its lock until an operator inspects the checkout.
5. Settlement is unchanged: `close` still reaps the client, and `await_quiet`
   and survivor reporting still gate `settled`. Nothing infers exit from age or
   PID.

## Verification

- A real `killpg` (SIGTERM and SIGINT) on a fresh session running the worker
  with a real child fake client: `cancelled`, `interrupt_requested` recorded,
  lock released. Without `start_new_session` it ends `unknown`.
- A SIGKILLed stand-in worker: its client, launched with the worker's options,
  dies. Without the parent-death signal it survives.
- No `prctl`: refused before launch, `not_started`, lock released.
- Gate: `uv run --locked ruff check && uv run --locked ruff format --check`,
  `uv run --locked python tests/parallel.py tests/test_*.py`.

## Live qualification

Pending; the coordinator records it in
[docs/evidence/231-live-qualification.md](../evidence/231-live-qualification.md).
