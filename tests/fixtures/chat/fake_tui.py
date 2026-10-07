#!/usr/bin/env python3
"""Fake interactive agent CLI (claude or codex) for Chat-mode tests.

Copied into a trusted program directory as `claude` and `codex`. It reads
`scenario.json` next to its own file: a list of actions run in order, each a
list whose first item names the action:

- ["write", PATH, TEXT] / ["append", PATH, TEXT]: write a file in the checkout
- ["print", TEXT]: print a line to the terminal
- ["read_line"]: block until one line arrives on stdin, record it
- ["try_write", PATH]: record "ok" or the errno of a failed write
- ["run", [ARGV...]]: run a command, record its exit status and output
- ["sleep", SECONDS]
- ["close_terminal"]: close fds 0-2, as an agent does just before it exits
- ["ignore", "SIGHUP"]: ignore a signal
- ["wait_winch", SECONDS]: wait for a window-size change, record the size
- ["swap_log_dir"]: replace this step's log directory with a symlink
- ["exit", CODE]

After every action it rewrites `report.json` there (or $FAKE_TUI_REPORT) with its
argv, the names of its environment variables, whether fds 0-2 are TTYs, the name of its
terminal, whether /dev/tty opens, the targets of its open descriptors, its
session ID and the action results. It never reads anything else.

`codex sandbox ...` (Ballast's nested-sandbox probe) exits with
$FAKE_CODEX_NESTS (default 0) and runs no scenario. When $FAKE_ORDER_LOG is
set, the agent appends "agent start" and "agent exit" to it.
"""

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
# A real bwrap overlays ~/.cache, so a confined test names a visible path.
REPORT = Path(os.environ.get("FAKE_TUI_REPORT") or HERE / "report.json")
results: list[object] = []
winch = {"seen": False}


def _descriptors() -> dict[str, str]:
    found = {}
    for entry in sorted(Path("/proc/self/fd").iterdir(), key=lambda p: int(p.name)):
        try:
            found[entry.name] = str(entry.readlink())
        except OSError:
            continue
    return found


def _controlling_terminal() -> str:
    try:
        fd = os.open("/dev/tty", os.O_RDWR)
    except OSError as error:
        return f"error {error.errno}"
    os.close(fd)
    return "ok"


def _size() -> list[int] | None:
    try:
        size = os.get_terminal_size(0)
    except OSError:
        return None
    return [size.columns, size.lines]


def _report() -> None:
    try:
        tty_name = os.ttyname(0)
    except OSError:
        tty_name = None
    data = {
        "argv": sys.argv[1:],
        "program": Path(sys.argv[0]).name,
        "env": sorted(os.environ),
        "environ": {
            key: os.environ[key]
            for key in ("PATH", "BALLAST_GIT", "PYTHONPYCACHEPREFIX")
            if key in os.environ
        },
        "isatty": [os.isatty(fd) for fd in (0, 1, 2)],
        "ttyname": tty_name,
        "controlling_terminal": _controlling_terminal(),
        "fds": _descriptors(),
        "sid": os.getsid(0),
        "pid": os.getpid(),
        "cwd": str(Path.cwd()),
        "size": _size(),
        "results": results,
    }
    staged = REPORT.with_suffix(".tmp")
    staged.parent.mkdir(parents=True, exist_ok=True)
    staged.write_text(json.dumps(data))
    staged.replace(REPORT)


def _on_winch(*_: object) -> None:
    winch["seen"] = True


def _swap_log_dir() -> str:
    agents = sorted(
        Path.cwd().glob(".specify/workflow-state/*/agents/*"),
        key=lambda p: p.stat().st_mtime,
    )
    if not agents:
        return "no log directory"
    current = agents[-1]
    moved = current.with_name(current.name + "-moved")
    decoy = HERE / "decoy"
    decoy.mkdir(exist_ok=True)
    current.rename(moved)
    current.symlink_to(decoy)
    return str(moved)


def _order(text: str) -> None:
    log = os.environ.get("FAKE_ORDER_LOG")
    if log:
        with Path(log).open("a") as handle:
            handle.write(text + "\n")


def main() -> int:  # noqa: C901, D103, PLR0912, PLR0915 - one branch per action
    if sys.argv[1:2] == ["sandbox"]:
        return int(os.environ.get("FAKE_CODEX_NESTS", "0"))
    signal.signal(signal.SIGWINCH, _on_winch)
    scenario = HERE / "scenario.json"
    actions = json.loads(scenario.read_text()) if scenario.exists() else []
    _order("agent start")
    _report()
    code = 0
    for action in actions:
        name, *args = action
        if name in {"write", "append"}:
            path = Path(args[0])
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a" if name == "append" else "w") as handle:
                handle.write(args[1])
            results.append([name, args[0]])
        elif name == "print":
            sys.stdout.write(args[0] + "\n")
            sys.stdout.flush()
        elif name == "read_line":
            results.append(["read_line", sys.stdin.readline().rstrip("\r\n")])
        elif name == "try_write":
            try:
                with Path(args[0]).open("a") as handle:
                    handle.write("")
                results.append(["try_write", args[0], "ok"])
            except OSError as error:
                results.append(["try_write", args[0], error.errno])
        elif name == "run":
            try:
                done = subprocess.run(  # noqa: S603
                    args[0], capture_output=True, text=True, check=False, timeout=60
                )
                results.append(
                    ["run", args[0], done.returncode, done.stdout + done.stderr]
                )
            except (OSError, subprocess.TimeoutExpired) as error:
                results.append(["run", args[0], None, str(error)])
        elif name == "sleep":
            time.sleep(float(args[0]))
        elif name == "close_terminal":
            null = os.open(os.devnull, os.O_RDWR)
            for fd in (0, 1, 2):
                os.dup2(null, fd)
        elif name == "ignore":
            signal.signal(getattr(signal, args[0]), signal.SIG_IGN)
        elif name == "wait_winch":
            deadline = time.monotonic() + float(args[0])
            while not winch["seen"] and time.monotonic() < deadline:
                time.sleep(0.02)
            results.append(["wait_winch", winch["seen"], _size()])
        elif name == "swap_log_dir":
            results.append(["swap_log_dir", _swap_log_dir()])
        elif name == "exit":
            code = int(args[0])
            break
        _report()
    _report()
    _order("agent exit")
    return code


if __name__ == "__main__":
    sys.exit(main())
