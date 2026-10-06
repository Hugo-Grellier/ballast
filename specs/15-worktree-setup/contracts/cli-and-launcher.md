# Contract: CLI trigger and launcher preflight

Decisions: [research.md](../research.md) R1 to R3, R9.

## `tools/ballast` (global CLI)

`ballast run|ledger|intake …` in checkout `root`, after `command_standard` (unchanged: not fetched → `standard <ref> is not fetched; run \`ballast setup\``, no network):

1. **Needs an installation** when `root/.ballast/spec_workflow/run.py` is not a file, or `operator_state(root)/setup-attempt.json` exists. Otherwise skip to step 5.
2. The standard's `tools/cli.toml` does not declare `[setup] prepare = true`: when `run.py` is missing → `ballast: refusing: nothing is installed in this checkout; run \`ballast setup\``, exit 2 (AC-007); when only the journal exists, skip to step 5 so the launcher reports the unfinished setup as today. A version that declares `prepare` always continues to step 3, including when only a journal exists, because a killed preparation can leave `run.py` live (AC-018); `--prepare` recovers a `prepare` journal and refuses any other with the launcher's unfinished-setup text.
3. Unless `BALLAST_STANDARD_DIR` is set, `damage(standard)` is not `None` → `ballast: refusing: the cached standard <ref> is damaged at <path>; run \`ballast setup\` to fetch it again`, exit 2, no fetch (AC-013).
4. Run `[PYTHON, "-IS", standard/"tools/setup", "--project", root, "--prepare"]` with inherited stdio and `cwd=root`. Non-zero → return its exit code (1 when a signal killed it).
5. `execv` the launcher as today.

`ballast trust`, `discard-runs`, `status`, `doctor`, `preview`: no preparation. `trust` and `discard-runs` on an uninstalled checkout whose version does not declare `prepare` get the step-2 refusal from the CLI; otherwise the launcher's (below). `doctor`, `status --json` and `preview` stay read-only (AC-005).

`ballast doctor`'s trust check on an uninstalled checkout keeps `the workflow is not installed in this checkout` and its remedy names `ballast setup`, plus, when the pinned version declares `[setup] prepare`, `or the first \`ballast run\`, \`ledger\` or \`intake\`, which prepares it from a verified installation on this machine` (plan review F-005).

Usage text and module docstring gain one sentence: the first `run`, `ledger` or `intake` in a new worktree prepares its installation from a verified installation on this machine, without downloading.

## `tools/spec_workflow/launcher.py` (pinned standard)

- `_trust_refusal`, no baseline: `no trusted baseline for this checkout; review its protected inputs (ballast.toml, .ballast/spec_workflow, .specify[, .venv][, .git]), then run \`ballast trust\`` — only the bases that exist are listed. Prefix `no trusted baseline` unchanged (doctor relies on it).
- `trust` and `discard-runs` with nothing installed: `ballast: refusing: nothing is installed in this checkout; run \`ballast setup\`, or \`ballast run\`, \`ledger\` or \`intake\` to prepare it from a verified installation on this machine`, exit 2; no state directory or file is created. The installed check runs before `_hold`, so not even `checkout.lock` is created in an existing state directory (plan review F-003). Exception (DEC-0001): `discard-runs` on an uninstalled checkout whose `in-progress` marker exists runs as on an installed one, so the unfinished step that setup and preparation refuse on can be cleared.
- `run`, `ledger`, `intake` with nothing installed (reachable only with an old CLI): same message, exit 2.
- Every other refusal, its order, the lock and `status --json` are unchanged.

## `tools/cli.toml`

```toml
[setup]
recoverable = true
prepare = true
```

## Compatibility

| CLI | Pinned version | Uninstalled worktree, `ballast run` |
| --- | --- | --- |
| this feature | this feature | prepared from a verified local installation, then trust preflight |
| this feature | older | CLI refusal naming `ballast setup` |
| older | this feature | launcher refusal naming `ballast setup` (no preparation) |
| older | older | today's usage text |
