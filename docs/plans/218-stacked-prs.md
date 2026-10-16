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
child head (stale child: rebase first). The PR base is the claim's `base`, so a
child PR targets the parent branch. When the claim is part of a stack (parent
links over local claims, root first), `publish` appends a `## Stack` section
listing the merge order to the body, and on reuse of the existing PR rewrites
its body with `gh pr edit --body-file` so every PR carries the current order.

## Retarget after the parent merges

`coordinate.py retarget --claim CHILD --evidence TEXT`:

1. Requires the coordinator, a valid child claim, its parent claim, the parent's
   recorded PR and GitHub reporting that PR merged (no local record decides).
2. Requires the parent's base pushed and fetched, the parent's merged head
   contained in the child, and no worker lock on the child.
3. Rebases `--onto` the parent's base revision from the parent's merged head
   (works for squash merges); a conflict aborts the rebase and refuses.
4. Records the new base and base revision, drops `parent`, decrements
   descendants' `stack_position`, and adds a `retargeted` milestone with the
   heads before and after.
5. Edits the child PR base on GitHub when the child already has one.

The new head invalidates review and checks: `publish` already requires a
completed review of the exact head, and CI runs on the new push. The coordinator
pushes the rebased head, reviews it, and publishes again.

## Merge order rule

Merge the stack root first, then retarget the next child, re-review, re-check,
and merge it; never merge a child whose base is still a parent branch.

## Tests

Stacked preparation and its record; refusals for a missing, foreign
(other branch), settled or already-stacked parent; publication base and stack
section on create and reuse; refusal on a merged or advanced parent; retarget
after GitHub reports the merge, including the invalidated review; refusals while
the parent is unmerged, while a worker lock exists, and on conflict; overlap
suggestions and malformed planned input.
