# Plan review: Qualify one zero-cost provider fallback

- Review: plan (independent, agent-provisional). This is the third run of this review. It follows HD-0002, the upstream-sync block at validate-implementation. While the run was blocked, the host pilot (T001) ran and DEC-0002, DEC-0003 and DEC-0004 were recorded and resolved.
- Reviewer: claude/claude-opus-5-5, fresh context. The authoring provider is the same, so independence is reduced.
- Artifacts: `plan.md`, `research.md` (R1 to R10, including the new check 11a), `data-model.md`, `contracts/operator-cli.md`, `contracts/wrapper-fallback.md`, `contracts/ledger.md`, `quickstart.md`, `tasks.md` (only where the decisions changed it), `decisions.md` (DEC-0001 to DEC-0004) and the Pilot section of `evaluation.md`. All were checked against `spec.md`, `intent.md` and the run record. I compared each plan artifact with commit `e5ca07c`, which the previous plan review (PD-0010) assessed. I read the code changes from the implement step (`ledger.py`, `ledger-schema.md`, `templates/policies/model-routing.md`) only for context. The implementation review owns them.
- Policies: the `AGENTS.md` invariants, `docs/policies/workflow.md`, `docs/policies/engineering.md` through the engineering review skill, and the R2 boundaries in `docs/policies/project/workflow.md`.

## What changed since the previous review

During the block, `plan.md`, `research.md`, `quickstart.md`, `tasks.md`, `decisions.md` and one row of `contracts/wrapper-fallback.md` changed:

- **DEC-0004 (served context).** It is propagated consistently:
  - R5 check 11a refuses a model whose `num_ctx` is below 16384 or absent;
  - T037 adds tests before T013 implements the check;
  - `plan.md` states the requirement, and `quickstart.md` names the `qwen3:4b-16k` variant.
- **PD-0010 F-001 (Codex skill missing).** It is closed:
  - R5 check 9 requires `.agents/skills/<command>/SKILL.md` as a regular file inside the worktree, the path pilot item 6 confirmed;
  - the wrapper contract and the quickstart map `test_codex_skill_missing_refuses_capability`;
  - T029 states the prerequisite.
- **DEC-0002.** It changes no plan artifact, as its resolution says.

## DEC-0003 was resolved but not carried into the plan

DEC-0003's resolution chose option 1:

- the fallback talks only to `127.0.0.1:11434`;
- `--local-fallback-endpoint` is dropped;
- `CODEX_OSS_BASE_URL` and `CODEX_OSS_PORT` stay stripped.

Pilot item 2 shows that no `--config` key can pin the base URL of the built-in `ollama` provider. Codex refuses `model_providers.ollama.*` and exits 1. The option text itself says that `contracts/operator-cli.md` and R4, R5 and R6 change. None of these artifacts changed during the block:

- **`research.md`**:
  - R4 still defines `--local-fallback-endpoint URL`;
  - R6 still builds the fallback argv with "a `--config` that pins the Ollama provider's base URL to the setting's endpoint";
  - R6's rationale still relies on "overriding the base URL on the command line";
  - R10 item 1 still asks the pilot for that key.
- **`contracts/operator-cli.md`** still documents:
  - the option on `start` and `resume`;
  - its validation messages;
  - the printed `at ENDPOINT`.
- **`data-model.md`** keeps `endpoint` as a validated, operator-settable field.
- **`contracts/wrapper-fallback.md`** keeps `write_setting(…, endpoint)` and `validate_endpoint`.
- **`tasks.md`** still requires:
  - in T010's tests, `fallback_argv` with "the pinned base-URL `--config`";
  - in T012, "with the `--config` key recorded in T001";
  - the endpoint option in T026 and its tests in T024;
  - the endpoint option in T029's documentation;
  - in T006 and T007, a `validate_endpoint` that accepts any `127.0.0.0/8` literal and port.

An implementer who follows these tasks has two choices, and both are wrong:

- Add a `--config` key. Codex then refuses the argv, so the fallback can never complete and AC-001 to AC-004 cannot pass.
- Skip the key. Then the probes check the operator's endpoint, for example `127.0.0.2:9999`, while Codex sends the prompt to the default `127.0.0.1:11434`. The model on that server never went through checks 6 to 8 and 11a. If that server lists the same name as a cloud or remote model, repository content could leave the machine even though every probe passed. That would break AC-006 and FR-004.

This is a plan-level contradiction with an accepted decision on an R2 boundary. The plan needs an update before implementation continues. The draft records it.

## Other pilot results not carried into the plan

DEC-0003 item 3 lists five smaller findings "for the plan":

- Check 7 already uses the `/api/tags` entry.
- The `--json` error items fit R7's rule (fail closed on an unparsable stream) and do not need a change.
- The Ollama minimum version is no longer reachable on this host, but R5 check 6 still does not record it as a refusal.
- **Widening flags.** `codex exec` has widening flags that R6 and T012's `permission_mismatch` list do not name: `--approve-for-me`, `--enable`/`--disable`, `--dangerously-bypass-hook-trust`, `--worktree` and `--ignore-user-config`. The test list in T015 (`test_wider_argv_refused`) does not name them either. `--dangerously-bypass-hook-trust` is caught by the `--dangerously-*` prefix. R6 says "any difference refuses", but T012 describes a token denylist. The comparison would be robust only as an exact allowlist of the argv the wrapper builds. The plan should say which one it is.
- **Skill roots outside `CODEX_HOME`.** Pilot item 5 shows that Codex loads skills from `~/.agents/skills`, outside `CODEX_HOME`. Under bubblewrap, the agent-home overlay decides what that directory holds. A human-gated fallback has no overlay, so it reads the user's skill directory. R6 claims that "no user configuration is read". Check 11 covers only configuration layers. Skills are instructions, not tools or sandbox settings, so this does not widen Codex's sandbox. It does make R6's claim inaccurate, and it means the fallback's context differs from the canonical headless Codex step's. The plan should either cover this or state it as residual risk.

## Requirement coverage and anchors

These parts of the earlier review still hold:

- every AC, FR and SC maps to a design element and a planned test;
- the off path is unchanged;
- source authority stays single, with the launcher owning the setting, the wrapper owning attempts and the ledger holding the only record;
- fallback happens only after the first attempt;
- the state evidence covers ignored paths and refs;
- `CODEX_HOME` is private and empty.

The pilot confirms or pins several assumptions:

- the R7 event shape;
- the quota signatures for both CLIs, so AC-001 can be met on a real run;
- that `--oss` needs no login;
- the expected `incompatible-capability` result for Autonomous steps on this host, where `codex_sandbox_nests` is `False`.

The project `.codex/config.toml` is read only for a project that the user configuration trusts, so the private, empty `CODEX_HOME` excludes it.

## Minor consistency gaps

- Check 11a is numbered between 11 and 12. R5 says checks 5 to 11 share the 10 s budget, so it is unclear whether 11a counts against it. T013 places the served-context check eighth in its own list, under the deadline.
- `contracts/wrapper-fallback.md`'s refusal table and `data-model.md`'s decision tree do not list the served-context refusal under `incompatible-capability`.

These are wording gaps, and the tests in T037 pin the behavior.

## Uncertainty

I did not run Codex or Ollama. The pilot evidence is from the operator's host and recorded in `evaluation.md`. On CPU, a trivial prompt took 322 s with the 16k variant. A real Spec Kit step may therefore hit the wall-time limit, and SC-004 accepts that as a refusal with a recorded cause. I did not re-review all of `tasks.md`; the tasks gate judges it.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (high, architecture-issue, accepted-provisionally): DEC-0003 option 1 (fixed default endpoint 127.0.0.1:11434, --local-fallback-endpoint dropped, no base-URL --config key because Codex refuses model_providers.ollama.*) is not carried into research R4, R6 and R10, contracts/operator-cli.md, contracts/wrapper-fallback.md (write_setting endpoint, validate_endpoint), data-model.md (endpoint field) or tasks T006, T007, T010, T012, T024, T026 and T029. Implementing R6 as written gives an argv Codex rejects, so the fallback never completes (AC-001 to AC-004). Dropping only the key means the probes check the operator endpoint while Codex sends to the default one, whose model was never checked for remote or cloud status (AC-006, FR-004). This needs a plan and task update and stops the run for a human.
- F-002 (medium, architecture-issue, accepted-provisionally): DEC-0003 item 3 lists codex exec widening flags that R6, T012's permission_mismatch and T015's test_wider_argv_refused do not name: --approve-for-me, --enable/--disable, --worktree and --ignore-user-config. R6 says any difference refuses, but T012 describes a denylist. fallback_argv is built by the wrapper, so this is defense in depth rather than an open path. The plan should state an exact-argv allowlist comparison and extend the test cases. This can be fixed in the same plan update as F-001.
- F-003 (medium, spec-ambiguity, accepted-provisionally): Pilot item 5 shows that Codex loads skills from ~/.agents/skills, outside CODEX_HOME. A human-gated fallback has no agent-home overlay, so it reads the user's skill directory, while R6 claims that no user configuration is read and check 11 covers only configuration layers. Skills are instructions, not sandbox or tool settings, so the sandbox does not widen. The plan should either cover this root (for example, refuse when it is non-empty for a human-gated step) or record it as residual risk.
- F-004 (low, spec-ambiguity, open): Check 11a sits outside the stated budget of R5 checks 5 to 11, but T013 runs it under the 10 s deadline. The wrapper-fallback.md refusal table and the data-model.md decision tree do not list the served-context refusal, and R5 check 6 does not record the Ollama minimum version (0.13.4) that DEC-0003 item 3 noted. These are wording gaps; T037 pins the served-context behavior.
<!-- ballast-findings: end -->

## Resolution

Updated by the driving agent after the run blocked at `record-plan-review`. These changes are agent-provisional. `spec.md`, `intent.md` and `autonomous/record.md` are unchanged.

### F-001 (high): DEC-0003 option 1 carried through the plan

- **Decision applied**: the fallback uses only Ollama's default endpoint `127.0.0.1:11434`, the constant `OLLAMA_ENDPOINT`. There is no `--local-fallback-endpoint`, no `endpoint` setting field and no base-URL `--config` key. The probes and Codex use the same endpoint, so a probe cannot check a server Codex will not use. The wrapper still strips `CODEX_OSS_BASE_URL`, `CODEX_OSS_PORT` and `OLLAMA_HOST`.
- **`research.md`**: R1 names the fixed endpoint. R4 drops the option and validation and explains why. R5 check 5 now asserts the fixed endpoint and that no override variable survives in the built environment (`privacy-exclusion`). R6 removes the base-URL `--config` and its rationale. R10 item 1 records that the key does not exist.
- **`contracts/operator-cli.md`**: no endpoint option on `start` or `resume`; the printed line names `127.0.0.1:11434`; the option is refused.
- **`contracts/wrapper-fallback.md`**: `write_setting` has no endpoint argument, `validate_endpoint` is removed, `fallback_argv` takes the model, and the HTTP and refusal tables name the fixed endpoint.
- **`data-model.md`**: the `endpoint` field is gone and a file carrying one is invalid; the decision tree shows the override-variable refusal.
- **`plan.md`** (summary, ADR text, repository impact) and **`quickstart.md`** (AC-006 row) follow.
- **`tasks.md`**: T006 (`test_setting_has_no_endpoint` replaces the endpoint validation), T007 (constants, no `validate_endpoint`), T010, T012 (no base-URL key in `fallback_argv`), T013 (check 1), T024 (the option is refused), T026, T029, the header risk line, T001's done note and the closing note. No `-c model_providers.ollama.*` key appears in any argv.

### F-002 (medium): exact-argv allowlist

- `research.md` R6 and `contracts/wrapper-fallback.md` define `permission_mismatch(argv, env, codex_home, *, codex, prompt, model)` as an exact comparison: the inner Codex argv must equal `fallback_argv(...)` token for token, and the environment must equal what `fallback_env` builds. Any added, removed, reordered or changed token refuses. No token list needs to be kept current.
- R6 names `--approve-for-me`, `--enable`/`--disable`, `--worktree`, `--ignore-user-config`, `-p`/`--profile`, `--ignore-rules`, `--strict-config`, `--dangerously-bypass-hook-trust` and the earlier widening flags as test cases.
- `tasks.md` T012 states the allowlist. T015's `test_wider_argv_refused` has one case per flag, plus removed, reordered and changed-model cases and an unlisted future flag, and a new `test_endpoint_override_env_refused`. `quickstart.md` AC-008 follows.

### F-003 (medium): user skills outside `CODEX_HOME`

- **Option chosen**: refuse. Running Codex with a scratch `HOME` would also move the Git, bubblewrap overlay and systemd paths the step uses, and needs its own pilot.
- `research.md` R5 check 11 and a new R6 "User skills" paragraph: when `~/.agents/skills` in the operator's home is non-empty, a symlink or unreadable, the fallback refuses with `permission-mismatch` (detail `user skills directory is not empty`). The check applies to both modes, and the project's own `.agents/skills` is unaffected. R6's "no user configuration is read" now says "no user configuration file".
- `contracts/wrapper-fallback.md` (refusal table and flow note), `data-model.md` (decision tree) and `plan.md` (summary, ADR text) follow.
- `tasks.md`: T013 item 7 implements the check, T015 adds `test_user_skills_dir_refuses` (non-empty, symlink, unreadable refuse; absent and empty pass, in both modes), and T029 documents it. `quickstart.md` AC-008 maps it.

### F-004 (low): wording gaps closed

- The 10 s budget covers checks 5 to 11 and 11a (`research.md` R5, `contracts/wrapper-fallback.md`, `tasks.md` T013).
- The served-context refusal (`served context below 16384` or `unknown`) is in the `incompatible-capability` row of the wrapper-fallback refusal table and in the `data-model.md` decision tree. `plan.md` lists the check in its summary.
- R5 check 6 records the Ollama minimum 0.13.4 (`MIN_OLLAMA_VERSION`): an older or unparsable version refuses as `incompatible-capability`. T037 gains `test_old_ollama_refuses_capability` before T013 implements it, and the quickstart AC-007 row maps it.
