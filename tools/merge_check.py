"""Check the ADR-0026 R0 merge precondition; merge only with --merge."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# Direct isolated invocation loads only this operator-selected source tree.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import admission, worktree

SHA = re.compile(r"[0-9a-f]{40}")
FIELDS = "number,state,isDraft,headRefOid,headRefName,author,body,changedFiles,files"
# Paths whose change always needs a human merge (ADR-0026).
EXCLUDED_PREFIXES = (".github/",)
EXCLUDED_FILES = {
    "CHANGELOG.md",
    "release-please-config.json",
    ".release-please-manifest.json",
    "version.txt",
    "pyproject.toml",
    "uv.lock",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "requirements.txt",
    "go.mod",
    "go.sum",
    "Cargo.toml",
    "Cargo.lock",
}
EXCLUDED_BRANCHES = ("release-please--", "dependabot/", "renovate/")
TICKED = re.compile(r"(?im)^[ \t]*[-*][ \t]*\[[xX]\][ \t]*(R[012])\b")


def gh(*args: str) -> subprocess.CompletedProcess:
    """Run one bounded gh call; callers decide what a nonzero exit means."""
    return subprocess.run(  # noqa: S603 -- argument arrays, no shell
        ["gh", *args],  # noqa: S607 -- the operator's gh, as in worktree.command
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def read(*args: str) -> object:
    """Parse a gh JSON response; anything unreadable refuses."""
    try:
        return json.loads(gh(*args).stdout)
    except ValueError:
        worktree.fail("GitHub response is unreadable; nothing was merged")


def excluded(path: str) -> bool:
    """Whether a path is a workflow, permission, release or dependency file."""
    name = path.rsplit("/", 1)[-1]
    return path.startswith(EXCLUDED_PREFIXES) or name in EXCLUDED_FILES


def pull_request(pr: object, number: int, head: str) -> None:
    """Refuse a PR that is not an open, ready, R0-ticked PR at the reviewed head."""
    if not isinstance(pr, dict) or pr.get("number") != number:
        worktree.fail("Pull request response is malformed")
    if pr.get("state") != "OPEN":
        worktree.fail("The PR is not open")
    if pr.get("isDraft") is not False:
        worktree.fail("The PR is a draft")
    if pr.get("headRefOid") != head:
        worktree.fail("The PR head differs from the reviewed head")
    branch, author = pr.get("headRefName") or "", pr.get("author") or {}
    if branch.startswith(EXCLUDED_BRANCHES) or author.get("is_bot") is not False:
        worktree.fail("Release and dependency PRs need a human merge")
    if TICKED.findall(pr.get("body") or "") != ["R0"]:
        worktree.fail("The PR body must tick R0 and no other risk")
    files = pr.get("files")
    if not isinstance(files, list) or len(files) != pr.get("changedFiles"):
        worktree.fail("The changed file list is incomplete")
    if any(excluded(str(item.get("path"))) for item in files):
        worktree.fail("The PR changes a workflow, release or dependency path")


def check(repo: str, number: int, head: str, verdict: str, risk: str) -> dict:
    """Refuse unless every R0 merge precondition holds on the reviewed head."""
    if verdict != "approved":
        worktree.fail("The independent review did not approve this head")
    if risk != "R0":
        worktree.fail("The reviewer did not confirm R0; a human merges this PR")
    if not SHA.fullmatch(head):
        worktree.fail("The reviewed head is not a full commit SHA")
    target = f"github.com/{repo}"
    pull_request(
        read("pr", "view", str(number), "--repo", target, "--json", FIELDS),
        number,
        head,
    )
    checks = read(
        "pr", "checks", str(number), "--repo", target, "--required", "--json", "bucket"
    )
    if not isinstance(checks, list) or not checks:
        worktree.fail("No required checks are reported for the PR head")
    if any(item.get("bucket") != "pass" for item in checks):
        worktree.fail("A required check is not green on the PR head")
    command = ["gh", "pr", "merge", str(number), "--repo", target, "--squash"]
    return {"merge": [*command, "--match-head-commit", head]}


def parser() -> argparse.ArgumentParser:
    """Reviewer evidence comes from the pair review of this exact head."""
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument("--repo", required=True)
    root.add_argument("--pr", type=int, required=True)
    root.add_argument("--reviewed-head", required=True)
    root.add_argument("--verdict", required=True)
    root.add_argument("--risk", required=True, help="risk the reviewer confirmed")
    root.add_argument("--merge", action="store_true", help="perform the merge")
    return root


def run(args: argparse.Namespace) -> dict:
    """Check, then merge only on explicit request."""
    if worktree.inside_checkout():
        worktree.fail("Run merge checks from the project checkout, not an issue")
    result = check(args.repo, args.pr, args.reviewed_head, args.verdict, args.risk)
    if args.merge:
        # --match-head-commit makes GitHub refuse a head that moved since the check.
        if gh(*result["merge"][1:]).returncode:
            worktree.fail("GitHub refused the merge; nothing else was attempted")
        result["merged"] = True
    return result


def main() -> int:
    """Print the merge command, or the fixed reason the merge is refused."""
    try:
        result = run(parser().parse_args())
    except admission.FixedReasonError as error:
        sys.stderr.write(f"Merge refused: {error}\n")
        return 1
    except (OSError, subprocess.SubprocessError, AttributeError, TypeError) as error:
        sys.stderr.write(f"Merge refused: {type(error).__name__}\n")
        return 1
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
