# ADR-0014: Local zero-cost fallback through Codex local-provider mode

- Status: proposed (2026-10-06, with the plan of [feature 23](../../specs/23-free-fallback/plan.md#architecture-boundaries), where it is called ADR-0012 because that number was taken before the plan was written; agent-provisional in Autonomous run `f200c320`, accepted only when the operator merges the feature PR)
- Feature: [23-free-fallback](../../specs/23-free-fallback/spec.md), FR-001 to FR-011, AC-001 to AC-021; research [R1 to R10](../../specs/23-free-fallback/research.md); [decisions.md](../../specs/23-free-fallback/decisions.md) DEC-0001, DEC-0003, DEC-0004; host evidence in [evaluation.md](../../specs/23-free-fallback/evaluation.md)
- Extends: [ADR-0003](0003-launcher-github-authority.md) (trusted programs) and [ADR-0010](0010-autonomous-resume-and-bounded-recovery.md) (limits and retries)

## Context

A headless step stops the whole run when its agent's subscription quota runs out or its provider is unreachable. The operator has a local model on loopback (Ollama) that costs nothing and sends nothing off the machine. Running a step on it changes what the wrapper executes after a failure and sends repository content to a second model, so it touches the R2 boundaries: the headless-agent permission model, the privacy boundary for repository content, and what Ballast executes.

## Decision

- The wrapper (`agent.py`, with `fallback.py`) may make **one** fallback attempt per step on `codex exec --oss --local-provider ollama -m MODEL --json`, against an operator-named, locally installed, non-cloud model at Ollama's default loopback endpoint `127.0.0.1:11434`. The endpoint is a constant: the operator cannot choose another one, because Codex's built-in `ollama` provider refuses a `--config` base URL and the probes must check the server Codex will use (DEC-0003).
- **Conditions.** The operator opted in for the run (`ballast run start|resume --local-fallback MODEL`, stored in the run's operator directory, where no agent can write; never in Chat). The step's **first** primary attempt failed for a recoverable cause: quota exhausted, provider unavailable or CLI missing, recognized from fixed per-integration signatures in the last 64 KiB of the output. A draft-retry attempt never falls back, and a fallback is never retried, so a step that falls back makes exactly two attempts (DEC-0001).
- **Changed-state evidence.** The attempt must have changed nothing: the working-tree digest, the reviews, the drafts, a metadata digest of every git-ignored path (path, mode, size, mtime, ctime, inode, link target; protected inputs excluded) and a digest of `HEAD` and every ref. Any piece that cannot be established (a Git error, an unreadable entry, more than 200,000 ignored entries or more than 10 s) refuses as `changed-state`.
- **Runtime checks before any prompt is sent**, sharing one 10 s budget, each refusing with a fixed reason: no endpoint override in the environment; Ollama answers and is 0.13.4 or newer; the model is listed by exact name with a size and digest; it is neither remote nor cloud; a trusted `codex` supports `--oss` and the project holds Codex's skill for the step; Codex's sandbox starts under the step's own confinement; no Codex configuration layer exists outside the fallback's home and `~/.agents/skills` is empty; the model's served context is at least 16384 tokens (DEC-0004). Only the model name is ever sent to the server before the prompt.
- **Permission comparison.** The fallback argv must equal, token for token, `permission_args("codex", ["exec", prompt])` plus `--oss`, `--local-provider ollama`, `-m MODEL` and `--json`; the environment must be `confined_env` output without endpoint variables, plus `CODEX_HOME` set to a fresh, private, empty directory that is removed afterwards, and no operator proxy variable. Because Codex contacts `github.com` and `chatgpt.com` at start-up even with a local provider and an empty home (live check), the environment also sets `HTTP_PROXY`, `HTTPS_PROXY` and `ALL_PROXY` (both cases) to the closed local port `127.0.0.1:9` and `NO_PROXY` to loopback, so those requests fail and Ollama is reached directly. This is a reduction of egress, not a network boundary: the model request itself carries the prompt only to loopback, and tool processes have no network inside Codex's sandbox. The comparison is an exact allowlist, and a test pins the literal token list so a widening inside `permission_args` fails it.
- The attempt reuses the primary's code path: systemd scope, subreaper, bubblewrap for an Autonomous step, protected-state and tamper checks, draft snapshotting. It counts as an agent step. Every decision is an additive ledger `route` event (`failure_cause`, `fallback`, `fallback_reason`, `route_source: fallback`) with the fallback's `usage`; a review it completes is never counted as cross-provider.

## What it does not add

- No sandbox is loosened, no writable root or network access is added, and no bypass flag is used to make the fallback run (FR-005). A sandbox that does not start refuses.
- No paid or remote backend, no account, no credential, no download by Ballast, no model list, and no environment variable or `ballast.toml` key that enables it.
- No user Codex configuration is read.

## Consequences

- **Host result.** On the qualified host Codex's sandbox cannot start inside Ballast's bubblewrap, so every Autonomous step refuses the fallback with `incompatible-capability`; human-gated steps can use it ([evaluation.md](../../specs/23-free-fallback/evaluation.md#summary)). A 4B CPU model is slow (322 s for a trivial prompt) and may not satisfy a step's postconditions; the step then fails with both attempts recorded.
- **Cost of the state walk.** While the setting is on, every step pays one `lstat` walk of the worktree's ignored paths before and after its first attempt. A worktree whose ignored tree exceeds the cap always refuses; that is a missed fallback, never replayed state.
- **Residual risk.** A process that ignores proxy variables could still reach the network from the Codex CLI itself (start-up requests are observed and blocked by the variables above); the model request's destination is the fixed loopback endpoint. Codex's `--oss` mode pulls a missing model. The probe makes that unreachable unless the model is removed between the probe and the run; the race costs a download, never repository content.
- An operator who keeps personal skills in `~/.agents/skills` must empty it or leave the fallback off.
- A further backend (for example LM Studio) or another endpoint needs a new ADR.

## Rejected alternatives

- Claude Code pointed at Ollama's Anthropic-compatible endpoint: it redirects a paid-provider CLI by environment and needs a credential variable the confinement removes.
- A hosted free tier: remote, account-bound, and its free status and privacy cannot be established at run time.
- An operator-chosen endpoint: Codex cannot be pointed at it without an environment override, so the probes could check a server Codex does not use.
- Loosening either sandbox when Codex's does not nest: forbidden by BL-INV-003.
- A fallback on any attempt: a draft-retry attempt could have left partial state the first attempt's evidence does not cover (DEC-0001).
