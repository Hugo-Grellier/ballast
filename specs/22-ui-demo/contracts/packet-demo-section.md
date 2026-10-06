# Contract: the packet's demo section

The section is rendered by `packet.render` from `Sources.demo`, between `### UI states` and `### Sources`. It extends #19's [packet format](../../19-acceptance-packet/contracts/packet-format.md). The criteria lines, the counts and the header never read it (FR-014, AC-005).

## Section text

```markdown
### Demo captures

A demo video helps a reviewer see behavior. It is not evidence for any criterion and not an approval. Reproduce a scenario by running its command at the captured commit.

- login-journey (Chromium 1280x720, seeded fixtures): captured at `0123456789ab` · [video](https://github.com/o/r/actions/runs/11/artifacts/22) · reproduce: `npm run demo:login`
- checkout: in progress (running) at `0123456789ab` · [job](https://github.com/o/r/actions/runs/12) · reproduce: `npm run demo:checkout`
- empty-cart: failed (command-failed) at `0123456789ab` · [job](https://github.com/o/r/actions/runs/13) · reproduce: `...`
- settings: missing (expired) at `0123456789ab` · [job](https://github.com/o/r/actions/runs/14) · reproduce: `...`
- profile: stale (captured at `fedcba987654`; head is `0123456789ab`) · [job](https://github.com/o/r/actions/runs/15) · reproduce: `...`
- search: not yet requested · reproduce: `...`
```

## Rules

| Rule | Requirement |
| --- | --- |
| One line per declared scenario, in declaration order. A scenario's newest `demo_capture` event decides the line. | FR-010, AC-006, PD-0006 |
| `[video](…)` appears only for `captured` and not `stale`. Every other state shows `[job](…)` when a run is known, or no link. | FR-011, FR-012, SC-002 |
| `stale` precedes everything when the capture's commit ≠ head. It shows the outcome at that commit, with its reason. A stale `captured` links the job, not the video. | FR-011, AC-003, PD-0005 |
| Scenario name and environment are passed through `packet.inert`. The command is shown as declared in a code span, where GitHub renders no markup: backticks are removed, control characters become spaces, tokens are redacted, and `<!--` and approval wording are broken by a zero-width space ([DEC-0002](../decisions.md#dec-0002--resolution)). | FR-018, AC-007 |
| `(declared command changed since this capture)` is appended when the digests differ. | AC-007, research R7 |
| An event for a scenario that is no longer declared renders `<name>: no longer declared`, with no link. | SC-002 |
| `not configured` and `configuration invalid (<reason>)` are single lines. The rest of the packet publishes. | AC-015, AC-016 |
| At size level ≥ 3: `Demo captures: N scenarios, K captured at head.` | #19 R14 |
| Links are built only from the validated repository and integer IDs: `/actions/runs/<run>` and `/actions/runs/<run>/artifacts/<artifact>`. | #19 FR-011 |
| The finished text passes #19's marker and `HUMAN_APPROVAL` guard. | AC-005 |

## Packet step outcome

A GitHub read failure while collecting demo data makes the packet step `failed-retryable` with the classified cause. That is the same rule as a check-run read failure. The Draft PR outcome and the run's exit status are unchanged, and the next checkpoint retries.
