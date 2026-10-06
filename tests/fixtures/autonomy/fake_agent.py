#!/usr/bin/env python3
"""Fake agent integration for Autonomous runs.

Spec Kit calls `claude -p "/speckit-<command> <args>" ...` or
`codex exec ... "$speckit-<command> <args>"`. The fake looks up
`$FAKE_AGENT_PLAN/<command>[-<first arg>]/` and copies that directory's tree
into the checkout, so a test lays out exactly what each step writes (artifacts
and drafts). A `stdout.txt` file there is printed instead of being copied, and
a `tamper` file names a checkout path to overwrite. An `exec` file holds a
shell command whose exit status is printed as `exec-exit=N`; `kill-parent`
kills the agent wrapper (an agent step that never finishes its check) and
`interrupt` sends SIGINT to `$FAKE_INTERRUPT_PID`, Spec Kit and the wrapper
(an operator Ctrl-C). The
last two need an unconfined step: bwrap's PID namespace hides both processes.
When the wrapper reruns a step with its retry note (#21), the fake uses the
`<directory>-retry/` sibling instead, when there is one.
"""

import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path

# claude -p PROMPT ...; codex exec [options] PROMPT
args = sys.argv[1:]
prompt = args[-1] if args[:1] == ["exec"] else (args[1] if len(args) > 1 else "")
words = prompt.split()
command = words[0].lstrip("/$") if words else "agent"
plan = Path(os.environ.get("FAKE_AGENT_PLAN", "/nonexistent"))
step = plan / command
CONTROL = {"stdout.txt", "tamper", "exec", "kill-parent", "interrupt"}
if len(words) > 1 and (plan / f"{command}-{words[1]}").is_dir():
    step = plan / f"{command}-{words[1]}"
# A step the wrapper reruns after a refused draft (#21) reads `<step>-retry`.
if "Ballast retry" in prompt and step.with_name(step.name + "-retry").is_dir():
    step = step.with_name(step.name + "-retry")
if step.is_dir():
    for source in sorted(step.rglob("*")):
        relative = source.relative_to(step)
        if source.is_dir() or relative.name in CONTROL:
            continue
        target = Path.cwd() / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    if (step / "exec").is_file():
        shell = (step / "exec").read_text().strip()
        done = subprocess.run(["sh", "-c", shell], check=False)  # noqa: S603, S607
        sys.stdout.write(f"exec-exit={done.returncode}\n")
    if (step / "kill-parent").is_file():
        os.kill(os.getppid(), signal.SIGKILL)
    if (step / "interrupt").is_file():
        # Ctrl-C reaches the operator's whole foreground job: the test
        # runner, Spec Kit (the wrapper's parent) and the wrapper.
        wrapper = os.getppid()
        stat = Path(f"/proc/{wrapper}/stat").read_text()
        engine = int(stat.rpartition(")")[2].split()[1])
        for pid in (int(os.environ["FAKE_INTERRUPT_PID"]), engine, wrapper):
            os.kill(pid, signal.SIGINT)
    if (step / "tamper").is_file():
        target = Path.cwd() / (step / "tamper").read_text().strip()
        try:
            target.write_text("tampered\n", encoding="utf-8")
        except OSError as error:
            sys.stdout.write(f"tamper-refused={error.errno}\n")
    if (step / "stdout.txt").is_file():
        sys.stdout.write((step / "stdout.txt").read_text())
sys.stdout.write(f"fake agent ran {command}\n")
