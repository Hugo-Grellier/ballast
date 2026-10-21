# Stacked PRs for overlapping leaf issues — #218

Risk R2 (claim and publication semantics). Stacking stays an explicit
coordinator choice; GitHub stays authoritative for "parent merged".

## Overlap report

`coordinate.py select --planned FILE` reads a coordinator-supplied JSON object
mapping queue issue numbers to planned entries: `"path"` or `"path::function"`.
No code analysis. Two entries overlap when they name the same file and either
names no function or both name the same one. For every pair of planned issues,
`select` adds an `overlap` entry with the shared entries and a suggestion:
`parallel` (nothing shared), `stack` (shared, and both are eligible now) or
`serialize` (shared, and one of them cannot start now). A malformed file, or a
key outside the queue, refuses the whole call.

## Stacked preparation

`worktree.py --parent P --base BRANCH` prepares a child claim on the parent's
pushed branch. Under the shared lock, after admission, the parent claim must
exist (`issue-P.json`), belong to the same repository and coordinator, have
`branch == BRANCH`, not be settled `merged` or `stopped`, and have no other
stacked child (stacks stay linear). The existing pushed-base check (GitHub ref
equals `origin/BRANCH`) applies unchanged. The claim records
`parent: {issue, attempt}` and `stack_position` (parent position, root 1, + 1).

## Publication

For a claim with a parent, `publish` first rechecks the parent claim (missing or
foreign refuses), refuses when GitHub reports the parent PR merged (retarget
first), and refuses when the parent's pushed head is not an ancestor of the
child head: when the parent's checkout is still at the child's `base_sha`
(restacked by a retarget, not pushed yet), push the parent first; when the
child's `base_sha` is not an ancestor of the parent's pushed head, the parent
was rewritten (fixed refusal below); otherwise the parent only gained commits
(stale child: rebase first, which keeps `base_sha` in its history). The PR base is the claim's `base`, so a
child PR targets the parent branch. When the claim is part of a stack (parent
links over local claims, root first), `publish` appends a `## Stack` section
listing the merge order to the body, and on reuse of the existing PR rewrites
its body with `gh pr edit --body-file` so every PR carries the current order.

## Retarget after the parent merges

`coordinate.py retarget --claim CHILD --evidence TEXT`:

1. Requires the coordinator, a valid child claim, its parent claim, the parent's
   recorded PR and GitHub reporting that PR merged (no local record decides).
2. Requires the parent's base pushed and fetched and the parent's merged head
   contained in the child. Under the shared lock, the child and every later
   stack member must have no worker lock and no open coordinator execution
   (one writer per checkout).
3. Rebases `--onto` the parent's base revision from the parent's merged head
   (works for squash merges), then restacks each later member from its parent's
   old head onto its parent's new head. A conflict aborts that rebase, resets
   the checkouts already rebased and refuses with no record changed.
4. Records the new base and base revision, drops `parent`, decrements
   descendants' `stack_position`, sets each descendant's `base_sha` to its
   parent's new head (so `validate` keeps accepting it and the next retarget
   finds the parent's merged head in it), and adds `retargeted` / `restacked`
   milestones with the heads before and after. A child with a PR also gets
   `retarget_pending`.
5. While `retarget_pending` is set, reads the child PR's base on GitHub, edits
   it only when it differs, then clears the flag. A retry after a failed or
   lost edit skips steps 1-4 and only does this.

The new head invalidates review and checks: `publish` already requires a
completed review of the exact head, and CI runs on the new push. The coordinator
pushes the rebased head, reviews it, and publishes again.

## Never rewrite a stacked parent

A stacked parent's pushed branch must not be rewritten (amend, rebase onto a
moved base, force-push) while a child is stacked on it: rebasing the child onto
the rewritten branch drops the child's recorded `base_sha` from its history,
after which `validate`, `worker`, `publish` and `retarget` all refuse the claim
with no recovery. So when the child's `base_sha` is not an ancestor of the
parent's pushed head (`publish`) or of the parent's merged head (`retarget`),
both refuse with one fixed reason: the stacked parent branch was rewritten,
stacked parents must never be rewritten, settle the child `stopped` and prepare
a new child on the parent's current head. It never advises rebasing the child
in place, and the child claim stays valid because nothing rewrote it. The only
helper path that rewrites a parent is `retarget`, which restacks every later
member and records each new `base_sha` under the same lock, so no helper needs
a parent-side refusal. Restacking a child onto a rewritten unmerged parent
(replaying from its recorded `base_sha`, as `retarget` does for descendants) is
a possible follow-up.

## Merge order rule

Merge the stack root first, then retarget the next child, re-review, re-check,
and merge it; never merge a child whose base is still a parent branch.

## Tests

Stacked preparation and its record; refusals for a missing, foreign
(other branch), settled or already-stacked parent; publication base and stack
section on create and reuse; refusal on a merged, advanced, rewritten or
restacked-but-unpushed parent (the rewritten case also on retarget, with the
child claim still valid); retarget after GitHub reports the merge, including the invalidated review; refusals while
the parent is unmerged, while a worker lock or coordinator execution holds the
child or a descendant, and on conflict (child or descendant, every checkout
restored); a failed and a lost PR-base edit each followed by a retry; a
three-PR stack through successive squash merges; overlap
suggestions and malformed planned input.
