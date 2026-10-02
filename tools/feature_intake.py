#!/usr/bin/env python3
"""Inspect a GitHub issue and reconcile one approved intake setup.

The caller owns product classification and human approval. This helper owns
observable GitHub preconditions, bounded writes, and retry behavior.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, NoReturn, cast

MARKER = "<!-- ballast-intake: parent=#{parent}; slug={slug} -->"
SCOPE_MARKER = "<!-- ballast-intake: issue=#{issue}; scope={scope} -->"
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
BLOCKED_TEXT = re.compile(r"(?im)^\s*Blocked by:\s*#([1-9]\d*)\b")
ACCEPTANCE = re.compile(r"(?im)^#{1,4}\s+Acceptance (?:criteria|outcomes)\b")
PAGE_SIZE = 100
MAX_SCOPE = 10000
MAX_BODY = 60000
SHAPE_ERRORS = (TypeError, ValueError, KeyError, AttributeError)


class IntakeError(Exception):
    """A precondition or GitHub operation failed."""


def _fail(message: str) -> NoReturn:
    raise IntakeError(message)


class GitHub:
    """Small GitHub REST client through the authenticated gh executable."""

    def __init__(self, repo: str) -> None:
        """Bind operations to one validated repository."""
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
            _fail("--repo must be OWNER/REPO")
        self.repo = repo
        self.base = f"repos/{repo}"
        self.executable = shutil.which("gh")
        if self.executable is None:
            _fail("gh CLI is unavailable")

    def call(self, *args: str, missing_parent: bool = False) -> object:
        """Call gh without a shell and decode JSON output."""
        result = subprocess.run(  # noqa: S603 - fixed executable and argv, no shell
            [self.executable, *args], capture_output=True, text=True, check=False
        )
        if result.returncode:
            if missing_parent and "No parent issue found" in result.stderr:
                return None
            _fail(f"GitHub command failed: {' '.join(args[:3])}")
        if not result.stdout.strip():
            return None
        try:
            return json.loads(result.stdout)
        except ValueError:
            _fail("GitHub returned invalid JSON")

    def api(self, path: str, *args: str, missing_parent: bool = False) -> object:
        """Call one GitHub REST endpoint."""
        return self.call("api", path, *args, missing_parent=missing_parent)

    def pages(self, path: str) -> list[dict[str, Any]]:
        """Collect a bounded paginated REST list."""
        items: list[dict[str, Any]] = []
        for page in range(1, PAGE_SIZE + 1):
            separator = "&" if "?" in path else "?"
            result = self.api(f"{path}{separator}per_page={PAGE_SIZE}&page={page}")
            if not isinstance(result, list):
                _fail("GitHub returned a non-list page")
            items.extend(cast("list[dict[str, Any]]", result))
            if len(result) < PAGE_SIZE:
                return items
        _fail("GitHub pagination exceeded 100 pages")

    def issue(self, number: int) -> dict[str, Any]:
        """Read and verify an issue number."""
        result = self.api(f"{self.base}/issues/{number}")
        if not isinstance(result, dict) or result.get("number") != number:
            _fail(f"Issue #{number} could not be verified")
        return cast("dict[str, Any]", result)

    def parent(self, number: int) -> dict[str, Any] | None:
        """Return an issue's parent, when one exists."""
        result = self.api(f"{self.base}/issues/{number}/parent", missing_parent=True)
        return cast("dict[str, Any] | None", result)

    def children(self, number: int) -> list[dict[str, Any]]:
        """Return an issue's sub-issues."""
        return self.pages(f"{self.base}/issues/{number}/sub_issues")

    def blockers(self, number: int) -> list[dict[str, Any]]:
        """Return issues that block this issue."""
        return self.pages(f"{self.base}/issues/{number}/dependencies/blocked_by")

    def comments(self, number: int) -> list[dict[str, Any]]:
        """Return all issue comments for scope-marker reconciliation."""
        return self.pages(f"{self.base}/issues/{number}/comments")

    def all_issues(self) -> list[dict[str, Any]]:
        """Return repository issues, including closed items, for retry matching."""
        return [
            item
            for item in self.pages(f"{self.base}/issues?state=all")
            if "pull_request" not in item
        ]


def labels(issue: dict[str, Any]) -> set[str]:
    """Extract issue label names."""
    return {label["name"] for label in issue.get("labels", [])}


def preflight(gh: GitHub, number: int) -> dict[str, Any]:
    """Reject explicit Epic, closed, blocked, or underspecified issues."""
    issue = gh.issue(number)
    parent = gh.parent(number)
    children = gh.children(number)
    blockers = gh.blockers(number)
    textual_blockers = {
        int(value) for value in BLOCKED_TEXT.findall(issue.get("body") or "")
    }
    blocked = {item["number"] for item in blockers if item.get("state") == "open"}
    for blocker in textual_blockers:
        if gh.issue(blocker).get("state") == "open":
            blocked.add(blocker)
    problems = []
    if issue.get("state") != "open":
        problems.append("issue is not open")
    if "epic" in labels(issue) or children:
        problems.append("issue is an Epic or has sub-issues")
    if not ACCEPTANCE.search(issue.get("body") or ""):
        problems.append("issue has no acceptance criteria section")
    if blocked:
        problems.append("blocked by " + ", ".join(f"#{n}" for n in sorted(blocked)))
    return {
        "number": number,
        "title": issue.get("title"),
        "state": issue.get("state"),
        "labels": sorted(labels(issue)),
        "milestone": (issue.get("milestone") or {}).get("title"),
        "parent": parent.get("number") if parent else None,
        "sub_issues": [item["number"] for item in children],
        "blocked_by": sorted(blocked),
        "eligible_leaf": not problems,
        "problems": problems,
    }


def require_leaf(
    gh: GitHub, number: int, expected_parent: int | None
) -> dict[str, Any]:
    """Require one eligible leaf with expected parentage."""
    status = preflight(gh, number)
    if not status["eligible_leaf"]:
        _fail("; ".join(status["problems"]))
    if expected_parent is not None and status["parent"] not in (None, expected_parent):
        _fail(f"issue #{number} already has parent #{status['parent']}")
    return status


def find_child(gh: GitHub, parent: int, slug: str, title: str) -> int | None:
    """Find a unique existing approved child before creating one."""
    marker = MARKER.format(parent=parent, slug=slug)
    linked = gh.children(parent)
    matches = {
        item["number"] for item in gh.all_issues() if marker in (item.get("body") or "")
    }
    matches.update(item["number"] for item in linked if item.get("title") == title)
    if len(matches) > 1:
        _fail("multiple issues match this approved child; resolve manually")
    if matches:
        number = matches.pop()
        issue = gh.issue(number)
        if issue.get("title") != title:
            _fail("existing child marker has a different title")
        return number
    same_title = [
        item["number"] for item in gh.all_issues() if item.get("title") == title
    ]
    if same_title:
        _fail("an unlinked issue has the same child title; resolve manually")
    return None


def create_child(gh: GitHub, parent: int, slug: str, title: str, body: str) -> int:
    """Create a marked child and verify its durable marker."""
    marker = MARKER.format(parent=parent, slug=slug)
    result = gh.api(
        f"{gh.base}/issues",
        "-X",
        "POST",
        "-f",
        f"title={title}",
        "-f",
        f"body={body.rstrip()}\n\n{marker}\n",
    )
    number = result.get("number") if isinstance(result, dict) else None
    if not isinstance(number, int):
        _fail("created child number was not returned")
    if marker not in (gh.issue(number).get("body") or ""):
        _fail("created child marker could not be verified")
    return number


def ensure_parent(gh: GitHub, parent: int, child: int) -> bool:
    """Create a missing parent link and verify it."""
    existing = gh.parent(child)
    if existing:
        if existing.get("number") != parent:
            _fail(f"issue #{child} already has a different parent")
        return False
    child_id = gh.issue(child).get("id")
    if not isinstance(child_id, int):
        _fail("child issue has no numeric ID")
    parent_issue = gh.issue(parent)
    if parent_issue.get("state") != "open" or "epic" not in labels(parent_issue):
        _fail("parent is no longer an open Epic")
    gh.api(
        f"{gh.base}/issues/{parent}/sub_issues",
        "-X",
        "POST",
        "-F",
        f"sub_issue_id={child_id}",
    )
    verified = gh.parent(child)
    if not verified or verified.get("number") != parent:
        _fail("parent link could not be verified")
    return True


def ensure_scope(gh: GitHub, number: int, scope: str, text: str) -> bool:
    """Post one stable scope comment or reuse an exact match."""
    marker = SCOPE_MARKER.format(issue=number, scope=scope)
    expected = f"{text.rstrip()}\n\n{marker}\n"
    matches = [
        item
        for item in gh.comments(number)
        if "<!-- ballast-intake: issue=#" in (item.get("body") or "")
    ]
    if matches:
        if len(matches) != 1 or marker not in (matches[0].get("body") or ""):
            _fail("conflicting intake scope comment; resolve manually")
        if matches[0].get("body") != expected:
            _fail("existing intake scope comment differs; resolve manually")
        return False
    gh.api(
        f"{gh.base}/issues/{number}/comments", "-X", "POST", "-f", f"body={expected}"
    )
    if not any(marker in (item.get("body") or "") for item in gh.comments(number)):
        _fail("scope comment could not be verified")
    return True


def ensure_ready(gh: GitHub, number: int, parent: int | None) -> bool:
    """Apply ready-for-agent only after a fresh leaf check."""
    status = require_leaf(gh, number, parent)
    if parent is not None and status["parent"] != parent:
        _fail("parent link is missing")
    if "ready-for-agent" in status["labels"]:
        return False
    gh.api(
        f"{gh.base}/issues/{number}/labels",
        "-X",
        "POST",
        "-f",
        "labels[]=ready-for-agent",
    )
    if "ready-for-agent" not in labels(gh.issue(number)):
        _fail("ready-for-agent label could not be verified")
    return True


def _scope_text(path: Path) -> str:
    """Read the scope record required for an auditable setup."""
    scope = path.read_text(encoding="utf-8").strip()
    if not scope or len(scope) > MAX_SCOPE:
        _fail("scope file must contain 1-10000 characters")
    fields = ("Scope gate:", "Main outcome:", "In scope:", "Out of scope:")
    if any(
        not re.search(rf"(?m)^{re.escape(field)}[ \t]*\S", scope) for field in fields
    ) or not re.search(r"(?m)^Risk:[ \t]*R[012]\b", scope):
        _fail("scope file needs classification, outcome, in/out and R0/R1/R2 risk")
    return scope


def _validate_prepare(args: argparse.Namespace) -> str:
    """Reject incomplete setup requests before any GitHub write."""
    if args.parent is not None and (
        not args.slug or not args.title or not args.body_file
    ):
        _fail("child creation needs --slug, --title, and --body-file")
    if args.parent is not None and args.classification != "feature":
        _fail("new Epic children must use feature classification")
    if args.parent is not None and args.issue is not None:
        _fail("use --parent for a new child or --issue for an existing leaf")
    if args.parent is None and args.issue is None:
        _fail("existing leaf setup needs --issue")
    if args.slug and not SLUG.fullmatch(args.slug):
        _fail("--slug must be lowercase words joined by hyphens")
    return _scope_text(args.scope_file)


def _child_for_parent(gh: GitHub, args: argparse.Namespace) -> int:
    """Reuse a child or create it from a validated body."""
    parent_issue = gh.issue(args.parent)
    if parent_issue.get("state") != "open" or "epic" not in labels(parent_issue):
        _fail("parent must be an open Epic")
    number = find_child(gh, args.parent, args.slug, args.title)
    if number is not None:
        return number
    body = args.body_file.read_text(encoding="utf-8").strip()
    if not body or len(body) > MAX_BODY:
        _fail("child body must contain 1-60000 characters")
    if not ACCEPTANCE.search(body):
        _fail("child body needs an acceptance criteria section")
    return create_child(gh, args.parent, args.slug, args.title, body)


def prepare(gh: GitHub, args: argparse.Namespace) -> dict[str, Any]:
    """Reconcile the approved steps and report partial completion."""
    scope = _validate_prepare(args)
    result: dict[str, Any] = {"issue": args.issue, "completed": [], "pending": []}
    steps = ["child", "parent", "scope", "ready"] if args.parent else ["scope", "ready"]
    try:
        if args.parent is not None:
            number = _child_for_parent(gh, args)
            result["issue"] = number
            result["completed"].append("child")
            steps.remove("child")
            require_leaf(gh, number, args.parent)
            ensure_parent(gh, args.parent, number)
            result["completed"].append("parent")
            steps.remove("parent")
        else:
            number = args.issue
            require_leaf(gh, number, None)
        ensure_scope(gh, number, args.classification, scope)
        result["completed"].append("scope")
        steps.remove("scope")
        ensure_ready(gh, number, args.parent)
        result["completed"].append("ready")
        steps.remove("ready")
    except (IntakeError, OSError) as error:
        result["error"] = str(error)
        result["pending"] = steps
        result["note"] = "A failed write may exist on GitHub; retry rechecks state."
    except SHAPE_ERRORS:
        result["error"] = "GitHub returned an unexpected response shape"
        result["pending"] = steps
        result["note"] = "A failed write may exist on GitHub; retry rechecks state."
    return result


def main(argv: list[str] | None = None) -> int:
    """Run a read-only preflight or one approved setup reconciliation."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", required=True, help="OWNER/REPO")
    commands = parser.add_subparsers(dest="command", required=True)
    leaf = commands.add_parser("preflight", help="read-only dispatch check")
    leaf.add_argument("issue", type=int)
    setup = commands.add_parser("prepare", help="reconcile one approved leaf setup")
    setup.add_argument("--issue", type=int)
    setup.add_argument("--parent", type=int)
    setup.add_argument("--slug")
    setup.add_argument("--title")
    setup.add_argument("--body-file", type=Path)
    setup.add_argument("--scope-file", type=Path, required=True)
    setup.add_argument(
        "--classification", choices=("feature", "bug", "assess"), required=True
    )
    args = parser.parse_args(argv)
    try:
        gh = GitHub(args.repo)
        if args.command == "preflight":
            result = preflight(gh, args.issue)
            success = result["eligible_leaf"]
        else:
            result = prepare(gh, args)
            success = "error" not in result
    except (IntakeError, OSError) as error:
        result = {"error": str(error)}
        success = False
    except SHAPE_ERRORS:
        result = {"error": "GitHub returned an unexpected response shape"}
        success = False
    sys.stdout.write(json.dumps(result, sort_keys=True) + "\n")
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
