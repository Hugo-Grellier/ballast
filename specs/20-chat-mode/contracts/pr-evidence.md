# Contract: Chat publication and PR evidence

`ballast run publish RUN` for a `ballast-chat` run. The publisher is `autonomy.publish`, made mode-aware. It is never called by an agent, and it never merges, marks the PR ready, releases or deploys.

## Preconditions

1. No active step, and no tamper or `in-progress` marker (the launcher already refuses both).
2. The `final` human approval is current: the tree digest equals the approved digest.
3. The project-checks result for that tree passed, or is recorded `unavailable`.
4. The branch is the pinned branch and the remote matches `[github] repository` (existing publisher checks).

A failed precondition is recorded as a `refusal` and exits 2. A forge or permission failure exits 1. A later `publish` retries it, as for Autonomous.

## Actions (existing publisher path)

1. Commit, as the operator, the changes since `start_head` that are not yet committed. Hooks and filter drivers are disabled and protected paths are refused. The message follows the existing publisher's format, with the mode named.
2. Push without force from a throwaway repository with an empty configuration to the pinned repository.
3. Create or adopt the feature's single open Draft PR, re-read it and verify it is an open draft to the default branch.
4. Replace only the Chat section between `<!-- ballast:chat:begin -->` and `<!-- ballast:chat:end -->`, re-reading the body just before the edit. A body that changed in the meantime is left alone, and `publish` can be retried.

## Chat section (rendered only from operator records)

```markdown
<!-- ballast:chat:begin -->
## Chat run <run>

Mode: chat (driven by the operator; every gate below was approved by the operator through `ballast run approve`). History: <mode_history lines>.
Feature: specs/<N>-<slug> · Issue #N · branch <branch> · run <run>[ · continues <source> (<mode>)]

### Steps
| Phase | Agent (provider/model, role) | Started | Ended | Outcome | Postcondition |

### Human approvals
| Gate | Artifact | Digest | Decision | Approved at |

### Decisions
| DEC | Status | Human resolution |
<Carried agent-provisional decisions from the Autonomous source, each with "superseded by HD-NNNN" or "still provisional">

### Reviews
| Kind | Reviewer (provider/model) | Cross-provider | Verdict | Report |

### Checks
| Command | Exit | Seconds | Provenance |   (or "No [checks] table: checks unavailable")

### Changes made outside agent steps
<count, and paths up to 50>

Conversation logs and agent logs stay on the operator's machine and are not part of this PR.
<!-- ballast:chat:end -->
```

## Wording rules

- The section is rendered from `run.json`, `steps.jsonl`, `events.jsonl` and `human-decisions.jsonl`. The only agent-derived values are paths, IDs and the verdict enum, all passed through `autonomy.neutralize`.
- Each `gate-approval` row ends with the approval's state: `(current)`, `(stale)` or `(superseded)` by a later decision for the same gate (review finding ENG-003).
- The text "approved by the operator" is allowed only in the fixed header line and in rows rendered from `gate-approval` human decisions. The Autonomous `HUMAN_APPROVAL` guard stays in force for Autonomous bodies. For a Chat body, the guard is applied to every agent-derived value instead.
- Carried Autonomous decisions are always labeled `agent-provisional`, even after a human approval supersedes them; the superseding HD is shown next to them (FR-022).
- The body never contains or links to a conversation log, an agent log or `speckit-runs` content (FR-017).
- When the section would exceed `autonomy.MAX_BODY`, the steps and checks tables fall back to counts plus the latest failure, as the Autonomous renderer does.
