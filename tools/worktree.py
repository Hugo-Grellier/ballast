"""Claim one GitHub leaf issue and prepare a native Git worktree."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn

# Direct isolated invocation loads only this operator-selected source tree.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import admission


def fail(reason: str) -> NoReturn:
    """Stop with a fixed diagnostic that contains no backend payload."""
    raise admission.FixedReasonError(reason)


def inside_checkout() -> bool:
    """Whether this process runs inside an issue checkout.

    There it would block a worker's quiet check. Decided by path alone, never
    by a worker-writable gitfile.
    """
    return "ballast-v2" in Path.cwd().parts


def command(argv: list[str], cwd: Path) -> str:
    """Run a bounded native command, keeping diagnostics private."""
    result = subprocess.run(  # noqa: S603 -- argument arrays, no shell
        argv,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if result.returncode:
        fail("Native command failed; inspect the local checkout before retrying")
    return result.stdout.strip()


def git(cwd: Path, *args: str, git_dir: Path | None = None) -> str:
    """Run Git without checkout hooks or an external filesystem monitor.

    A pinned ``git_dir`` keeps Git from following the worker-writable gitfile.
    """
    pinned = ["--git-dir", str(git_dir), "--work-tree", str(cwd)] if git_dir else []
    return command(
        [
            "git",
            "-c",
            f"core.hooksPath={os.devnull}",
            "-c",
            "core.fsmonitor=false",
            *pinned,
            *args,
        ],
        cwd,
    )


def repository(cwd: Path, expected: str, git_dir: Path | None = None) -> None:
    """Require an unambiguous credential-free GitHub origin identity."""
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", expected):
        fail("Repository must be an explicit owner/name")
    remote = git(cwd, "remote", "get-url", "origin", git_dir=git_dir)
    match = re.fullmatch(
        r"(?:https://github\.com/|git@github\.com:)([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?/?",
        remote,
    )
    if match is None or match[1].lower() != expected.lower():
        fail("Origin does not match the requested GitHub repository")


def write_record(path: Path, value: dict) -> None:
    """Replace a local record atomically in its private directory."""
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def integration_revision(cwd: Path, repo: str, base: str) -> str:
    """Resolve the current branch revision from the verified GitHub host."""
    reference = json.loads(
        command(
            [
                "gh",
                "api",
                "--hostname",
                "github.com",
                f"repos/{repo}/git/ref/heads/{base}",
            ],
            cwd,
        )
    )
    if not isinstance(reference, dict) or not isinstance(reference.get("object"), dict):
        fail("Integration branch response is malformed")
    remote_base = reference["object"].get("sha")
    if not isinstance(remote_base, str):
        fail("Integration branch revision is missing")
    return remote_base


def prepare(cwd: Path, repo: str, issue: int, base: str) -> Path:
    """Claim before mutation; preserve the claim and residual files on failure."""
    repository(cwd, repo)
    if issue < 1 or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9/_.-]{0,127}", base):
        fail("Issue and integration branch must be explicit")
    data = json.loads(
        command(
            ["gh", "api", "--hostname", "github.com", f"repos/{repo}/issues/{issue}"],
            cwd,
        )
    )
    if not isinstance(data, dict):
        fail("Issue response is malformed")
    summary = data.get("sub_issues_summary", {"total": 0})
    if not isinstance(summary, dict):
        fail("Issue child summary is malformed")
    if (
        data.get("number") != issue
        or data.get("state") != "open"
        or "pull_request" in data
        or summary.get("total", 0)
    ):
        fail("Target is not an open leaf issue")
    # The coordinator gates semantic scope, acceptance and existing PRs.
    remote_base = integration_revision(cwd, repo, base)
    base_sha = git(
        cwd, "rev-parse", "--verify", f"refs/remotes/origin/{base}^{{commit}}"
    )
    if remote_base != base_sha:
        fail("Integration base is stale; fetch and reconsider before dispatch")
    common = Path(git(cwd, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    state = common / "ballast-v2"
    state.mkdir(mode=0o700, exist_ok=True)
    claim = state / f"issue-{issue}.json"
    attempt = uuid.uuid4().hex
    branch = f"issue-{issue}-{attempt[:8]}"
    checkout = state / "worktrees" / branch
    record = {
        "attempt": attempt,
        "repository": repo,
        "issue": issue,
        "base": base,
        "base_sha": base_sha,
        "branch": branch,
        "checkout": str(checkout),
        "created_at": datetime.now(UTC).isoformat(),
        "status": "preparing",
    }
    with admission.locked(state):
        if claim.exists():
            fail("Issue already claimed; reconcile its attempt before retrying")
        admission.admit_issue(state, record)
        with claim.open("x") as stream:
            json.dump(record, stream)
    try:
        git(cwd, "worktree", "add", "-b", branch, str(checkout), base_sha)
        if (
            git(checkout, "rev-parse", "HEAD") != base_sha
            or git(checkout, "branch", "--show-current") != branch
        ):
            fail("Prepared checkout identity differs from its claim")
        mark(claim, "ready")
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
        mark(claim, "setup_failed")
        raise
    return claim


def mark(claim: Path, status: str) -> None:
    """Change preparation status under the shared lock, keeping other updates."""
    with admission.locked(claim.parent):
        record = admission.read(claim)
        record["status"] = status
        admission.write(claim, record)


def validate(claim: Path, *, ready: bool = True) -> dict:
    """Revalidate checkout identity before every worker, including linked worktrees.

    Recovery passes ``ready=False`` to inspect an interrupted preparation.
    """
    record = json.loads(claim.read_text())
    fields = (
        "attempt",
        "repository",
        "base",
        "base_sha",
        "branch",
        "checkout",
        "status",
    )
    if (
        not isinstance(record, dict)
        or not all(isinstance(record.get(key), str) for key in fields)
        or type(record.get("issue")) is not int
    ):
        fail("Issue claim is malformed")
    cwd = Path(record["checkout"]).resolve(strict=True)
    # Derive Git metadata from the claim, never from the checkout a worker writes.
    common = claim.resolve().parent.parent
    admin = common / "worktrees" / cwd.name
    if (
        claim.resolve() != common / "ballast-v2" / f"issue-{record['issue']}.json"
        or (ready and record["status"] != "ready")
        or not admin.is_dir()
        or (admin / "gitdir").read_text().strip() != str(cwd / ".git")
    ):
        fail("Claim is not ready or belongs to another Git repository")
    record["git_dir"] = str(admin)
    repository(cwd, record["repository"], git_dir=admin)
    if git(cwd, "branch", "--show-current", git_dir=admin) != record["branch"]:
        fail("Checkout or branch differs from its claim")
    git(cwd, "merge-base", "--is-ancestor", record["base_sha"], "HEAD", git_dir=admin)
    return record


def main() -> int:
    """Print a local claim handle; it contains machine paths and stays private."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--issue", type=int, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--cwd", type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        claim = prepare(args.cwd.resolve(strict=True), args.repo, args.issue, args.base)
    except (
        OSError,
        ValueError,
        KeyError,
        RuntimeError,
        subprocess.SubprocessError,
    ) as error:
        # Admission reasons are fixed strings without private payloads.
        reason = (
            str(error)
            if isinstance(error, admission.FixedReasonError)
            else f"{type(error).__name__}; inspect local state"
        )
        sys.stderr.write(f"Preparation blocked: {reason}\n")
        return 1
    sys.stdout.write(json.dumps({"local_only": True, "claim": str(claim)}) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
