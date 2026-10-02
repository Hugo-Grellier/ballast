# Dependencies: Ballast specifics

- The shipped tools have no third-party dependencies and must stay that way (constitution principle 6).
- Tests use `pyyaml`, provided at run time by `uv run --with pyyaml`; there is no lockfile.
- Pinned upstream sources live in `tools/setup` (`SOURCES`, `VERSION`): Spec Kit, its extensions and the task-dependency preset. Changing a pin is a dependency change: inspect the upstream diff and license, and re-check the patches in `tools/spec-kit/` apply.
- Dependabot updates the GitHub Actions weekly with patch updates grouped.
