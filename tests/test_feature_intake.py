"""Behavioral tests for GitHub issue intake with a fake gh executable."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

SCRIPT = Path(__file__).resolve().parents[1] / "tools/feature_intake.py"
FAKE_GH = r"""#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

path = Path(os.environ["FAKE_GH_STATE"])
state = json.loads(path.read_text())
args = sys.argv[1:]
if args[0] != "api":
    raise SystemExit(2)
endpoint = urlsplit(args[1])
parts = endpoint.path.split("/")
method = args[args.index("-X") + 1] if "-X" in args else "GET"
fields = {}
for index, value in enumerate(args):
    if value in ("-f", "-F"):
        key, _, content = args[index + 1].partition("=")
        fields[key] = content

def save():
    path.write_text(json.dumps(state))

def output(value):
    print(json.dumps(value))

def fail(operation):
    if state.get("fail_at") == operation and not state.get("failed"):
        state["failed"] = True
        save()
        print("simulated failure after " + operation, file=sys.stderr)
        raise SystemExit(1)

def issue(number):
    return state["issues"].get(str(number))

if parts[:3] != ["repos", "owner", "repo"]:
    raise SystemExit(2)
if parts[3] != "issues":
    raise SystemExit(2)

if len(parts) == 4 and method == "GET":
    values = list(state["issues"].values())
    query = parse_qs(endpoint.query)
    page = int(query.get("page", ["1"])[0])
    output(values[(page - 1) * 100:page * 100])
elif len(parts) == 4 and method == "POST":
    number = state["next"]
    state["next"] += 1
    record = {"number": number, "id": 10000 + number, "title": fields["title"],
              "body": fields["body"], "state": "open", "labels": [], "milestone": None}
    state["issues"][str(number)] = record
    save()
    fail("create")
    output(record)
elif len(parts) == 5 and method == "GET":
    record = issue(parts[4])
    if record is None:
        print("gh: Not Found (HTTP 404)", file=sys.stderr)
        raise SystemExit(1)
    output(record)
elif len(parts) == 6 and parts[5] == "parent" and method == "GET":
    parent = state["parents"].get(parts[4])
    if parent is None:
        print("gh: No parent issue found (HTTP 404)", file=sys.stderr)
        raise SystemExit(1)
    output(issue(parent))
elif len(parts) == 6 and parts[5] == "sub_issues" and method == "GET":
    output([issue(number) for number, parent in state["parents"].items()
            if str(parent) == parts[4]])
elif len(parts) == 6 and parts[5] == "sub_issues" and method == "POST":
    child = int(fields["sub_issue_id"]) - 10000
    state["parents"][str(child)] = int(parts[4])
    save()
    fail("link")
    output(issue(child))
elif len(parts) == 7 and parts[5:] == ["dependencies", "blocked_by"]:
    output([issue(number) for number in state["blocked_by"].get(parts[4], [])])
elif len(parts) == 6 and parts[5] == "comments" and method == "GET":
    output([None] if state.get("bad_comments") else state["comments"].get(parts[4], []))
elif len(parts) == 6 and parts[5] == "comments" and method == "POST":
    state["comments"].setdefault(parts[4], []).append({"body": fields["body"]})
    save()
    fail("comment")
    output({"body": fields["body"]})
elif len(parts) == 6 and parts[5] == "labels" and method == "POST":
    record = issue(parts[4])
    label = fields["labels[]"]
    if {"name": label} not in record["labels"]:
        record["labels"].append({"name": label})
    save()
    fail("label")
    output(record["labels"])
else:
    print("unexpected fake endpoint: " + endpoint.path, file=sys.stderr)
    raise SystemExit(2)
"""


def issue(number: int, *, epic: bool = False, body: str | None = None) -> dict:
    """Build a fictional issue for the fake GitHub server."""
    return {
        "number": number,
        "id": 10000 + number,
        "title": "Parent Epic" if epic else "Existing feature",
        "body": body or "## Acceptance criteria\n\n- [ ] Works",
        "state": "open",
        "labels": [{"name": "epic"}] if epic else [{"name": "keep-me"}],
        "milestone": {"title": "MVP"},
    }


class FeatureIntakeTests(unittest.TestCase):
    """Exercise preflight and partial-write recovery through the CLI boundary."""

    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        fake = self.root / "gh"
        fake.write_text(FAKE_GH)
        fake.chmod(0o755)
        self.state_path = self.root / "state.json"
        self.state = {
            "issues": {"89": issue(89, epic=True), "103": issue(103)},
            "parents": {},
            "blocked_by": {},
            "comments": {},
            "next": 200,
        }
        self.save()
        self.scope = self.root / "scope.md"
        self.scope.write_text(
            "Scope gate: Feature / actionable leaf\nMain outcome: import text\n"
            "In scope: text\nOut of scope: audio\nRisk: R1\n"
        )
        self.body = self.root / "body.md"
        self.body.write_text(
            "## Outcome\n\nImport text\n\n"
            "## Acceptance criteria\n\n- [ ] Inspect text\n"
        )

    def save(self) -> None:
        self.state_path.write_text(json.dumps(self.state))

    def run_intake(self, *args: str) -> tuple[int, dict]:
        env = {
            **os.environ,
            "PATH": f"{self.root}:{os.environ['PATH']}",
            "FAKE_GH_STATE": str(self.state_path),
        }
        result = subprocess.run(  # noqa: S603
            [sys.executable, str(SCRIPT), "--repo", "owner/repo", *args],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        self.assertTrue(result.stdout, result.stderr)
        return result.returncode, json.loads(result.stdout)

    def test_preflight_rejects_epic_blocked_and_closed(self) -> None:
        code, result = self.run_intake("preflight", "89")
        self.assertEqual(code, 1)
        self.assertFalse(result["eligible_leaf"])
        self.state["blocked_by"]["103"] = [89]
        self.save()
        code, result = self.run_intake("preflight", "103")
        self.assertEqual(code, 1)
        self.assertEqual(result["blocked_by"], [89])
        self.state["blocked_by"] = {}
        self.state["issues"]["103"]["state"] = "closed"
        self.save()
        code, result = self.run_intake("preflight", "103")
        self.assertEqual(code, 1)
        self.assertIn("issue is not open", result["problems"])

    def test_preflight_rejects_unlabelled_parent_and_missing_acceptance(self) -> None:
        self.state["issues"]["103"]["labels"] = []
        self.state["parents"]["200"] = 103
        self.state["issues"]["200"] = issue(200)
        self.save()
        code, result = self.run_intake("preflight", "103")
        self.assertEqual(code, 1)
        self.assertIn("issue is an Epic or has sub-issues", result["problems"])
        self.state["parents"] = {}
        self.state["issues"]["103"]["body"] = "No acceptance section"
        self.save()
        code, result = self.run_intake("preflight", "103")
        self.assertEqual(code, 1)
        self.assertIn("issue has no acceptance criteria section", result["problems"])

    def test_retries_after_each_partial_write_without_duplicate_child(self) -> None:
        for failure in ("create", "link", "comment", "label"):
            with self.subTest(failure=failure):
                self.state["issues"] = {"89": issue(89, epic=True)}
                self.state["parents"] = {}
                self.state["comments"] = {}
                self.state["next"] = 200
                self.state["fail_at"] = failure
                self.state["failed"] = False
                self.save()
                command = (
                    "prepare",
                    "--parent",
                    "89",
                    "--slug",
                    "text-import",
                    "--title",
                    "Import text",
                    "--body-file",
                    str(self.body),
                    "--scope-file",
                    str(self.scope),
                    "--classification",
                    "feature",
                )
                code, first = self.run_intake(*command)
                self.assertEqual(code, 1, first)
                self.assertTrue(first["pending"])
                code, second = self.run_intake(*command)
                self.assertEqual(code, 0, second)
                state = json.loads(self.state_path.read_text())
                self.assertEqual(len(state["issues"]), 2)
                self.assertEqual(state["parents"], {"200": 89})
                self.assertEqual(len(state["comments"]["200"]), 1)
                self.assertEqual(
                    {label["name"] for label in state["issues"]["200"]["labels"]},
                    {"ready-for-agent"},
                )
                self.assertEqual(state["issues"]["89"]["milestone"], {"title": "MVP"})
                self.assertEqual(state["issues"]["89"]["labels"], [{"name": "epic"}])

    def test_conflicting_child_and_scope_are_not_overwritten(self) -> None:
        marker = "<!-- ballast-intake: parent=#89; slug=text-import -->"
        self.state["issues"]["200"] = issue(200, body=marker)
        self.state["issues"]["200"]["title"] = "Import text"
        self.state["issues"]["201"] = issue(201, body=marker)
        self.state["issues"]["201"]["title"] = "Import text"
        self.save()
        command = (
            "prepare",
            "--parent",
            "89",
            "--slug",
            "text-import",
            "--title",
            "Import text",
            "--body-file",
            str(self.body),
            "--scope-file",
            str(self.scope),
            "--classification",
            "feature",
        )
        code, result = self.run_intake(*command)
        self.assertEqual(code, 1)
        self.assertIn("multiple issues", result["error"])
        self.assertEqual(len(json.loads(self.state_path.read_text())["issues"]), 4)

    def test_invalid_child_body_does_not_create_issue(self) -> None:
        self.body.write_text("## Outcome\n\nImport text\n")
        command = (
            "prepare",
            "--parent",
            "89",
            "--slug",
            "text-import",
            "--title",
            "Import text",
            "--body-file",
            str(self.body),
            "--scope-file",
            str(self.scope),
            "--classification",
            "feature",
        )
        code, result = self.run_intake(*command)
        self.assertEqual(code, 1)
        self.assertIn("acceptance criteria", result["error"])
        self.assertEqual(len(json.loads(self.state_path.read_text())["issues"]), 2)

    def test_existing_leaf_preserves_unrelated_issue_state(self) -> None:
        command = (
            "prepare",
            "--issue",
            "103",
            "--scope-file",
            str(self.scope),
            "--classification",
            "feature",
        )
        code, result = self.run_intake(*command)
        self.assertEqual(code, 0, result)
        code, result = self.run_intake(*command)
        self.assertEqual(code, 0, result)
        state = json.loads(self.state_path.read_text())
        self.assertEqual(len(state["comments"]["103"]), 1)
        self.assertEqual(
            {label["name"] for label in state["issues"]["103"]["labels"]},
            {"keep-me", "ready-for-agent"},
        )
        self.assertEqual(state["issues"]["103"]["milestone"], {"title": "MVP"})

    def test_prepare_cannot_label_an_epic(self) -> None:
        command = (
            "prepare",
            "--issue",
            "89",
            "--scope-file",
            str(self.scope),
            "--classification",
            "feature",
        )
        code, result = self.run_intake(*command)
        self.assertEqual(code, 1)
        self.assertIn("Epic", result["error"])
        state = json.loads(self.state_path.read_text())
        self.assertEqual(state["issues"]["89"]["labels"], [{"name": "epic"}])
        self.assertFalse(state["comments"])

    def test_retry_rejects_changed_scope_classification(self) -> None:
        command = (
            "prepare",
            "--issue",
            "103",
            "--scope-file",
            str(self.scope),
            "--classification",
            "feature",
        )
        self.assertEqual(self.run_intake(*command)[0], 0)
        changed = (*command[:-1], "bug")
        code, result = self.run_intake(*changed)
        self.assertEqual(code, 1)
        self.assertIn("conflicting intake scope", result["error"])
        self.assertEqual(
            len(json.loads(self.state_path.read_text())["comments"]["103"]), 1
        )

    def test_malformed_github_response_keeps_recovery_result(self) -> None:
        self.state["bad_comments"] = True
        self.save()
        command = (
            "prepare",
            "--issue",
            "103",
            "--scope-file",
            str(self.scope),
            "--classification",
            "feature",
        )
        code, result = self.run_intake(*command)
        self.assertEqual(code, 1)
        self.assertEqual(
            result["error"], "GitHub returned an unexpected response shape"
        )
        self.assertEqual(result["pending"], ["scope", "ready"])
        self.assertEqual(result["completed"], [])


if __name__ == "__main__":
    unittest.main()
