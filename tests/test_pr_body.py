"""PR body check: every defect is reported, a complete body passes."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from tools import pr_body

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / ".github/pull_request_template.md").read_text(encoding="utf-8")
HEADINGS = pr_body.HEADING.findall(TEMPLATE)
HASH = "ab" * 32
SPEC_LINK = "https://github.com/o/r/issues/5#issuecomment-77"
SPEC = f"Spec hash: {HASH}\nSpec approval: {SPEC_LINK}\n"


def body(
    *,
    drop: str | None = None,
    link: str = "Closes #7",
    ticks: tuple[str, ...] = ("R1",),
    approval: str = "",
    spec: str = SPEC,
) -> str:
    """Build a conforming body, then break one thing."""
    parts = []
    for heading in HEADINGS:
        if heading == drop:
            continue
        text = f"## {heading}\n\n"
        if heading == "Related issue":
            text += f"{link}\n\n"
        if heading == "Risk":
            text += "".join(
                f"- [{'x' if r in ticks else ' '}] {r}\n" for r in ("R0", "R1", "R2")
            )
            text += f"{approval}\n\n" if approval else "\n"
        if heading == "Spec":
            text += f"{spec}\n"
        parts.append(text)
    return "".join(parts)


class PrBodyTests(unittest.TestCase):
    """Structure checks on built bodies and the command line."""

    def check(self, text: str) -> list[str]:
        return pr_body.problems(text, TEMPLATE)

    def test_complete_body_passes(self) -> None:
        self.assertEqual(self.check(body()), [])
        self.assertEqual(self.check(body(link="Refs #7")), [])

    def test_each_missing_heading_is_reported(self) -> None:
        for heading in HEADINGS:
            with self.subTest(heading=heading):
                found = self.check(body(drop=heading))
                self.assertIn(f"missing section: ## {heading}", found)

    def test_missing_issue_link(self) -> None:
        self.assertTrue(
            any("issue link" in p for p in self.check(body(link="see the issue")))
        )

    def test_risk_boxes(self) -> None:
        for ticks in ((), ("R0", "R2")):
            with self.subTest(ticks=ticks):
                self.assertTrue(
                    any("risk box" in p for p in self.check(body(ticks=ticks)))
                )

    def test_r2_needs_an_approval_comment_link(self) -> None:
        base = "https://github.com/o/r"
        ok = (
            f"Relayed: {base}/issues/5#issuecomment-123",
            f"Direct: {base}/pull/9#issuecomment-1",
            f"Review: {base}/pull/9#pullrequestreview-2",
        )
        for link in ok:
            with self.subTest(link=link):
                self.assertEqual(self.check(body(ticks=("R2",), approval=link)), [])
        for bad in ("", "approved in chat", f"{base}/issues/5", f"{base}/issues/5#x"):
            with self.subTest(bad=bad):
                found = self.check(body(ticks=("R2",), approval=bad))
                self.assertTrue(any("R2 needs" in p for p in found))

    def test_approval_link_outside_risk_section_does_not_count(self) -> None:
        link = "https://github.com/o/r/issues/5#issuecomment-123"
        text = body(ticks=("R2",)).replace("## Summary\n", f"## Summary\n{link}\n")
        self.assertTrue(any("R2 needs" in p for p in self.check(text)))

    def test_r0_and_r1_need_no_approval_link(self) -> None:
        for tick in ("R0", "R1"):
            self.assertEqual(self.check(body(ticks=(tick,))), [])

    def test_r1_and_r2_need_a_spec_hash_and_approval_link(self) -> None:
        link = "https://github.com/o/r/issues/5#issuecomment-123"
        no_hash = f"Spec approval: {SPEC_LINK}\n"
        no_link = f"Spec hash: {HASH}\n"
        for tick, approval in (("R1", ""), ("R2", link)):
            for label, spec, fragment in (
                ("no hash", no_hash, "Spec hash"),
                ("short hash", no_hash + "Spec hash: abc\n", "Spec hash"),
                ("no link", no_link, "Spec approved"),
                (
                    "PR comment link",
                    no_link + link.replace("issues", "pull"),
                    "Spec approved",
                ),
                ("commented out", f"<!-- {SPEC} -->", "Spec hash"),
                (
                    "reviewer waiver",
                    "No behavior changed (reviewer).\n" + no_hash,
                    "Spec hash",
                ),
            ):
                with self.subTest(tick=tick, case=label):
                    found = self.check(
                        body(ticks=(tick,), approval=approval, spec=spec)
                    )
                    self.assertTrue(any(fragment in p for p in found), found)

    def test_spec_hash_outside_the_spec_section_does_not_count(self) -> None:
        text = body(spec="").replace("## Summary\n", f"## Summary\n{SPEC}\n")
        found = self.check(text)
        self.assertTrue(any("Spec hash" in p for p in found), found)
        self.assertTrue(any("Spec approved" in p for p in found), found)

    def test_r0_needs_no_spec_hash(self) -> None:
        self.assertEqual(self.check(body(ticks=("R0",), spec="none")), [])

    def test_commented_out_content_does_not_count(self) -> None:
        self.assertTrue(self.check(body(link="<!-- Closes #7 -->")))

    def run_main(self, *args: str) -> tuple[int, str]:
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = pr_body.main(
                [*args, "--template", str(ROOT / ".github/pull_request_template.md")]
            )
        return code, err.getvalue()

    def test_cli_body_file_and_event_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            good, bad, event, null = (Path(tmp) / n for n in ("g", "b", "e", "n"))
            good.write_text(body())
            bad.write_text(body(drop="Security impact"))
            event.write_text(json.dumps({"pull_request": {"body": body()}}))
            null.write_text(json.dumps({"pull_request": {"body": None}}))
            self.assertEqual(self.run_main("--body-file", str(good))[0], 0)
            code, err = self.run_main("--body-file", str(bad))
            self.assertEqual(code, 1)
            self.assertIn("## Security impact", err)
            self.assertEqual(self.run_main("--event-file", str(event))[0], 0)
            self.assertEqual(self.run_main("--event-file", str(null))[0], 1)

    def test_crlf_event_payload_passes(self) -> None:
        crlf = body().replace("\n", "\r\n")
        with tempfile.TemporaryDirectory() as tmp:
            event = Path(tmp) / "e"
            event.write_text(json.dumps({"pull_request": {"body": crlf}}))
            self.assertEqual(self.run_main("--event-file", str(event))[0], 0)
        self.assertEqual(self.check(crlf), [])

    def test_event_without_pull_request_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            event = Path(tmp) / "e"
            event.write_text("{}")
            self.assertEqual(self.run_main("--event-file", str(event))[0], 2)

    def test_adopter_copies_match_the_source(self) -> None:
        pairs = {
            "templates/github/scripts/pr_body.py": "tools/pr_body.py",
            "templates/github/pull_request_template.md": (
                ".github/pull_request_template.md"
            ),
        }
        for copy, source in pairs.items():
            self.assertEqual(
                (ROOT / copy).read_bytes(), (ROOT / source).read_bytes(), copy
            )
        workflow = (ROOT / "templates/github/workflows/pr-body.yml").read_text()
        self.assertIn(
            '.github/scripts/pr_body.py --event-file "$GITHUB_EVENT_PATH"', workflow
        )
        self.assertNotIn("github.event.pull_request.body", workflow)

    def test_generated_prs_are_skipped(self) -> None:
        for path in (
            ".github/workflows/pr-body.yml",
            "templates/github/workflows/pr-body.yml",
        ):
            workflow = (ROOT / path).read_text()
            self.assertIn(
                "github.event.pull_request.user.login != 'dependabot[bot]'",
                workflow,
                path,
            )
            self.assertIn(
                "!startsWith(github.head_ref, 'release-please--')", workflow, path
            )


if __name__ == "__main__":
    unittest.main()
