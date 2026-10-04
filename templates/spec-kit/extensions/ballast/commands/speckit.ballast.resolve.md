---
description: "Give each open implementation discovery an agent-provisional resolution"
---

# Resolve implementation discoveries provisionally

In the human-gated workflow, each `## DEC-NNNN — Proposal` in `decisions.md` waits for a human. In a `ballast-autonomous` run you give it an **agent-provisional** resolution that the human reviews at merge. Implementation is evidence, not authority.

## User Input

```text
$ARGUMENTS
```

## Steps

1. Read `feature_directory` from `.specify/feature.json`; below, `<f>` is that path. Read `<f>/decisions.md` (if it is missing, there is nothing to do: stop), `<f>/spec.md`, `<f>/intent.md`, `<f>/plan.md`, `<f>/tasks.md` and the review reports.
2. For each proposal without a resolution, decide. If a resolution needs a code change, or no safe and reversible resolution exists, block (below): this run has no fix loop.
3. Append, right after the proposal:

   ```text
   ## DEC-NNNN — Resolution

   - **Status**: agent-provisional
   - **Resolution**: what is decided and why
   - **Material**: yes|no
   ```

   The resolution is **material** when it changes product behavior, scope, data authority, a security boundary or accepted architecture. You may update `<f>/spec.md`, `<f>/plan.md` and `<f>/tasks.md` to apply an accepted resolution; never change code or tests.
4. For each resolution write `<f>/autonomous/drafts/decision-resolution-<NNNN>.json`, where `<NNNN>` is the DEC number:

   ```json
   {
     "point": "decision-resolution",
     "decision": "resolve",
     "summary": "DEC-NNNN: one line resolution",
     "basis": "Why this resolution is safe before merge review",
     "evidence": ["<f>/decisions.md"],
     "artifact": "<f>/decisions.md",
     "model": "<your model name>",
     "material": false,
     "supersedes": null,
     "privileged_actions": [],
     "review": null,
     "assumption": null
   }
   ```

   Set `material` exactly as in the resolution record. The recorder rewrites the status line with the decision ID it records.

## Block

Write `<f>/autonomous/drafts/block.json` as described in `speckit.ballast.decide` (`decision` or `contradiction`, at least two options with consequences, `no_safe_default` for a `decision`), print exactly `RECONCILE_STATUS: BLOCKED_DECISION` and stop.

## Never

- Change code, tests, `<f>/autonomous/record.md`, the blocks in `<f>/intent.md`, `.specify/`, `.ballast/` or `ballast.toml`.
- Write that anything was "approved by" a human or call it "human-approved".
- Ask the operator a question.
