"""Public progress validation: secret shapes are refused, ordinary words are not."""

from __future__ import annotations

import unittest

from tools import admission, progress

REPO = "owner/repo"


def declare(summary: str) -> dict:
    """Build a plan declaration around one summary."""
    return {"kind": "plan", "state": "proposed", "summary": summary}


class ProgressValidationTests(unittest.TestCase):
    """Table-driven accepted and refused public progress text and revisions."""

    def test_summary_filter(self) -> None:
        accepted = (
            "Tokenizer tests passed",
            "Account page renders",
            "Fix /health endpoint",
            "Protocol docs updated",
            "Reasoning section reworded",
            "See https://github.com/x/y/pull/1 for evidence",
            "Docs at https://example.com/a/b updated",
            "Task-force risk-review done",
            "Compass=north, bypass=on",
            "Tests pass: all green",
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
            "DB_PASSWORD=hunter2",
            "GITHUB_TOKEN=abc",
            "client_secret=abc",
            "access_token: abc",
            "AWS_SECRET_ACCESS_KEY=x",
            "api key: abc",
            "Authorization Basic xyz",
            "xoxb-123-abc",
            "xoxe-123-abc",
            "aws-secret-access-key=abc",
            "secret-access-key: abc",
            "credential=abc",
            "eyJhbGciOi.eyJzdWIiOi",
            "clone https://user:pw@example.com/repo",
            "see [/home/x/y]",
            "see {/home/x/y}",
            "see <ftp:/home/x/y>",
            "dir:/home/x/y",
            "a,/home/x/y",
            "AKIAABCDEFGHIJKLMNOP",
            "glpat-abc123",
            "XOXB-123-abc",
            "eyjhbGciOi.eyjzdWIiOi",
            "ASIAABCDEFGHIJKLMNOP",
            "see file:///home/x/y",
            "file:///x",
            "pwd=hunter2",
            "DB_PASS=hunter2",
            "pass = abc",
            "-----BEGIN RSA PRIVATE KEY-----",
            "see /dev/sda",
            "see /Volumes/Work",
            "see /workspace/acme/app",
            "see /nix/store/x",
            "see /data/x",
            "see /Library/x",
            "(/home/x)",
            "`/home/x`",
            "dir=/home/x",
            "C:\\Users\\x",
            "line\x00break",
            "tab\there",
        )
        for text in accepted:
            with self.subTest(accepted=text):
                value = declare(text)
                self.assertEqual(progress.validate(value, REPO), value)
        for text in rejected:
            with (
                self.subTest(rejected=text),
                self.assertRaises(admission.AdmissionError),
            ):
                progress.validate(declare(text), REPO)

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
