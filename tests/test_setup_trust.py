"""Setup and preparation record the trust baseline only when eligible (#55).

A local bare repository stands in for the pinned repository through the
`setup_trust.repository_url` seam; no test reaches github.com.
"""

from __future__ import annotations

import ast
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

if TYPE_CHECKING:
    from collections.abc import Callable
    from contextlib import AbstractContextManager

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "tools/spec_workflow"))
import branch_sync  # noqa: E402
import launcher  # noqa: E402
import setup_trust  # noqa: E402
import test_setup as ts  # noqa: E402
from test_autonomy import outside_temp  # noqa: E402

sys.path.pop(0)
sys.path.pop(0)

REPO = "example/project"
CONFIG = ts.PIN.format("vA") + f'\n[github]\nrepository = "{REPO}"\n'
CONSTITUTION = "project constitution\n"
WIDENED = '\n[agents.permissions]\nextra_allow = ["Bash(*)"]\n'
DIFFERS = f"differs from {REPO}'s default branch and from your last trusted baseline"
POINTER = "the .git pointer does not name a worktree of this repository"


def _commit(root: Path, message: str = "change") -> None:
    ts.git(root, "add", "-A")
    ts.git(root, "commit", "-q", "--allow-empty", "-m", message)


class TrustMixin:
    """A project whose configuration equals a stand-in default branch."""

    COMMIT = True

    def new_project(self, name: str, *, constitution: bool = True) -> Path:
        del constitution
        root = self.base / name
        root.mkdir()
        ts.git(root, "init", "-q")
        (root / ".gitignore").write_text(ts.setup.GITIGNORE)
        (root / "ballast.toml").write_text(CONFIG)
        (root / ".specify/memory").mkdir(parents=True)
        (root / ".specify/memory/constitution.md").write_text(CONSTITUTION)
        if self.COMMIT:
            _commit(root, "project")
        if name == "project":
            self.argv: list = []
            self.remotes = {REPO: self.stand_in(REPO)}
            for seam, value in (
                (setup_trust, {"repository_url": self.url, "ARGV_LOG": self.argv}),
            ):
                for attribute, replacement in value.items():
                    patcher = patch.object(seam, attribute, replacement)
                    patcher.start()
                    self.addCleanup(patcher.stop)
            launcher.add_reviewed(root, REPO)
        return root

    def stand_in(
        self,
        repository: str,
        files: dict[str, str] | None = None,
        branch: str = "main",
    ) -> Path:
        """Build a bare repository whose default branch carries the given files."""
        slug = repository.replace("/", "-") + f"-{len(list(self.base.iterdir()))}"
        bare = self.base / f"{slug}.git"
        work = self.base / f"{slug}-work"
        ts.git(self.base, "init", "-q", "--bare", "-b", branch, str(bare))
        work.mkdir()
        ts.git(work, "init", "-q")
        files = files or {
            "ballast.toml": CONFIG,
            ".specify/memory/constitution.md": CONSTITUTION,
        }
        for name, text in files.items():
            (work / name).parent.mkdir(parents=True, exist_ok=True)
            (work / name).write_text(text)
        _commit(work, "default")
        ts.git(work, "push", "-q", f"file://{bare}", f"HEAD:refs/heads/{branch}")
        return bare

    def url(self, root: Path, owner: str, name: str, *, origin: str = "") -> str:
        del root, origin
        return f"file://{self.remotes[f'{owner}/{name}']}"

    # --- helpers -------------------------------------------------------------

    def verdict(
        self, root: Path | None = None, mode: str = "setup"
    ) -> setup_trust.Verdict:
        root = root or self.root
        state = self.state(root)
        record = ts.setup.launcher.read_record(root, state)
        return setup_trust.settle(root, state, record, standard=ts.ROOT, mode=mode)

    def baseline(self, root: Path | None = None) -> bytes | None:
        path = self.state(root) / launcher.TRUSTED
        return path.read_bytes() if path.exists() else None

    def provenance(self, root: Path | None = None) -> dict:
        return json.loads((self.state(root) / launcher.TRUSTED_SOURCE).read_text())

    def fresh(self, root: Path | None = None) -> None:
        for name in (launcher.TRUSTED, launcher.TRUSTED_SOURCE):
            (self.state(root) / name).unlink(missing_ok=True)

    def network_commands(self) -> list[list[str]]:
        return [argv for where, argv in self.argv if where == "throwaway"]

    def assert_skipped(
        self, verdict: setup_trust.Verdict, reason: str, *, network: bool = False
    ) -> None:
        self.assertEqual(verdict.kind, "skipped", verdict)
        self.assertIn(reason, verdict.text)
        self.assertIsNone(self.baseline())
        self.assertFalse((self.state() / launcher.TRUSTED_SOURCE).exists())
        if not network:
            self.assertEqual(self.network_commands(), [])
        self.assertIn("ballast trust", "\n".join(verdict.lines()))
        self.assertEqual(self.state() / "setup-trust", self.state() / "setup-trust")
        leftover = self.state() / "setup-trust"
        self.assertEqual(list(leftover.iterdir()) if leftover.exists() else [], [])


class TrustCase(TrustMixin, ts.ProjectCase):
    """An installed, committed, eligible project; the baseline is cleared."""

    def setUp(self) -> None:
        patcher = patch.object(tempfile, "tempdir", str(outside_temp()))
        patcher.start()
        self.addCleanup(patcher.stop)
        super().setUp()
        self.installed()
        self.fresh()
        self.argv.clear()


class TrustWorktreeCase(TrustMixin, ts.WorktreeCase):
    """The same, with linked worktrees; WorktreeCase commits the project."""

    COMMIT = False

    def setUp(self) -> None:
        patcher = patch.object(tempfile, "tempdir", str(outside_temp()))
        patcher.start()
        self.addCleanup(patcher.stop)
        super().setUp()
        self.argv.clear()

    def branch_worktree(
        self, files: dict[str, str], source: Path | None = None, name: str = "feat"
    ) -> Path:
        """Add a worktree on a new branch with the given files committed."""
        self.count += 1
        path = self.base / f"branch-{self.count}"
        ts.git(
            source or self.root,
            "worktree",
            "add",
            "-q",
            "-b",
            f"{name}-{self.count}",
            str(path),
        )
        for file, text in files.items():
            (path / file).write_text(text)
        _commit(path, "branch change")
        return path


# --- US1: setup records ------------------------------------------------------


class SetupRecordsTests(TrustCase):
    """AC-001, AC-002, AC-003, AC-005."""

    def test_clean_checkout_is_recorded_and_accepted(self) -> None:
        # AC-001, AC-002: a fresh clone equal to the default branch.
        code, out, err = self.setup()
        self.assertEqual(code, 0, err)
        commit = ts.git(self.remotes[REPO], "rev-parse", "main").strip()
        count = len(json.loads(self.baseline()))
        self.assertIn(
            f"Recorded the trust baseline for {count} protected inputs: ballast.toml "
            f"and the constitution match {REPO}'s default branch main at "
            f"{commit[:12]}.\n"
            "The next ballast run, ledger or intake needs no ballast trust.\n",
            out,
        )
        self.assertNotIn("run `ballast trust`", out)
        provenance = self.provenance()
        self.assertEqual(provenance["source"], "setup")
        self.assertEqual(
            provenance["reference"],
            {
                "kind": "default-branch",
                "repository": REPO,
                "branch": "main",
                "commit": commit,
            },
        )
        status = json.loads(self.launcher("status", "--json").stdout)
        self.assertEqual(
            status, {"installed": True, "refusal": None, "baseline_source": "setup"}
        )
        for command in ("run", "ledger", "intake"):
            result = self.launcher(command)
            self.assertNotIn("refusing", result.stderr, command)

    def test_second_setup_leaves_a_matching_baseline_alone(self) -> None:
        self.setup()
        before = (
            self.baseline(),
            (self.state() / launcher.TRUSTED_SOURCE).read_bytes(),
        )
        mtimes = [
            (self.state() / n).stat().st_mtime_ns
            for n in (launcher.TRUSTED, launcher.TRUSTED_SOURCE)
        ]
        self.argv.clear()
        _, out, _ = self.setup()
        self.assertIn(
            "The trust baseline setup recorded still matches; left unchanged.", out
        )
        self.assertEqual(
            before,
            (self.baseline(), (self.state() / launcher.TRUSTED_SOURCE).read_bytes()),
        )
        self.assertEqual(
            mtimes,
            [
                (self.state() / n).stat().st_mtime_ns
                for n in (launcher.TRUSTED, launcher.TRUSTED_SOURCE)
            ],
        )
        self.assertEqual(self.network_commands(), [])

    def test_no_op_setup_without_a_baseline_records_one(self) -> None:
        # AC-005: installed, current, no baseline.
        _, out, _ = self.setup()
        self.assertIn("Recorded the trust baseline", out)
        self.fresh()
        _, out, _ = self.setup()
        self.assertIn("nothing changed: vA is set up and verified", out)
        self.assertIn("Recorded the trust baseline", out)
        self.assertEqual(self.provenance()["source"], "setup")

    def test_an_operator_baseline_is_left_untouched(self) -> None:
        # AC-005, FR-011
        self.trust()
        before = {
            n: ((self.state() / n).read_bytes(), (self.state() / n).stat().st_mtime_ns)
            for n in (launcher.TRUSTED, launcher.TRUSTED_SOURCE)
        }
        _, out, _ = self.setup()
        self.assertIn(
            "The trust baseline you recorded with ballast trust still matches; "
            "left unchanged.",
            out,
        )
        after = {
            n: ((self.state() / n).read_bytes(), (self.state() / n).stat().st_mtime_ns)
            for n in (launcher.TRUSTED, launcher.TRUSTED_SOURCE)
        }
        self.assertEqual(before, after)
        self.assertEqual(self.provenance()["source"], "trust")

    def test_init_installs_without_recording(self) -> None:
        # `ballast init` never records trust, even for an eligible checkout.
        installation = ts.setup.Setup(self.root)
        installation.records_trust = False
        out = io.StringIO()
        with ts.fakes(), redirect_stdout(out):
            installation.main()
            installation.main()
        self.assertIsNone(self.baseline())
        self.assertFalse((self.state() / launcher.TRUSTED_SOURCE).exists())
        self.assertEqual(self.network_commands(), [])
        self.assertIn("nothing changed: vA is set up and verified\n", out.getvalue())
        self.assertNotIn("trust baseline", out.getvalue())

    def test_no_trust_line_when_recorded(self) -> None:
        # FR-016
        _, out, _ = self.setup()
        self.assertNotIn("Review the changed protected inputs", out)


class OperatorBaselineTests(TrustCase):
    """AC-004: the checkout's earlier baseline recorded by `ballast trust`."""

    def setUp(self) -> None:
        super().setUp()
        # A committed configuration the default branch does not carry.
        (self.root / "ballast.toml").write_text(CONFIG + WIDENED)
        _commit(self.root, "widen")
        self.inputs = launcher.trusted_inputs(self.root)

    def earlier(self, *, source: str | None, tamper: bool = False) -> None:
        """Write an earlier baseline with other installed digests."""
        recorded = {**self.inputs, ".specify/scripts/python/common.py": "0" * 64}
        state = self.state()
        if source is None:
            (state / launcher.TRUSTED).write_text(json.dumps(recorded, indent=1))
            (state / launcher.TRUSTED_SOURCE).unlink(missing_ok=True)
        else:
            launcher.record_baseline(state, recorded, source=source, reference={})
        if tamper:
            (state / launcher.TRUSTED).write_text(json.dumps(recorded, indent=2))

    def test_equal_to_a_legacy_baseline(self) -> None:
        self.earlier(source=None)
        verdict = self.verdict()
        self.assertEqual(verdict.kind, "recorded", verdict)
        self.assertIn("the baseline you recorded with ballast trust", verdict.text)
        self.assertEqual(self.provenance()["reference"], {"kind": "operator-baseline"})
        self.assertEqual(self.network_commands(), [])

    def test_equal_to_a_bound_trust_baseline(self) -> None:
        self.earlier(source="trust")
        verdict = self.verdict()
        self.assertEqual(verdict.kind, "recorded", verdict)
        self.assertEqual(self.provenance()["source"], "setup")
        self.assertEqual(self.network_commands(), [])

    def test_a_setup_baseline_does_not_count(self) -> None:
        self.earlier(source="setup")
        before = self.baseline()
        verdict = self.verdict()
        self.assertEqual(verdict.kind, "skipped", verdict)
        self.assertIn(DIFFERS, verdict.text)
        self.assertEqual(self.baseline(), before)

    def test_unbound_provenance_does_not_count(self) -> None:
        self.earlier(source="trust", tamper=True)
        before = self.baseline()
        verdict = self.verdict()
        self.assertEqual(verdict.kind, "skipped", verdict)
        self.assertEqual(self.baseline(), before)

    def test_other_configuration_in_the_baseline_does_not_count(self) -> None:
        recorded = {**self.inputs, "ballast.toml": "1" * 64}
        launcher.record_baseline(self.state(), recorded, source="trust")
        self.assertEqual(self.verdict().kind, "skipped")


# --- US3: ineligible checkouts ----------------------------------------------


class LocalIneligibleTests(TrustCase):
    """AC-010, AC-011, AC-012: nothing is recorded, with no network access."""

    def test_uncommitted_pin_bump(self) -> None:
        # AC-010
        with (self.root / "ballast.toml").open("a") as handle:
            handle.write("# pin bump\n")
        self.assert_skipped(self.verdict(), "ballast.toml has uncommitted changes")

    def test_uncommitted_constitution(self) -> None:
        path = self.root / ".specify/memory/constitution.md"
        path.write_text("edited\n")
        self.assert_skipped(
            self.verdict(), ".specify/memory/constitution.md has uncommitted changes"
        )

    def test_deleted_constitution_is_a_change(self) -> None:
        (self.root / ".specify/memory/constitution.md").unlink()
        self.assert_skipped(self.verdict(), "has uncommitted changes")

    def test_committed_widened_permissions(self) -> None:
        # AC-011: no operator baseline, differs from the default branch.
        (self.root / "ballast.toml").write_text(CONFIG + WIDENED)
        _commit(self.root, "widen")
        self.assert_skipped(self.verdict(), DIFFERS, network=True)

    def test_extra_file_under_specify(self) -> None:
        # AC-012
        (self.root / ".specify/extra.sh").write_text("echo hi\n")
        self.assert_skipped(
            self.verdict(), ".specify/extra.sh was not written by setup"
        )

    def test_edited_installed_file(self) -> None:
        (self.root / ".ballast/spec_workflow/run.py").write_text("print(1)\n")
        self.assert_skipped(
            self.verdict(), ".ballast/spec_workflow/run.py was not written by setup"
        )

    def test_a_venv_is_not_written_by_setup(self) -> None:
        (self.root / ".venv/bin").mkdir(parents=True)
        (self.root / ".venv/bin/python").write_text("x\n")
        self.assert_skipped(self.verdict(), ".venv/bin/python was not written by setup")

    def test_a_removed_record_file(self) -> None:
        (self.root / ".specify/scripts/python/common.py").unlink()
        self.assert_skipped(
            self.verdict(),
            ".specify/scripts/python/common.py was not written by setup",
        )

    def test_a_linked_installed_file(self) -> None:
        path = self.root / ".specify/scripts/python/common.py"
        path.unlink()
        path.symlink_to("/etc/passwd")
        self.assert_skipped(self.verdict(), "was not written by setup")

    def test_a_standard_inside_the_checkout(self) -> None:
        state, root = self.state(), self.root
        record = ts.setup.launcher.read_record(root, state)
        verdict = setup_trust.settle(
            root, state, record, standard=root / "tools", mode="setup"
        )
        self.assert_skipped(verdict, "setup runs from this checkout")

    def test_a_linked_protected_directory_is_not_recorded(self) -> None:
        # SEC-001: `.specify` linked to an identical copy outside the checkout.
        reasons = {
            ".specify": ".specify is a link",
            ".ballast": ".ballast is a link",
            # The constitution then has no entry in the launcher's snapshot.
            ".specify/memory": "protected inputs changed while setup checked",
        }
        for name, reason in reasons.items():
            with self.subTest(name=name):
                path = self.root / name
                outside = self.base / "outside-copy"
                shutil.copytree(path, outside, symlinks=True)
                shutil.rmtree(path)
                path.symlink_to(outside)
                self.assert_skipped(self.verdict(), reason)
                path.unlink()
                shutil.move(outside, path)
        self.assertEqual(self.verdict().kind, "recorded")

    def test_setup_says_so_for_a_linked_directory(self) -> None:
        outside = self.base / "outside-copy"
        shutil.copytree(self.root / ".specify", outside, symlinks=True)
        shutil.rmtree(self.root / ".specify")
        (self.root / ".specify").symlink_to(outside)
        _, out, _ = self.setup()
        self.assertIn("No trust baseline recorded: .specify is a link", out)
        self.assertIsNone(self.baseline())

    def test_a_standard_in_a_temp_directory(self) -> None:
        # SEC-005: agents can write /tmp and $TMPDIR too.
        with patch.object(setup_trust.ledger, "agent_temp_roots", lambda: (ts.ROOT,)):
            self.assert_skipped(self.verdict(), "or a temp directory")

    def test_an_unexpected_failure_never_escapes(self) -> None:
        # ENG-002
        with patch.object(setup_trust, "_evaluate", side_effect=RuntimeError("boom")):
            verdict = self.verdict()
        self.assertEqual(verdict.kind, "skipped")
        self.assertIn("could not record it (boom)", verdict.text)
        self.assertIsNone(self.baseline())

    def test_a_crash_in_the_decision_never_fails_the_installation(self) -> None:
        root = self.new_project("crash")
        with patch.object(setup_trust, "settle", side_effect=ValueError("bad")):
            code, out, err = self.setup(root)
        self.assertEqual(code, 0, err)
        self.assertIn(ts.SUCCESS, out)
        self.assertIn("No trust baseline recorded: could not decide it (bad).", out)
        self.assertIn("run `ballast trust`", out)
        self.assertIsNone(self.baseline(root))

    def test_stale_scratch_directories_are_removed(self) -> None:
        # ENG-005: a killed setup left one behind.
        stale = self.state() / "setup-trust/dead"
        stale.mkdir(parents=True)
        (stale / "reviewed.git").write_text("x")
        self.assertEqual(self.verdict().kind, "recorded")
        self.assertEqual(list((self.state() / "setup-trust").iterdir()), [])

    def test_a_missing_installation_record(self) -> None:
        verdict = setup_trust.settle(
            self.root, self.state(), None, standard=ts.ROOT, mode="setup"
        )
        self.assert_skipped(verdict, "installation record")

    def test_a_link_for_the_configuration(self) -> None:
        path = self.root / "ballast.toml"
        path.rename(self.root / "real.toml")
        path.symlink_to("real.toml")
        self.assert_skipped(self.verdict(), "ballast.toml is not a regular file")

    def test_an_oversized_configuration(self) -> None:
        with (self.root / "ballast.toml").open("a") as handle:
            handle.write("# " + "x" * (256 * 1024) + "\n")
        self.assert_skipped(self.verdict(), "ballast.toml is not a regular file")

    def test_no_commit(self) -> None:
        shutil_target = self.root / ".git/refs/heads"
        for ref in shutil_target.iterdir():
            ref.unlink()
        self.assert_skipped(self.verdict(), "no commit")


class PreparationBaselineTests(TrustCase):
    """TEST-002: only setup counts the checkout's own earlier baseline."""

    def test_a_preparation_never_reads_the_baseline(self) -> None:
        (self.root / "ballast.toml").write_text(CONFIG + WIDENED)
        _commit(self.root, "widen")
        launcher.record_baseline(
            self.state(),
            {**launcher.trusted_inputs(self.root), "x": "0" * 64},
            source="trust",
        )
        prepared = self.verdict(mode="prepare")
        self.assertEqual(prepared.kind, "skipped", prepared)
        self.assertIn(DIFFERS, prepared.text)
        self.assertEqual(self.verdict(mode="setup").kind, "recorded")


class ConfigurationReadTests(TrustCase):
    """TEST-006, TEST-009: the bytes judged are the bytes snapshotted, from a file."""

    def test_bytes_that_differ_from_the_snapshot(self) -> None:
        real = setup_trust._read_regular  # noqa: SLF001

        def swapped(path: Path, limit: int) -> bytes | None:
            data = real(path, limit)
            return data + b"# swapped\n" if path.name == "ballast.toml" else data

        with patch.object(setup_trust, "_read_regular", swapped):
            verdict = self.verdict()
        self.assert_skipped(verdict, "protected inputs changed while setup checked")

    def test_a_directory_or_a_pipe_is_not_a_configuration_file(self) -> None:
        path = self.root / "ballast.toml"
        path.rename(self.root / "moved.toml")
        for make in (path.mkdir, lambda: os.mkfifo(path)):
            with self.subTest(make=make):
                make()
                self.assert_skipped(
                    self.verdict(), "ballast.toml is not a regular file"
                )
                if path.is_dir():
                    path.rmdir()
                else:
                    path.unlink()


class AgentTraceEligibilityTests(TrustCase):
    """AC-018 to AC-020."""

    def test_tamper_marker(self) -> None:
        # AC-019
        (self.root / launcher.TAMPER_MARKER).write_text("")
        self.assert_skipped(self.verdict(), "BALLAST_TAMPERED")
        self.assertIn("restore the checkout", self.verdict().text)

    def test_tamper_marker_with_a_matching_baseline(self) -> None:
        # F-003: the remedy is named even when the baseline matches.
        self.trust()
        before = self.baseline()
        (self.root / launcher.TAMPER_MARKER).write_text("")
        verdict = self.verdict()
        self.assertEqual(verdict.kind, "skipped")
        self.assertIn("BALLAST_TAMPERED", verdict.text)
        self.assertEqual(self.baseline(), before)

    def test_in_progress_marker(self) -> None:
        # AC-018
        (self.state() / launcher.IN_PROGRESS).write_text("")
        self.assert_skipped(self.verdict(), "an agent step's marker exists")
        self.assertIn("ballast discard-runs", self.verdict().text)

    def test_saved_run_state_in_the_checkout(self) -> None:
        # AC-020
        for name in launcher.RUN_STATE:
            with self.subTest(name=name):
                path = self.root / name / "r1/state.json"
                path.parent.mkdir(parents=True)
                path.write_text("{}\n")
                self.assert_skipped(
                    self.verdict(), "saved run state shows agents ran here"
                )
                path.unlink()
                path.parent.rmdir()

    def test_a_linked_run_state_directory(self) -> None:
        path = self.root / ".specify/workflow-state"
        path.symlink_to("/")
        self.assert_skipped(self.verdict(), "saved run state shows agents ran here")

    def test_an_empty_run_state_directory_is_not_run_state(self) -> None:
        (self.root / ".specify/workflows/runs").mkdir(parents=True)
        (self.root / ".specify/workflow-state").mkdir(parents=True)
        self.assertEqual(self.verdict().kind, "recorded")

    def write_run(self, name: str, text: str | None) -> None:
        path = self.state() / "runs" / name
        path.mkdir(parents=True)
        if text is not None:
            (path / "run.json").write_text(text)

    def test_unfinished_operator_runs(self) -> None:
        # AC-020
        cases = {
            "active": json.dumps({"status": "active"}),
            "stopped": json.dumps({"status": "stopped"}),
            "unknown": json.dumps({"status": "mystery"}),
            "garbage": "not json",
            "list": "[]",
            "unreadable-run": None,
        }
        for name, text in cases.items():
            with self.subTest(name=name):
                self.write_run(name, text)
                (self.state() / "runs" / name / "other").write_text("x")
                self.assert_skipped(
                    self.verdict(), "saved run state shows agents ran here"
                )
                for child in (self.state() / "runs" / name).iterdir():
                    child.unlink()
                (self.state() / "runs" / name).rmdir()

    def test_finished_and_empty_operator_runs_are_eligible(self) -> None:
        self.write_run("empty", None)
        for index, status in enumerate(("completed", "published", "continued")):
            self.write_run(f"done-{index}", json.dumps({"status": status}))
        self.assertEqual(self.verdict().kind, "recorded")

    def test_a_marker_makes_setup_refuse(self) -> None:
        # AC-018, AC-021: an agent step holds the marker.
        (self.state() / launcher.IN_PROGRESS).write_text("")
        (self.root / "ballast.toml").write_text(CONFIG + "# reinstall\n")
        _commit(self.root, "pin")
        code, out, err = self.setup()
        self.assertEqual(code, 2, err)
        self.assertIn("an agent step did not finish", err)
        self.assertIn("ballast discard-runs", err)
        self.assertNotIn("Recorded", out)
        self.assertIsNone(self.baseline())


class RecoveredSetupTests(TrustCase):
    """TEST-001: an interrupted setup records nothing until it is recovered."""

    def test_a_killed_setup_records_only_after_recovery(self) -> None:
        for point in ("switching", "committed"):
            with self.subTest(point=point):
                root = self.new_project(f"killed-{point}")
                self.kill(point, 0, root)
                self.assertIsNone(self.baseline(root))
                code, out, err = self.setup(root)
                self.assertEqual(code, 0, err)
                self.assertIn("recovered an interrupted setup: ", out)
                self.assertIn("Recorded the trust baseline", out)
                self.assertEqual(
                    json.loads(self.baseline(root)), launcher.trusted_inputs(root)
                )
                self.assertEqual(self.provenance(root)["source"], "setup")

    def test_an_interrupted_attempt_never_leaves_a_baseline(self) -> None:
        root = self.new_project("killed-early")
        self.kill("validate", 0, root)
        self.assertIsNone(self.baseline(root))
        self.assertFalse((self.state(root) / launcher.TRUSTED_SOURCE).exists())


class WorktreePointerTests(TrustWorktreeCase):
    """AC-013."""

    def setUp(self) -> None:
        super().setUp()
        self.wt = self.worktree()
        _, _, err = self.prepare(self.wt)[0:3]
        self.assertEqual(self.verdict(self.wt, "prepare").kind, "recorded", err)
        self.fresh(self.wt)

    def point(self, text: str) -> None:
        (self.wt / ".git").write_text(text)

    def test_a_pointer_to_a_repository_inside_the_checkout(self) -> None:
        evil = self.wt / "evil"
        ts.git(self.wt, "init", "-q", str(evil))
        admin = evil / ".git/worktrees/w"
        admin.mkdir(parents=True)
        (admin / "commondir").write_text("../..\n")
        (admin / "gitdir").write_text(f"{self.wt}/.git\n")
        self.point(f"gitdir: {admin}\n")
        self.skipped_pointer()

    def test_a_repository_an_agent_can_write(self) -> None:
        # A well-formed pointer whose repository lies in an agent temp directory.
        with patch.object(setup_trust.ledger, "agent_temp_roots", lambda: (self.base,)):
            self.skipped_pointer()

    def skipped_pointer(self) -> None:
        verdict = self.verdict(self.wt, "prepare")
        self.assertEqual(verdict.kind, "skipped", verdict)
        self.assertIn(POINTER, verdict.text)
        self.assertIsNone(self.baseline(self.wt))

    def test_a_missing_back_link(self) -> None:
        admin = Path((self.wt / ".git").read_text().split(": ", 1)[1].strip())
        (admin / "gitdir").unlink()
        self.skipped_pointer()

    def test_a_wrong_back_link(self) -> None:
        admin = Path((self.wt / ".git").read_text().split(": ", 1)[1].strip())
        (admin / "gitdir").write_text(f"{self.base}/elsewhere/.git\n")
        self.skipped_pointer()

    def test_a_pointer_swapped_after_the_snapshot(self) -> None:
        # SEC-002: the bytes judged are the bytes snapshotted.
        real = launcher.trusted_inputs
        stale = {".git": "0" * 64}
        with patch.object(
            setup_trust.launcher, "trusted_inputs", lambda r: {**real(r), **stale}
        ):
            verdict = self.verdict(self.wt, "prepare")
        self.assertEqual(verdict.kind, "skipped")
        self.assertIn("protected inputs changed while setup", verdict.text)

    def test_an_admin_directory_that_is_not_a_worktree_entry(self) -> None:
        # TEST-005: a consistent commondir and back-link, but no worktrees/<name>.
        fake = self.base / "elsewhere/admin"
        fake.mkdir(parents=True)
        (fake / "commondir").write_text(f"{self.root / '.git'}\n")
        (fake / "gitdir").write_text(f"{self.wt}/.git\n")
        self.point(f"gitdir: {fake}\n")
        self.skipped_pointer()

    def test_a_symbolic_link(self) -> None:
        target = self.base / "pointer"
        (self.wt / ".git").rename(target)
        (self.wt / ".git").symlink_to(target)
        self.skipped_pointer()

    def test_malformed_pointers(self) -> None:
        for text in ("garbage\n", "gitdir: relative/path\n", "gitdir: /nowhere\n", ""):
            with self.subTest(text=text):
                original = (self.wt / ".git").read_text()
                self.point(text)
                self.skipped_pointer()
                self.point(original)

    def test_a_genuine_worktree_is_eligible(self) -> None:
        self.assertEqual(self.verdict(self.wt, "prepare").kind, "recorded")

    def test_a_primary_checkouts_git_directory_is_not_checked(self) -> None:
        self.assertTrue((self.root / ".git").is_dir())
        self.assertIsNone(setup_trust._check_pointer(self.root))  # noqa: SLF001


# --- observation -------------------------------------------------------------


class ObservationTests(TrustCase):
    """AC-014, AC-015, F-006."""

    def intercept(
        self, word: str, result: setup_trust.Result
    ) -> AbstractContextManager:
        real = setup_trust._run  # noqa: SLF001

        def run(argv: list[str], **kwargs: Any) -> setup_trust.Result:  # noqa: ANN401
            return result if word in argv else real(argv, **kwargs)

        return patch.object(setup_trust, "_run", run)

    def test_unreachable_repository(self) -> None:
        self.remotes[REPO] = self.base / "missing.git"
        verdict = self.verdict()
        self.assert_skipped(
            verdict,
            f"could not read {REPO}'s default branch: offline or unreachable",
            network=True,
        )

    def test_refused_credentials(self) -> None:
        denied = setup_trust.Result(128, b"", "fatal: Authentication failed for x")
        with self.intercept("ls-remote", denied):
            verdict = self.verdict()
        self.assert_skipped(
            verdict, "no access with your Git credentials", network=True
        )

    def test_a_hung_request(self) -> None:
        with self.intercept("ls-remote", setup_trust.Result(-1, timed_out=True)):
            verdict = self.verdict()
        self.assert_skipped(verdict, "timed out", network=True)

    def test_a_hung_fetch(self) -> None:
        with self.intercept("fetch", setup_trust.Result(-1, timed_out=True)):
            verdict = self.verdict()
        self.assert_skipped(verdict, "timed out", network=True)

    def test_run_bounds_a_command_and_never_prompts(self) -> None:
        result = setup_trust._run(  # noqa: SLF001
            [sys.executable, "-c", "import time; time.sleep(30)"],
            cwd=self.base,
            env=dict(os.environ),
            timeout=0.2,
            where="checkout",
        )
        self.assertTrue(result.timed_out)
        echo = setup_trust._run(  # noqa: SLF001
            [sys.executable, "-c", "import sys; print(sys.stdin.read() == '')"],
            cwd=self.base,
            env=dict(os.environ),
            timeout=10,
            where="checkout",
        )
        self.assertEqual(echo.stdout.strip(), b"True")

    def test_the_network_commands_are_bounded(self) -> None:
        seen: dict[str, float] = {}
        real = setup_trust._run  # noqa: SLF001

        def spy(argv: list[str], **kwargs: Any) -> setup_trust.Result:  # noqa: ANN401
            for word in ("ls-remote", "fetch"):
                if word in argv:
                    seen[word] = kwargs["timeout"]
            return real(argv, **kwargs)

        with patch.object(setup_trust, "_run", spy):
            self.assertEqual(self.verdict().kind, "recorded")
        self.assertEqual(
            seen,
            {
                "ls-remote": setup_trust.LS_REMOTE_TIMEOUT,
                "fetch": setup_trust.FETCH_TIMEOUT,
            },
        )
        self.assertLessEqual(seen["ls-remote"], 30)
        self.assertLessEqual(seen["fetch"], 120)

    def test_a_default_branch_name_the_tool_refuses(self) -> None:
        # Valid for Git, outside the branch pattern Ballast passes on.
        for name in ("feat@x", "caf\u00e9", "a+b"):
            with self.subTest(name=name):
                self.remotes[REPO] = self.stand_in(REPO, branch=name)
                self.assert_skipped(self.verdict(), "no default branch", network=True)

    def test_no_default_branch(self) -> None:
        ts.git(self.remotes[REPO], "symbolic-ref", "HEAD", "refs/heads/nope")
        self.assert_skipped(self.verdict(), "no default branch", network=True)

    def test_a_missing_or_malformed_repository_pin(self) -> None:
        for text in (
            ts.PIN.format("vA"),
            ts.PIN.format("vA") + '[github]\nrepository = "no good"\n',
        ):
            with self.subTest(text=text):
                (self.root / "ballast.toml").write_text(text)
                _commit(self.root, "pin")
                verdict = self.verdict()
                self.assert_skipped(
                    verdict, "ballast.toml names no valid [github] repository"
                )

    def test_unobservable_with_a_matching_operator_baseline_still_records(self) -> None:
        # AC-014: the checkout's own earlier baseline needs no network.
        (self.root / "ballast.toml").write_text(CONFIG + WIDENED)
        _commit(self.root, "widen")
        launcher.record_baseline(
            self.state(),
            {**launcher.trusted_inputs(self.root), "x": "0" * 64},
            source="trust",
        )
        self.remotes[REPO] = self.base / "missing.git"
        self.assertEqual(self.verdict().kind, "recorded")
        self.assertEqual(self.network_commands(), [])

    def test_local_refs_remotes_and_rewrites_are_ignored(self) -> None:
        # AC-015: an agent repoints everything local at the changed file.
        (self.root / "ballast.toml").write_text(CONFIG + WIDENED)
        _commit(self.root, "widen")
        evil = self.stand_in(
            REPO,
            {
                "ballast.toml": CONFIG + WIDENED,
                ".specify/memory/constitution.md": CONSTITUTION,
            },
        )
        ts.git(self.root, "remote", "add", "origin", f"file://{evil}")
        ts.git(self.root, "fetch", "-q", "origin")
        ts.git(
            self.root,
            "config",
            f"url.file://{evil}.insteadOf",
            f"file://{self.remotes[REPO]}",
        )
        ts.git(
            self.root,
            "update-ref",
            "refs/remotes/origin/HEAD",
            "refs/remotes/origin/main",
        )
        verdict = self.verdict()
        self.assert_skipped(verdict, DIFFERS, network=True)
        words = " ".join(" ".join(argv) for _, argv in self.argv)
        self.assertNotIn(str(evil), words)
        self.assertIn(f"file://{self.remotes[REPO]}", words)
        self.assertTrue(self.network_commands())

    def test_only_the_documented_commands_run(self) -> None:
        self.assertEqual(self.verdict().kind, "recorded")
        verbs = {
            "init",
            "ls-remote",
            "fetch",
            "rev-parse",
            "ls-tree",
            "remote",
            "version",
        }
        found: dict[str, set[str]] = {"checkout": set(), "throwaway": set()}
        for where, argv in self.argv:
            if "version" not in argv:
                self.assertIn("core.hooksPath=/dev/null", argv)
                self.assertIn("core.fsmonitor=false", argv)
            found[where].add(next(a for a in argv[1:] if a in verbs))
        # SEC-003: only the two network commands may use a transport.
        for _, argv in self.argv:
            verb = next(a for a in argv[1:] if a in verbs)
            local = verb not in {"ls-remote", "fetch", "version"}
            self.assertEqual("protocol.allow=never" in argv, local, argv)
        self.assertEqual(found["checkout"], {"version", "rev-parse", "remote"})
        self.assertEqual(
            found["throwaway"], {"init", "ls-remote", "fetch", "rev-parse", "ls-tree"}
        )

    def test_the_filtered_fetch_works_with_and_without_server_support(self) -> None:
        for allowed in ("true", "false"):
            with self.subTest(allow_filter=allowed):
                bare = self.remotes[REPO]
                ts.git(bare, "config", "uploadpack.allowFilter", allowed)
                self.fresh()
                self.assertEqual(self.verdict().kind, "recorded")

    def test_a_symbolic_link_is_not_the_file(self) -> None:
        # F-006: a symlink whose target text equals the file's bytes.
        work = self.base / "linkwork"
        work.mkdir()
        ts.git(work, "init", "-q")
        (work / "blob").write_text(CONFIG)
        blob = ts.git(work, "hash-object", "-w", "blob").strip()
        ts.git(
            work, "update-index", "--add", "--cacheinfo", f"120000,{blob},ballast.toml"
        )
        (work / ".specify/memory").mkdir(parents=True)
        (work / ".specify/memory/constitution.md").write_text(CONSTITUTION)
        ts.git(work, "add", ".specify")
        ts.git(work, "commit", "-q", "-m", "link")
        bare = self.base / "link.git"
        ts.git(self.base, "init", "-q", "--bare", "-b", "main", str(bare))
        ts.git(work, "push", "-q", f"file://{bare}", "HEAD:refs/heads/main")
        self.remotes[REPO] = bare
        self.assert_skipped(self.verdict(), DIFFERS, network=True)

    def test_the_throwaway_is_removed(self) -> None:
        self.assertEqual(self.verdict().kind, "recorded")
        left = self.state() / "setup-trust"
        self.assertEqual(list(left.iterdir()) if left.exists() else [], [])

    def test_a_default_branch_with_a_slash(self) -> None:
        self.remotes[REPO] = self.stand_in(REPO, branch="release/1")
        self.assertEqual(self.verdict().kind, "recorded")
        self.assertEqual(self.provenance()["reference"]["branch"], "release/1")


class ReviewedRepositoryTests(TrustCase):
    """AC-016."""

    def test_a_repointed_repository_is_not_reviewed(self) -> None:
        changed = CONFIG.replace(REPO, "evil/project") + WIDENED
        (self.root / "ballast.toml").write_text(changed)
        _commit(self.root, "repoint")
        self.remotes["evil/project"] = self.stand_in(
            "evil/project",
            {
                "ballast.toml": changed,
                ".specify/memory/constitution.md": CONSTITUTION,
            },
        )
        verdict = self.verdict()
        self.assert_skipped(
            verdict, "the pinned repository is not one you trusted on this machine"
        )

    def test_a_never_trusted_machine(self) -> None:
        (launcher.state_base(self.root) / launcher.REVIEWED).unlink()
        self.assert_skipped(
            self.verdict(),
            "the pinned repository is not one you trusted on this machine",
        )

    def test_matching_is_case_insensitive(self) -> None:
        (launcher.state_base(self.root) / launcher.REVIEWED).unlink()
        launcher.add_reviewed(self.root, "Example/PROJECT")
        self.assertEqual(self.verdict().kind, "recorded")

    def test_a_malformed_record_reads_as_empty(self) -> None:
        path = launcher.state_base(self.root) / launcher.REVIEWED
        for text in (
            "{",
            '{"schema": 2, "repositories": ["example/project"]}',
            '{"schema": 1, "repositories": [1]}',
            '{"schema": 1, "repositories": ["a b"]}',
        ):
            with self.subTest(text=text):
                path.write_text(text)
                self.assertEqual(launcher.reviewed_repositories(self.root), frozenset())
                self.assertEqual(self.verdict().kind, "skipped")
                self.fresh()


class EveryRefusalTests(TrustCase):
    """AC-017: reason and `ballast trust` printed, same exit status, baseline kept."""

    def test_every_skipped_case_reports_and_keeps_the_baseline(self) -> None:
        def widen(root: Path) -> None:
            (root / "ballast.toml").write_text(CONFIG + WIDENED)
            _commit(root, "widen")

        def uncommitted(root: Path) -> None:
            (root / "ballast.toml").write_text(CONFIG + "# x\n")

        def runs(root: Path) -> None:
            path = root / ".specify/workflows/runs/r1/f"
            path.parent.mkdir(parents=True)
            path.write_text("{}")

        def unreviewed(root: Path) -> None:
            (root / "ballast.toml").write_text(CONFIG.replace(REPO, "other/repo"))
            _commit(root, "repoint")

        def venv(root: Path) -> None:
            (root / ".venv").mkdir()
            (root / ".venv/x").write_text("x")

        def tamper(root: Path) -> None:
            (root / launcher.TAMPER_MARKER).write_text("")

        cases = {
            "widened": (widen, DIFFERS),
            "uncommitted": (uncommitted, "has uncommitted changes"),
            "runs": (runs, "saved run state"),
            "unreviewed": (unreviewed, "not one you trusted"),
            "venv": (venv, ".venv/x was not written by setup"),
            "tamper": (tamper, "BALLAST_TAMPERED"),
        }
        for number, (name, (mutate, reason)) in enumerate(cases.items()):
            with self.subTest(case=name):
                root = self.new_project(f"case-{number}")
                mutate(root)
                state = self.state(root)
                state.mkdir(parents=True)
                launcher.record_baseline(
                    state, {"ballast.toml": "9" * 64}, source="trust"
                )
                kept = {
                    n: (state / n).read_bytes()
                    for n in (launcher.TRUSTED, launcher.TRUSTED_SOURCE)
                }
                code, out, err = self.setup(root)
                self.assertEqual(code, 0, err)
                self.assertIn(ts.SUCCESS, out)
                self.assertIn("No trust baseline recorded: ", out)
                self.assertIn(reason, out)
                self.assertIn("run `ballast trust`", out)
                self.assertEqual(
                    kept,
                    {n: (state / n).read_bytes() for n in kept},
                )

    def test_an_unobservable_branch_reports_too(self) -> None:
        root = self.new_project("offline")
        with patch.dict(self.remotes, {REPO: self.base / "missing.git"}):
            code, out, err = self.setup(root)
        self.assertEqual(code, 0, err)
        self.assertIn("offline or unreachable", out)
        self.assertIn("run `ballast trust`", out)
        self.assertIsNone(self.baseline(root))

    def test_a_failed_installation_records_nothing(self) -> None:
        root = self.new_project("failed")
        with patch.dict(ts.FAKE, {"fail": "init"}):
            code, out, err = self.setup(root)
        self.assertEqual(code, 1, err)
        self.assertNotIn("trust baseline", out)
        self.assertIsNone(self.baseline(root))


class RecordStepTests(TrustCase):
    """F-004: a failed or raced recording restores the previous baseline."""

    NAMES = (launcher.TRUSTED, launcher.TRUSTED_SOURCE)

    def previous(self) -> dict[str, bytes | None]:
        launcher.record_baseline(
            self.state(), {"ballast.toml": "9" * 64}, source="trust"
        )
        return self.current()

    def current(self) -> dict[str, bytes | None]:
        return {
            n: (self.state() / n).read_bytes() if (self.state() / n).exists() else None
            for n in self.NAMES
        }

    def after_writing(self, then: Callable[[], None]) -> AbstractContextManager:
        """Patch the writer: it writes the baseline for real, then `then` runs."""
        real = launcher.record_baseline

        def wrapped(state: Path, inputs: dict[str, str], **kwargs: Any) -> None:  # noqa: ANN401
            real(state, inputs, **kwargs)
            then()

        return patch.object(setup_trust.launcher, "record_baseline", wrapped)

    def test_an_input_changing_during_the_check(self) -> None:
        before = self.previous()
        late = self.root / ".specify/late.sh"
        with self.after_writing(lambda: late.write_text("late\n")):
            verdict = self.verdict()
        self.assertEqual(verdict.kind, "skipped")
        self.assertIn("protected inputs changed while setup checked them", verdict.text)
        self.assertEqual(self.current(), before)

    def test_a_failing_write(self) -> None:
        before = self.previous()

        def full() -> None:
            raise OSError(28, "No space left on device")

        with self.after_writing(full):
            verdict = self.verdict()
        self.assertEqual(verdict.kind, "skipped")
        self.assertIn("could not record it", verdict.text)
        self.assertEqual(self.current(), before)

    def test_nothing_before_means_nothing_after(self) -> None:
        def broken() -> None:
            raise OSError(5, "I/O error")

        with self.after_writing(broken):
            self.assertEqual(self.verdict().kind, "skipped")
        self.assertEqual(self.current(), dict.fromkeys(self.NAMES))


# --- US2: preparation ---------------------------------------------------------


class PrepareTrustTests(TrustWorktreeCase):
    """AC-006 to AC-009."""

    def test_a_new_worktree_is_trusted_by_its_first_command(self) -> None:
        # AC-006
        worktree = self.worktree()
        code, out, err = self.prepare(worktree)
        self.assertEqual(code, 0, err)
        self.assertIn("Prepared the vA installation from ", out)
        self.assertIn("Recorded the trust baseline", out)
        self.assertEqual(self.provenance(worktree)["source"], "setup")
        self.assertEqual(
            launcher.trusted_inputs(worktree),
            json.loads(self.baseline(worktree)),
        )
        status = self.launcher("status", "--json", root=worktree)
        self.assertEqual(
            json.loads(status.stdout),
            {"installed": True, "refusal": None, "baseline_source": "setup"},
        )

    def test_a_branch_that_changed_the_configuration(self) -> None:
        # AC-007: installed by setup there first, then prepared from it.
        changed = self.branch_worktree({"ballast.toml": CONFIG + WIDENED})
        code, out, err = self.setup(changed)
        self.assertEqual(code, 0, err)
        self.assertIsNone(self.baseline(changed))
        second = self.branch_worktree({}, source=changed)
        self.assertEqual((second / "ballast.toml").read_text(), CONFIG + WIDENED)
        code, out, err = self.prepare(second)
        self.assertEqual(code, 0, err)
        self.assertIn("Prepared the vA installation", out)
        self.assertIn("No trust baseline recorded: ", out)
        self.assertIn("run `ballast trust`", out)
        self.assertIsNone(self.baseline(second))
        refusal = json.loads(self.launcher("status", "--json", root=second).stdout)
        self.assertIn("ballast trust", refusal["refusal"])

    def test_a_branch_that_changed_the_constitution(self) -> None:
        worktree = self.branch_worktree(
            {".specify/memory/constitution.md": "weakened\n"}
        )
        self.assertEqual(self.prepare(worktree)[0], 0)
        self.assertIsNone(self.baseline(worktree))
        refusal = json.loads(self.launcher("status", "--json", root=worktree).stdout)
        self.assertIn("ballast trust", refusal["refusal"])

    def test_a_stale_baseline_at_a_reused_path_is_never_reused(self) -> None:
        # AC-008, eligible and ineligible variants.
        for changed in (False, True):
            with self.subTest(changed=changed):
                files = {".specify/memory/constitution.md": "x\n"} if changed else {}
                worktree = self.branch_worktree(files)
                state = self.state(worktree)
                state.mkdir(parents=True, exist_ok=True)
                launcher.record_baseline(state, {"stale": "0" * 64}, source="trust")
                stale = (state / launcher.TRUSTED).read_bytes()
                self.assertTrue((state / launcher.TRUSTED_SOURCE).exists())
                code, out, err = self.prepare(worktree)
                self.assertEqual(code, 0, err)
                self.assertIn("removed a trust baseline recorded before", out)
                if changed:
                    self.assertIsNone(self.baseline(worktree))
                    self.assertFalse(
                        (self.state(worktree) / launcher.TRUSTED_SOURCE).exists()
                    )
                else:
                    self.assertNotEqual(self.baseline(worktree), stale)
                    self.assertEqual(self.provenance(worktree)["source"], "setup")

    def test_no_other_checkouts_baseline_is_read_or_copied(self) -> None:
        # AC-009
        self.trust()
        own = self.baseline()
        worktree = self.worktree()
        opened: list[str] = []
        code, _, err = self.prepare(worktree, opened)
        self.assertEqual(code, 0, err)
        other = str(self.state())
        for path in opened:
            self.assertFalse(
                path.startswith(other)
                and path.rsplit("/", 1)[-1]
                in {"trusted.json", "trusted-source.json", "run.json"},
                path,
            )
        self.assertNotEqual(self.baseline(worktree), own)
        self.assertEqual(
            json.loads(self.baseline(worktree)), launcher.trusted_inputs(worktree)
        )

    def test_a_second_preparation_records_nothing(self) -> None:
        worktree = self.worktree()
        self.prepare(worktree)
        before = self.baseline(worktree)
        code, out, _ = self.prepare(worktree)
        self.assertEqual(code, 0)
        self.assertIn("nothing to prepare", out)
        self.assertEqual(self.baseline(worktree), before)

    def test_a_killed_preparation_records_only_once_complete(self) -> None:
        # TEST-001: an interrupted attempt never leaves a baseline; the recovery
        # applies the same conditions to the recovered installation.
        for point, count in (("validate", 0), ("switching", 0), ("committed", 0)):
            with self.subTest(point=point):
                worktree = self.worktree()
                self.kill(point, count, worktree, ("--prepare",))
                self.assertIsNone(self.baseline(worktree))
                code, out, err = self.prepare(worktree)
                self.assertEqual(code, 0, err)
                self.assertIn("recovered an interrupted preparation: ", out)
                self.assertIn("Recorded the trust baseline", out)
                self.assertEqual(
                    json.loads(self.baseline(worktree)),
                    launcher.trusted_inputs(worktree),
                )
                self.assertEqual(self.provenance(worktree)["source"], "setup")

    def test_a_recovered_preparation_that_is_ineligible_records_nothing(self) -> None:
        worktree = self.branch_worktree({".specify/memory/constitution.md": "x\n"})
        self.kill("committed", 0, worktree, ("--prepare",))
        code, out, err = self.prepare(worktree)
        self.assertEqual(code, 0, err)
        self.assertIn("is complete", out)
        self.assertIn("No trust baseline recorded: ", out)
        self.assertIsNone(self.baseline(worktree))

    def test_two_preparations_at_once_record_once(self) -> None:
        # TEST-010: the second finds the work done and records nothing.
        worktree = self.worktree()
        real = ts.setup.Setup.fill_from_candidates

        def slow(setup_self: object, stage: Path, state: Path) -> Path:
            time.sleep(1.0)
            return real(setup_self, stage, state)

        out = io.StringIO()
        codes: list[int] = []
        with (
            patch.object(ts.setup.Setup, "fill_from_candidates", slow),
            redirect_stdout(out),
        ):
            threads = [
                threading.Thread(
                    target=lambda: codes.append(
                        ts.setup.cli(["--project", str(worktree), "--prepare"])
                    )
                )
                for _ in range(2)
            ]
            threads[0].start()
            time.sleep(0.3)
            threads[1].start()
            for thread in threads:
                thread.join(timeout=60)
        self.assertEqual(codes, [0, 0])
        self.assertEqual(out.getvalue().count("Recorded the trust baseline"), 1)
        self.assertIn("nothing to prepare", out.getvalue())
        self.assertEqual(self.provenance(worktree)["source"], "setup")

    def test_a_second_preparation_waits_for_a_baseline_decision(self) -> None:
        # ENG-001: the holder may be asking the network; never refuse meanwhile.
        worktree = self.worktree()
        self.prepare(worktree)
        state = self.state(worktree)
        installation = ts.setup.Setup(worktree)
        holder = state / "setup-holder.json"
        descriptor = launcher.checkout_lock(state, shared=False)
        self.assertIsNotNone(descriptor)
        threading.Timer(1.5, os.close, (descriptor,)).start()
        waits = {"phase": "settling", "pid": os.getpid()}
        holder.write_text(json.dumps({"mode": "prepare", **waits}))
        with patch.object(ts.setup, "LOCK_RETRY_SECONDS", 0.3):
            held = installation.hold(state)
        self.assertIsNone(held)  # it was installed meanwhile: nothing to prepare

    def test_a_second_preparation_still_refuses_a_plain_holder(self) -> None:
        worktree = self.worktree()
        self.prepare(worktree)
        state = self.state(worktree)
        descriptor = launcher.checkout_lock(state, shared=False)
        self.addCleanup(os.close, descriptor)
        (state / "setup-holder.json").write_text(
            json.dumps({"mode": "prepare", "pid": os.getpid()})
        )
        with (
            patch.object(ts.setup, "LOCK_RETRY_SECONDS", 0.3),
            self.assertRaises(ts.setup.RefusedError),
        ):
            ts.setup.Setup(worktree).hold(state)

    def test_a_stale_settling_holder_does_not_wait(self) -> None:
        worktree = self.worktree()
        self.prepare(worktree)
        state = self.state(worktree)
        descriptor = launcher.checkout_lock(state, shared=False)
        self.addCleanup(os.close, descriptor)
        (state / "setup-holder.json").write_text(
            json.dumps({"mode": "prepare", "phase": "settling", "pid": 2**22 + 7})
        )
        with (
            patch.object(ts.setup, "LOCK_RETRY_SECONDS", 0.3),
            self.assertRaises(ts.setup.RefusedError),
        ):
            ts.setup.Setup(worktree).hold(state)

    def test_a_marker_makes_preparation_refuse(self) -> None:
        # AC-018
        worktree = self.worktree()
        state = self.state(worktree)
        state.mkdir(parents=True, exist_ok=True)
        (state / launcher.IN_PROGRESS).write_text("")
        code, _, err = self.prepare(worktree)
        self.assertEqual(code, 2)
        self.assertIn("ballast discard-runs", err)
        self.assertIsNone(self.baseline(worktree))


# --- shared rules ------------------------------------------------------------


class SharedRulesTests(unittest.TestCase):
    """F-002, FR-020."""

    def test_branch_sync_shares_the_git_environment(self) -> None:
        self.assertIs(branch_sync.DROPPED_ENV, setup_trust.DROPPED_ENV)
        self.assertIs(branch_sync.draft_pr.GIT_LOCATION, setup_trust.GIT_LOCATION)
        ambient = (
            "GIT_TERMINAL_PROMPT",
            "GIT_ASKPASS",
            "SSH_ASKPASS_REQUIRE",
            "GIT_NO_LAZY_FETCH",
            "GIT_NO_REPLACE_OBJECTS",
        )
        with patch.dict(os.environ):
            for key in ambient:
                os.environ.pop(key, None)
            env = setup_trust.throwaway_environment(ROOT)
        for key, value in {
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_ASKPASS": "",
            "SSH_ASKPASS_REQUIRE": "never",
            "GIT_NO_LAZY_FETCH": "1",
            "GIT_NO_REPLACE_OBJECTS": "1",
        }.items():
            self.assertEqual(env[key], value)
        with patch.dict(
            os.environ,
            {
                "GIT_DIR": "/x",
                "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "a",
                "DISPLAY": ":0",
                "SSH_ASKPASS": "/x",
            },
        ):
            env = setup_trust.throwaway_environment(ROOT)
        for key in (
            "GIT_DIR",
            "GIT_CONFIG_COUNT",
            "GIT_CONFIG_KEY_0",
            "DISPLAY",
            "SSH_ASKPASS",
        ):
            self.assertNotIn(key, env)

    def test_the_url_rule(self) -> None:
        self.assertEqual(
            setup_trust.repository_url(ROOT, "o", "n", origin="https://github.com/a/b"),
            "https://github.com/o/n.git",
        )
        for origin in ("", "git@github.com:a/b.git", "ssh://git@github.com/a/b"):
            self.assertEqual(
                setup_trust.repository_url(ROOT, "o", "n", origin=origin),
                "ssh://git@github.com/o/n.git",
            )
        self.assertEqual(
            branch_sync._url(ROOT, "o", "n", origin="https://x"),  # noqa: SLF001
            "https://github.com/o/n.git",
        )

    def test_the_module_imports_only_the_standard_library_and_the_launcher_set(
        self,
    ) -> None:
        tree = ast.parse((ROOT / "tools/spec_workflow/setup_trust.py").read_text())
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                names.add((node.module or "").split(".")[0])
        local = {"autonomy", "launcher", "ledger"}
        self.assertEqual(names & local, local)
        self.assertEqual(
            {n for n in names - local if n not in sys.stdlib_module_names}, set()
        )

    def test_check_and_doctor_never_import_it(self) -> None:
        code = (
            "import sys, runpy\n"
            "sys.argv = ['setup', '--project', sys.argv[1], '--check']\n"
            "try:\n"
            f"    runpy.run_path({str(ROOT / 'tools/setup')!r}, run_name='__main__')\n"
            "except SystemExit:\n"
            "    pass\n"
            "assert 'setup_trust' not in sys.modules, 'imported'\n"
        )
        with TemporaryDirectory() as directory:
            (Path(directory) / "ballast.toml").write_text(ts.PIN.format("v1"))
            result = subprocess.run(  # noqa: S603
                [sys.executable, "-I", "-S", "-c", code, directory],
                capture_output=True,
                text=True,
                check=False,
                env={**os.environ, "XDG_STATE_HOME": str(outside_temp())},
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        doctor = (ROOT / "tools/ballast").read_text()
        self.assertNotIn("setup_trust", doctor)
        self.assertTrue(re.search(r"^import|^from", doctor, re.MULTILINE))


if __name__ == "__main__":
    unittest.main()
