#!/usr/bin/env python3
"""Fake `gh`: serves canned JSON from $FAKE_GH_DIR and records every argv.

`api PATH` reads `<PATH with / replaced by _>.json` (query dropped; pages after
the first are empty); `repo view` reads `repo.json`; `pr list` reads
`pr-list.json` (default `[]`); `pr create` copies the body to `pr-body.md` and
prints a PR URL; `auth status` succeeds only when `auth.ok` exists. A missing
file is an HTTP 404. `FAIL_<word>` files make the matching subcommand fail.
"""

import json
import os
import shutil
import sys
from pathlib import Path

data = Path(os.environ["FAKE_GH_DIR"])
args = sys.argv[1:]
with open(os.environ["FAKE_GH_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps(args) + "\n")


def serve(name: str, default: str | None = None) -> None:
    path = data / name
    if path.is_file():
        sys.stdout.write(path.read_text(encoding="utf-8"))
    elif default is not None:
        sys.stdout.write(default)
    else:
        sys.stderr.write("HTTP 404: Not Found\n")
        sys.exit(1)


if (data / f"FAIL_{args[0]}").exists() or (
    data / f"FAIL_{'_'.join(args[:2])}"
).exists():
    sys.stderr.write("simulated failure\n")
    sys.exit(1)
if args[:1] == ["api"]:
    path, _, query = args[1].partition("?")
    if "page=" in query and "page=1" not in query.split("&"):
        sys.stdout.write("[]")
    else:
        serve(path.replace("/", "_") + ".json")
elif args[:2] == ["repo", "view"]:
    serve("repo.json")
elif args[:2] == ["pr", "list"]:
    serve("pr-list.json", "[]")
elif args[:2] == ["pr", "create"]:
    body = args[args.index("--body-file") + 1]
    shutil.copyfile(body, data / "pr-body.md")
    sys.stdout.write("https://github.com/acme/demo/pull/7\n")
elif args[:2] == ["auth", "status"]:
    if not (data / "auth.ok").exists():
        sys.stderr.write("You are not logged into any GitHub hosts.\n")
        sys.exit(1)
else:
    sys.stderr.write(f"fake gh: unsupported {args}\n")
    sys.exit(2)
