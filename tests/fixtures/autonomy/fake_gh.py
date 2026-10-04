#!/usr/bin/env python3
"""Fake `gh`: serves canned JSON from $FAKE_GH_DIR and records every argv.

`api PATH` reads `<PATH with / replaced by _>.json` (query dropped; pages after
the first are empty; `--paginate --slurp` wraps the page in a list); `repo
view` reads `repo.json`; `pr list` reads `pr-list.json` (default `[]`); `pr
create` copies the body (`--body-file PATH` or `-` for stdin) to `pr-body.md`,
prints a PR URL, and serves PR #7 as `repos/acme/demo/pulls/7` (from
`created-pr.json` when it exists, which is also listed as `repos/acme/demo/pulls`,
else from the create arguments; `create-override.json` is merged in); `pr
edit` copies the body to `pr-body.md`. After serving `<name>.json`, a
`<name>.then.json` replaces it (a concurrent change on GitHub); `auth
status` succeeds only when `auth.ok` exists. A missing file is an HTTP 404.
`FAIL_<word>` files make the matching subcommand fail, printing their content
(or `simulated failure`).
"""

import json
import os
import shutil
import sys
from pathlib import Path

data = Path(os.environ["FAKE_GH_DIR"])
args = sys.argv[1:]
with Path(os.environ["FAKE_GH_LOG"]).open("a", encoding="utf-8") as log:
    log.write(json.dumps(args) + "\n")


def serve(name: str, default: str | None = None, *, slurp: bool = False) -> None:
    """Print a canned response, or fail like a GitHub 404."""
    path = data / name
    if path.is_file():
        text = path.read_text(encoding="utf-8")
        sys.stdout.write(f"[{text}]" if slurp else text)
        then = path.with_suffix(".then.json")
        if then.is_file():
            then.replace(path)
    elif default is not None:
        sys.stdout.write(default)
    else:
        sys.stderr.write("HTTP 404: Not Found\n")
        sys.exit(1)


for fail in (data / f"FAIL_{args[0]}", data / f"FAIL_{'_'.join(args[:2])}"):
    if fail.exists():
        sys.stderr.write(fail.read_text(encoding="utf-8") or "simulated failure\n")
        sys.exit(1)


def copy_body() -> None:
    """Keep the body given as --body-file PATH or --body-file - (stdin)."""
    body = args[args.index("--body-file") + 1]
    if body == "-":
        (data / "pr-body.md").write_text(sys.stdin.read(), encoding="utf-8")
    else:
        shutil.copyfile(body, data / "pr-body.md")


if args[:1] == ["api"]:
    path, _, query = args[-1].partition("?")
    pages = [item for item in query.split("&") if item.startswith("page=")]
    if pages and pages != ["page=1"]:
        sys.stdout.write("[]")
    else:
        serve(path.replace("/", "_") + ".json", slurp="--slurp" in args)
elif args[:2] == ["repo", "view"]:
    serve("repo.json")
elif args[:2] == ["pr", "list"]:
    serve("pr-list.json", "[]")
elif args[:2] == ["pr", "create"]:
    copy_body()
    created = data / "created-pr.json"
    body = (data / "pr-body.md").read_text(encoding="utf-8")
    if created.is_file():
        pr = json.loads(created.read_text(encoding="utf-8"))
        pr["body"] = body
        (data / "repos_acme_demo_pulls.json").write_text(json.dumps([pr]))
    else:
        repo = args[args.index("--repo") + 1]
        pr = {
            "number": 7,
            "html_url": "https://github.com/acme/demo/pull/7",
            "state": "open",
            "merged_at": None,
            "draft": "--draft" in args,
            "body": body,
            "base": {"ref": args[args.index("--base") + 1] if "--base" in args else ""},
            "head": {
                "ref": args[args.index("--head") + 1],
                "repo": {"full_name": repo, "owner": {"login": repo.split("/")[0]}},
            },
        }
    override = data / "create-override.json"
    if override.is_file():
        pr |= json.loads(override.read_text(encoding="utf-8"))
    (data / "repos_acme_demo_pulls_7.json").write_text(json.dumps(pr))
    sys.stdout.write("https://github.com/acme/demo/pull/7\n")
elif args[:2] == ["pr", "edit"]:
    copy_body()
elif args[:2] == ["auth", "status"]:
    if not (data / "auth.ok").exists():
        sys.stderr.write("You are not logged into any GitHub hosts.\n")
        sys.exit(1)
else:
    sys.stderr.write(f"fake gh: unsupported {args}\n")
    sys.exit(2)
