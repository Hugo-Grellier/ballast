# Backport LoreForge's agent-first profile into the standard

**Status:** Plan, decisions resolved 2026-09-28; nothing executed yet
**Source:** `Hugo-Grellier/LoreForge` `origin/main` @ `14c2b12`. The PRs involved are #88 (adopt the profile), #104 (artifact postconditions) and #105 (issue intake).

## Goal

1. **Backport:** move everything generic that LoreForge built on top of these specs into `templates/`, so the standard stops being spec-only.
2. **Generalize:** keep only a small per-project config and a set of overrides. There should be no `loreforge` string in the shipped material.
3. **Clean up LoreForge:** use the same trick as `scripts/setup-speckit`. LoreForge pins one version of the standard, and a setup script installs it into **git-ignored** paths. LoreForge then commits only its project-specific overrides, and the roughly 5k lines of vendored process material leave its tree.

## How Spec Kit is handled today (the model to copy)

`scripts/setup-speckit` pins upstream sources by commit SHA and runs `specify init/extension/preset`. It applies `scripts/spec-kit/*.patch`, restores the `PRESERVED` committed customizations, and writes a fingerprint stamp. That stamp lets a rerun do nothing when nothing changed, and lets a worktree copy the install from its primary checkout. Everything the script generates is listed in `.gitignore`. The committed files are:

- the pins
- the patches
- `.specify/templates/*`
- the workflow registry
- `.specify/workflows/loreforge-feature/`

## Inventory: generic vs project-specific

Coupling comes from grepping for `loreforge|campaign|foundry|vault|LF-|M1|.venv|web/` and from reading the files.

| LoreForge path | Lines | Classification | Target in standard |
| --- | ---: | --- | --- |
| `docs/engineering/agentic-profile.md` | 3003 | Copy of `specs/*` with a LoreForge header | **Delete in LoreForge**; link to the pinned standard version |
| `.agents/skills/{engineering,test,documentation,spec-reconciliation}-review`, `dependency-{evaluation,migration}`, `database-migration` | ~10 each | Generic; the only coupling is "LoreForge" in `description` | `templates/skills/<name>/SKILL.md` |
| `.agents/skills/security-review` | 24 | Structure is generic. The checklist is domain-specific (Visibility, Foundry, Discord) and so are the `LF-SEC`/`LF-INV` IDs | Generic skill that reads the project's `docs/policies/security.md` and constitution for boundaries and invariant IDs |
| `.agents/skills/model-routing` + `docs/engineering/model-routing.md` | 28 + 120 | ~95 % generic (subscription-quota routing across Claude and Codex) | `templates/skills/model-routing`, `templates/policies/model-routing.md` |
| `.agents/skills/feature-intake` + `scripts/feature_intake.py` + its tests | 36 + 400 + 377 | Generic. The `<!-- loreforge-intake -->` marker and the workflow name vary per project | `templates/skills/feature-intake`, `tools/feature_intake.py`, with the marker prefix set in config |
| `docs/policies/{engineering,documentation}.md` | 13, 7 | Generic | `templates/policies/` |
| `docs/policies/{security,testing,dependencies,migrations,observability}.md` | 5–17 | Generic skeleton plus project boundary lists | `templates/policies/` as the base; the project keeps only `docs/policies/project/<name>.md` |
| `docs/engineering/workflow.md` (risk R0–R2, review matrix, gates) | 55 | The matrix and procedure are generic. The R2 examples and the `scripts/check`/`verify` commands are project-specific | Generic `templates/policies/workflow.md`; the project's R2 boundary list and gate commands come from config and `docs/policies/project/workflow.md` |
| `docs/spec-kit-workflow.md` | 527 | ~80 % generic (scope gate, lifecycle, runner contract) | `templates/docs/spec-kit-workflow.md`; the LoreForge architecture areas move to `docs/policies/project/spec-kit-workflow.md` |
| `.specify/workflows/loreforge-feature/workflow.yml` | 144 | Generic apart from its id | `templates/spec-kit/workflows/feature/workflow.yml` (id `agentic-feature`, or set in config) |
| `.specify/templates/{spec,plan,tasks}-template.md` | 469 | Generic (the preset output plus patches) | `templates/spec-kit/templates/` |
| `.specify/memory/constitution.md` | 20 | **Project-specific** (LF-INV-00x) | Stays in LoreForge. The standard ships `templates/spec-kit/constitution.template.md` |
| `scripts/spec_workflow/{artifacts,agent,run}.py`, `bin/*`, tests (703) | 908 | Generic. Names, the `LOREFORGE_SPEC_WORKFLOW` env var, `.venv/bin/python` and the temp prefix vary | `tools/spec_workflow/`; the name, env var and python command come from config |
| `scripts/spec_workflow/claude-settings.json` | 41 | Base allow/deny list is generic. `pnpm --dir web ...` and `campaigns/**` are project-specific | Generic base + project `extra_allow`/`extra_deny` in config, merged at setup |
| `scripts/setup-speckit` + `scripts/spec-kit/*.patch` | 273 + 294 | Generic apart from `PRESERVED`, `MATCH_FILES` and the stamp name | `tools/setup` (a single installer covering both Spec Kit and the standard) |
| `.github/pull_request_template.md`, `workflows/acceptance.yml` | 46 + 46 | PR template is generic; acceptance.yml is project-specific | `templates/github/pull_request_template.md`; acceptance stays in LoreForge |
| `AGENTS.md` | ~80 | About half generic (issue/spec workflow, conflict rules, routing, PR rules) | `templates/AGENTS.md` gains the generic sections; LoreForge keeps commands, invariants, the R2 list and the conditional table rows |
| `campaign-setup`, `session-prep`, `session-return` skills | — | Product domain | **Not backported** |
| `docs/reviews/pr-88-final.md`, `specs/103-*` | — | History and evidence | Not backported; they can serve as fixtures and examples |

## Proposed shape of the standard

```text
templates/                      # copied or rendered into the target repo (git-ignored there)
  AGENTS.md                     # generic sections + <!-- project: ... --> slots
  skills/<name>/SKILL.md        # 10 skills; the installer symlinks .claude/skills -> .agents/skills
  policies/*.md                 # generic base policies
  spec-kit/{templates,workflows/feature,patches,constitution.template.md}
  github/pull_request_template.md
tools/
  setup                         # replaces LoreForge's setup-speckit; reads agentic.toml
  spec_workflow/                # artifacts.py, agent.py, run.py (stdlib only)
  feature_intake.py
tests/                          # the #104/#105 tests, moved over and de-LoreForged
```

### Per-project config (committed in the target repo)

The config lives in `agentic.toml` at the repository root.

```toml
[standard]
repo = "Hugo-Grellier/agentic-repo-standard"
ref  = "<sha>"                 # pinned the same way the Spec Kit sources are

[project]
name     = "loreforge"          # used for the workflow id, env var and intake marker
python   = ".venv/bin/python"
check    = "./scripts/check"
verify   = "./scripts/verify"

[agents.permissions]            # merged into the generated claude-settings.json
extra_allow = ["Bash(pnpm --dir web run lint)", "..."]
extra_deny  = ["Edit(./campaigns/**)"]

[overrides]                     # committed project files the installer must never overwrite
preserve = [".specify/memory/constitution.md"]   # docs/policies/project/ is never touched
```

### Override rule: base plus addendum, never a fork

A generic policy or skill reads `docs/policies/<name>.md` from the standard, which is installed and ignored. It **also** reads `docs/policies/project/<name>.md` when that file exists, and that file is committed. This keeps project knowledge (Visibility, Foundry, `LF-INV-*`) out of the standard, and upgrades never have to merge edits to a fork.

## Phases

1. **Seed the standard (this repo).** Import the generic files from the inventory as-is. Replace `LoreForge`/`loreforge` with config lookups, rename the workflow to `agentic-feature`, and parameterize the env var, marker, python command and permissions. Move the tests with them: 703 + 377 lines, including the fake Spec Kit PTY run. Add `tools/setup`, generalized from `setup-speckit`. Translate `PRODUCT-SPEC.md` to English. Update `README.md`, `TECHNICAL-SPEC.md` §55 and `CHANGELOG.md`. Make a first commit, then tag `v0.1.0`.
2. **Dry-run on a scratch repo.** Run `tools/setup` on an empty repo, then run `specify workflow run agentic-feature` with the fake integration from the tests. This proves the standard works without LoreForge.
3. **Clean up LoreForge (one PR, R2, because it changes the headless-agent permission source).**
   - Add `agentic.toml`, pinned to `v0.1.0`.
   - Delete `scripts/setup-speckit` and `scripts/spec-kit/`; `agentic-workflow setup` replaces them, including as the Orca worktree setup script.
   - Delete the vendored files: the generic skills, policy bases, `spec_workflow/*`, `feature_intake.py` and its tests, patches, templates, and `agentic-profile.md`. Add them to `.gitignore`.
   - Turn the project-specific parts into `docs/policies/project/*.md` files: the security boundaries, the R2 list, the architecture areas in `spec-kit-workflow`, and the `claude-settings` extras.
   - Keep `constitution.md`, `acceptance.yml`, the domain skills and `specs/`.
   - Check: `./scripts/check`. Then check that `python3 tools/spec_workflow/artifacts.py convergence --feature specs/103-...` still passes on existing specs. Then do one fresh `run.py start` to the intent gate.
   - Backward compatibility: the workflow id becomes `agentic-feature` and the launcher variable becomes `AGENTIC_SPEC_WORKFLOW`. No compatibility alias: finish or restart any local `loreforge-feature` run before migrating.
   - Restore LoreForge's project permissions through `agentic.toml` `extra_allow`/`extra_deny`, since the base list no longer has them: `./scripts/check`, `./scripts/generate-api`, `uv run --locked ruff *`, `uv run --locked ty check*`, `uv run --locked python -m unittest *`, `pnpm --dir web run lint|typecheck|test*`, and deny `Read`/`Edit(./campaigns/**)`.
   - LoreForge's `.gitignore` Spec Kit lines are replaced by the block `tools/setup` prints. `.specify/.gitignore`, `.specify/templates/*` and `.specify/workflows/workflow-registry.json` become untracked; only `.specify/memory/constitution.md` stays committed.
   - Report upstream in LoreForge: its `skills.patch` garbles `speckit-intent-decisions` ("preserve .specify/extensions/intent/intent/spec/plan").
4. **Upgrade path.** Bumping `ref` in `agentic.toml` changes the fingerprint, so `setup` reinstalls. Document this in the standard's README.

## Decisions (resolved 2026-09-28)

- **Distribution:** pinned tarball of the standard at a commit SHA or tag, installed into git-ignored paths. No submodule.
- **Spec Kit ownership:** `setup-speckit`, its pins and its patches move into the standard as part of `tools/setup`. Projects keep only `agentic.toml`; the global `agentic-workflow setup` fetches the pinned version and runs its `tools/setup`.
- **Project overrides:** go in `docs/policies/project/<name>.md` (committed). Generic bases are installed to `docs/policies/<name>.md` (ignored). A skill reads the base, then the project file if it exists.
- **Install location:** everything the installer adds to a project lives under git-ignored `.agentic/` (tools at `.agentic/spec_workflow/`). Agents may not edit it.
- **Language:** full English. Both specs get translated before `v0.1.0`.

## Sync log

- 2026-10-01: synced LoreForge #112 (agent run ledger) and #113 (headless guard, trusted launcher) at `9eb5849` into `tools/spec_workflow/` with the same renames. The ledger reads `docs/policies/model-routing.md`, so that policy moved forward into `templates/policies/`. LoreForge's `scripts/agent-metrics` wrapper is not ported; `agentic-workflow ledger report` covers it.  LoreForge keeps its own `specs/*/workflow-runs/` ignore line for run records written before #112; new projects never produce them.

- 2026-10-01: imported the workflow guide (`templates/policies/spec-kit-workflow.md`) and the intake skill and helper at `9eb5849`, including #113's launcher handoff. Standard skills carry an `agentic-` prefix; `tools/setup` installs skills, helper and policies.

## Parity checklist (gate for the first merge)

The standard is public and merged once every LoreForge process asset is either in the standard or deliberately left to the project. Checked against LoreForge `origin/main` @ `43dfcbe` (nothing process-related changed after `9eb5849`).

| LoreForge asset | Status |
| --- | --- |
| `scripts/spec_workflow/*`, `.specify/workflows/loreforge-feature`, Spec Kit templates | Done (`tools/spec_workflow/`, `templates/spec-kit/`) |
| `scripts/setup-speckit`, `scripts/spec-kit/*.patch` | Done (`tools/setup`, `tools/spec-kit/`, `tools/agentic-workflow`) |
| `scripts/feature_intake.py`, `feature-intake` skill | Done (`agentic-feature-intake`) |
| `docs/spec-kit-workflow.md`, `docs/engineering/model-routing.md` | Done (`templates/policies/`) |
| `scripts/agent-metrics` | Covered by `agentic-workflow ledger report` |
| 9 review/routing skills (engineering, test, documentation, security, spec-reconciliation, dependency-evaluation, dependency-migration, database-migration, model-routing) | Done (`agentic-*`) |
| `docs/policies/*.md` (7) and `docs/engineering/workflow.md` (risk and review matrix) | Done (`templates/policies/`); LoreForge specifics move to its `docs/policies/project/` (see below) |
| `docs/agents/issue-tracker.md`, `triage-labels.md` | Done as policies; `docs/agents/domain.md` stays project-owned |
| `.github/pull_request_template.md` | Done as a copy-once template (GitHub reads it from the default branch, so it cannot be ignored) |
| `AGENTS.md` generic sections | Done in `templates/AGENTS.md` (copy-once; agents load it automatically, so it stays committed) |
| `.specify/memory/constitution.md` | Project-owned; Spec Kit supplies the template |
| `THIRD_PARTY_NOTICES.md` | Done: covers the upstream excerpts in `tools/spec-kit/*.patch` |
| CI running the workflow tests | Done: `.github/workflows/ci.yml` (systemd, Codex sandbox and Spec Kit CLI tests skip there; run them locally before a release) |
| `specs/PRODUCT-SPEC.md` and `specs/TECHNICAL-SPEC.md` in English (both were mostly French) | Done |
| `dependabot.yml` (patch grouping), `ci.yml` PR-title job | Done as copy-once templates (`templates/github/`); this repository uses both |
| Ruff `ALL` configuration | Done for this repository (`pyproject.toml`) |
| `ci.yml` check job, `acceptance.yml`, Release Please, Docker release, `docs/agents/domain.md`, domain skills | Project-owned (stack- or product-specific); not backported |

## LoreForge content that moves to `docs/policies/project/`

The generic policies dropped these LoreForge specifics; the cleanup PR writes them to LoreForge's `docs/policies/project/`:

- `security.md`: campaign membership and GM/player permissions as the confidentiality boundary; Visibility fail-closed rules; vault paths; editor commands as JSON argument arrays; Foundry, Discord recording consent and MCP bounds.
- `testing.md`: the critical-evidence list (GM-only inference, cross-campaign access, grant/Visibility revocation, resource IDs across renames, unsafe paths, unchanged campaign sources, failed migrations), PostgreSQL and browser/API seams, Foundry qualification, `./scripts/check` and `./scripts/verify`, generated API check.
- `dependencies.md`: `uv.lock` and the two pnpm lockfiles, Dependabot groups, the `@hey-api/openapi-ts` prerelease exception and its audit findings (#91).
- `migrations.md` and `observability.md`: PostgreSQL/Alembic, the release-process migration gate, campaign IDs.
- `workflow.md`: the R2 list (Visibility, player/GM boundary, Foundry writes, Discord recording/consent), `uv sync`/`pnpm` install commands, the `check`/`verify` gates and CI behavior.
- `engineering.md`, `documentation.md`: `CONTEXT.md` and `docs/v1-architecture.md` as the domain and architecture references.
- `spec-kit-workflow.md`: the architecture areas (core/domain, Foundry, Discord, CLI/TUI, web/API, AI providers, retrieval and vault, transcription, translation, persistence, infrastructure) and that M1, M2, ... are Epics.
- Skills: `security-review` and `database-migration` lose their Visibility, campaign and Alembic specifics; the project files above restore them.

## Intake markers on LoreForge issues

The intake helper's retry-safe GitHub markers are now `<!-- agentic-intake: ... -->`. The helper no longer recognizes LoreForge's existing `<!-- loreforge-intake: ... -->` markers, so retrying a half-finished intake could create a duplicate child. Before migrating, finish any intake in progress; then either leave old markers (completed setups are never retried) or rewrite them on open issues.

## Risks

- Artifact postconditions (#104) are the most valuable piece and the easiest to break while renaming. Move the tests first and keep them green on every rename step.
- Some LoreForge worktrees have Spec Kit installed from the primary checkout (`_matching_primary`). After cleanup, the new fingerprint forces one reinstall per worktree.
- Symlinks from `.claude/skills` to `.agents/skills` must be created by the installer, because they are ignored and no longer committed.
- One `agentic-workflow` launcher is installed per machine, but projects may pin different standard versions. A launcher from one version may misjudge another project's inputs. **Fixed (2026-10-01)** with the version-manager shim pattern (Gradle wrapper, rbenv, Volta): `tools/agentic-workflow` is installed once per machine. `setup` fetches the pinned version into `$XDG_DATA_HOME/agentic/standard/<ref>/`; every other command runs that version's launcher and refuses an unfetched one. The repository is fixed in the shim, so a project picks a version, never a source. `agentic.toml` is a trusted input, so an agent that changes the pin is refused by the launcher's baseline check.
- `tools/setup` rewrites `.specify/` and `.agentic/`, so every real reinstall needs a fresh `agentic-workflow trust`. **Decided:** keep trust a manual, reviewed step; setup never trusts on its own. Setup ends by telling the operator to review and run `trust`, and the launcher's refusal names `trust` as the fix.
