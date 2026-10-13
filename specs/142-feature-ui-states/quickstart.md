# Quickstart: validating feature-local UI states

## Prerequisites

- Python ≥ 3.11 and `uv`. No GitHub access: the tests use `PacketCase`'s temporary Git repository and the scripted `gh` fake.
- Formats and reasons: [contracts/ui-states-file.md](contracts/ui-states-file.md), [contracts/packet-ui-section.md](contracts/packet-ui-section.md).

## Commands

```sh
uvx ruff check && uvx ruff format --check
uv run --no-project --python 3.13 --with pyyaml python -m unittest tests/test_packet.py
uv run --no-project --python 3.13 --with pyyaml python -m unittest tests/test_*.py
```

## Scenarios

Each scenario writes `ui-states.toml` (and, where noted, `ballast.toml`) in the fixture, commits the head, publishes the packet and checks the rendered text. "Feature file" means `<feature>/ui-states.toml` at the head commit.

| # | AC | Setup | Expected |
| --- | --- | --- | --- |
| 1 | AC-001 | Feature file with a `path` entry for AC-001 (file committed), a `check` entry for AC-002 (check run passed), a `path` entry for AC-006 (file absent). | Section lists the three with the label; AC-001 row shows `UI <name> (agent-declared in ui-states.toml): [present at head](<blob>)`, AC-002 `[passed](<run>)`, AC-006 `missing`. |
| 2 | AC-002 | Feature entry citing `AC-099`. | `UI states: configuration invalid (ui-states.toml: UI state names a criterion the spec does not define).`; `### Criteria` and every other section present; packet `published`/`updated`. |
| 3 | AC-003 | One subtest per entry rule (unknown key, 81-character name, `AC-1`, missing `criteria`, `criteria = []`, both `path` and `check`, neither, `../x` path, 101-character check), plus `ui_states` as a string and an extra top-level key. | The matching `ui-states.toml:` reason from the contract, rest of the packet published. |
| 4 | AC-004 | Feature file with invalid TOML; with non-UTF-8 bytes; larger than 1 MiB. | `ui-states.toml: not valid TOML`, `… not UTF-8 text`, `… larger than 1 MiB`; rest published. |
| 5 | AC-005, AC-009 | Second feature directory committed with its own `ui-states.toml` naming `AC-003` (a different screen) and `AC-099`. | The run's packet shows only its own `AC-003` screen and no `configuration invalid`. |
| 6 | AC-006 | Commit a valid feature file, then change it in the working tree without committing. | Packet shows the committed entry. |
| 7 | AC-007 | No feature file, no `[review]`; another feature's file present. | `UI states: not configured.` |
| 8 | AC-008 | No feature file; `ballast.toml` with one criterion-less `check` entry. | Section lists `- <name>: <result>` without label or parentheses; no criterion row contains `UI `. |
| 9 | AC-010 | One repository entry and one feature entry. | Repository line first, then labelled feature line; only the feature entry appears beside its criterion. |
| 10 | AC-011 | Repository entry with `criteria = ["AC-001"]`; then with `criteria = []`. | `UI states: configuration invalid (ballast.toml: UI state criteria belong in the feature's ui-states.toml).` both times. |
| 11 | AC-012 | 30 repository entries and 21 feature entries; also 51 in one source. | `UI states: configuration invalid (more than 50 UI states).` |
| 12 | AC-013 | Criterion-less repository entries breaking each other rule (the rewritten `ReviewConfigTests` cases). | The matching `ballast.toml:` reason. |
| 13 | AC-013 / R4 | Repository and feature file both invalid. | The `ballast.toml:` reason. |
| 14 | AC-014 | Scenario 9's packet. | `agent-declared in ui-states.toml` appears once per feature line and beside each named criterion, never on the repository line. |
| 15 | AC-015 | Feature entry named with the hostile text of `HostileTextTests` (packet markers, a link, a mention, a backtick, `|`). | The name is inert; markers and links do not appear raw; section and table structure intact; no row state changes. |
| 16 | AC-016 | Same fixture published without the file, with a valid file and with an invalid file. | Every criterion's state cell and reason are identical across the three. |
| 17 | — | Existing `UiStateTests` with its four entries moved to the feature file. | Same results as before; section line gains the label. |
| 18 | AC-017, AC-018 | Read `templates/policies/spec-kit-workflow.md`, acceptance packet section. | States the feature file with schema and example, the criterion-less repository table merged with it, the 50 total limit, the move error, the agent-declared label, that entries never change a criterion's state, and how screenshots are kept current (`path` committed with the change and linked at head, `check` read at head, `missing` otherwise). |
| 19 | AC-019 | Read `docs/adr/0019-feature-local-ui-states.md` and ADR-0006. | ADR-0019 records the move, amends ADR-0006's configuration statement and states no new program, GitHub call, fetch or authority; ADR-0006 carries a pointer to it. |

## Expected outcome

All `tests/test_*.py` pass, lint and format are clean, and no test outside `ReviewConfigTests` and `UiStateTests` changes its expectations (FR-018).
