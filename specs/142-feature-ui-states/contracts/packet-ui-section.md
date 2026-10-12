# Contract: packet UI states rendering

Extends #19's [packet format](../../19-acceptance-packet/contracts/packet-format.md#ui-states). Only the UI lines change; every other section is byte-identical for the same sources.

## UI states section

```text
### UI states

UI states: not configured.
or
UI states: configuration invalid (<fixed reason>).
or
None (0).
or
- <inert name>: <result>                                                  # repository entry
- <inert name> (<AC IDs>, agent-declared in ui-states.toml): <result>     # feature entry
or, at shortening level ≥ 3
UI states: <n>, <k> with a result.
```

- Repository entries are listed first, then feature entries, each in file order.
- `<result>` is unchanged from #19: `[present at head](<blob>)`, `[passed](<run>)`, `[failed](<run>)`, `[not run](<run>)`, `[not run (in progress)](<run>)` or `missing`.
- The list is capped like every other list (`_capped`).

## Beside a criterion

```text
… · UI <inert name> (agent-declared in ui-states.toml): <result>
```

Only feature entries appear beside a criterion, once per criterion they name. Repository entries never do.

## Invariants

- `agent-declared in ui-states.toml` is fixed Ballast text; repository entries never carry it (AC-014).
- `<inert name>` is `inert(name, 80)`: it cannot end the section, form a link or mention, or change a state or label (AC-015).
- AC IDs shown are validated `AC-NNN`; links are built only from a validated `safe_path` or a check-run integer ID (FR-011).
- A criterion's state cell and reason are identical with and without the feature file, valid or invalid (AC-016).
- A `configuration invalid` UI section leaves every other section unchanged and the packet published (AC-002, AC-004, FR-008).
