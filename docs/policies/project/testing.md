# Testing: Ballast specifics

- Fast gate: `uvx ruff check`, `uvx ruff format --check`, and `uv run --no-project --python 3.13 --with pyyaml python -m unittest tests/test_*.py`. CI runs the same.
- Four tests skip in CI because they need a systemd user session, the Codex sandbox or the Spec Kit CLI. Run the suite on such a machine before a release and for any change to `tools/spec_workflow/agent.py`, `launcher.py` or the workflow file.
- Critical evidence: a step that changes a protected input fails (including `ballast.toml`); the launcher refuses before trust, after a tamper marker and after an unfinished step; `ballast` never runs a launcher from the checkout and only `setup` downloads; `tools/setup` refuses unignored installed paths and keeps run state and the constitution across a reinstall; every relative link in installed documents resolves.
- A change to `tools/setup` or `tools/ballast` also needs an end-to-end run on a scratch project: `ballast setup`, `ballast trust`, `ballast ledger report`, and a clean `git status` apart from the project's own files.
