"""Compute a PR's merge verdict (ADR-0026, ADR-0027): MERGE, HUMAN or BLOCK.

Prints the verdict with its reasons and what would raise it; merges only on
MERGE and only with --merge, squash, pinned to the reviewed head. Exit 0 on
MERGE, 3 on HUMAN, 1 on BLOCK.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path

# Direct isolated invocation loads only this operator-selected source tree.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import admission, spec_approval, spec_check, worktree

SHA = re.compile(r"[0-9a-f]{40}")
REPO = re.compile(r"[\w.-]+/[\w.-]+")
RISKS = ("R0", "R1", "R2")
FIELDS = (
    "number,state,isDraft,headRefOid,headRefName,baseRefName,author,body,"
    "changedFiles,closingIssuesReferences"
)
BRANCH = re.compile(r"[\w.-]+(?:/[\w.-]+)*")
# File names whose change always needs a human merge (ADR-0026): release files,
# dependency manifests and lockfiles of common ecosystems. A project adds its own
# with `Human-only:` lines in project/workflow.md, or --exclude.
EXCLUDED_PREFIXES = (".github/",)
EXCLUDED_NAMES = (
    "CHANGELOG.md",
    "release-please-config.json",
    ".release-please-manifest.json",
    "version.txt",
    "*.lock",
    "*.lockb",
    "*-lock.json",
    "*-lock.yaml",
    "pyproject.toml",
    "requirements*.txt",
    "requirements*.in",
    "constraints*.txt",
    "Pipfile",
    "setup.py",
    "setup.cfg",
    "package.json",
    "packages.lock.json",
    "go.mod",
    "go.sum",
    "go.work",
    "Cargo.toml",
    "Gemfile",
    "*.gemspec",
    "composer.json",
    "pom.xml",
    "build.gradle*",
    "settings.gradle*",
    "*.csproj",
    "Directory.Packages.props",
    "mix.exs",
    "Podfile",
    "flake.nix",
    ".pre-commit-config.yaml",
    ".tool-versions",
)
EXCLUDED_BRANCHES = ("release-please--", "dependabot/", "renovate/")
TICKED = re.compile(r"(?im)^[ \t]*[-*][ \t]*\[[xX]\][ \t]*(R[012])\b")
# Any line that looks like a workflow key; only the strict form counts, so a
# misspelled or list-item key is malformed rather than silently ignored.
WORKFLOW_KEY = re.compile(
    r"(?im)^[ \t]*(?:[-*+][ \t]+)?(?:human-only|coverage-exempt)[ \t]*:.*$"
)
WORKFLOW_LINE = re.compile(r"^(Human-only|Coverage-exempt):[ \t]+(\S+)[ \t]*$")
MERGED_NOTE = (
    "Merged by `tools/merge_check.py` under ADR-0027: verdict MERGE on reviewed"
    " head {head}, confirmed risk {risk}. This is not a human approval."
)


def gh(*args: str) -> subprocess.CompletedProcess:
    """Run one bounded gh call; callers decide what a nonzero exit means."""
    return subprocess.run(  # noqa: S603 -- argument arrays, no shell
        ["gh", *args],  # noqa: S607 -- the operator's gh, as in worktree.command
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def fetch(root: Path, repo: str, base: str, head: str) -> str:
    """Fetch the target branch tip and the reviewed head; return the tip SHA."""
    url = f"https://github.com/{repo}.git"
    tip = ""
    for ref in (f"refs/heads/{base}", head):
        result = subprocess.run(  # noqa: S603 -- fixed git argv, no shell
            ["git", "-C", str(root), "fetch", "--quiet", "--no-tags", url, ref],  # noqa: S607 -- git from PATH
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if result.returncode:
            worktree.fail("Fetching the target branch or the reviewed head failed")
        tip = tip or spec_check.git(root, "rev-parse", "FETCH_HEAD").strip()
    return tip


def read(*args: str, codes: frozenset[int] = frozenset({0})) -> object:
    """Parse a gh JSON response; a failed call or unreadable output refuses.

    A failed call can still print parseable partial output (one page of a
    paginated read), so the exit code is checked before the output is used.
    """
    result = gh(*args)
    if result.returncode not in codes:
        worktree.fail("A GitHub read failed; nothing was merged")
    try:
        return json.loads(result.stdout)
    except ValueError:
        worktree.fail("GitHub response is unreadable; nothing was merged")


def excluded(path: str, extra: tuple[str, ...] = ()) -> bool:
    """Whether a path is a workflow, permission, release or dependency file."""
    name = path.rsplit("/", 1)[-1]
    return path.startswith(EXCLUDED_PREFIXES) or any(
        fnmatch.fnmatchcase(name, pattern) or fnmatch.fnmatchcase(path, pattern)
        for pattern in (*EXCLUDED_NAMES, *extra)
    )


class Findings:
    """BLOCK and HUMAN reasons, each with what would raise the verdict."""

    def __init__(self) -> None:
        """Start with no reason: the verdict is MERGE until one is added."""
        self.block: list[dict] = []
        self.human: list[dict] = []
        self.paths: set[str] = set()

    def add(
        self, level: str, reason: str, action: str, paths: list | None = None
    ) -> None:
        """Record a reason at level BLOCK or HUMAN, and the paths behind it."""
        target = self.block if level == "BLOCK" else self.human
        target.append({"reason": reason, "to_raise": action})
        self.paths.update(paths or [])

    def verdict(self) -> str:
        """BLOCK takes precedence over HUMAN, and HUMAN over MERGE."""
        return "BLOCK" if self.block else "HUMAN" if self.human else "MERGE"


def pull_request(
    pr: object, number: int, head: str, risk: str, found: Findings
) -> None:
    """Judge the PR's state, origin and ticked risk against the reviewed head."""
    if not isinstance(pr, dict) or pr.get("number") != number:
        worktree.fail("Pull request response is malformed")
    if pr.get("state") != "OPEN":
        found.add("BLOCK", "The PR is not open", "reopen the PR")
    if pr.get("isDraft") is not False:
        found.add("BLOCK", "The PR is a draft", "mark the PR ready for review")
    if pr.get("headRefOid") != head:
        found.add(
            "BLOCK",
            "The PR head differs from the reviewed head: the review is stale",
            "review the current head again",
        )
    branch, author = pr.get("headRefName") or "", pr.get("author") or {}
    if branch.startswith(EXCLUDED_BRANCHES) or author.get("is_bot") is not False:
        found.add(
            "HUMAN", "Release and dependency PRs need a human merge", "a human merges"
        )
    ticked = TICKED.findall(pr.get("body") or "")
    if len(ticked) != 1:
        found.add(
            "BLOCK",
            "The PR body must tick exactly one risk",
            "tick one risk box in the PR body",
        )
    elif ticked[0] != risk:
        found.add(
            "HUMAN",
            f"The risk is disputed: the PR ticks {ticked[0]}, the reviewer"
            f" confirmed {risk}",
            "a human settles the risk",
        )
    if risk == "R2":
        found.add("HUMAN", "An R2 PR needs a human merge", "a human merges")


def base_branch(pr: dict) -> str:
    """Return the PR's base branch name, or refuse a malformed one."""
    base = pr.get("baseRefName")
    if not isinstance(base, str) or not BRANCH.fullmatch(base) or ".." in base:
        worktree.fail("The PR base branch is malformed")
    return base


def changed_paths(pages: object, count: object) -> list[str]:
    """Every current and previous path of the PR's files, or refuse.

    A rename counts under both names, so moving a workflow out of `.github/`
    still needs a human merge.
    """
    if not isinstance(pages, list) or not all(isinstance(p, list) for p in pages):
        worktree.fail("The changed file list is malformed")
    files = [item for page in pages for item in page]
    if len(files) != count:
        worktree.fail("The changed file list is incomplete")
    paths = []
    for item in files:
        if not isinstance(item, dict):
            worktree.fail("The changed file list is malformed")
        names = [item.get("filename")]
        if "previous_filename" in item:
            names.append(item["previous_filename"])
        if not all(isinstance(name, str) and name for name in names):
            worktree.fail("The changed file list is malformed")
        paths += names
    return paths


def required_contexts(repo: str, base: str) -> set[str]:
    """Every status check the base branch requires, from rulesets and protection.

    `gh pr checks --required` lists only required checks that reported, so a
    required check that never started would go unnoticed without this set.
    """
    pages = read("api", f"repos/{repo}/rules/branches/{base}", "--paginate", "--slurp")
    branch = read("api", f"repos/{repo}/branches/{base}")
    if (
        not isinstance(pages, list)
        or not all(isinstance(page, list) for page in pages)
        or not isinstance(branch, dict)
        or branch.get("name") != base
    ):
        worktree.fail("The base branch rules are unreadable")
    contexts = []
    for rule in (rule for page in pages for rule in page):
        if not isinstance(rule, dict):
            worktree.fail("The base branch rules are unreadable")
        if rule.get("type") == "required_status_checks":
            parameters = rule.get("parameters") or {}
            items = parameters.get("required_status_checks")
            if not isinstance(items, list) or not all(
                isinstance(item, dict) for item in items
            ):
                worktree.fail("The base branch rules are unreadable")
            contexts += [item.get("context") for item in items]
    protection = (branch.get("protection") or {}).get("required_status_checks") or {}
    legacy = protection.get("contexts") or []
    if not isinstance(legacy, list):
        worktree.fail("The base branch rules are unreadable")
    contexts += legacy
    if not all(isinstance(name, str) and name for name in contexts):
        worktree.fail("The base branch rules are unreadable")
    return set(contexts)


def required_checks(repo: str, number: int, base: str, found: Findings) -> None:
    """Require every required check of the base branch green on the PR head."""
    required = required_contexts(repo, base)
    if not required:
        found.add(
            "BLOCK",
            "No required checks are configured for the base branch",
            "require at least one status check on the base branch",
        )
    # gh pr checks exits 1 for a failing and 8 for a pending check, still
    # printing the list; each bucket is checked below.
    checks = read(
        "pr",
        "checks",
        str(number),
        "--repo",
        f"github.com/{repo}",
        "--json",
        "name,bucket",
        codes=frozenset({0, 1, 8}),
    )
    if not isinstance(checks, list) or not all(isinstance(c, dict) for c in checks):
        worktree.fail("The PR check list is unreadable")
    for name in sorted(required):
        buckets = [item.get("bucket") for item in checks if item.get("name") == name]
        if not buckets:
            found.add(
                "BLOCK",
                f"Required check {name} has not reported on the PR head",
                "wait for it",
            )
        elif any(bucket != "pass" for bucket in buckets):
            found.add(
                "BLOCK",
                f"Required check {name} is not green on the PR head",
                "fix or rerun it",
            )


def project_workflow(root: Path, tip: str, found: Findings) -> dict | None:
    """Read the human-only and coverage-exempt globs from the target branch.

    Never from the PR head, so a PR cannot remove its own exclusion. A missing,
    unreadable or malformed file gives HUMAN.
    """
    try:
        text = spec_check.git(root, "show", f"{tip}:{spec_check.WORKFLOW}")
    except spec_check.SpecError:
        text = None
    lines = WORKFLOW_KEY.findall(text or "")
    parsed = [WORKFLOW_LINE.match(line) for line in lines]
    if text is None or not all(parsed):
        found.add(
            "HUMAN",
            f"{spec_check.WORKFLOW} is missing or malformed on the target branch",
            f"add `Human-only: GLOB` and `Coverage-exempt: GLOB` lines to"
            f" {spec_check.WORKFLOW} on the target branch",
        )
        return None
    globs: dict = {"Human-only": [], "Coverage-exempt": []}
    for match in parsed:
        globs[match.group(1)].append(match.group(2))
    return globs


def issue(repo: str, number: int) -> tuple[str, list[dict]]:
    """Return an issue's body and every comment, or refuse a malformed one."""
    data = read("api", f"repos/{repo}/issues/{number}")
    pages = read(
        "api",
        f"repos/{repo}/issues/{number}/comments?per_page=100",
        "--paginate",
        "--slurp",
    )
    body = (data.get("body") if isinstance(data, dict) else None) or ""
    if not isinstance(pages, list) or not all(isinstance(p, list) for p in pages):
        worktree.fail("Issue comments response is malformed")
    comments = [c for page in pages for c in page]
    if not isinstance(body, str) or not all(
        isinstance(c, dict) and isinstance(c.get("body"), str) for c in comments
    ):
        worktree.fail("Issue response is malformed")
    return body, comments


def closing_issues(repo: str, pr: dict, found: Findings) -> tuple[str, list]:
    """Return the risk floor and each closing issue's (approval, comments).

    The floor is the highest `Risk:` line and approved risk of the closing
    issues. No closing issue, one in another repository or one without a
    single parseable `Risk:` line gives HUMAN.
    """
    references = pr.get("closingIssuesReferences")
    if not isinstance(references, list):
        worktree.fail("Pull request response is malformed")
    if not references:
        found.add(
            "HUMAN",
            "The PR closes no issue, so its risk floor is unknown",
            "link the issue with `Closes #N`",
        )
    floor, approvals = "R0", []
    for reference in references:
        if not isinstance(reference, dict):
            worktree.fail("Pull request response is malformed")
        repository = reference.get("repository") or {}
        owner = (repository.get("owner") or {}).get("login")
        number = reference.get("number")
        where = f"{owner}/{repository.get('name')}"
        if not isinstance(number, int) or where.lower() != repo.lower():
            found.add(
                "HUMAN",
                "The PR closes an issue outside this repository",
                "close only issues of this repository",
            )
            continue
        body, comments = issue(repo, number)
        risks = spec_approval.RISK.findall(body.replace("\r\n", "\n"))
        if len(risks) != 1:
            found.add(
                "HUMAN",
                f"Issue #{number} has no single parseable `Risk:` line",
                f"state `Risk: R0|R1|R2` once in issue #{number}",
            )
        try:
            approval = spec_approval.approval(repo, number, comments)
        except admission.FixedReasonError:
            approval = None
        floor = max([floor, *risks, *([approval["approved_risk"]] if approval else [])])
        if approval:
            approvals.append((approval, comments))
    return floor, approvals


def edited(approval: dict, comments: list[dict]) -> bool:
    """Whether the approval, or its delta after the approval, was edited."""
    by_url = {c.get("html_url"): c for c in comments}
    delta_id = approval["delta"].rsplit("-", 1)[-1]
    delta = next(c for c in comments if str(c.get("id")) == delta_id)
    approved = by_url[approval["approval"]]
    stamps = [approved.get(k) for k in ("created_at", "updated_at")]
    stamps.append(delta.get("updated_at"))
    if not all(isinstance(stamp, str) and stamp for stamp in stamps):
        worktree.fail("Issue comments response is malformed")
    created, updated, delta_updated = stamps
    return updated != created or delta_updated > created


def stale(root: Path, tip: str, entries: list[dict]) -> bool:
    """Whether a delta entry's base no longer matches the target branch tip.

    A modified or removed entry needs its base text there; an added entry's key
    must not exist there yet.
    """
    target = {
        name: spec_check.spec_texts(text)
        for name, text in spec_check.specs_at(root, tip).items()
    }
    for item in entries:
        texts = target.get(item["file"], {})
        key = (item["requirement"], item["scenario"])
        if item["change"] == "added" and key in texts:
            return True
        if item["change"] != "added" and texts.get(key) != item["base"]:
            return True
    return False


def covers_at(root: Path, revision: str) -> list[str]:
    """Return every `Covers:` glob of the specs at a revision."""
    return [
        glob
        for name, text in spec_check.specs_at(root, revision).items()
        for glob in spec_check.parse_covers(text, name)[0]
    ]


def specs(args: argparse.Namespace, tip: str, paths: list, found: Findings) -> dict:
    """Judge coverage, the spec delta and its approval; return the handoff spec."""
    root, head, risk = args.root, args.reviewed_head, args.risk
    workflow = project_workflow(root, tip, found)
    human_only = workflow["Human-only"] if workflow else []
    exempt = [*(workflow["Coverage-exempt"] if workflow else []), "docs/specs/**"]
    risky = [
        p
        for p in paths
        if excluded(p, tuple(args.exclude)) or spec_check.matches(p, human_only)
    ]
    if risky:
        found.add(
            "HUMAN",
            "The PR changes a workflow, release, dependency or human-only path",
            "a human merges",
            risky,
        )
    entries = spec_check.git_delta(root, tip, head)
    digest = spec_check.delta_hash(entries)
    if stale(root, tip, entries):
        found.add(
            "BLOCK",
            "The spec delta is stale: the target branch changed its base text"
            " or already has an added entry",
            "rebase, then post and approve a new delta",
        )
    head_covers, tip_covers = covers_at(root, head), covers_at(root, tip)
    uncovered = [p for p in paths if not spec_check.matches(p, head_covers + exempt)]
    if uncovered:
        found.add(
            "HUMAN",
            "Changed paths no spec covers",
            "add them to a spec's `Covers:` lines, or list them `Coverage-exempt:`",
            uncovered,
        )
    if risk == "R0":
        covered = [p for p in paths if spec_check.matches(p, head_covers + tip_covers)]
        if covered:
            found.add(
                "HUMAN",
                "An R0 PR changes paths a spec covers",
                "classify it R1 with an approved spec delta",
                covered,
            )
        if any(item["change"] != "added" for item in entries):
            found.add(
                "HUMAN",
                "An R0 PR modifies or removes a spec entry",
                "classify it R1 with an approved spec delta",
            )
    return {"hash": digest, "entries": len(entries)}


def approved_spec(
    risk: str, digest: str, approvals: list, found: Findings
) -> dict | None:
    """Require, for R1, an unedited approval on a closing issue quoting digest."""
    matching = [(a, c) for a, c in approvals if a["hash"] == digest]
    if matching:
        approval, comments = matching[0]
        if edited(approval, comments):
            found.add(
                "BLOCK",
                "The spec delta or its approval was edited after the approval",
                "post a new delta and get it approved",
            )
        return approval
    if risk == "R0":
        return None
    if approvals:
        found.add(
            "BLOCK",
            f"Spec hash mismatch: the reviewed head's docs/specs/ delta hashes"
            f" {digest}, the approval quotes {approvals[0][0]['hash']}",
            "make the spec change match the approved delta, or approve the new one",
        )
    elif risk == "R1":
        found.add(
            "BLOCK",
            f"An R1 PR needs an approved spec delta on its closing issue (a PR"
            f" changing no spec needs an approved empty delta); this head's"
            f" delta hashes {digest}",
            "post the delta and get it approved",
        )
    return None


def evaluate(args: argparse.Namespace, found: Findings) -> dict:
    """Collect every BLOCK and HUMAN reason for the reviewed head."""
    number, head, risk = args.pr, args.reviewed_head, args.risk
    if args.verdict != "approved":
        found.add(
            "BLOCK",
            "The independent review did not approve this head",
            "get an approving independent review of the exact head",
        )
    if risk not in RISKS:
        worktree.fail("The confirmed risk is not R0, R1 or R2")
    if not SHA.fullmatch(head):
        worktree.fail("The reviewed head is not a full commit SHA")
    if not REPO.fullmatch(args.repo):
        worktree.fail("The repository is not OWNER/NAME")
    target = f"github.com/{args.repo}"
    pr = read("pr", "view", str(number), "--repo", target, "--json", FIELDS)
    pull_request(pr, number, head, risk, found)
    base = base_branch(pr)
    pages = read(
        "api",
        f"repos/{args.repo}/pulls/{number}/files?per_page=100",
        "--paginate",
        "--slurp",
    )
    paths = changed_paths(pages, pr.get("changedFiles"))
    floor, approvals = closing_issues(args.repo, pr, found)
    if floor > risk:
        found.add(
            "HUMAN",
            f"The confirmed risk {risk} is below the closing issue's {floor}",
            "a human accepts the lower risk",
        )
    tip = fetch(args.root, args.repo, base, head)
    spec = specs(args, tip, paths, found)
    approval = approved_spec(risk, spec["hash"], approvals, found)
    required_checks(args.repo, number, base, found)
    return {
        "risk": risk,
        "floor": floor,
        "spec": {**spec, **(approval or {})},
    }


def check(args: argparse.Namespace) -> dict:
    """Return the verdict, its reasons and, on MERGE, the pinned merge command.

    Any state not listed under MERGE or HUMAN, including an unreadable
    response, is BLOCK.
    """
    found = Findings()
    facts: dict = {}
    try:
        facts = evaluate(args, found)
    except (admission.FixedReasonError, spec_check.SpecError) as error:
        found.add("BLOCK", str(error), "fix the cause and run the check again")
    result: dict = {"verdict": found.verdict(), **facts}
    if found.block:
        result["block"] = found.block
    if found.human:
        result["human"] = found.human
    if result["verdict"] == "HUMAN":
        result["handoff"] = {
            "risky_paths": sorted(found.paths),
            "approved_spec": facts.get("spec"),
            "review_findings": args.finding,
        }
    if result["verdict"] == "MERGE":
        command = ["gh", "pr", "merge", str(args.pr), "--repo"]
        command += [f"github.com/{args.repo}", "--squash"]
        result["merge"] = [*command, "--match-head-commit", args.reviewed_head]
    return result


def parser() -> argparse.ArgumentParser:
    """Reviewer evidence comes from the pair review of this exact head."""
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument("--repo", required=True)
    root.add_argument("--pr", type=int, required=True)
    root.add_argument("--reviewed-head", required=True)
    root.add_argument("--verdict", required=True)
    root.add_argument("--risk", required=True, help="risk the reviewer confirmed")
    root.add_argument(
        "--finding",
        action="append",
        default=[],
        help="a surviving review finding, listed in the HUMAN handoff",
    )
    root.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="extra glob (file name or path) that always needs a human merge",
    )
    root.add_argument(
        "--root", type=Path, default=Path(), help="the project checkout (Git)"
    )
    root.add_argument("--merge", action="store_true", help="merge on MERGE")
    return root


def run(args: argparse.Namespace) -> dict:
    """Compute the verdict, then merge only on MERGE and explicit request."""
    if worktree.inside_checkout():
        worktree.fail("Run merge checks from the project checkout, not an issue")
    result = check(args)
    if args.merge and result["verdict"] == "MERGE":
        # --match-head-commit makes GitHub refuse a head that moved since the check.
        if gh(*result["merge"][1:]).returncode:
            result["verdict"] = "BLOCK"
            result["block"] = [
                {
                    "reason": "GitHub refused the merge; nothing else was attempted",
                    "to_raise": "check the PR on GitHub and run the check again",
                }
            ]
            return result
        result["merged"] = True
        note = MERGED_NOTE.format(head=args.reviewed_head, risk=args.risk)
        comment = ("pr", "comment", str(args.pr), "--repo", result["merge"][5])
        result["noted"] = gh(*comment, "--body", note).returncode == 0
    return result


EXIT = {"MERGE": 0, "BLOCK": 1, "HUMAN": 3}


def main() -> int:
    """Print the verdict as JSON; the exit code follows the verdict."""
    try:
        result = run(parser().parse_args())
    except admission.FixedReasonError as error:
        result = {"verdict": "BLOCK", "block": [{"reason": str(error)}]}
    except (OSError, subprocess.SubprocessError, AttributeError, TypeError) as error:
        result = {"verdict": "BLOCK", "block": [{"reason": type(error).__name__}]}
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    return EXIT[result["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
