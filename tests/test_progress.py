"""Public progress validation: secret shapes are refused, ordinary words are not."""

from __future__ import annotations

import unittest

from tools import admission, progress

REPO = "owner/repo"


def declare(summary: str, **extra: object) -> dict:
    """Build a plan declaration around one summary."""
    return {"kind": "phase", "state": "plan", **extra, "summary": summary}


class ProgressValidationTests(unittest.TestCase):
    """Table-driven accepted and refused public progress text and revisions."""

    def test_summary_filter(self) -> None:
        accepted = (
            "Tokenizer tests passed",
            "Account page renders",
            "Fix /health endpoint",
            "Protocol docs updated",
            "Reasoning section reworded",
            "Task-force risk-review done",
        )
        rejected = (
            "key sk-abc123def456",
            "pushed with ghp_abc123def456",
            "github_pat_11ABC",
            "Bearer abc123def",
            "password=hunter2",
            "token: abc",
            "API_KEY=abc",
            "see /home/x/project",
            "see /etc/passwd",
            "wrote ~/notes",
            "see output.txt",
            "line\x00break",
            "tab\there",
        )
        for text in accepted:
            with self.subTest(accepted=text):
                value = declare(text, kind="plan", state="proposed")
                self.assertEqual(progress.validate(value, REPO), value)
        for text in rejected:
            with (
                self.subTest(rejected=text),
                self.assertRaises(admission.AdmissionError),
            ):
                progress.validate(declare(text, kind="plan", state="proposed"), REPO)

    def test_revision_accepts_sha1_and_sha256_only(self) -> None:
        check = {"kind": "check", "state": "passed", "summary": "Checks passed"}
        for revision in ("a" * 40, "0" * 64):
            with self.subTest(accepted=len(revision)):
                progress.validate({**check, "revision": revision}, REPO)
        for revision in ("a" * 39, "a" * 41, "a" * 63, "A" * 40, "a" * 65, None):
            with (
                self.subTest(rejected=revision),
                self.assertRaises(admission.AdmissionError),
            ):
                progress.validate({**check, "revision": revision}, REPO)


if __name__ == "__main__":
    unittest.main()
