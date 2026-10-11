"""PreToolUse hook of an interactive Claude Chat step (#20, DEC-0001).

`claude-chat-settings.json` runs it before every tool call. A Chat step runs
in `dontAsk` mode, where anything the headless rules do not allow is denied
without a prompt. Shift+Tab can leave that mode inside the session, and the
other modes prompt; this hook then denies every tool call, so the operator is
never asked to grant more. Shift+Tab does not cycle back to `dontAsk`, so the
remedy is to end the step and run it again (#113). It reads only its JSON input
and fails closed.
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
        f"this session is in {mode!r} mode and cannot return to it. End the step "
        "(`/exit`) and run the same `ballast run step` again.\n"
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
