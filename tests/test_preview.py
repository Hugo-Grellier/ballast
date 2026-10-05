"""Offline checks for `ballast preview` (#14, User Story 3)."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import unittest
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SHIM = ROOT / "tools/ballast"
_loader = SourceFileLoader("ballast_preview", str(SHIM))
shim = module_from_spec(spec_from_loader("ballast_preview", _loader))
_loader.exec_module(shim)

sys.path.insert(0, str(ROOT / "tests"))
from test_autonomy import operator_state, outside_temp  # noqa: E402

sys.path.pop(0)

PROJECT_IGNORE = ".ballast/\n.agents/skills/\ndocs/policies/*.md\n"
# A fixture standard's tools/setup: it installs FILES, removing what an
# earlier version installed, and, when recoverable, records the installation
# where this feature's setup does. `--check` reports whether it is current.
FAKE_SETUP = """\
import hashlib, json, os, shutil, sys
from pathlib import Path

GITIGNORE = {gitignore!r}
IGNORE_PROBES = ((".ballast/spec_workflow/run.py", True),)
REF, RECOVERABLE, FAIL, FILES = {ref!r}, {recoverable!r}, {fail!r}, {files!r}

args = sys.argv[1:]
project = Path(args[args.index("--project") + 1])
stamp = project / ".ballast/.setup-version"
if "--check" in args:
    current = stamp.is_file() and stamp.read_text().strip() == "fp-" + REF
    print("current" if current else "stale")
    sys.exit(0 if current else 1)
if FAIL:
    sys.exit("setup: spec-kit init failed: exit status 1")
for name in (".ballast/spec_workflow", ".agents/skills", ".newtool"):
    shutil.rmtree(project / name, ignore_errors=True)
for path in (project / "docs/policies").glob("*.md"):
    path.unlink()
for name, text in FILES.items():
    (project / name).parent.mkdir(parents=True, exist_ok=True)
    (project / name).write_text(text)
stamp.parent.mkdir(parents=True, exist_ok=True)
stamp.write_text("fp-" + REF + "\\n")
if RECOVERABLE:
    names = [*FILES, ".ballast/.setup-version"]
    files = {{n: hashlib.sha256((project / n).read_bytes()).hexdigest() for n in names}}
    key = hashlib.sha256(str(project.resolve()).encode()).hexdigest()[:16]
    state = Path(os.environ["XDG_STATE_HOME"]) / "ballast" / key
    state.mkdir(parents=True, exist_ok=True)
    record = {{"schema": 1, "ref": REF, "fingerprint": "fp-" + REF,
              "entries": names, "files": files}}
    (state / "installation.json").write_text(json.dumps(record))
"""
VERSIONS = {
    "vA": {
        "recoverable": True,
        "minimum": "0.1.0",
        "resumes": ["ballast-run/1"],
        "files": {
            ".ballast/spec_workflow/run.py": "run 1\n",
            ".agents/skills/ballast-a/SKILL.md": "a\n",
            "docs/policies/old.md": "old\n",
        },
    },
    "vB": {
        "recoverable": True,
        "minimum": "0.1.0",
        "resumes": ["ballast-run/1"],
        "files": {
            ".ballast/spec_workflow/run.py": "run 2\n",
            ".agents/skills/ballast-a/SKILL.md": "a\n",
            ".agents/skills/ballast-new/SKILL.md": "new\n",
        },
    },
    # Older than this feature: no [setup] or [runs], and a new top-level path.
    "vC": {
        "recoverable": False,
        "minimum": "99.0.0",
        "resumes": None,
        "files": {
            ".ballast/spec_workflow/run.py": "run 0\n",
            ".newtool/file": "x\n",
        },
        "gitignore": PROJECT_IGNORE + ".newtool/\n",
    },
    "vD": {"recoverable": True, "fail": True, "files": {}},
}


def fixture_standard(directory: Path, ref: str) -> None:
    """Write a cached standard version, with its content record."""
    version = VERSIONS[ref]
    tools = directory / "tools"
    tools.mkdir(parents=True)
    (tools / "setup").write_text(
        FAKE_SETUP.format(
            gitignore=version.get("gitignore", PROJECT_IGNORE),
            ref=ref,
            recoverable=version["recoverable"],
            fail=version.get("fail", False),
            files=version["files"],
        )
    )
    manifest = f'[cli]\nminimum = "{version.get("minimum", "0.1.0")}"\n'
    if version["recoverable"]:
        manifest += "[setup]\nrecoverable = true\n"
    if version.get("resumes") is not None:
        manifest += (
            f'[runs]\nformat = "ballast-run/1"\nresumes = {version["resumes"]}\n'
        )
    (tools / "cli.toml").write_text(manifest)
    record = shim.cache_record(directory, ref)
    (directory / shim.CACHE_RECORD).write_text(json.dumps(record))


def tree(root: Path) -> dict[str, str]:
    """Every file and link under root with its digest."""
    found = {}
    for path in sorted(root.rglob("*")) if root.is_dir() else []:
        name = path.relative_to(root).as_posix()
        if path.is_symlink():
            found[name] = "link:" + str(path.readlink())
        elif path.is_file():
            found[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return found


class PreviewTests(unittest.TestCase):
    """The preview reports what an update would do and changes nothing."""

    def setUp(self) -> None:
        directory = TemporaryDirectory(dir=outside_temp())
        self.addCleanup(directory.cleanup)
        self.base = Path(directory.name)
        self.data = self.base / "data"
        self.state = operator_state(self)
        for ref in VERSIONS:
            fixture_standard(self.data / "ballast/standard" / ref, ref)
        self.env = {
            "XDG_DATA_HOME": str(self.data),
            "XDG_STATE_HOME": str(self.state),
        }
        environment = patch.dict(os.environ, self.env)
        environment.start()
        self.addCleanup(environment.stop)
        os.environ.pop("BALLAST_STANDARD_DIR", None)
        self.project = self.make_project("project")

    def make_project(self, name: str) -> Path:
        project = self.base / name
        project.mkdir()
        subprocess.run(["git", "init", "-q", str(project)], check=True)  # noqa: S603, S607
        (project / ".gitignore").write_text(PROJECT_IGNORE)
        (project / "ballast.toml").write_text('[standard]\nref = "vA"\n')
        (project / ".specify/memory").mkdir(parents=True)
        (project / ".specify/memory/constitution.md").write_text("constitution\n")
        for run, status in (("r1", "paused"), ("r2", "paused"), ("r3", "completed")):
            (project / ".specify/workflows/runs" / run).mkdir(parents=True)
            state = project / ".specify/workflows/runs" / run / "state.json"
            state.write_text(json.dumps({"status": status}))
        archive = project / ".git/speckit-runs/r1"
        archive.mkdir(parents=True)
        (archive / "run-format.json").write_text(
            '{"schema": 1, "format": "ballast-run/1"}'
        )
        self.install(project, "vA")
        return project

    def install(self, project: Path, ref: str) -> None:
        setup = self.data / "ballast/standard" / ref / "tools/setup"
        subprocess.run(  # noqa: S603
            [sys.executable, "-I", "-S", str(setup), "--project", str(project)],
            check=True,
        )

    def snapshot(self) -> dict[str, dict[str, str]]:
        cache = self.data / "ballast/standard"
        return {
            "project": tree(self.project),
            "state": tree(self.state),
            "cache": {
                k: v for k, v in tree(cache).items() if not k.startswith(".locks")
            },
        }

    def preview(self, *args: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        before = self.snapshot()
        with (
            contextlib.chdir(self.project),
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(err),
        ):
            try:
                code = shim.main(["preview", *args])
            except SystemExit as error:
                code = error.code
        # AC-020: the checkout, its run state, archives and operator state are
        # unchanged, and no disposable build is left.
        self.assertEqual(self.snapshot(), before)
        preview = self.data / "ballast/preview"
        self.assertEqual(list(preview.iterdir()) if preview.exists() else [], [])
        return code, out.getvalue(), err.getvalue()

    def report(self, ref: str) -> tuple[int, dict]:
        code, out, err = self.preview(ref, "--json")
        self.assertIn(code, (0, 1), err)
        return code, json.loads(out)

    def test_reports_versions_runs_paths_and_steps(self) -> None:
        code, report = self.report("vB")
        self.assertEqual(code, 1)  # r2 records no format
        # AC-016
        self.assertEqual(
            (report["pinned"], report["installed"], report["target"]),
            ("vA", "vA", "vB"),
        )
        self.assertTrue(report["target_recoverable"])
        self.assertEqual(
            report["cli"], {"version": shim.VERSION, "minimum": "0.1.0", "meets": True}
        )
        # AC-017: a completed run is not listed; a run without a format blocks.
        self.assertEqual(
            report["runs"],
            [
                {
                    "id": "r1",
                    "status": "paused",
                    "format": "ballast-run/1",
                    "compatible": True,
                },
                {"id": "r2", "status": "paused", "format": None, "compatible": False},
            ],
        )
        self.assertEqual(
            report["blockers"],
            ["run r2 cannot resume under vB: finish or discard it before updating"],
        )
        # AC-018, SC-006: equal to the actual update of a copy.
        copy = self.make_project("copy")
        before = self.recorded(copy)
        (copy / "ballast.toml").write_text('[standard]\nref = "vB"\n')
        self.install(copy, "vB")
        after = self.recorded(copy)
        self.assertEqual(
            report["paths"],
            {
                "added": sorted(after.keys() - before.keys()),
                "changed": sorted(
                    n for n in after.keys() & before.keys() if after[n] != before[n]
                ),
                "removed": sorted(before.keys() - after.keys()),
            },
        )
        self.assertEqual(report["paths"]["removed"], ["docs/policies/old.md"])
        self.assertEqual(
            report["ignore"], {"ok": True, "not_ignored": [], "block": None}
        )
        self.assertEqual(report["project_owned_changed"], [])
        # AC-019
        self.assertEqual(
            report["steps"],
            [
                'Set ref = "vB" under [standard] in ballast.toml, review and commit it',
                "ballast setup",
                (
                    "Review the changed protected inputs: ballast.toml, "
                    ".ballast/spec_workflow/run.py"
                ),
                "ballast trust",
                "Run the project's checks: none configured",
            ],
        )
        code, text, _ = self.preview("vB")
        self.assertEqual(code, 1)
        for line in (
            "  pinned     vA",
            "  installed  vA",
            "  target     vB (recovery guarantees: yes)",
            f"  CLI        v{shim.VERSION} meets vB's minimum 0.1.0",
            "  r1  paused  ballast-run/1  can resume under vB",
            "  r2  paused  (no format)  cannot resume: finish or discard it",
            "  added    .agents/skills/ballast-new/SKILL.md",
            "  changed  .ballast/spec_workflow/run.py",
            "  removed  docs/policies/old.md",
            "Project-owned files: none would change",
            "  2. ballast setup",
            "Blocked: run r2 cannot resume under vB: finish or discard it",
        ):
            self.assertIn(line, text)

    def recorded(self, project: Path) -> dict[str, str]:
        key = hashlib.sha256(str(project.resolve()).encode()).hexdigest()[:16]
        record = self.state / "ballast" / key / "installation.json"
        return json.loads(record.read_text())["files"]

    def test_older_target_is_flagged(self) -> None:
        # AC-021, AC-016 (unmet minimum), AC-018 (ignore impact).
        code, report = self.report("vC")
        self.assertEqual(code, 1)
        self.assertFalse(report["target_recoverable"])
        self.assertEqual(report["cli"]["meets"], False)
        self.assertEqual(report["runs"][0]["compatible"], False)
        self.assertEqual(
            report["ignore"],
            {
                "ok": False,
                "not_ignored": [".newtool/file"],
                "block": VERSIONS["vC"]["gitignore"],
            },
        )
        self.assertEqual(report["paths"]["added"], [".newtool/file"])
        self.assertIn(".agents/skills/ballast-a/SKILL.md", report["paths"]["removed"])
        self.assertTrue(report["steps"][0].startswith("Install the CLI v99.0.0: "))
        self.assertTrue(report["steps"][1].startswith("Add this block to .gitignore"))
        self.assertIn(
            f"this CLI v{shim.VERSION} is below vC's minimum 99.0.0", report["blockers"]
        )
        _, text, _ = self.preview("vC")
        self.assertIn(
            "target     vC (recovery guarantees: no — a failed setup or rollback to "
            "this version can leave the checkout without a usable installation)",
            text,
        )

    def test_checkout_text_cannot_drive_the_terminal(self) -> None:
        # Run IDs and states come from the agent-writable checkout.
        run = self.project / ".specify/workflows/runs/r\x1b]0;x\x07"
        run.mkdir(parents=True)
        (run / "state.json").write_text(json.dumps({"status": "\x1b[2Jpaused"}))
        _, text, _ = self.preview("vB")
        self.assertNotIn("\x1b", text)
        self.assertNotIn("\x07", text)
        self.assertIn("?[2Jpaused", text)

    def test_failed_build_reports_nothing_compatible(self) -> None:
        code, out, err = self.preview("vD")
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("ballast: preview of vD failed: the build of vD failed: ", err)
        self.assertIn("spec-kit init failed", err)

    def test_refusals_change_nothing(self) -> None:
        for args, reason in (
            (("../x",), "../x is not a tag or commit of the standard"),
            (("vB", "--json"), "BALLAST_STANDARD_DIR is set"),
        ):
            with self.subTest(reason=reason), contextlib.ExitStack() as stack:
                if "BALLAST" in reason:
                    stack.enter_context(
                        patch.dict(os.environ, {"BALLAST_STANDARD_DIR": str(ROOT)})
                    )
                code, out, err = self.preview(*args)
                self.assertEqual((code, out), (2, ""))
                self.assertIn(f"ballast: refusing: {reason}", err)
        key = hashlib.sha256(str(self.project.resolve()).encode()).hexdigest()[:16]
        state = self.state / "ballast" / key
        state.mkdir(parents=True, exist_ok=True)
        (state / "setup-attempt.json").write_text("{}\n")
        code, _, err = self.preview("vB")
        self.assertEqual(code, 2)
        self.assertIn(
            "setup did not finish in this checkout; run `ballast setup` first", err
        )
        (state / "setup-attempt.json").unlink()
        holder = subprocess.Popen(  # noqa: S603
            [
                sys.executable,
                "-c",
                (
                    "import fcntl, os, sys, time\n"
                    "fd = os.open(sys.argv[1], os.O_RDWR | os.O_CREAT, 0o600)\n"
                    "fcntl.flock(fd, fcntl.LOCK_EX)\nprint('held', flush=True)\n"
                    "time.sleep(60)\n"
                ),
                str(state / "checkout.lock"),
            ],
            stdout=subprocess.PIPE,
            text=True,
        )
        self.addCleanup(holder.stdout.close)
        self.addCleanup(holder.wait)
        self.addCleanup(holder.kill)
        self.assertEqual(holder.stdout.readline(), "held\n")
        code, _, err = self.preview("vB")
        self.assertEqual(code, 2)
        self.assertIn("ballast setup is running in this checkout", err)
        shutil.rmtree(self.data / "ballast/preview", ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
