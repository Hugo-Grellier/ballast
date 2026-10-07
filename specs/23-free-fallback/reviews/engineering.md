# Engineering review: local zero-cost fallback (#23)

- Review: engineering. Agent-provisional, run during the operator's human-gated continuation of Autonomous run `f200c320` (not human approval).
- Reviewer: claude/claude-sonnet-5-5, driving agent; the implementation came from an earlier session of the same provider family (reduced independence).
- Method: `.agents/skills/ballast-engineering-review/SKILL.md` and `docs/policies/engineering.md`; `spec.md` (FR-001 to FR-011, AC-001 to AC-021), `plan.md`, `research.md`, the contracts, `decisions.md` (DEC-0001 to DEC-0004), ADR-0014 and the diff from `origin/main` (`fallback.py` new, `agent.py` +476, `autonomy.py`, `ledger.py`, `artifacts.py`, `run.py`), traced through the wrapper's callers, the run record and the ledger.
- Constitution and architecture: BL-INV-002, BL-INV-003, BL-INV-005 and BL-INV-006, ADR-0003, ADR-0004 and ADR-0010. A new ADR is required and present (ADR-0014, proposed).

## Behavior and boundaries checked

- **Control flow.** `agent.main` runs the primary, classifies it (`fallback.classify`: exit code, blocking, containment and the output tail), and calls `_fallback_step` only for a recoverable cause on the first attempt of the step. A draft-retry attempt records its cause and never falls back; a fallback is never retried. A missing primary CLI becomes a `cli-unavailable` cause instead of an early return only when the setting is on, so the off path is byte-for-byte today's (`test_setting_off_matches_today`).
- **Decision order.** State evidence, then the probes in the order of research R5 under one 10 s budget, then the exact permission comparison; each refusal returns the primary's exit code, writes one `route` event and the primary's step entry, and sends nothing.
- **Reuse, no duplicated authority.** The second attempt is `_attempt_in(route=...)`, the same function as the primary, so scope, subreaper, bubblewrap, tamper checks, draft snapshots and the step counter are not re-implemented. The fallback uses its own trusted `codex` (`autonomy.trusted_program`), never a checkout path.
- **Durable identity and idempotency.** Ledger events carry fixed IDs (`fallback:<step>:<attempt>:<kind>`), so a repeat adds nothing; `route` and `usage` sources are `runner` and `client-counter`, as the ledger requires. The step entry gains `failure_cause` and `fallback` fields that readers accept.
- **Composition with the per-CLI credentials of #89.** The fallback calls `confined_argv(integration="codex")` with `CODEX_HOME` set to the private home, so only Codex's homes get the throwaway overlay and the Claude homes are emptied; pinned by `ConfinementCompositionTests`. A Claude-primary run's fallback step therefore sees no Claude login.
- **Failure behavior.** A Git or `lstat` error, an unreadable entry, more than 200,000 ignored entries, a probe timeout or an unknown answer refuses; an unparsable `--json` stream fails the attempt; a timeout (3600 s human-gated, the remaining wall time Autonomous) ends it as `incomplete`; ledger write failures are reported, never raised, so the step's own result stands.
- **Compatibility.** Ledger schema stays 1 with additive optional fields and enumerated values; `ledger report` counts a review completed by the fallback as not cross-provider in Autonomous and human-gated runs; `render_record` adds a line only when the operator set the setting.

## Findings

- F-001 (low, spec-ambiguity): `plan.md`, `tasks.md` and the run record call the ADR ADR-0012; the number was taken before the plan was written, and the file is `docs/adr/0014-local-zero-cost-fallback.md`, whose header says so. The plan and tasks are digest-bound to the reviews already recorded, so they are not edited here.
- F-002 (low, implementation-bug): `privacy-exclusion` for an endpoint override is unreachable through the wrapper, since the fallback environment is built without the variables. It remains as a defense in depth and is tested at the probe. The policy text claimed the wrapper refuses on `OLLAMA_HOST`.
- F-003 (low, spec-ambiguity): stock `qwen3:4b` shows no `num_ctx` in `/api/show`, so the refusal reads `served context unknown`, not `below 16384`. Safe and consistent with DEC-0004.
- F-004 (low, architecture issue): `agent.py` grows by about 480 lines and keeps several `noqa` complexity markers (`_fallback_step`, `_attempt_in`). The function is one linear decision, the module already carried the same style, and splitting it now would duplicate the primary path. Accepted.
- F-005 (info, spec-ambiguity): the 546 s and 210 s CPU completions for a trivial prompt show a real planning step may time out or miss its postconditions; the step then fails with both attempts recorded, as the ADR states.
- F-006 (high, implementation-bug), from the security review: the operator's proxy variables reached Codex. Fixed; see [security.md](security.md) F-001 and F-002 and the blackhole environment (`fallback.BLACKHOLE`).

## Resolution

- F-001: accepted; the ADR names the renumbering.
- F-002: fixed in the policy text (the wrapper removes the variables; the refusal covers a survivor). No code change.
- F-003: accepted; the policy says `below 16384 or unknown`.
- F-004, F-005: accepted.
- F-006: fixed test-first (`PermissionTests.test_extra_env_refused`, `InvocationTests.test_fallback_env`); the two live reruns confirm the step still completes on the local model.

- Verdict: approved
