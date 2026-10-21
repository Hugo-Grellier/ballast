"""Check a PR body against the PR template.

Checks headings, issue link, one risk box, and an approval link when R2 is ticked.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HEADING = re.compile(r"^##[ \t]+(.+?)[ \t]*$", re.MULTILINE)
ISSUE_LINK = re.compile(
    r"\b(?:Closes|Refs)[ \t]+(?:[\w.-]+/[\w.-]+)?#\d+\b", re.IGNORECASE
)
RISK_BOX = re.compile(r"^[ \t]*[-*][ \t]+\[[xX]\][ \t]+R[0-2]\b", re.MULTILINE)
R2_BOX = re.compile(r"^[ \t]*[-*][ \t]+\[[xX]\][ \t]+R2\b", re.MULTILINE)
RISK_SECTION = re.compile(
    r"^##[ \t]+Risk[ \t]*$(.*?)(?=^##[ \t]|\Z)", re.MULTILINE | re.DOTALL
)
APPROVAL_LINK = re.compile(
    r"https://github\.com/[\w.-]+/[\w.-]+/(?:issues|pull)/\d+"
    r"#(?:issuecomment|pullrequestreview)-\d+"
)
COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


def problems(body: str, template: str) -> list[str]:
    """Return one line per structural defect; empty means the body conforms."""
    body = COMMENT.sub("", body.replace("\r\n", "\n").replace("\r", "\n"))
    template = template.replace("\r\n", "\n").replace("\r", "\n")
    present = set(HEADING.findall(body))
    found = [
        f"missing section: ## {h}"
        for h in HEADING.findall(template)
        if h not in present
    ]
    if not ISSUE_LINK.search(body):
        found.append("missing issue link: write `Closes #N` or `Refs #N`")
    ticked = len(RISK_BOX.findall(body))
    if ticked != 1:
        found.append(f"tick exactly one risk box (R0, R1 or R2); found {ticked}")
    risk = RISK_SECTION.search(body)
    if R2_BOX.search(body) and not (risk and APPROVAL_LINK.search(risk.group(1))):
        found.append(
            "R2 needs a link to the human approval comment in the Risk section"
            " (…/issues/N#issuecomment-ID or …/pull/N#issuecomment-ID)"
        )
    return found


def main(argv: list[str] | None = None) -> int:
    """Check the body named on the command line; exit 1 on a defect."""
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--body-file", type=Path)
    source.add_argument(
        "--event-file", type=Path, help="GitHub pull_request event payload"
    )
    parser.add_argument(
        "--template", type=Path, default=Path(".github/pull_request_template.md")
    )
    args = parser.parse_args(argv)
    if args.body_file:
        body = args.body_file.read_text(encoding="utf-8")
    else:
        pull_request = json.loads(args.event_file.read_text(encoding="utf-8")).get(
            "pull_request"
        )
        if not isinstance(pull_request, dict):
            sys.stderr.write("event payload has no pull_request\n")
            return 2
        body = pull_request.get("body") or ""
    found = problems(body, args.template.read_text(encoding="utf-8"))
    for line in found:
        sys.stderr.write(line + "\n")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
