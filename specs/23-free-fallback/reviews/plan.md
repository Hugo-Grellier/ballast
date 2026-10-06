# Plan review: Qualify one zero-cost provider fallback

- Review: plan (independent, agent-provisional). This is the fourth run of this review. It follows HD-0003 in the run record: the run stopped at `record-plan-review` on the third review, and the driving agent then updated the plan artifacts in commit `8d14f2a`.
- Reviewer: claude/claude-opus-5-5, fresh context. The authoring provider is the same, so independence is reduced.
- Artifacts: `plan.md`, `research.md` (R1, R4, R5, R6, R10), `data-model.md`, `contracts/operator-cli.md`, `contracts/wrapper-fallback.md`, `quickstart.md`, and `tasks.md` T006, T007, T010 to T015, T024, T026, T029 and T037. I checked them against `spec.md` (AC-006, AC-008, FR-001, FR-004, FR-005, FR-006), `intent.md` (PD-0007), `decisions.md` (DEC-0001 to DEC-0004), the Pilot section of `evaluation.md` and the run record.
- Policies: the `AGENTS.md` invariants, `docs/policies/workflow.md`, `docs/policies/engineering.md` through the engineering review skill, and the R2 boundaries in `docs/policies/project/workflow.md`.
- The findings of this review are in the review draft; the recorder renders them below this narrative.

## Method

I read the diff of `8d14f2a` for the plan artifacts, then searched every plan artifact for a remaining endpoint option, `validate_endpoint`, an endpoint field or a base-URL `--config` key. I compared the public function table and refusal table of the wrapper contract with research R5 and R6 and with the T013 and T015 task text, and followed each changed acceptance row in `quickstart.md` to a named test.

## What the update changed

### Fixed endpoint (DEC-0003)

DEC-0003 option 1 now runs through every plan artifact:

- `research.md` R1 and R4 name the fixed `OLLAMA_ENDPOINT` `127.0.0.1:11434` and drop the option and its validation. R6 builds the argv with no base-URL key and explains why (pilot item 2). R10 item 1 records that the key does not exist.
- `contracts/operator-cli.md` has no endpoint option on `start` or `resume`, prints the fixed endpoint, and states that the option is refused.
- `contracts/wrapper-fallback.md` drops the endpoint argument and `validate_endpoint`. HTTP requests go only to `OLLAMA_ENDPOINT`.
- `data-model.md` has no `endpoint` field, and a file that carries one is invalid.
- `tasks.md` T006, T007, T010, T012, T013, T024, T026 and T029 follow. T024 tests that the option is refused, and the closing note forbids adding it back.

The search found the old wording only in `decisions.md`, `discovery.md` and `evaluation.md`, which are history, and in `spec.md`. The spec does not require an operator-chosen endpoint: FR-001 asks the setting to name the model, and AC-006 and FR-004 ask that the endpoint be loopback. A constant loopback literal, plus the check that no override variable survives in the environment, meets both. The probes and Codex now use the same endpoint, so the probes can no longer check one server while the prompt goes to another.

### Exact-argv comparison

R6, the wrapper contract and T012 define `permission_mismatch` as an exact comparison with the argv that `fallback_argv` builds. T015's `test_wider_argv_refused` names every widening flag from the pilot, plus an unlisted flag and a removed, reordered or changed token.

### User skills directory

R5 check 11, a new R6 paragraph, the refusal table, the decision tree, ADR-0012's text, T013 item 7, T015's `test_user_skills_dir_refuses` and T029 add a `permission-mismatch` refusal when `~/.agents/skills` is non-empty, a symlink or unreadable. The narrower option was chosen, and the reason for not rewriting `HOME` is stated. R6's claim now reads "no user configuration file".

### Budget, served context and Ollama version

Check 11a counts against the 10 s budget. The served-context refusal appears in the refusal table and the decision tree. R5 check 6 refuses an Ollama older than 0.13.4, and T037 tests this before T013 implements it.

## Requirement coverage and boundaries

Every AC, FR and SC still maps to a design element and a planned test in `quickstart.md`, and the changed rows (AC-006, AC-007, AC-008) name existing or newly planned tests. Earlier reviews' anchors still hold:

- the off path is unchanged (`test_setting_off_matches_today`);
- the fallback runs only after the first attempt (DEC-0001);
- the state evidence covers ignored paths and refs;
- `CODEX_HOME` is private and empty;
- the launcher owns the setting, the wrapper owns attempts, and the ledger is the one record.

No boundary widens. The environment allowlist adds nothing beyond `CODEX_HOME`, the argv check is stricter than before, and the user-skills check only adds refusals. Every new check fails closed.

## Uncertainty

I did not run Codex or Ollama. The host facts come from the operator's pilot in `evaluation.md`. On that host, Autonomous steps are still expected to refuse (Codex's sandbox does not nest), and a real CPU step may hit the wall-time limit, which SC-004 accepts as a refusal with a recorded cause. I did not re-review the tasks that the update did not touch, or the implement step's code changes (`ledger.py`, `ledger-schema.md`, the model-routing policy). The tasks gate and the implementation review own those.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (low, spec-ambiguity, open): The contract signature probe(setting, *, root, autonomous, codex, prompt) does not receive the built environment, yet T013 item 1 and research R5 check 5 make the probe refuse an endpoint override variable in that environment as privacy-exclusion, and test_endpoint_override_env_refused expects that reason. permission_mismatch also sees the environment but maps to permission-mismatch. The plan should name the function that owns the check so the expected reason is unambiguous. Either placement fails closed, so no content can leave loopback.
- F-002 (low, missing-test, open): permission_mismatch compares the argv with fallback_argv itself, so at run time it catches drift between building and launching (for example forwarded primary arguments) but not a widening inside permission_args or fallback_argv. Research R6 still claims a later permission_args change cannot widen the fallback silently. test_fallback_argv_is_primary_codex_profile ties the fallback to the primary profile, which is what FR-005 asks; a test pinning the literal fallback token list (workspace-write, network_access=false, writable_roots=[] and the fixed tokens) would make the R6 claim true.
- F-003 (info, spec-ambiguity, open): T037 cites FR-006, but the served-context check belongs to FR-004 (capability). The data-model.md decision tree lists the served-context refusal before the configuration-layer refusal, while R5 and T013 run it last. Traceability and ordering wording only.
<!-- ballast-findings: end -->
