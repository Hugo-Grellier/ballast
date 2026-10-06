
## Ballast workflow

This repository uses Ballast. `ballast.toml` pins the standard; `ballast setup` installs its policies and skills under git-ignored paths.

- Issues and specs: apply the [scope gate](docs/policies/spec-kit-workflow.md#scope-and-decomposition-gate) before specifying, and follow the [Spec Kit workflow](docs/policies/spec-kit-workflow.md) for features, bug fixes and assessments. For `Start #N`, `Fix #N`, `Investigate #N` or `Continue #N`, use the [feature-intake skill](.agents/skills/ballast-feature-intake/SKILL.md).
- Risk and review: classify the change with the [risk and review matrix](docs/policies/workflow.md); each installed policy also reads `docs/policies/project/<name>.md` when it exists.
- Runs: start and resume feature runs only through `ballast run`; if it refuses, stop and report why. Every gate needs `ballast run approve` from the operator's terminal.
- Trust: only the operator reviews the protected inputs (`ballast.toml`, `.specify/`, `.ballast/spec_workflow/`) and runs `ballast trust`. An agent never runs it.
- Read the [constitution](.specify/memory/constitution.md) when planning a significant feature or checking a conflict.
