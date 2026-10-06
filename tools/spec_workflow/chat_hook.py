"""PreToolUse hook of an interactive Claude Chat step (#20, DEC-0001).

`claude-chat-settings.json` runs it before every tool call. A Chat step runs
in `dontAsk` mode, where anything the headless rules do not allow is denied
without a prompt. Shift+Tab can leave that mode inside the session, and the
other modes prompt; this hook then denies every tool call, so the operator is
never asked to grant more. It reads only its JSON input and fails closed.
"""

import json
import sys

MODE = "dontAsk"


def main() -> int:
    """Exit 0 in dontAsk mode; otherwise block the call (exit 2)."""
    try:
        mode = json.load(sys.stdin).get("permission_mode")
    except (ValueError, AttributeError):
        mode = None
    if mode == MODE:
        return 0
    sys.stderr.write(
        f"Ballast Chat steps run in {MODE} mode, so nothing is granted by a prompt; "
        f"this session is in {mode!r} mode. Press Shift+Tab until it is {MODE}.\n"
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
