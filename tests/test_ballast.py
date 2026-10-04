"""Offline checks for the global ballast shim."""

from __future__ import annotations

import hashlib
import io
import os
import re
import shutil
import subprocess
import sys
import tarfile
import types
import unittest
from contextlib import redirect_stderr, redirect_stdout
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SHIM = ROOT / "tools/ballast"
_loader = SourceFileLoader("ballast", str(SHIM))
shim = module_from_spec(spec_from_loader("ballast", _loader))
_loader.exec_module(shim)

FAKE_LAUNCHER = b"import sys; print('launcher', *sys.argv[1:])\n"
README = ROOT / "README.md"
CONTRACT = ROOT / "specs/12-cli-install-doctor/contracts/install.md"
RELEASES = "https://github.com/Hugo-Grellier/ballast/releases/download"
START, END = "<!-- x-release-please-start-version -->", "<!-- x-release-please-end -->"
DOCTOR_HINT = "; run `ballast doctor` for details"


def readme_install_line(text: str | None = None) -> str:
    """Return the single install line inside the README's Release Please block."""
    block = (text or README.read_text()).split(START, 1)[1].split(END, 1)[0]
    (line,) = [line for line in block.splitlines() if line.startswith("(")]
    return line


def release_build(version: str, *, drop_version: bool = False) -> bytes:
    """tools/ballast as a release of the given version would ship it."""
    source = SHIM.read_text()
    line = f'VERSION = "{shim.VERSION}"  # x-release-please-version\n'
    self_check = line in source
    assert self_check, "VERSION line moved"  # noqa: S101
    return source.replace(
        line, "" if drop_version else line.replace(shim.VERSION, version)
    ).encode()


class ShimTests(unittest.TestCase):
    """A project picks a fetched version; the launcher never comes from it."""

    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.base = Path(self.directory.name)
        self.project = self.base / "project"
        self.project.mkdir()
        self.env = {**os.environ, "XDG_DATA_HOME": str(self.base / "data")}
        self.env.pop("BALLAST_STANDARD_DIR", None)

    def tearDown(self) -> None:
        self.directory.cleanup()

    def pin(self, ref: str) -> None:
        (self.project / "ballast.toml").write_text(f'[standard]\nref = "{ref}"\n')

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
        self.assertIn("cannot read ballast.toml", self.shim("trust").stderr)
        for ref in ("../other", "-x", "a/b", ""):
            self.pin(ref)
            self.assertIn("needs [standard] ref", self.shim("trust").stderr)

    def test_only_setup_fetches(self) -> None:
        self.pin("v0.1.0")
        result = self.shim("run", "start")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("v0.1.0 is not fetched", result.stderr)
        self.assertFalse((self.base / "data/ballast/standard/v0.1.0").exists())

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
        planted = self.project / ".ballast/spec_workflow/launcher.py"
        planted.parent.mkdir(parents=True)
        planted.write_text("print('planted')\n")
        self.pin("v0.1.0")
        result = self.shim("run", "start")
        self.assertEqual(result.stdout, "launcher run start\n", result.stderr)


class VersionTests(unittest.TestCase):
    """`--version` needs nothing; an old interpreter gets a message (FR-006)."""

    def test_version_needs_no_project_or_network(self) -> None:
        with TemporaryDirectory() as directory:
            data = Path(directory) / "data"
            data.mkdir()
            env = {**os.environ, "XDG_DATA_HOME": str(data)}
            env.pop("BALLAST_STANDARD_DIR", None)
            result = subprocess.run(  # noqa: S603
                [str(SHIM), "--version"],
                cwd=directory,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(
                (result.returncode, result.stdout), (0, f"v{shim.VERSION}\n")
            )
            self.assertEqual(list(data.iterdir()), [])

    def test_old_interpreter_gets_a_message_not_a_traceback(self) -> None:
        stderr = io.StringIO()
        stub = types.SimpleNamespace(
            version_info=(3, 10, 4), stderr=stderr, exit=sys.exit
        )
        code = compile(SHIM.read_text(), str(SHIM), "exec")
        with (
            patch.dict(sys.modules, {"sys": stub}),
            self.assertRaises(SystemExit) as raised,
        ):
            exec(code, {"__name__": "ballast_old_python"})  # noqa: S102
        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(
            stderr.getvalue(), "ballast: needs Python 3.11 or newer (found 3.10)\n"
        )


class InstallTests(unittest.TestCase):
    """The README line installs a verified release, or changes nothing."""

    TAG = "v9.8.7"

    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.base = Path(self.directory.name)
        self.home = self.base / "home"
        self.home.mkdir()
        self.bin = self.home / ".local/bin"
        self.target = self.bin / "ballast"
        self.releases = self.base / "releases/download"
        self.env = {"HOME": str(self.home), "PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}
        self.publish(self.TAG)
        self.temporaries = set(Path("/tmp").glob("tmp.*"))  # noqa: S108

    def tearDown(self) -> None:
        # The line leaves its verified download under /tmp; drop ours only.
        for path in set(Path("/tmp").glob("tmp.*")) - self.temporaries:  # noqa: S108
            if path.is_dir() and {p.name for p in path.iterdir()} <= {
                "ballast",
                "ballast.sha256",
            }:
                shutil.rmtree(path)
        self.directory.cleanup()

    def publish(self, tag: str, content: bytes | None = None) -> Path:
        release = self.releases / tag
        release.mkdir(parents=True, exist_ok=True)
        content = release_build(tag[1:]) if content is None else content
        (release / "ballast").write_bytes(content)
        checksum = hashlib.sha256(content).hexdigest()
        (release / "ballast.sha256").write_text(f"{checksum}  ballast\n")
        return release

    def line(self, tag: str) -> str:
        line = readme_install_line()
        self.assertRegex(line, r"v=v\d+\.\d+\.\d+;")
        line = re.sub(r"v=v\d+\.\d+\.\d+;", f"v={tag};", line)
        return line.replace(RELEASES, self.releases.as_uri())

    def install(
        self, tag: str | None = None, *, cwd: Path | None = None, **env: str
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(  # noqa: S603
            [
                "/bin/bash",
                "-c",
                self.line(tag or self.TAG) + '; s=$?; echo "AFTER=$PATH"; exit $s',
            ],
            cwd=cwd or self.base,
            env={**self.env, **env},
            capture_output=True,
            text=True,
            check=False,
        )

    def version_of(self, path: Path) -> str:
        return subprocess.run(  # noqa: S603
            [str(path), "--version"], capture_output=True, text=True, check=True
        ).stdout.strip()

    def assert_unchanged(self, before: bytes, version: str) -> None:
        self.assertEqual(self.target.read_bytes(), before)
        self.assertEqual(self.version_of(self.target), version)

    def test_readme_line_is_the_contract_line(self) -> None:
        line = readme_install_line()
        (version,) = re.findall(r"v=(v\d+\.\d+\.\d+);", line)
        self.assertEqual(line, shim.install_line(version))
        self.assertIn(shim.INSTALL_LINE, CONTRACT.read_text())
        # Release Please's generic updater bumps every version in the block.
        readme = README.read_text()
        start, end = readme.index(START), readme.index(END)
        bumped = (
            readme[:start]
            + re.sub(r"\d+\.\d+\.\d+", "0.42.0", readme[start:end])
            + readme[end:]
        )
        self.assertEqual(readme_install_line(bumped), shim.install_line("v0.42.0"))
        marker = re.compile(
            r"^(.*)\d+\.\d+\.\d+(.*# x-release-please-version)$", re.MULTILINE
        )
        self.assertEqual(len(marker.findall(SHIM.read_text())), 1)

    def test_fresh_install_reports_the_release_version(self) -> None:
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"installed ballast {self.TAG} at {self.target}", result.stdout)
        self.assertEqual(self.version_of(self.target), self.TAG)
        released = (self.releases / self.TAG / "ballast").read_bytes()
        self.assertEqual(self.target.read_bytes(), released)
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o755)
        again = self.install()
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertIn(f"ballast {self.TAG} is already installed", again.stdout)

    def test_path_hint_and_caller_path(self) -> None:
        result = self.install()
        self.assertIn(f'export PATH="{self.bin}:$PATH"', result.stdout)
        self.assertIn("AFTER=/usr/bin:/bin\n", result.stdout)
        on_path = f"{self.bin}:/usr/bin:/bin"
        result = self.install(PATH=on_path)
        self.assertNotIn("export PATH", result.stdout)
        self.assertIn(f"AFTER={on_path}\n", result.stdout)

    def test_failures_leave_the_previous_install(self) -> None:
        self.publish("v1.0.0")
        self.assertEqual(self.install("v1.0.0").returncode, 0)
        before = self.target.read_bytes()
        good = release_build(self.TAG[1:])
        other = b"something else\n"
        cases = {
            "corrupted": good + b"# tampered\n",
            "truncated": good[: len(good) // 2],
        }
        for name, content in cases.items():
            with self.subTest(name):
                release = self.publish(self.TAG)
                (release / "ballast").write_bytes(content)
                result = self.install()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(f"checksum mismatch for {self.TAG}", result.stderr)
                self.assert_unchanged(before, "v1.0.0")
        with self.subTest("checksum of another file"):
            release = self.publish(self.TAG)
            checksum = hashlib.sha256(other).hexdigest()
            (release / "ballast.sha256").write_text(f"{checksum}  other\n")
            result = self.install()
            self.assertIn("checksum mismatch", result.stderr)
            self.assert_unchanged(before, "v1.0.0")
        with self.subTest("unknown version"):
            result = self.install("v7.7.7")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "ballast: cannot download v7.7.7 from "
                f"{self.releases.as_uri()}/v7.7.7; nothing installed",
                result.stderr,
            )
            self.assert_unchanged(before, "v1.0.0")

    def test_upgrade_names_both_versions(self) -> None:
        self.bin.mkdir(parents=True)
        self.target.write_bytes(release_build("0.1.0", drop_version=True))
        self.target.chmod(0o755)
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            f"replaced ballast (previous version unknown) with {self.TAG}",
            result.stdout,
        )
        self.publish("v10.0.0")
        result = self.install("v10.0.0")
        self.assertIn(f"replaced ballast {self.TAG} with v10.0.0", result.stdout)
        self.assertEqual(self.version_of(self.target), "v10.0.0")

    def test_foreign_target_is_refused_without_force(self) -> None:
        self.bin.mkdir(parents=True)
        self.target.write_text("#!/bin/sh\necho other tool\n")
        self.target.chmod(0o755)
        before = self.target.read_bytes()
        result = self.install()
        self.assertEqual(result.returncode, 2)
        self.assertIn(
            f"{self.target} is not a Ballast command; rerun with --force", result.stderr
        )
        self.assertEqual(self.target.read_bytes(), before)
        released = self.releases / self.TAG / "ballast"
        forced = subprocess.run(  # noqa: S603
            ["/usr/bin/python3", "-I", "-S", str(released), "self-install", "--force"],
            env=self.env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(forced.returncode, 0, forced.stderr)
        self.assertEqual(self.target.read_bytes(), released.read_bytes())
        self.target.unlink()
        self.target.mkdir()
        self.assertEqual(self.install().returncode, 2)
        self.assertTrue(self.target.is_dir())

    def test_symlinked_target_is_never_kept(self) -> None:
        checkout = self.base / "checkout"
        (checkout / ".git").mkdir(parents=True)
        released = self.releases / self.TAG / "ballast"
        same = checkout / "ballast"
        same.write_bytes(released.read_bytes())
        same.chmod(0o755)
        self.bin.mkdir(parents=True)
        self.target.symlink_to(same)
        result = self.install()
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn(f"{self.target} is not a Ballast command", result.stderr)
        self.assertTrue(self.target.is_symlink())
        forced = subprocess.run(  # noqa: S603
            ["/usr/bin/python3", "-I", "-S", str(released), "self-install", "--force"],
            env=self.env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(forced.returncode, 0, forced.stderr)
        self.assertFalse(self.target.is_symlink())
        self.assertEqual(self.target.read_bytes(), released.read_bytes())
        self.assertEqual(same.read_bytes(), released.read_bytes())

    def test_io_failures_change_nothing(self) -> None:
        self.bin.mkdir(parents=True)
        self.target.write_bytes(release_build("1.0.0"))
        before = self.target.read_bytes()
        failures = {
            "rename": patch.object(os, "replace", side_effect=OSError("disk full")),
            "verification": patch.object(shim, "digest", return_value="0" * 64),
        }
        for name, failure in failures.items():
            with self.subTest(name):
                stderr = io.StringIO()
                with failure, redirect_stderr(stderr), redirect_stdout(io.StringIO()):
                    code = shim.self_install(["--dir", str(self.bin)])
                self.assertEqual(code, 1)
                self.assertIn("ballast: cannot install:", stderr.getvalue())
                self.assertEqual(self.target.read_bytes(), before)
                self.assertEqual([p.name for p in self.bin.iterdir()], ["ballast"])

    def test_nothing_is_read_or_run_from_the_checkout(self) -> None:
        checkout = self.base / "checkout"
        sentinels = self.base / "sentinels"
        sentinels.mkdir()
        subprocess.run(["git", "init", "-q", str(checkout)], check=True)  # noqa: S603, S607
        planted = {
            "tools/ballast": "python",
            "sitecustomize.py": "python",
            "bin/curl": "shell",
            "bin/sha256sum": "shell",
            "bin/python3": "shell",
        }
        for relative, kind in planted.items():
            path = checkout / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            sentinel = sentinels / path.name
            if kind == "python":
                path.write_text(f"open({str(sentinel)!r}, 'w').write('ran')\n")
            else:
                # A shadow sha256sum that always "succeeds".
                path.write_text(f"#!/bin/sh\ntouch {sentinel}\necho 0  ballast\n")
            path.chmod(0o755)
        (checkout / "tmp").mkdir()
        # A curl configuration in the checkout is never read (`curl -q`).
        (checkout / ".curlrc").write_text(f"trace-ascii = {sentinels / 'curlrc'}\n")
        env = {
            "PATH": f"{checkout / 'bin'}:/usr/bin:/bin",
            "TMPDIR": str(checkout / "tmp"),
            "PYTHONPATH": str(checkout),
            "CURL_HOME": str(checkout),
            "XDG_CONFIG_HOME": str(checkout),
        }
        result = self.install(cwd=checkout, **env)
        self.assertEqual(result.returncode, 0, result.stderr)
        released = (self.releases / self.TAG / "ballast").read_bytes()
        self.assertEqual(self.target.read_bytes(), released)
        before = self.target.read_bytes()
        release = self.publish(self.TAG)
        (release / "ballast").write_bytes(released + b"# tampered\n")
        result = self.install(cwd=checkout, **env)
        self.assertIn("checksum mismatch", result.stderr)
        self.assertEqual(self.target.read_bytes(), before)
        self.assertEqual(list(sentinels.iterdir()), [])
        self.assertEqual(list((checkout / "tmp").iterdir()), [])
        # An install directory that resolves into a working tree is refused.
        link = self.base / "linked-bin"
        link.symlink_to(checkout / "tmp")
        refused = subprocess.run(  # noqa: S603
            [
                "/usr/bin/python3",
                "-I",
                "-S",
                str(self.publish(self.TAG) / "ballast"),
                "self-install",
                "--dir",
                str(link),
            ],
            env=self.env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(refused.returncode, 2)
        self.assertIn("inside a Git working tree", refused.stderr)
        self.assertEqual(list((checkout / "tmp").iterdir()), [])


class CompatibilityTests(unittest.TestCase):
    """A project pinning a version without tools/cli.toml works as before (FR-019)."""

    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        base = Path(self.directory.name)
        self.project = base / "project"
        workflow = self.project / ".ballast/spec_workflow"
        shutil.copytree(ROOT / "tools/spec_workflow", workflow)
        subprocess.run(["git", "init", "-q", str(self.project)], check=True)  # noqa: S603, S607
        (self.project / "ballast.toml").write_text('[standard]\nref = "v0.1.0"\n')
        standard = base / "data/ballast/standard/v0.1.0"
        shutil.copytree(ROOT / "tools", standard / "tools")
        (standard / "tools/cli.toml").unlink()
        (standard / "tools/setup").write_text(
            "import sys; print('setup', *sys.argv[1:], "
            "sys.flags.isolated, sys.flags.no_site)\n"
        )
        self.env = {
            **os.environ,
            "XDG_DATA_HOME": str(base / "data"),
            "XDG_STATE_HOME": str(base / "state"),
        }
        self.env.pop("BALLAST_STANDARD_DIR", None)

    def tearDown(self) -> None:
        self.directory.cleanup()

    def ballast(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(  # noqa: S603
            [str(SHIM), *args],
            cwd=self.project,
            env=self.env,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_commands_behave_as_before(self) -> None:
        setup = self.ballast("setup", "--extra")
        self.assertEqual(
            (setup.returncode, setup.stdout),
            (0, f"setup --project {self.project} --extra 1 1\n"),
        )
        refused = self.ballast("run", "start")
        self.assertEqual(refused.returncode, 2)
        self.assertEqual(
            refused.stderr,
            "ballast: refusing: no trusted baseline; review the checkout, "
            "then run `trust`\n",
        )
        trusted = self.ballast("trust")
        self.assertEqual(trusted.returncode, 0, trusted.stderr)
        self.assertRegex(
            trusted.stdout, rf"^trusted \d+ workflow inputs for {self.project}\n$"
        )
        report = self.ballast("ledger", "report", "--all")
        self.assertEqual(report.returncode, 0, report.stderr)

    def test_failure_messages_only_gain_the_doctor_hint(self) -> None:
        (self.project / "ballast.toml").write_text('[standard]\nref = "v9.9.9"\n')
        self.assertEqual(
            self.ballast("trust").stderr,
            "ballast: standard v9.9.9 is not fetched; run `ballast setup`"
            f"{DOCTOR_HINT}\n",
        )
        (self.project / "ballast.toml").write_text("[standard\n")
        stderr = self.ballast("trust").stderr
        self.assertTrue(stderr.startswith("ballast: cannot read ballast.toml: "))
        self.assertTrue(stderr.endswith(DOCTOR_HINT + "\n"))
        (self.project / "ballast.toml").write_text('[standard]\nref = "v0.1.0"\n')
        launcher = Path(self.env["XDG_DATA_HOME"]) / "ballast/standard/v0.1.0/tools"
        (launcher / "spec_workflow/launcher.py").unlink()
        self.assertEqual(
            self.ballast("trust").stderr,
            f"ballast: {launcher.parent} has no launcher{DOCTOR_HINT}\n",
        )


if __name__ == "__main__":
    unittest.main()
