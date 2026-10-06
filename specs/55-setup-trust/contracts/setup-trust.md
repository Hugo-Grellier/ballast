# Contract: setup and preparation record a baseline

Owner: `tools/spec_workflow/setup_trust.py`, called from `tools/setup` (`Setup.main` and `Setup.prepare`). Data shapes: [data-model.md](../data-model.md). Decisions: [research.md](../research.md).

## Entry point

```python
setup_trust.settle(root: Path, state: Path, record: dict, *, standard: Path,
                   mode: Literal["setup", "prepare"]) -> Verdict
```

`Verdict` is one of `recorded(reference)`, `kept(source)` or `skipped(reason)`, with the line setup prints. `settle` never raises for an ineligible checkout; an `OSError` while writing operator state is reported as `skipped` with the cause, after removing any half-written baseline and provenance, and the installation's exit status is unchanged.

## When it is called

| Path in `tools/setup` | Called? |
| --- | --- |
| `main()` after `attempt()` committed and `finish()` removed the journal | yes, before the lock is released |
| `main()` "nothing changed" (`current(state)`) | yes, before the lock is released |
| `main()` after `recover()` restored or finished an attempt, then installed or found nothing to change | yes (once, at the end) |
| `prepare()` after `attempt()` committed | yes, before the lock is released |
| `prepare()` after `recover()` finished a committed preparation | yes, before the lock is released |
| `prepare()` "nothing to prepare" (another command prepared it) | no |
| `--check`; any refusal or failed stage | no |

## Order of evaluation

1. **Standard and markers** (data-model rows 1 and 2): the standard outside the checkout, no `BALLAST_TAMPERED`, no in-progress marker. A skipped verdict names the remedy even when a baseline matches (decisions.md DEC-0001).
2. **Keep a matching baseline** (FR-011), setup only. If `trusted.json` parses and equals a fresh `trusted_inputs(root)` snapshot, return `kept(source)` with the reported source. Nothing is written. A preparation never opens its own baseline (DEC-0004).
3. **Local conditions**, first failure wins: data-model eligibility rows 3 to 7.
4. **Operator baseline** (row 8a), setup only: eligible with `operator-baseline`.
5. **Reviewed repository** (row 8b), then **default branch** (row 9): eligible with `default-branch`.
6. **Record**: `launcher.record_baseline(state, snapshot, source="setup", reference=...)`.
7. **Recheck**: a second snapshot must equal the first; otherwise restore the previous `trusted.json` and provenance (or remove both when there were none) and return `skipped("protected inputs changed while setup checked them")`. A failed write is restored the same way.

No step after a failure runs; no network access happens before step 5, and none at all when step 4 succeeds.

## Default-branch observation

As research R9. Only these Git invocations, each with a list argv, absolute Git outside working trees, stdin closed:

| Where | Command | Timeout |
| --- | --- | --- |
| checkout (local plumbing) | `rev-parse --show-object-format`; `rev-parse --verify --quiet HEAD:<path>` (two paths); `remote get-url origin` (scheme only) | 30 s each |
| throwaway | `init --quiet --bare --template= --object-format=sha1 <dir>` | 30 s |
| throwaway (network, new session) | `ls-remote --symref <url> HEAD` | 30 s |
| throwaway (network, new session) | `fetch --depth=1 --no-tags --no-write-fetch-head --filter=blob:none reviewed +refs/heads/<default>:refs/reviewed/default` with `-c remote.reviewed.url=<url> -c remote.reviewed.promisor=true -c remote.reviewed.partialclonefilter=blob:none` | 120 s |
| throwaway | `rev-parse --verify refs/reviewed/default^{commit}`; `ls-tree -z <commit> -- ballast.toml .specify/memory/constitution.md` | 30 s |

Every throwaway command adds `autonomy.GIT_HARDENING` and `-c maintenance.auto=false -c gc.auto=0 -c core.commitGraph=false`. The throwaway lives under `<state>/setup-trust/<random hex>/` with its own object store and is removed in a `finally`. `<default>` must match `ledger.REF` (DEC-0005); `<commit>` must be 40 hex digits. Git's output is parsed, never printed.

## Output

The installation's lines come first, unchanged. Then one verdict block:

| Verdict | Lines |
| --- | --- |
| recorded, default branch | `Recorded the trust baseline for N protected inputs: ballast.toml and the constitution match OWNER/NAME's default branch BRANCH at <12 hex>.` / `The next ballast run, ledger or intake needs no ballast trust.` |
| recorded, operator baseline | `Recorded the trust baseline for N protected inputs: ballast.toml and the constitution match the baseline you recorded with ballast trust.` / same second line |
| kept | `The trust baseline you recorded with ballast trust still matches; left unchanged.` or `The trust baseline setup recorded still matches; left unchanged.` |
| skipped, setup | `No trust baseline recorded: <reason>.` / `Review the changed protected inputs, then run ballast trust before the next workflow run.` |
| skipped, preparation | `No trust baseline recorded: <reason>.` / `Review this worktree's protected inputs, then run ballast trust.` |

In a preparation, a skipped verdict's `No trust baseline recorded: <reason>.` line comes before the `Prepared the ... installation ...` line, so the output still ends with today's two lines (decisions.md DEC-0003). `<reason>` is a data-model fixed phrase; any checkout-derived value in it (a path, a branch, a repository name) goes through `printable()`. Today's "Spec Kit ... are set up." and "Prepared the ... installation from ..." lines are unchanged; the old trust line moves into the skipped block with the same wording (backticks kept as today).

## Guarantees

- Never records while an in-progress marker, `BALLAST_TAMPERED`, saved run state or an unfinished operator-state run exists (AC-018 to AC-021).
- Never modifies or removes an existing baseline when skipped (FR-008, AC-017), except preparation's removal of one left at a reused path before installing (AC-008).
- Never opens another checkout's `trusted.json`, provenance or run records (FR-010, AC-009).
- Never reads the repository, branch or compared files from the checkout's Git configuration or refs; only `origin`'s scheme selects HTTPS or SSH (FR-004, AC-015).
- Never prompts; every network command is bounded (spec edge case).
