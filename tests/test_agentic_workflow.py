"""Offline checks for the global agentic-workflow shim."""

from __future__ import annotations

import io
import os
import subprocess
import tarfile
import unittest
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
SHIM = ROOT / "tools/agentic-workflow"
_loader = SourceFileLoader("agentic_workflow", str(SHIM))
shim = module_from_spec(spec_from_loader("agentic_workflow", _loader))
_loader.exec_module(shim)

FAKE_LAUNCHER = b"import sys; print('launcher', *sys.argv[1:])\n"


class ShimTests(unittest.TestCase):
    """A project picks a fetched version; the launcher never comes from it."""

    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.base = Path(self.directory.name)
        self.project = self.base / "project"
        self.project.mkdir()
        self.env = {**os.environ, "XDG_DATA_HOME": str(self.base / "data")}
        self.env.pop("AGENTIC_STANDARD_DIR", None)

    def tearDown(self) -> None:
        self.directory.cleanup()

    def pin(self, ref: str) -> None:
        (self.project / "agentic.toml").write_text(f'[standard]\nref = "{ref}"\n')

    def shim(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(  # noqa: S603
            [str(SHIM), *args],
            cwd=self.project,
            env=self.env,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_requires_a_valid_ref(self) -> None:
        self.assertIn("cannot read agentic.toml", self.shim("trust").stderr)
        for ref in ("../other", "-x", "a/b", ""):
            self.pin(ref)
            self.assertIn("needs [standard] ref", self.shim("trust").stderr)

    def test_only_setup_fetches(self) -> None:
        self.pin("v0.1.0")
        result = self.shim("run", "start")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("v0.1.0 is not fetched", result.stderr)
        self.assertFalse((self.base / "data/agentic/standard/v0.1.0").exists())

    def test_runs_the_launcher_of_the_pinned_version(self) -> None:
        archive = self.base / "standard.tar.gz"
        with tarfile.open(archive, "w:gz") as contents:
            info = tarfile.TarInfo("standard-v0.1.0/tools/spec_workflow/launcher.py")
            info.size = len(FAKE_LAUNCHER)
            contents.addfile(info, io.BytesIO(FAKE_LAUNCHER))
        os.environ["XDG_DATA_HOME"] = self.env["XDG_DATA_HOME"]
        try:
            shim.ARCHIVE = archive.as_uri()
            shim.fetch("v0.1.0", shim.standard_dir("v0.1.0"))
        finally:
            del os.environ["XDG_DATA_HOME"]
        # A launcher planted in the checkout is never used.
        planted = self.project / ".agentic/spec_workflow/launcher.py"
        planted.parent.mkdir(parents=True)
        planted.write_text("print('planted')\n")
        self.pin("v0.1.0")
        result = self.shim("run", "start")
        self.assertEqual(result.stdout, "launcher run start\n", result.stderr)


if __name__ == "__main__":
    unittest.main()
