# Contract: packet step in the PR checkpoint

Module `tools/spec_workflow/packet.py`, installed as `.ballast/spec_workflow/packet.py`. Standard library only. Imported by `draft_pr.py` at module load, so `run.py` loads it at startup before any agent step (BL-INV-002).

## Entry points

```python
# draft_pr.py
def checkpoint(root: Path, run_id: str) -> Outcome
# Outcome gains: packet: packet.PacketOutcome | None

# packet.py
def publish(work: draft_pr._Checkpoint, outcome: draft_pr.Outcome) -> PacketOutcome
def collect(work, pr: dict) -> Sources          # all I/O, through work.git / work.gh
def render(sources: Sources, level: int) -> str  # pure
def format_line(outcome: PacketOutcome) -> str
```

- `checkpoint` records the #17 `pull_request` event first, then calls `packet.publish` inside its own `try/except Exception`, then records the `acceptance_packet` event. A raised exception becomes `failed-retryable/internal-error` with the exception type as `detail`. Neither path changes the #17 `Outcome`'s state, reason or remedy (FR-015).
- `skipped` (tamper or in-progress marker) attempts no packet and records no event.
- #17 outcome `created` or `reused` → the packet is attempted. `pending` or `failed-retryable` → `pending/no-pr`. `blocked-*` → `pending/pr-blocked`. Neither of the last two makes a `gh` call.
- `run.py` `_checkpoint` prints `draft_pr.format_line(outcome)`, then, when `outcome.packet` is set, `packet.format_line(outcome.packet)`. The existing `except (Exception, KeyboardInterrupt)` still guards both lines; the exit status is never assigned.

## Output line

```text
Acceptance packet: <state>[ (<reason>)][ #<pr> head <12 hex>][: <remedy>][ (<detail>)]
```

No `gh` output, environment value, path outside the repository, or credential is printed (FR-016).

## Commands (all through `_command`, the #17 environment and resolved programs)

| Purpose | Command |
| --- | --- |
| PR, head and base | `<gh> api repos/<o>/<r>/pulls/<n>` (`head.sha`, `base.sha`, `body`, `state`, `head.ref`, `html_url` re-validated by #17's rules) |
| Head present | `<git> cat-file -e <head>^{commit}` |
| Feature version | `<git> rev-parse --verify <head>:<feature>` |
| Feature files | `<git> ls-tree -r -z --name-only <head> -- <feature>/` |
| File bytes | `<git> cat-file blob <head>:<path>` (≤ 1 MB, else `source-unreadable` for spec, `not present (too large)` otherwise) |
| Head fingerprint | `ledger.commit_tree(root, head, git=work.git)` (`read-tree`, `rm --cached`, `write-tree` with `GIT_INDEX_FILE` set to a private temporary file) |
| UI path present | `<git> cat-file -e <head>:<path>` |
| CI | `<gh> api --paginate --slurp "repos/<o>/<r>/commits/<head>/check-runs?per_page=100"` |
| OpenAPI | `<gh> api "repos/<o>/<r>/contents/<quoted path>?ref=<sha>"` for base and head; 404 → absent at that commit |
| Re-read before edit | `<gh> api repos/<o>/<r>/pulls/<n>`, whose body must equal the first read |
| Edit | `<gh> pr edit <n> --repo <o>/<r> --body-file -` (body on stdin) |

Commit IDs are validated as `oid` before use. Path segments are validated by `PATH_SEGMENT` and URL-quoted. `git` gets `--` before every path and `-z` for lists. `gh` runs from an empty temporary directory, as in #17. Ballast never passes `--title`, `--base`, labels, reviewers, `--ready` or `--draft`, and never fetches, pushes or commits.

Call budget per checkpoint, after #17: 2 PR reads, 1 to N check-run pages, 0 or 2 contents reads and at most 1 edit; Git calls are local.

## Body edit rule

1. `body` = first read. Count the packet markers: 0 → append with `_after(body, packet)`; exactly 1 pair in order → replace that span; anything else → `failed-retryable/section-unmanaged`.
2. Masked text equal to the current section → `unchanged`, no further call.
3. The new body must leave every byte outside the packet span unchanged (asserted before writing). The #17 section and the #27 summary are outside it.
4. Re-read. A different body → `failed-retryable/body-changed`. Otherwise `pr edit` → `published` (0 markers before) or `updated`.
5. The archive copy is written after a successful build, whether or not the edit succeeds.
