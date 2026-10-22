"""Living spec checker: each refusal, coverage, and the canonical delta hash."""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools import spec_check

TEST_FILE = """\
import unittest


class QueueTests(unittest.TestCase):
    def test_admits(self):
        pass

    def test_full(self):
        pass
"""

SPEC = """\
# Queue

Covers: tools/queue.py

### Requirement: Admission
The queue SHALL admit an issue while a
slot is free.

#### Scenario: Free slot
- WHEN a slot is free
- THEN the issue is admitted
- Test: tests/test_queue.py::QueueTests::test_admits

#### Scenario: Full queue
- WHEN no slot is free
- THEN the issue waits
- Test: tests/test_queue.py::QueueTests::test_full
"""


def run_git(root: Path, *args: str) -> str:
    """Run git in root for a test fixture."""
    return subprocess.run(  # noqa: S603 -- fixed git argv
        ["git", "-C", str(root), *args],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    ).stdout


class Repo:
    """A throwaway Git repository with a test file and specs."""

    def __init__(self, base: Path) -> None:
        """Initialize the repository with a test file and a source file."""
        self.root = base
        run_git(base, "init", "-q", "-b", "main")
        run_git(base, "config", "user.email", "t@example.invalid")
        run_git(base, "config", "user.name", "t")
        run_git(base, "config", "commit.gpgsign", "false")
        self.write("tests/test_queue.py", TEST_FILE)
        self.write("tools/queue.py", "")

    def write(self, path: str, text: str) -> None:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def commit(self, message: str = "c") -> None:
        run_git(self.root, "add", "-A")
        run_git(self.root, "commit", "-q", "-m", message)

    def main(self, *args: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = spec_check.main(["--root", str(self.root), *args])
        return code, out.getvalue(), err.getvalue()


class SpecFormatTests(unittest.TestCase):
    """Each malformed spec is refused with a named defect."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Repo(Path(tmp.name))

    def defects(self, text: str) -> list[str]:
        return spec_check.check_spec(text, "docs/specs/q.md", self.repo.root, {})

    def assert_defect(self, text: str, fragment: str) -> None:
        found = self.defects(text)
        self.assertTrue(any(fragment in d for d in found), found)

    def test_valid_spec_passes(self) -> None:
        self.assertEqual(self.defects(SPEC), [])

    def test_requirement_without_shall(self) -> None:
        self.assert_defect(SPEC.replace("SHALL", "may"), "without a SHALL")

    def test_requirement_without_name(self) -> None:
        text = SPEC.replace("Requirement: Admission", "Requirement:")
        self.assert_defect(text, "requirement without a name")

    def test_unknown_level_three_heading(self) -> None:
        self.assert_defect(SPEC + "\n### Notes\n", "must be `Requirement: NAME`")

    def test_scenario_without_when_or_then(self) -> None:
        self.assert_defect(SPEC.replace("- WHEN a slot", "- IF a slot"), "WHEN line")
        self.assert_defect(SPEC.replace("- THEN the issue w", "- so w"), "THEN line")

    def test_scenario_outside_requirement(self) -> None:
        text = "Covers: x\n\n#### Scenario: Lost\n- WHEN a\n- THEN b\n"
        self.assert_defect(text, "scenario outside a requirement")

    def test_scenario_without_test_reference(self) -> None:
        text = SPEC.replace("- Test: tests/test_queue.py::QueueTests::test_full\n", "")
        self.assert_defect(text, "no `Test: path::Class::method` reference")

    def test_malformed_test_reference(self) -> None:
        text = SPEC.replace("QueueTests::test_full", "test_full")
        self.assert_defect(text, "malformed test reference")

    def test_reference_to_missing_file(self) -> None:
        text = SPEC.replace(
            "tests/test_queue.py::QueueTests::test_full", "t/no.py::A::b"
        )
        self.assert_defect(text, "test file not found: t/no.py")

    def test_reference_outside_repository(self) -> None:
        text = SPEC.replace("tests/test_queue.py::Q", "../x.py::Q")
        self.assert_defect(text, "outside the repository")

    def test_reference_to_missing_class_or_method(self) -> None:
        self.assert_defect(SPEC.replace("QueueTests::test_full", "No::x"), "class not")
        self.assert_defect(SPEC.replace("::test_full", "::test_gone"), "method not")

    def test_duplicate_requirement(self) -> None:
        second = SPEC[SPEC.index("### Requirement") :]
        self.assert_defect(SPEC + "\n" + second, "duplicate requirement: Admission")

    def test_duplicate_scenario(self) -> None:
        text = SPEC.replace("Scenario: Full queue", "Scenario: Free slot")
        self.assert_defect(text, "duplicate scenario: Free slot")

    def test_heading_inside_a_code_fence_is_body_text(self) -> None:
        fence = "- THEN the issue waits\n```\n### Notes\n#### x\n```\n"
        self.assertEqual(
            self.defects(SPEC.replace("- THEN the issue waits\n", fence)), []
        )

    def in_scenario(self, block: str) -> str:
        """Insert block into the last scenario body of the valid spec."""
        return SPEC.replace(
            "- THEN the issue waits\n", "- THEN the issue waits\n" + block
        )

    def test_fence_rules_follow_commonmark(self) -> None:
        for label, block in (
            ("tilde fence", "~~~\n### Notes\n~~~\n"),
            ("backticks inside tildes", "~~~\n```\n### Requirement: Hidden\n~~~\n"),
            ("shorter close", "````\n```\n### Notes\n````\n"),
            ("close with text after it", "```\n``` x\n### Notes\n```\n"),
            ("backtick in the info string", "```a`b\n"),
            ("indented four spaces", "    ```\n"),
        ):
            with self.subTest(case=label):
                self.assertEqual(self.defects(self.in_scenario(block)), [])

    def test_unclosed_fence_is_refused(self) -> None:
        for block in ("```\n", "~~~\n```\n", "```\n~~~\n"):
            with self.subTest(block=block):
                self.assert_defect(self.in_scenario(block), "code fence left open")

    def test_fenced_lines_do_not_count_as_covers(self) -> None:
        example = "```\n### Requirement: Example\nCovers: fenced/**\n```\n\n"
        text = SPEC.replace(
            "Covers: tools/queue.py", example + "Covers: tools/queue.py"
        )
        self.assertEqual(self.defects(text), [])
        covers, _, _ = spec_check.parse_spec(text, "q")
        self.assertEqual(covers, ["tools/queue.py"])

    def test_missing_or_late_covers(self) -> None:
        self.assert_defect(SPEC.replace("Covers: tools/queue.py\n", ""), "no `Covers:")
        self.assert_defect(SPEC + "\nCovers: y\n", "Covers: lines must open")


class SpecCheckCommandTests(unittest.TestCase):
    """The command line: notice, exit codes, overlap and uncovered paths."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Repo(Path(tmp.name))

    def test_repository_without_specs_passes_with_notice(self) -> None:
        self.repo.commit()
        code, _, err = self.repo.main()
        self.assertEqual(code, 0)
        self.assertIn("notice: no docs/specs/", err)

    def test_valid_specs_pass_and_defects_fail(self) -> None:
        self.repo.write("docs/specs/queue.md", SPEC)
        self.repo.commit()
        self.assertEqual(self.repo.main()[0], 0)
        self.repo.write("docs/specs/queue.md", SPEC.replace("SHALL", "may"))
        code, _, err = self.repo.main()
        self.assertEqual(code, 1)
        self.assertIn("without a SHALL", err)

    def test_overlap_is_checked_over_tracked_files(self) -> None:
        # The globs overlap, but only on a path that is not tracked yet.
        self.repo.write(
            "docs/specs/queue.md", SPEC.replace("tools/queue.py", "tools/q*.py")
        )
        self.repo.write(
            "docs/specs/tools.md", SPEC.replace("tools/queue.py", "tools/*x.py")
        )
        self.repo.commit()
        self.repo.write("tools/qx.py", "")
        self.assertEqual(self.repo.main()[0], 0)
        run_git(self.repo.root, "add", "tools/qx.py")
        code, _, err = self.repo.main()
        self.assertEqual(code, 1)
        self.assertIn("tools/qx.py: covered by more than one spec", err)

    def test_uncovered_changed_paths_are_reported(self) -> None:
        self.repo.write("docs/specs/queue.md", SPEC)
        self.repo.commit()
        run_git(self.repo.root, "branch", "base")
        self.repo.write("tools/queue.py", "x = 1\n")
        self.repo.write("tools/other.py", "")
        self.repo.write("docs/guide.md", "")
        self.repo.write("docs/specs/queue.md", SPEC + "\n")
        self.repo.commit()
        code, out, _ = self.repo.main("--changed-from", "base")
        self.assertEqual(code, 0)
        self.assertEqual(
            out.splitlines(), ["uncovered: docs/guide.md", "uncovered: tools/other.py"]
        )
        self.repo.write(
            "project/workflow.md",
            "Coverage-exempt: docs/**\nCoverage-exempt: project/*\n",
        )
        self.repo.commit()
        code, out, _ = self.repo.main("--changed-from", "base")
        self.assertEqual(out.splitlines(), ["uncovered: tools/other.py"])

    def test_stray_files_under_specs_are_refused(self) -> None:
        self.repo.write("docs/specs/queue.md", SPEC)
        self.repo.commit()
        run_git(self.repo.root, "branch", "target")
        for stray in ("docs/specs/sub/nested.md", "docs/specs/notes.txt"):
            with self.subTest(path=stray):
                self.repo.write(stray, SPEC)
                code, _, err = self.repo.main()
                self.assertEqual(code, 1)
                self.assertIn(f"{stray}: docs/specs/ holds only flat *.md", err)
                # A diff hash never silently drops a stray spec edit.
                self.repo.commit()
                code, _, err = self.repo.main("--diff-hash", "target")
                self.assertEqual(code, 2)
                self.assertIn(stray, err)
                (self.repo.root / stray).unlink()
                self.repo.commit()

    def test_glob_semantics(self) -> None:
        self.assertTrue(spec_check.matches("tools/a.py", ["tools/*.py"]))
        self.assertFalse(spec_check.matches("tools/x/a.py", ["tools/*.py"]))
        self.assertTrue(spec_check.matches("tools/x/a.py", ["tools/**"]))
        self.assertTrue(spec_check.matches("a.py", ["**/a.py"]))
        self.assertTrue(spec_check.matches("x/y/a.py", ["**/a.py"]))


MODIFIED = SPEC.replace("- THEN the issue waits", "- THEN the issue waits in order")

DELTA_MODIFIED = """\
# Delta

## Capability: docs/specs/queue.md

### Requirement: Admission

#### Modified Scenario: Full queue
Base:
- WHEN no slot is free
- THEN the issue waits
Result:
- WHEN no slot is free
- THEN the issue waits
  in order
- Test: tests/test_queue.py::QueueTests::test_full

## Open questions

- Should order be FIFO? (not part of the hash)

## Risk

R1
"""


class DeltaHashTests(unittest.TestCase):
    """A delta document and a Git diff hash equal for the same change."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Repo(Path(tmp.name))

    def diff_hash(self, base: str, head: str) -> str:
        """Commit base then head on a branch and hash the docs/specs/ diff."""
        if base:
            self.repo.write("docs/specs/queue.md", base)
        self.repo.commit("base")
        run_git(self.repo.root, "branch", "-f", "target")
        if head:
            self.repo.write("docs/specs/queue.md", head)
        else:
            (self.repo.root / "docs/specs/queue.md").unlink()
        self.repo.commit("head")
        code, out, err = self.repo.main("--diff-hash", "target")
        self.assertEqual(code, 0, err)
        return out.strip()

    def doc_hash(self, text: str) -> str:
        return spec_check.delta_hash(spec_check.parse_delta(text))

    def test_modified_scenario_hashes_equal(self) -> None:
        self.assertEqual(self.diff_hash(SPEC, MODIFIED), self.doc_hash(DELTA_MODIFIED))

    def test_base_text_is_part_of_the_hash(self) -> None:
        # A delta whose Base: is not the real base text never matches the diff.
        wrong = DELTA_MODIFIED.replace(
            "Base:\n- WHEN no slot is free\n- THEN the issue waits\n",
            "Base:\n- WHEN no slot is free\n- THEN the issue is refused\n",
        )
        self.assertNotEqual(wrong, DELTA_MODIFIED)
        self.assertNotEqual(self.diff_hash(SPEC, MODIFIED), self.doc_hash(wrong))

    def test_delta_with_duplicate_key_or_empty_name_is_refused(self) -> None:
        duplicate = (
            DELTA_ADDED + "\n#### Added Scenario: Free slot\n- WHEN a\n- THEN b\n"
        )
        for label, text in (
            ("duplicate entry", duplicate),
            (
                "empty requirement",
                DELTA_ADDED.replace("Requirement: Admission", "Requirement:"),
            ),
            ("empty scenario", DELTA_ADDED.replace("Scenario: Free slot", "Scenario:")),
        ):
            with self.subTest(case=label), self.assertRaises(spec_check.SpecError):
                spec_check.parse_delta(text)

    def test_delta_hash_command_prints_the_hash(self) -> None:
        self.repo.write("delta.md", DELTA_ADDED)
        code, out, err = self.repo.main(
            "--delta-hash", str(self.repo.root / "delta.md")
        )
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out.strip(), self.doc_hash(DELTA_ADDED))

    def test_delta_hash_command_exits_2_on_a_malformed_document(self) -> None:
        duplicate = (
            DELTA_ADDED + "\n#### Added Scenario: Free slot\n- WHEN a\n- THEN b\n"
        )
        self.repo.write("delta.md", duplicate)
        code, out, err = self.repo.main(
            "--delta-hash", str(self.repo.root / "delta.md")
        )
        self.assertEqual((code, out), (2, ""))
        self.assertNotEqual(err, "")

    def test_heading_inside_a_code_fence_in_a_delta(self) -> None:
        fenced = DELTA_ADDED.replace(
            "- THEN the issue waits\n", "- THEN the issue waits\n```\n## Risk\n```\n"
        )
        entries = spec_check.parse_delta(fenced)
        self.assertEqual(len(entries), 3)
        self.assertIn("## Risk", entries[-1]["text"])

    def test_unclosed_fence_in_a_delta_is_refused(self) -> None:
        with self.assertRaises(spec_check.SpecError):
            spec_check.parse_delta(
                DELTA_ADDED.replace(
                    "#### Added Scenario: Full", "```\n#### Added Scenario: Full"
                )
            )

    def test_three_dot_diff_ignores_target_branch_progress(self) -> None:
        expected = self.doc_hash(DELTA_MODIFIED)
        self.repo.write("docs/specs/queue.md", SPEC)
        self.repo.commit("base")
        run_git(self.repo.root, "checkout", "-q", "-b", "feature")
        self.repo.write("docs/specs/queue.md", MODIFIED)
        self.repo.commit("feature")
        run_git(self.repo.root, "checkout", "-q", "main")
        self.repo.write(
            "docs/specs/other.md", SPEC.replace("tools/queue.py", "tools/o.py")
        )
        self.repo.commit("unrelated")
        code, out, _ = self.repo.main("--diff-hash", "main", "--head", "feature")
        self.assertEqual((code, out.strip()), (0, expected))

    def test_added_spec_file(self) -> None:
        delta = DELTA_ADDED
        self.assertEqual(self.diff_hash("", SPEC), self.doc_hash(delta))

    def test_removed_requirement_lists_its_scenarios(self) -> None:
        entries = spec_check.diff_entries("docs/specs/queue.md", SPEC, None)
        keys = [(e["requirement"], e["scenario"], e["change"]) for e in entries]
        self.assertEqual(
            keys,
            [
                ("Admission", None, "removed"),
                ("Admission", "Free slot", "removed"),
                ("Admission", "Full queue", "removed"),
            ],
        )
        partial = DELTA_ADDED.replace("Added", "Removed")
        self.assertEqual(self.diff_hash(SPEC, ""), self.doc_hash(partial))
        dropped = partial[: partial.index("#### Removed Scenario: Full queue")]
        self.assertNotEqual(self.doc_hash(partial), self.doc_hash(dropped))

    def test_shall_when_then_changes_change_the_hash(self) -> None:
        base = spec_check.delta_hash(spec_check.diff_entries("f", SPEC, MODIFIED))
        for old, new in (
            ("SHALL admit", "SHALL refuse"),
            ("WHEN no slot", "WHEN one slot"),
            ("THEN the issue waits in order", "THEN the issue fails"),
        ):
            with self.subTest(line=old):
                changed = MODIFIED.replace(old, new)
                entries = spec_check.diff_entries("f", SPEC, changed)
                self.assertNotEqual(spec_check.delta_hash(entries), base)

    def test_test_and_covers_lines_are_not_part_of_the_delta(self) -> None:
        moved = SPEC.replace("test_full", "test_admits").replace("queue.py\n", "q.py\n")
        self.assertEqual(spec_check.diff_entries("f", SPEC, moved), [])

    def test_key_elements_each_change_the_hash(self) -> None:
        entry = spec_check.entry(("f", "R", "S"), "modified", "t", "b")
        base = spec_check.delta_hash([entry])
        for field, value in (
            ("file", "g"),
            ("requirement", "R2"),
            ("scenario", None),
            ("change", "added"),
            ("text", "u"),
            ("base", "c"),
        ):
            with self.subTest(field=field):
                self.assertNotEqual(
                    spec_check.delta_hash([{**entry, field: value}]), base
                )

    def test_hash_is_independent_of_entry_order(self) -> None:
        entries = spec_check.diff_entries("f", None, SPEC)
        self.assertEqual(
            spec_check.delta_hash(entries), spec_check.delta_hash(entries[::-1])
        )

    def test_normalization_rules(self) -> None:
        plain = spec_check.diff_entries("f", None, SPEC)
        for label, text in (
            ("CRLF line endings", SPEC.replace("\n", "\r\n")),
            ("trailing whitespace", SPEC.replace("is free.\n", "is free.   \n")),
            ("rewrapped paragraph", SPEC.replace("while a\nslot", "while\na slot")),
        ):
            with self.subTest(rule=label):
                self.assertEqual(spec_check.diff_entries("f", None, text), plain)
        joined = spec_check.normalize(["a", "b  ", "", "- c", "- d", " \t", "e"])
        self.assertEqual(joined, "a b\n\n- c\n- d\n\ne")

    def test_modified_entry_without_base_is_refused(self) -> None:
        text = DELTA_MODIFIED.replace("Base:\n", "")
        with self.assertRaises(spec_check.SpecError):
            spec_check.parse_delta(text)


EMPTY = spec_check.delta_hash([])


class ConformanceTests(unittest.TestCase):
    """The PR's three-dot docs/specs/ diff must hash to the stated approved hash."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Repo(Path(tmp.name))
        self.repo.write("docs/specs/queue.md", SPEC)
        self.repo.commit("base")
        run_git(self.repo.root, "branch", "target")
        self.body = Path(tmp.name) / "body.md"
        self.approved = spec_check.delta_hash(spec_check.parse_delta(DELTA_MODIFIED))

    def run_check(self, stated: str, *extra: str) -> tuple[int, str]:
        self.body.write_text(f"## Spec\n\nSpec hash: {stated}\n\n## Risk\n")
        code, _, err = self.repo.main(
            "--conformance", "target", "--body-file", str(self.body), *extra
        )
        return code, err

    def test_matching_diff_passes(self) -> None:
        self.repo.write("docs/specs/queue.md", MODIFIED)
        self.repo.commit("head")
        self.assertEqual(self.run_check(self.approved), (0, ""))

    def test_drift_from_the_approved_delta_is_refused(self) -> None:
        self.repo.write("docs/specs/queue.md", MODIFIED.replace("in order", "last"))
        self.repo.commit("head")
        code, err = self.run_check(self.approved)
        self.assertEqual(code, 1)
        self.assertIn("spec drift: the docs/specs/ diff hashes", err)
        self.assertIn(f"approved {self.approved}", err)

    def test_no_spec_change_needs_an_approved_empty_delta(self) -> None:
        self.repo.write("tools/queue.py", "x = 1\n")
        self.repo.commit("head")
        self.assertEqual(self.run_check(EMPTY)[0], 0)
        code, err = self.run_check(self.approved)
        self.assertEqual(code, 1)
        self.assertIn(f"needs an approved empty delta ({EMPTY})", err)
        empty_doc = "## Spec delta\nHash: x\nRisk: R1\n\n## Open questions\n"
        self.assertEqual(
            spec_check.delta_hash(spec_check.parse_delta(empty_doc)), EMPTY
        )

    def test_diff_is_three_dot_from_the_merge_base(self) -> None:
        run_git(self.repo.root, "checkout", "-q", "-b", "feature")
        self.repo.write("docs/specs/queue.md", MODIFIED)
        self.repo.commit("feature")
        run_git(self.repo.root, "checkout", "-q", "target")
        self.repo.write("docs/specs/o.md", SPEC.replace("tools/queue.py", "o.py"))
        self.repo.commit("target moves on")
        self.assertEqual(self.run_check(self.approved, "--head", "feature")[0], 0)

    def test_two_stated_hashes_are_refused(self) -> None:
        self.body.write_text(f"## Spec\nSpec hash: {EMPTY}\nSpec hash: {'a' * 64}\n")
        code, _, err = self.repo.main(
            "--conformance", "target", "--body-file", str(self.body)
        )
        self.assertEqual(code, 1)
        self.assertIn("more than one hash", err)

    def test_hash_outside_the_spec_section_or_commented_is_not_read(self) -> None:
        for text in (
            f"## Summary\nSpec hash: {self.approved}\n## Spec\nnone\n",
            f"## Spec\n<!-- Spec hash: {self.approved} -->\n",
        ):
            with self.subTest(text=text):
                self.assertEqual(spec_check.stated_hashes(text), [])
        self.body.write_text("## Spec\nnone\n")
        code, _, err = self.repo.main(
            "--conformance", "target", "--body-file", str(self.body)
        )
        self.assertEqual(code, 0)
        self.assertIn("states no spec hash", err)

    def test_event_payload(self) -> None:
        event = self.body.with_name("event.json")
        for payload, expected in (
            ({"pull_request": {"body": f"## Spec\nSpec hash: {EMPTY}\n"}}, 0),
            ({"pull_request": {"body": f"## Spec\nSpec hash: {'a' * 64}\n"}}, 1),
            ({"pull_request": {"body": None}}, 0),
            ({}, 2),
            ([], 2),
            ({"pull_request": {"body": 3}}, 2),
        ):
            with self.subTest(payload=payload):
                event.write_text(json.dumps(payload))
                code, _, _ = self.repo.main(
                    "--conformance", "target", "--event-file", str(event)
                )
                self.assertEqual(code, expected)
        event.write_text("{not json")
        args = ("--conformance", "target", "--event-file", str(event))
        self.assertEqual(self.repo.main(*args)[0], 2)

    def test_unknown_base_is_a_usage_error(self) -> None:
        self.body.write_text(f"## Spec\nSpec hash: {EMPTY}\n")
        code, _, err = self.repo.main(
            "--conformance", "nope", "--body-file", str(self.body)
        )
        self.assertEqual(code, 2)
        self.assertIn("merge-base", err)

    def test_conformance_needs_one_body_source(self) -> None:
        for args in (
            ("--conformance", "target"),
            ("--body-file", str(self.body)),
        ):
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    self.repo.main(*args)
                self.assertEqual(raised.exception.code, 2)


DELTA_ADDED = """\
## Capability: docs/specs/queue.md

### Added Requirement: Admission
The queue SHALL admit an issue while a slot is free.

#### Added Scenario: Free slot
- WHEN a slot is free
- THEN the issue is admitted

#### Added Scenario: Full queue
- WHEN no slot is free
- THEN the issue waits
"""


if __name__ == "__main__":
    unittest.main()
