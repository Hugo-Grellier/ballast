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


def fail(reason: str) -> NoReturn:
    """Stop with a fixed diagnostic that contains no backend payload."""
    raise RuntimeError(reason)


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


def git(cwd: Path, *args: str) -> str:
    """Run Git without checkout hooks or an external filesystem monitor."""
    return command(
        [
            "git",
            "-c",
            f"core.hooksPath={os.devnull}",
            "-c",
            "core.fsmonitor=false",
            *args,
        ],
        cwd,
    )


def repository(cwd: Path, expected: str) -> None:
    """Require an unambiguous credential-free GitHub origin identity."""
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", expected):
        fail("Repository must be an explicit owner/name")
    remote = git(cwd, "remote", "get-url", "origin")
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
    try:
        with claim.open("x") as stream:
            json.dump(record, stream)
    except FileExistsError:
        fail("Issue already claimed; reconcile its recorded attempt before retrying")
    try:
        git(cwd, "worktree", "add", "-b", branch, str(checkout), base_sha)
        if (
            git(checkout, "rev-parse", "HEAD") != base_sha
            or git(checkout, "branch", "--show-current") != branch
        ):
            fail("Prepared checkout identity differs from its claim")
        record["status"] = "ready"
        write_record(claim, record)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
        record["status"] = "setup_failed"
        write_record(claim, record)
        raise
    return claim


def validate(claim: Path) -> dict:
    """Revalidate checkout identity before every worker, including linked worktrees."""
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
    common = Path(git(cwd, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    if (
        claim.resolve() != common / "ballast-v2" / f"issue-{record['issue']}.json"
        or record["status"] != "ready"
    ):
        fail("Claim is not ready or belongs to another Git repository")
    repository(cwd, record["repository"])
    if (
        git(cwd, "rev-parse", "--show-toplevel") != str(cwd)
        or git(cwd, "branch", "--show-current") != record["branch"]
    ):
        fail("Checkout or branch differs from its claim")
    git(cwd, "merge-base", "--is-ancestor", record["base_sha"], "HEAD")
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
        sys.stderr.write(
            f"Preparation blocked: {type(error).__name__}; inspect local state\n"
        )
        return 1
    sys.stdout.write(json.dumps({"local_only": True, "claim": str(claim)}) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
