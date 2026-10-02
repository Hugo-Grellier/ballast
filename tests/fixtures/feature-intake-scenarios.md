# Feature intake routing scenarios

Use these fictional issue snapshots for a read-only agent skill check. The agent must report route, next action, and human gate. It must not use GitHub or change files.

| Request | Issue and repository state | Expected route and gate |
| --- | --- | --- |
| `Start #800` | Open Epic with three independently useful outcomes, no children and a proposed child map explicitly marked unapproved. | Present decomposition and first unblocked child; wait for human scope approval. Never dispatch or label the Epic. |
| `Start #801` | Open Epic with an owner-approved child map and linked child #811. #811 is open, unblocked, has one outcome and acceptance criteria, a scope-gate approval comment and `ready-for-agent`. | Reuse #811 and hand it to `agentic-feature`; no new child or repeat scope approval. |
| `Start #802` | Open leaf with one cohesive feature outcome, in/out boundary, acceptance criteria, no blocker, and a recorded scope gate. | Preflight #802, then hand off to `agentic-feature`; do not split its implementation tasks into issues. |
| `Fix #803` | Open leaf bug with a narrow reproduction and acceptance criteria, no new product contract. | Hand off to existing `bugfix`; promote to feature only if fix needs a new contract or scope. |
| `Investigate #804` | Open leaf research question with an expected decision note, no requested behavior change. | Hand off to existing `assess`; no implementation from a `go` verdict alone. |
| `Continue #805` | Open active feature with `specs/805-demo/{intent,spec,plan,tasks}` and a valid local run belonging to that directory. | Reuse the directory and resume that run. Do not create another spec directory or reset approvals. |
| `Start #806` | Open leaf with acceptance criteria, but an open `blocked_by` relationship to #807. | Report blocker and stop dispatch/ready-label setup until resolved. |
