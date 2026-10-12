# Dependencies: Ballast specifics

- The shipped tools have no third-party dependencies and must stay that way (constitution principle 6).
- The gate's tools (`ruff`, `pyyaml`) are pinned exactly in the `dev` group of `pyproject.toml` and locked in `uv.lock`; `pyproject.toml` is a non-package uv project. Run `uv lock` after changing a pin.
- Pinned upstream sources live in `tools/setup` (`SOURCES`, `VERSION`): Spec Kit, its extensions and the task-dependency preset. Changing a pin is a dependency change: inspect the upstream diff and license, and re-check the patches in `tools/spec-kit/` apply.
- Dependabot updates the GitHub Actions and the `uv` lock weekly, with patch updates grouped.
