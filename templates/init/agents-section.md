
## Ballast workflow

This repository uses Ballast. `ballast.toml` pins the standard; `ballast setup` installs its policies and skills under git-ignored paths.

- Issues and specs: apply the [scope gate](docs/policies/spec-kit-workflow.md#scope-and-decomposition-gate) before specifying, and follow the [Spec Kit workflow](docs/policies/spec-kit-workflow.md) for features, bug fixes and assessments. For `Start #N`, `Fix #N`, `Investigate #N` or `Continue #N`, use the [feature-intake skill](.agents/skills/ballast-feature-intake/SKILL.md).
- Risk and review: classify the change with the [risk and review matrix](docs/policies/workflow.md); each installed policy also reads `docs/policies/project/<name>.md` when it exists.
- Runs: start and resume feature runs only through `ballast run`; if it refuses, stop and report why. The operator's agent session (outside any step) runs the commands that carry no decision and relays decisions only within the run's autonomy, with `--relayed-by SESSION`: an approval only in a Chat run after the operator's yes in chat, a resume of a block that carries a decision only with `--ref` naming the operator's answer. `ballast run reject`, `resolve` and `mode` stay at the operator's terminal. See [Agent sessions](docs/policies/spec-kit-workflow.md#agent-sessions-and-relayed-decisions).
- Trust: a change merged on the pinned repository's default branch refreshes trust automatically; anything else needs a review of the protected inputs (`ballast.toml`, `.specify/`, `.ballast/spec_workflow/`) and `ballast trust`, which the operator, or the operator's agent session on a checkout it set up, runs outside any step. An agent inside a step never runs it.
- Read the [constitution](.specify/memory/constitution.md) when planning a significant feature or checking a conflict.
