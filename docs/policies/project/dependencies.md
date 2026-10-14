# Dependencies: Ballast specifics

- The shipped tools have no third-party dependencies and must stay that way (constitution principle 6).
- The gate's tools (`ruff`, `pyyaml`) are pinned exactly in the `dev` group of `pyproject.toml` and locked in `uv.lock`; `pyproject.toml` is a non-package uv project. Run `uv lock` after changing a pin.
- The Spec Kit CLI version lives in the `spec-kit` dependency group in `pyproject.toml` and is locked in `uv.lock`; `tools/setup` reads that exact pin. The upstream source SHAs live in `tools/setup` (`SOURCES`): Spec Kit, its extensions and the task-dependency preset. Changing a CLI pin is a dependency change: inspect the upstream diff and license, and re-check the patches in `tools/spec-kit/` apply.
- Dependabot updates the GitHub Actions and the `uv` lock weekly, with patch updates grouped.
