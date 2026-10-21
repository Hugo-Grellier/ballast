"""Qualify queue, worktree claim, worker, review and publish end to end.

`local` runs every helper as a subprocess against a fake Codex app-server and a
fake `gh` in a throwaway clone: no network, model, account or approval. `live`
runs the same path against the installed Codex and GitHub on an operator-named
disposable repository. It deletes nothing: its ledger records what it created
and it prints the commands that would remove it, for the operator to run.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

TOOLS = Path(__file__).resolve().parent
COORDINATOR = "qualification"
PREFIX = "ballast-qualification-"
DISPOSABLE = re.compile(rf"[A-Za-z0-9-]+/{PREFIX}[A-Za-z0-9_.-]+")
LOCAL_REPO = f"example/{PREFIX}local"
LOCAL_ROUTE = ("fake-model", "low")
ARTIFACT = "QUALIFICATION.md"
IMPLEMENT_TASK = (
    f"Create {ARTIFACT} at the checkout root containing the single line "
    "`qualified`. Change nothing else. Report the file you created."
)
REVIEW_TASK = (
    "Review the committed head {head} against base {base}. Acceptance: "
    f"{ARTIFACT} exists with the single line `qualified` and nothing else "
    "changed. Do not edit. Report findings, then end with the single line "
    "`Verdict: approve` or `Verdict: changes_required`."
)
APPROVED = re.compile(r"[\W_]*verdict[\W_]*approve[\W_]*", re.IGNORECASE)
COMMAND_SECONDS = 1200


class QualificationError(RuntimeError):
    """A qualification step failed; the message names the step."""


def run(argv: list[str], cwd: Path) -> str:
    """Run one native command; a failure names it with its diagnostic."""
    result = subprocess.run(  # noqa: S603 -- argument arrays, no shell
        argv,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=COMMAND_SECONDS,
        check=False,
    )
    if result.returncode:
        message = f"{shlex.join(argv[:3])} failed: {result.stderr.strip()[-500:]}"
        raise QualificationError(message)
    return result.stdout.strip()


def git(cwd: Path, *args: str) -> str:
    """Coordinator Git without checkout hooks."""
    return run(["git", "-c", f"core.hooksPath={os.devnull}", *args], cwd)


def worker_summary(result: dict) -> dict:
    """Path-free worker evidence."""
    keys = ("status", "role", "sandbox", "requested", "observed", "client_version")
    return {key: result.get(key) for key in (*keys, "head_before", "head_after")}


def scenario(
    project: Path,
    repo: str,
    issue: int,
    route: tuple[str, str],
    created: Callable[[str, object], None],
) -> dict:
    """Drive the documented coordinator steps through the shipped helpers."""

    def helper(name: str, *args: str) -> dict:
        argv = [sys.executable, "-I", "-S", str(TOOLS / name), *args]
        return json.loads(run(argv, project))

    def queue(*args: str) -> dict:
        return helper("coordinate.py", "--cwd", str(project), *args)

    def work(role: str, text: str) -> dict:
        task = scratch / f"{role}.txt"
        task.write_text(text)
        result = helper(
            "worker.py",
            *("--claim", claim, "--task", str(task), "--role", role),
            *("--model", route[0], "--effort", route[1], "--timeout", "600"),
        )
        if result.get("status") != "completed":
            message = f"{role} worker ended {result.get('status')}"
            raise QualificationError(message)
        return result

    scratch = project.parent / "tasks"
    scratch.mkdir()
    revision = "unversioned"
    if (TOOLS.parent / ".git").exists():
        revision = git(TOOLS.parent, "rev-parse", "HEAD")
    queue(
        *("create", "--repo", repo, "--issue", str(issue)),
        *("--coordinator", COORDINATOR, "--revision", revision),
    )
    selected = queue("select")
    if selected["eligible"] != [issue]:
        message = f"queue did not select #{issue}: {selected}"
        raise QualificationError(message)
    claim = helper(
        "worktree.py",
        *("--repo", repo, "--issue", str(issue), "--base", "main"),
        *("--cwd", str(project)),
    )["claim"]
    record = json.loads(Path(claim).read_text())
    checkout = Path(record["checkout"])
    implement = work("implement", IMPLEMENT_TASK)
    # The whole result against the base: no commit, nothing but one regular file.
    committed = git(checkout, "rev-parse", "HEAD") != record["base_sha"]
    changed = git(checkout, "status", "--porcelain", "--untracked-files=all")
    artifact = checkout / ARTIFACT
    if (
        committed
        or changed != f"?? {ARTIFACT}"
        or artifact.is_symlink()
        or artifact.read_text() != "qualified\n"
    ):
        message = f"implementation must add only {ARTIFACT} containing `qualified`"
        raise QualificationError(message)
    git(checkout, "add", "-A")
    git(checkout, "commit", "-q", "-m", f"Qualification for #{issue}")
    head = git(checkout, "rev-parse", "HEAD")
    review = work("review", REVIEW_TASK.format(head=head, base=record["base_sha"]))
    # Read the private output for its verdict only; it never enters evidence.
    output = Path(claim).parent / "workers" / review["worker"] / "output.txt"
    lines = output.read_text().strip().splitlines() or [""]
    if not APPROVED.fullmatch(lines[-1].strip()):
        message = "review did not end with `Verdict: approve`"
        raise QualificationError(message)
    created("branches", {"name": record["branch"], "sha": head})
    git(checkout, "push", "-q", "origin", record["branch"])
    body = scratch / "body.md"
    body.write_text(f"Fictional qualification for #{issue}. Do not merge.\n")
    published = queue(
        *("publish", "--claim", claim, "--body-file", str(body)),
        *("--title", f"Qualification for #{issue}"),
    )
    queue("settle", "--claim", claim, "pr_wait", "--evidence", published["pr"]["url"])
    status = queue("status")
    return {
        "ballast_revision": revision,
        "repository": repo,
        "issue": issue,
        "base": record["base_sha"],
        "head": head,
        "selected": selected["eligible"],
        "implement": worker_summary(implement),
        "review": worker_summary(review),
        "verdict": "approve",
        "pr": published["pr"],
        "activity": status["issues"][0]["activity"],
    }


def local(root: Path) -> dict:
    """Seed a clone whose GitHub, push target and Codex are local fakes."""
    bin_dir, project = root / "bin", root / "project"
    bin_dir.mkdir()
    for name in ("gh", "codex"):
        fake = bin_dir / name
        target = shlex.join([sys.executable, "-I", "-S", __file__, f"fake-{name}"])
        fake.write_text(f'#!/bin/sh\nexec {target} "$@"\n')
        fake.chmod(0o755)
    # This process only runs the local mode; helpers inherit the fakes.
    os.environ.update(
        {
            "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
            "BALLAST_FAKE_ROOT": str(root),
            "BALLAST_COORDINATOR": COORDINATOR,
            # The operator's own URL rewrites must not alter the canonical origin.
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
        }
    )
    remote = root / "remote" / f"{LOCAL_REPO}.git"
    remote.mkdir(parents=True)
    project.mkdir()
    git(remote, "init", "-q", "--bare", "-b", "main")
    git(project, "init", "-q", "-b", "main")
    for key, value in (
        ("user.name", "Fictional Coordinator"),
        ("user.email", "fictional@example.invalid"),
        (f"url.file://{root}/remote/.pushInsteadOf", "https://github.com/"),
    ):
        git(project, "config", key, value)
    (project / "README.md").write_text("Fictional qualification project.\n")
    git(project, "add", ".")
    git(project, "commit", "-q", "-m", "Fictional base")
    origin = f"https://github.com/{LOCAL_REPO}.git"
    git(project, "remote", "add", "origin", origin)
    git(project, "push", "-q", "origin", "main")
    evidence = scenario(project, LOCAL_REPO, 1, LOCAL_ROUTE, lambda *_: None)
    return {"mode": "local", **evidence}


def disposable(repo: str, *, confirmed: bool) -> str:
    """Refuse anything but an explicitly confirmed, prefix-named repository."""
    if not confirmed:
        message = "Live qualification needs --confirm-disposable"
        raise QualificationError(message)
    if not DISPOSABLE.fullmatch(repo):
        message = f"Live qualification needs a repository named OWNER/{PREFIX}*"
        raise QualificationError(message)
    return repo


def save(ledger: Path, record: dict) -> None:
    """Persist what this run created before the next step can fail."""
    ledger.write_text(json.dumps(record, indent=2) + "\n")


def repository_id(repo: str, cwd: Path) -> str:
    """GitHub's immutable node id; a recreated repository gets a new one."""
    value = json.loads(run(["gh", "repo", "view", repo, "--json", "id"], cwd))["id"]
    if not isinstance(value, str) or not value:
        message = "repository id is missing"
        raise QualificationError(message)
    return value


def ensure_repository(repo: str, ledger: Path, cwd: Path) -> dict:
    """Reuse an existing disposable repository or create and record a new one.

    The ledger is written before each external effect, so a failure after
    `gh repo create` still records the attempt; `id` stays null until GitHub
    identifies the repository.
    """
    record = {
        "repository": repo,
        "id": None,
        "created": False,
        "issues": [],
        "branches": [],
    }
    try:
        run(["gh", "repo", "view", repo, "--json", "name"], cwd)
    except QualificationError:
        record["created"] = True
        save(ledger, record)
        run(["gh", "repo", "create", repo, "--private", "--add-readme"], cwd)
    # The id lets the operator confirm a later deletion targets this repository.
    record["id"] = repository_id(repo, cwd)
    save(ledger, record)
    return record


def leftovers(record: dict) -> list[str]:
    """Commands that would remove what this run created; never run by this tool.

    Deleting a repository or branch is destructive cleanup, which needs an
    explicit human decision (AGENTS.md); the operator runs these after checking
    the recorded repository id and branch heads.
    """
    repo = record["repository"]
    if record["created"]:
        return [f"gh repo delete {repo}"]
    commands = [
        f"gh api -X DELETE repos/{repo}/git/refs/heads/{branch['name']}"
        for branch in record["branches"]
    ]
    closes = [f"gh issue close {issue} --repo {repo}" for issue in record["issues"]]
    return commands + closes


def live(args: argparse.Namespace) -> dict:
    """Qualify against real Codex and GitHub on a disposable repository."""
    repo = disposable(args.repo, confirmed=args.confirm_disposable)
    if args.ledger.exists():
        # An earlier run's ledger is the operator's cleanup record: never reuse it.
        message = "ledger already exists; pass a new file for each run"
        raise QualificationError(message)
    workdir = Path(tempfile.mkdtemp(prefix=PREFIX))
    ledger = args.ledger
    record = ensure_repository(repo, ledger, workdir)

    def created(kind: str, value: object) -> None:
        record[kind].append(value)
        save(ledger, record)

    url = run(
        [
            *("gh", "issue", "create", "--repo", repo),
            *("--title", "Fictional: add a qualification marker"),
            *("--body", f"Fictional. Create {ARTIFACT} containing `qualified`."),
        ],
        workdir,
    )
    issue = int(url.rsplit("/", 1)[-1])
    created("issues", issue)
    project = workdir / "project"
    run(["gh", "repo", "clone", repo, str(project)], workdir)
    os.environ["BALLAST_COORDINATOR"] = COORDINATOR
    route = (args.model, args.effort)
    evidence = scenario(project, repo, issue, route, created)
    # Nothing is deleted here: the ledger and these commands list what remains.
    return {"mode": "live", **evidence, "leftovers": leftovers(record)}


def fake_gh(args: list[str]) -> int:
    """Answer the `gh` calls the helpers make, from the local bare remote."""
    root = Path(os.environ["BALLAST_FAKE_ROOT"])
    store = root / "pulls.json"
    pulls = json.loads(store.read_text()) if store.exists() else []

    def sha(repo: str, branch: str) -> str:
        remote = root / "remote" / f"{repo}.git"
        return git(remote, "rev-parse", "--verify", f"refs/heads/{branch}")

    if args[:2] == ["api", "graphql"]:
        nodes = {
            f"i{number}": {
                "number": int(number),
                "state": "OPEN",
                "body": "Fictional qualification issue.",
                "subIssuesSummary": {"total": 0},
                "blockedBy": {"pageInfo": {"hasNextPage": False}, "nodes": []},
                "closedByPullRequestsReferences": {"nodes": []},
            }
            for number in re.findall(r"\bi(\d+):", " ".join(args))
        }
        answer: object = {"data": {"repository": nodes}}
    elif args[:1] == ["api"] and (
        found := re.fullmatch(r"repos/([^/]+/[^/]+)/(.+)", args[-1])
    ):
        repo, rest = found.groups()
        if issue := re.fullmatch(r"issues/(\d+)", rest):
            answer = {"number": int(issue[1]), "state": "open", "body": "Fictional."}
        elif branch := re.fullmatch(r"git/ref/heads/(.+)", rest):
            answer = {"object": {"sha": sha(repo, branch[1])}}
        elif head := re.fullmatch(r"pulls\?state=all&head=[^:]+:(.+)", rest):
            answer = [pr for pr in pulls if pr["head"]["ref"] == head[1]]
        else:
            return 2
    elif args[:2] == ["pr", "create"]:
        options = dict(zip(args[2::2], args[3::2], strict=False))
        repo, branch = options["--repo"], options["--head"]
        number = len(pulls) + 1
        pulls.append(
            {
                "number": number,
                "html_url": f"https://github.com/{repo}/pull/{number}",
                "state": "open",
                "merged_at": None,
                "base": {"ref": options["--base"]},
                "head": {
                    "ref": branch,
                    "sha": sha(repo, branch),
                    "repo": {"full_name": repo},
                },
            }
        )
        store.write_text(json.dumps(pulls))
        answer = pulls[-1]["html_url"]
    else:
        return 2
    sys.stdout.write(answer if isinstance(answer, str) else json.dumps(answer))
    return 0


def unrelated(cwd: Path, fault: str) -> None:
    """Faulty implementations the coordinator check must refuse."""
    if fault in ("unrelated-edit", "committed-edit"):
        (cwd / "README.md").write_text("Unrelated.\n")
    if fault == "committed-edit":
        # A committed edit leaves only the marker untracked.
        git(cwd, "commit", "-q", "-am", "Unrelated")


def fake_codex(_: list[str]) -> int:
    """Serve a verified route, then one completed turn per task."""
    model, effort = LOCAL_ROUTE
    fixed = {
        "initialize": {"userAgent": "fake-codex/0.0.0"},
        "account/read": {"account": {"type": "chatgpt"}},
        "model/list": {
            "data": [
                {
                    "model": model,
                    "supportedReasoningEfforts": [{"reasoningEffort": effort}],
                }
            ],
            "nextCursor": None,
        },
    }
    sandbox = ""
    # Tests select a faulty worker to prove the coordinator checks catch it.
    fault = os.environ.get("BALLAST_FAKE_FAULT", "")
    marker = "wrong\n" if fault == "wrong-output" else "qualified\n"
    verdict = "changes_required" if fault == "changes-required" else "approve"

    def send(**message: object) -> None:
        sys.stdout.write(json.dumps(message) + "\n")
        sys.stdout.flush()

    for line in sys.stdin:
        message = json.loads(line)
        method, identifier = message.get("method"), message.get("id")
        params = message.get("params", {})
        if method in fixed:
            send(id=identifier, result=fixed[method])
        elif method == "thread/start":
            sandbox = (
                "readOnly" if params["sandbox"] == "read-only" else "workspaceWrite"
            )
            policy = {"type": sandbox, "networkAccess": False, "writableRoots": []}
            policy |= {"excludeTmpdirEnvVar": True, "excludeSlashTmp": True}
            receipt = {
                "model": params["model"],
                "reasoningEffort": params["config"]["model_reasoning_effort"],
                "modelProvider": "openai",
                "cwd": params["cwd"],
                "approvalPolicy": "never",
                "thread": {"id": "fake-thread"},
                "sandbox": policy,
            }
            send(id=identifier, result=receipt)
        elif method == "turn/start":
            text = f"No findings.\nVerdict: {verdict}"
            if sandbox == "workspaceWrite":
                cwd = Path(params["cwd"])
                (cwd / ARTIFACT).write_text(marker)
                unrelated(cwd, fault)
                text = f"Created {ARTIFACT}."
            send(id=identifier, result={"turn": {"id": "fake-turn"}})
            item = {"type": "agentMessage", "text": text}
            turn = {"id": "fake-turn", "status": "completed", "error": None}
            for kind, value in (("item", item), ("turn", turn)):
                params = {"threadId": "fake-thread", kind: value}
                send(method=f"{kind}/completed", params=params)
        elif identifier is not None:
            send(id=identifier, error={"message": "unsupported by the fake"})
    return 0


def parser() -> argparse.ArgumentParser:
    """Modes; see docs/standalone.md#qualification."""
    root = argparse.ArgumentParser(description=__doc__)
    modes = root.add_subparsers(dest="mode", required=True)
    modes.add_parser("local")
    live_mode = modes.add_parser("live")
    live_mode.add_argument("--repo", required=True)
    live_mode.add_argument("--confirm-disposable", action="store_true")
    live_mode.add_argument("--model", required=True)
    live_mode.add_argument("--effort", required=True)
    live_mode.add_argument("--ledger", type=Path, required=True)
    return root


def main() -> int:
    """Print path-free evidence for docs/evidence/; local state is removed."""
    if len(sys.argv) > 1 and sys.argv[1] in ("fake-gh", "fake-codex"):
        fake = fake_gh if sys.argv[1] == "fake-gh" else fake_codex
        return fake(sys.argv[2:])
    args = parser().parse_args()
    try:
        if args.mode == "local":
            with tempfile.TemporaryDirectory(prefix=PREFIX) as root:
                result: dict = local(Path(root))
        else:
            result = live(args)
    except (QualificationError, OSError, ValueError, KeyError) as error:
        sys.stderr.write(f"Qualification failed: {error}\n")
        return 1
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
