# Contract: acceptance packet text

`packet.render(sources, level) -> str` is deterministic: the same `Sources` give byte-identical text except the `Generated:` line (FR-009). All agent-written values go through `inert()` ([research R9](../research.md#r9-rendering-agent-written-text-inertly-fr-013-fr-016)). Every link is built by Ballast:

- file: `https://github.com/<o>/<r>/blob/<head>/<path>` (`?plain=1#L<n>` for a line)
- diff: `https://github.com/<o>/<r>/compare/<base>...<head>`
- check run: `https://github.com/<o>/<r>/runs/<id>`
- check runs of the head commit: `https://github.com/<o>/<r>/commit/<head>/checks`, only when the R8 read reported at least one check run at head
- test file: `https://github.com/<o>/<r>/blob/<head>/<path>`, where `<path>` is the longest dotted prefix of the test name whose `.py` file exists at head (DEC-0001)

The ledger is local and has no URL: evidence held only there is written `ledger event <seq> of run <run_id>` (DEC-0001).

## Sections, in order

```text
<!-- ballast:acceptance-packet:begin -->
## Acceptance packet

Derived summary for review. The linked sources are authoritative; this packet is not an approval and records none.

- Feature: `<feature>/` version `<tree 12>` (spec `sha256:<12>`)
- Base: `<base 12>` · Head: `<head 12>` · [diff](<diff link>)
- Run: `<run_id>` (<mode>)
- Generated: <UTC ISO 8601>
- Risk: <level> (<source>)
- Criteria: <n> · verified <a> · failed <b> · not run <c> · stale <d> · missing <e>
- Open findings: <n> · Provisional decisions: <n> · Human decisions: <n>

### Criteria

| ID | Criterion | Evidence | Detail |
| --- | --- | --- | --- |
| [AC-001](<spec line link>) | <inert title> | verified | 2/2 tests passed at head: [`tests.….test_a`](<test file link>) (ledger event 41 of run <run_id>), [`tests.….test_b`](<test file link>) (ledger event 43 of run <run_id>) · CI at head: [check runs](<head checks link>) or no CI result at head |
| [AC-004](<spec line link>) | <inert title> | stale | `tests.….test_x`: stale (commit `abc123def456`) |
| [AC-003](<spec line link>) | <inert title> | missing | no test named in acceptance-evidence.json |

Evidence for unknown criteria: AC-031 (in [acceptance-evidence.json](<link>), not in the spec)   ← only when present
UI: <state name> for AC-018: [present at head](<blob link>) | missing   ← per mapped criterion, only when configured

To record evidence for one criterion at the current commit: `ballast ledger check <run_id> AC-NNN <test>`.

### Decisions

- PD-0002 (clarification, agent-provisional): <inert summary> — [record](<record.md line link>)
- gate approve-plan: approve (human; observed by runner) — [ledger event 42 of run <run_id>]
- DEC-0001 (resolved; see record) — [decisions.md](<line link>)
None (0).   ← when there are none

### Open findings

- F-003 (medium, open): <inert reason> — [report](<link>)
None (0).

### Checks

- run-checks (runner, before publication, not bound to the head commit): `<inert command>` exited 0 in 12.3s
- run-checks: not run
- GitHub check runs at head: [<inert name>](<run link>) completed/success · [<name>](<link>) in progress
- GitHub check runs at head: none reported

### API changes

API: not configured.   ← single line when not configured (AC-015)
or
API (`<path>`, base → head): 1 added, 1 removed, 1 changed; 2 potentially breaking.
This classification is automatic and needs human review; it is not an approval.
- added: POST /orders
- removed: DELETE /orders/{id} — potentially breaking (operation removed)
- changed: GET /orders — response changed
or
API (`<path>`): no API change | added in this PR | removed in this PR | could not compare (not JSON)

### UI states

UI states: not configured.
or
- <inert name> (AC-018): [present at head](<blob>) | [passed](<run>) | not run (in progress) | missing

### Sources

- intent: [intent.md](<blob>) · spec: [spec.md](<blob>) · plan: [plan.md](<blob>) · tasks: [tasks.md](<blob>)
- decisions: not present
- acceptance evidence: [acceptance-evidence.json](<blob>)
- reviews: [plan-review-1.md](<blob>), …   or   reviews: not present
- run record: [autonomous/record.md](<blob>)   or   run record: not present
- diff: [<base 12>...<head 12>](<diff link>)
<!-- ballast:acceptance-packet:end -->
```

## Rules (tested)

- Every criterion ID in the spec appears exactly once, in spec order (AC-001, SC-002). A spec without IDs gives `No acceptance criteria found in [spec.md](…).` instead of the table.
- Every summary line carries a link to its source (AC-009). A ledger-only source with no URL is named by run ID and event sequence (DEC-0001).
- A `verified` row links each named test's file at head and, when GitHub reported check runs at head, the head's check runs (AC-002). A test whose file is not found at head is named unlinked with `file not found at head`. CI is suite-wide and never changes a criterion's state (R4).
- Absent artifacts read `not present`, with no link (AC-008).
- Zero counts are written as `None (0).` or `0` (FR-004).
- Fixed text only for states and labels. Labels are `agent-provisional`, `human` and `see record`, as recorded (AC-006).
- Outside inert data, the body never matches `(?i)\b(human[- ]approved|approved by (the )?(human|operator|user))\b`. The text contains exactly one begin marker and one end marker.
- The table cell separator `|` in inert text is escaped. No raw `<`, `>` or marker text comes from a source.
- Shortened levels ([research R14](../research.md#r14-size-fr-014-ac-021)) add, under the header: `Shortened to fit the PR description. Complete packet: speckit-runs/<run_id>/acceptance-packet.md in the operator's clone.`
