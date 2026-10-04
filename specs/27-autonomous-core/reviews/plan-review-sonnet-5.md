REJECT

Reviewer: Claude Sonnet 5.5 (same provider as author; not cross-provider). Codex quota exhausted until 20:39.

New findings (all addressed in round-5 revision):
- N-1 Critical, architecture issue: bwrap left Unix sockets (/run/user, D-Bus, systemd user bus, agents' sockets) and host PIDs visible; agent code could start an unconfined process via `systemd-run --user`, read `/proc/<pid>/environ`, use keyring/ssh/gpg agents. Fix: --unshare-pid --unshare-ipc --new-session, tmpfs over /run, /var/run, $XDG_RUNTIME_DIR; fail-closed self-test.
- N-2 High, spec violation: agent steps after review/run-checks (resolve-decisions, decide-final, reviewer steps) could change the published tree. Fix: tree digest at run-checks, verified by record-final and publisher; reviewer steps limited to reports/drafts; PD artifact re-hash.
- N-3 High, architecture issue: run-checks ran agent-written code with writable .ballast/.specify/ballast.toml/.venv. Fix: ro-bind protected inputs in every confined process; hash check after run-checks.
- N-4 High, architecture issue: repository Git config could hold a readable forge token. Fix: refuse Autonomous start on credential-bearing Git config.

Mediums adopted: integration API-key allowlist; PR Checks section shows runner results; check timeout capped at remaining wall time; escaped agent text in PR body; scope-comment author association; no symlink artifact/report.
Mediums left to the implementer: linked-worktree `.git` read-only behavior for speckit commands; state residual risk of renew-intent without re-review in the merge summary; staging check wording; extra tests (agent-invoked `ballast run` fails; record-final rejects stale intent; `Autonomous: yes` intake parsing).
