# Data model: Autonomous stop rule

This feature adds no stored data, schema or runtime state. Its "entities" are the concepts ADR-0020 defines; sibling leaves #151–#154 give them a runtime form. The required statements are in [contracts/adr-0020.md](contracts/adr-0020.md).

| Concept | Defined by | Runtime form delivered by | Rules ADR-0020 fixes |
| --- | --- | --- | --- |
| Stop rule | ADR-0020 Decision | #151 (clarify, decide), #153 | A run blocks only for a decision that takes effect before merge (run authority, launcher execution, external writes, credentials) or a contradiction with a runner-enforced invariant. |
| Material provisional decision | ADR-0020 Decision | #151 | A decision that would previously have stopped the run; agent-provisional (BL-INV-006); listed at the top of the PR. Counts toward the cap. |
| Trusted author | ADR-0020 Decision | #152 | Named only in operator-controlled data, never in the Issue or an agent-writable file. An Issue by a trusted author stands in for `ready-for-agent`; other eligibility rules are unchanged. An untrusted author without the label is still `ineligible`. |
| Limit outcome | ADR-0020 Decision | #153 | Any run limit (agent steps, wall time, fix cycles, draft retries, the cap), in any phase, publishes a Draft PR listing open findings and failed checks, every unmet criterion `unverified`. A Draft PR is never merged without the operator. |
| Usage-limit self-resume | ADR-0020 Decision | #154 | Runner resumes once the provider limit resets; records a runner event naming the block, never a human decision; mode, risk, limits and integrations unchanged. |
| Material-decision cap | ADR-0020 Consequences | #151, #153 | Runner-enforced bound per run; reaching it gets the limit outcome with the reason "cap reached". Value and configuration left to the leaves. |

## State transitions (authorized, not implemented here)

```text
active ──decision with no safe default──▶ active   (material provisional decision; was: stopped/decision)
active ──any limit reached─────────────▶ completed → Draft PR, unmet criteria unverified   (was: stopped/limit)
active ──provider usage limit──────────▶ stopped ──limit resets, runner event──▶ active   (was: operator block-resolution)
active ──pre-merge authority or invariant▶ stopped   (unchanged)
```

Chat runs have no provisional decisions and are outside every transition above (ADR-0009, unchanged).
