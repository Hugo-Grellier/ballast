#!/usr/bin/env python3
"""Fake agent integration for Autonomous runs.

Spec Kit calls `<agent> -p "/speckit-<command> <args>" ...`. The fake looks up
`$FAKE_AGENT_PLAN/<command>[-<first arg>]/` and copies that directory's tree
into the checkout, so a test lays out exactly what each step writes (artifacts
and drafts). A `stdout.txt` file there is printed instead of being copied, and
a `tamper` file names a checkout path to overwrite.
"""

import os
import shutil
import sys
from pathlib import Path

prompt = sys.argv[2] if len(sys.argv) > 2 else ""  # noqa: PLR2004
words = prompt.split()
command = words[0].lstrip("/$") if words else "agent"
plan = Path(os.environ.get("FAKE_AGENT_PLAN", "/nonexistent"))
step = plan / command
if len(words) > 1 and (plan / f"{command}-{words[1]}").is_dir():
    step = plan / f"{command}-{words[1]}"
if step.is_dir():
    for source in sorted(step.rglob("*")):
        relative = source.relative_to(step)
        if source.is_dir() or relative.name in {"stdout.txt", "tamper"}:
            continue
        target = Path.cwd() / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    if (step / "tamper").is_file():
        target = Path.cwd() / (step / "tamper").read_text().strip()
        target.write_text("tampered\n", encoding="utf-8")
    if (step / "stdout.txt").is_file():
        sys.stdout.write((step / "stdout.txt").read_text())
print(f"fake agent ran {command}")
