# Release notes draft: Autonomous run core (#27)

- New: `ballast run start --mode autonomous` runs an eligible feature to a Draft PR with agent-provisional decisions; merging the PR is the single human approval. New commands `ballast run continue` and `ballast run publish`; new `ballast.toml` tables `[autonomous]` (optional, narrowing only) and `[checks]` (required for Autonomous). Autonomous needs `bwrap` on the host. Human-gated runs are unchanged.
- Constitution 1.1.0 adds BL-INV-006: a provisional decision is never human approval; only merging the PR that contains it accepts it.
- Copy-once files: `templates/AGENTS.md` (risk sentence) and `templates/github/pull_request_template.md` (R2 line) changed. Projects that already copied them keep their old wording until they copy them again; the old wording stays correct for human-gated runs.
