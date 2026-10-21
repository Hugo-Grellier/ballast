"""`ballast <command>`: run one helper isolated, as `python3 -I -S tools/X.py` does."""

from __future__ import annotations

import os
import sys
from pathlib import Path

COMMANDS = {
    "coordinate": "coordinate.py",
    "dashboard": "dashboard.py",
    "merge-check": "merge_check.py",
    "worker": "worker.py",
    "worktree": "worktree.py",
}


def main() -> int:
    """Replace this process with the helper, so it gets `-I -S` and its own exit."""
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:  # noqa: PLR2004 -- argv[1]
        sys.stderr.write(f"usage: ballast {{{','.join(COMMANDS)}}} [args ...]\n")
        return 2
    script = str(Path(__file__).resolve().with_name(COMMANDS[sys.argv[1]]))
    os.execv(sys.executable, [sys.executable, "-I", "-S", script, *sys.argv[2:]])  # noqa: S606 -- fixed helper path
    return 1  # pragma: no cover -- execv does not return


if __name__ == "__main__":
    sys.exit(main())
