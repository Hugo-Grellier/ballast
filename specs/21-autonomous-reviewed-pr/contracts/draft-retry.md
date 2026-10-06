# Contract: correctable draft retries in the agent wrapper

Applies only to Autonomous agent steps (an active `ballast-autonomous` run record). Human-gated agent steps are unchanged.

## Step-to-point map (`artifacts.STEP_POINTS`)

| Command and first argument | Draft points checked |
| --- | --- |
| `speckit.ballast.decide <point>` | `<point>` (`scope`, `intent`, `plan`, `tasks`, `final-acceptance`) |
| `speckit.ballast.discover`, `speckit.ballast.clarify` | `clarification` (zero or more) |
| `speckit.ballast.review plan` | `plan-review` |
| `speckit.ballast.review implementation` / `implementation-recheck` | `implementation-review` |
| `speckit.ballast.review specialists` / `specialists-recheck` | `specialist-review` (one or more) |
| `speckit.ballast.review spec-reconciliation` | `spec-reconciliation` |
| `speckit.ballast.resolve` | `decision-resolution` (zero or more) |
| any command that exits 3 | `block.json` (`autonomy.validate_block_draft`) |
| anything else (`speckit.specify`, `plan`, `tasks`, `analyze`, `implement`, `converge`, `speckit.ballast.fix`) | none; no retry |

## Sequence per step invocation

```text
attempt = 1
loop:
  _autonomous_run()           # active? limits? count the step (attempt counts)
  run agent (confined, own scope, own log dir, in-progress marker)
  protected-input check       # tamper -> EXIT_TAMPERED, no retry
  drafts = _created_drafts()
  try: artifacts.check_step_drafts(feature, command, args, step, drafts)
  except DraftError as e:
      append step entry {attempt, refused: msg(e)}
      if attempt == 1 + DRAFT_RETRIES: exit EXIT_LIMIT, reason "draft refused after 2 retries: …", limit "retries"
      move drafts to set-aside/<step>/retry-<attempt>/
      prompt = original + RETRY_NOTE(msg(e), attempt)
      attempt += 1; continue
  append step entry {attempt}
  exit with the agent's code
```

A limit refusal in `_autonomous_run` on a retry exits `EXIT_LIMIT` with the reason `<limit> exhausted after a refused draft: <msg>` and `limit` set to `agent-steps` or `wall-time`.

## Retry note appended to the prompt

```text

Ballast retry <n> of 2: the trusted recorder refused the draft you wrote:
<message>
Write a corrected draft. Keep within the stated limits. Paraphrase and cite
any human approval you rely on; never quote approval wording.
```

`<message>` is the `DraftError` text, made printable and cut to 500 characters. It contains field names, IDs and limits, never draft content.

## Invariants

- `check_step_drafts` calls the same functions as `record_decision` (`_expected_drafts`, `_validate_draft`, `_validate_review`, `_check_narrative`, `_check_dispositions` with the cycle rule, and `validate_block_draft`). No validator is changed or skipped (FR-017).
- Only `DraftError` is retried. Every other exception, a tamper, a limit or an interrupt ends the step as today.
- `_qualifying_steps` ignores entries with `refused`. The recorder takes drafts only from the last attempt.
- The recorder writes `agent.attempts` and `agent.refusals` into each decision it records from that step.
