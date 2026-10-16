# Live qualification: #231 client signal isolation

Date: 2026-10-16. Host: Linux, Codex CLI 0.162.1 (app-server), real
subscription model. Code under test: `tools/worker.py` at
80419820e238a2ab7687147ec9655ca87278b127. Run by the coordinating session on the
real #231 issue claim of a bounded queue; no GitHub writes, no disposable
repository needed because publication is not touched.

## Procedure

Each run starts the worker as the leader of its own session (`setsid`),
records its process group and the client's, waits for `task_accepted`, then
sends one signal to the whole worker process group (`kill -SIG -- -PGID`), the
shape a terminal Ctrl-C or a harness stopping a process group produces. Route
for every run: requested openai / gpt-6.1-sol / low, observed the same
(`codex-app-server:thread/start`).

## Results

| Run | Task | Signal | Client group | Events after dispatch | Outcome | Lock |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | run `sleep 120` | SIGTERM to group | own (≠ worker) | interrupt_requested → unknown (33 s) | `unknown`: sandboxed `sleep` and a `codex` helper still ran in the checkout | held; released by the coordinator with `coordinate.py release` after both exited |
| 2 | stream text, no command | SIGTERM to group | own (≠ worker) | interrupt_requested → cancelled (5 s) | `cancelled`, head unchanged | released |
| 3 | stream text, no command | SIGINT to group | own (≠ worker) | interrupt_requested → cancelled (1 s) | `cancelled`, head unchanged | released |

Runs 2 and 3 show the outcome #231 asks for: a group-wide SIGTERM or SIGINT
no longer reaches the client, the worker interrupts the turn and settles
`cancelled` with terminal evidence. Run 1 is the documented survivor rule, not a
signal-isolation failure: the interrupt was delivered, but a tool command
running inside the checkout outlived it, so the worker kept `unknown` and its
lock. Follow-up: #242.

A baseline run on the parent revision was not repeated (implementation attempt
budget for the claim was spent); the unit test
`test_group_signal_after_dispatch_settles_cancelled` fails without
`start_new_session`.
