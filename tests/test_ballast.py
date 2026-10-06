"""Offline checks for the global ballast shim."""

from __future__ import annotations

import ast
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time
import types
import unittest
import uuid
from contextlib import redirect_stderr, redirect_stdout, suppress
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(ROOT / "tests"))
from test_autonomy import operator_state, outside_temp  # noqa: E402

sys.path.pop(0)
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
        self.directory = TemporaryDirectory(dir=outside_temp())
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

    def test_standard_in_a_temp_directory_is_refused(self) -> None:
        # An agent could rewrite the launcher there (#34).
        self.pin("v0.1.0")
        with TemporaryDirectory() as temp:
            for command in ("run", "setup"):
                result = subprocess.run(  # noqa: S603
                    [sys.executable, str(SHIM), command],
                    cwd=self.project,
                    env={**self.env, "XDG_DATA_HOME": temp},
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("which agents can write", result.stderr)
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_temp_roots_match_the_launcher(self) -> None:
        sys.path.insert(0, str(ROOT / "tools/spec_workflow"))
        try:
            import launcher  # noqa: PLC0415
        finally:
            sys.path.pop(0)
        self.assertEqual(shim.TEMP_ROOTS, launcher.TEMP_ROOTS)
        self.assertEqual(shim.REF.pattern, launcher.REF.pattern)

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
        (planted.parent / "run.py").write_text("print('planted')\n")
        self.pin("v0.1.0")
        result = self.shim("run", "start")
        self.assertEqual(result.stdout, "launcher run start\n", result.stderr)
        # #15 AC-007: a version that cannot prepare refuses an uninstalled
        # checkout before its launcher, naming setup.
        shutil.rmtree(self.project / ".ballast")
        for command in ("run", "ledger", "intake"):
            result = self.shim(command, "x")
            self.assertEqual(
                (result.returncode, result.stdout, result.stderr),
                (
                    2,
                    "",
                    (
                        "ballast: refusing: nothing is installed in this checkout; run "
                        "`ballast setup`\n"
                    ),
                ),
            )
        self.assertFalse((self.project / ".ballast").exists())


class NotFetchedTests(ShimTests):
    """An unfetched pin names the installed version and both recoveries (AC-008)."""

    def record(self, ref: str, stamp: str) -> None:
        sys.path.insert(0, str(ROOT / "tools/spec_workflow"))
        try:
            import launcher  # noqa: PLC0415
        finally:
            sys.path.pop(0)
        self.env["XDG_STATE_HOME"] = str(operator_state(self))
        with patch.dict(os.environ, {"XDG_STATE_HOME": self.env["XDG_STATE_HOME"]}):
            state = launcher.state_dir(self.project)
        state.mkdir(parents=True)
        record = {"schema": 1, "ref": ref, "fingerprint": "fp", "files": {}}
        (state / "installation.json").write_text(json.dumps(record))
        (self.project / ".ballast").mkdir()
        (self.project / ".ballast/.setup-version").write_text(stamp + "\n")

    def test_installed_version_is_named(self) -> None:
        self.pin("v0.2.0")
        self.record("v0.1.0", "fp")
        self.assertEqual(
            self.shim("run", "start").stderr,
            "ballast: standard v0.2.0 is not fetched; run `ballast setup`; "
            'installed v0.1.0, pinned v0.2.0: restore ref = "v0.1.0" in '
            f"ballast.toml, or fix the cause and rerun `ballast setup`{DOCTOR_HINT}\n",
        )

    def test_stale_record_is_not_named(self) -> None:
        # F-003: an older setup rewrote the stamp after this record.
        self.pin("v0.2.0")
        self.record("v0.1.0", "older")
        self.assertEqual(
            self.shim("run", "start").stderr,
            "ballast: standard v0.2.0 is not fetched; run `ballast setup`"
            f"{DOCTOR_HINT}\n",
        )


def standard_archive(path: Path, ref: str, files: dict[str, bytes]) -> Path:
    """Write a GitHub-style archive of a standard version."""
    with tarfile.open(path, "w:gz") as contents:
        for name, data in files.items():
            info = tarfile.TarInfo(f"ballast-{ref}/{name}")
            info.size = len(data)
            info.mode = 0o755 if name.endswith("setup") else 0o644
            contents.addfile(info, io.BytesIO(data))
    return path


# Fetches one ref in a child process with a counted, slow download.
FETCHER = """\
import os, sys, time, urllib.request
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
loader = SourceFileLoader("ballast", sys.argv[1])
shim = module_from_spec(spec_from_loader("ballast", loader))
loader.exec_module(shim)
shim.ARCHIVE = sys.argv[2]
retrieve = urllib.request.urlretrieve
def counted(url, path):
    with open(sys.argv[3], "a") as count:
        count.write("download\\n")
    time.sleep(float(sys.argv[5]))
    return retrieve(url, path)
urllib.request.urlretrieve = counted
from pathlib import Path
shim.ensure_standard(Path.cwd(), sys.argv[4])
"""


class CacheTests(unittest.TestCase):
    """Each cached version is complete, recorded and verified (US2)."""

    REF = "v0.6.0"
    FILES: dict[str, bytes] = {  # noqa: RUF012
        "tools/setup": b"print('setup')\n",
        "tools/cli.toml": b"[cli]\nminimum = '0.1.0'\n",
        "templates/policies/a.md": b"policy\n",
    }

    def setUp(self) -> None:
        directory = TemporaryDirectory(dir=outside_temp())
        self.addCleanup(directory.cleanup)
        self.base = Path(directory.name)
        self.project = self.base / "project"
        self.project.mkdir()
        self.archive = standard_archive(self.base / "a.tar.gz", self.REF, self.FILES)
        self.count = self.base / "downloads"
        self.cache = self.base / "data/ballast/standard"
        for patcher in (
            patch.dict(os.environ, {"XDG_DATA_HOME": str(self.base / "data")}),
            patch.object(shim, "ARCHIVE", self.archive.as_uri()),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def ensure(self) -> tuple[int, str]:
        stderr = io.StringIO()
        try:
            with redirect_stderr(stderr):
                shim.ensure_standard(self.project, self.REF)
        except SystemExit as error:
            if isinstance(error.code, str):
                return 1, stderr.getvalue() + error.code
            return error.code, stderr.getvalue()
        return 0, stderr.getvalue()

    def leftovers(self) -> list[str]:
        if not self.cache.is_dir():
            return []
        return sorted(
            p.name
            for p in self.cache.iterdir()
            if p.name.startswith(".") and p.name != ".locks"
        )

    def test_fetch_publishes_the_tree_with_its_record(self) -> None:
        self.assertEqual(self.ensure(), (0, ""))
        tree = self.cache / self.REF
        record = json.loads((tree / shim.CACHE_RECORD).read_text())
        self.assertEqual(record["ref"], self.REF)
        self.assertEqual(
            record["files"]["tools/setup"],
            {
                "sha256": hashlib.sha256(self.FILES["tools/setup"]).hexdigest(),
                "exec": True,
            },
        )
        self.assertEqual(sorted(record["files"]), sorted(self.FILES))
        self.assertIsNone(shim.damage(tree))
        self.assertEqual(self.leftovers(), [])
        # A verified copy is used again without a download (AC-012, AC-022).
        with patch.object(shim, "ARCHIVE", (self.base / "absent.tar.gz").as_uri()):
            self.assertEqual(self.ensure(), (0, ""))

    def test_failed_download_leaves_nothing(self) -> None:
        # AC-001: no partial copy in the cache.
        truncated = self.base / "truncated.tar.gz"
        truncated.write_bytes(self.archive.read_bytes()[:40])
        for url in ((self.base / "absent.tar.gz").as_uri(), truncated.as_uri()):
            with self.subTest(url=url), patch.object(shim, "ARCHIVE", url):
                code, message = self.ensure()
                self.assertEqual(code, 1)
                self.assertIn(f"cannot fetch standard {self.REF}: ", message)
                self.assertIn(
                    "the cache and the checkout are unchanged. Next: check network "
                    "access (`ballast doctor`), then rerun the command",
                    message,
                )
                self.assertFalse((self.cache / self.REF).exists())
                self.assertEqual(self.leftovers(), [])

    def test_damage_is_detected_and_refetched(self) -> None:
        # AC-013, SC-005: a missing, added or altered file, or no record.
        damages = {
            "tools/setup": lambda tree: (tree / "tools/setup").unlink(),
            "tools/extra.py": lambda tree: (tree / "tools/extra.py").write_text("x"),
            "templates/policies/a.md": lambda tree: (
                tree / "templates/policies/a.md"
            ).write_text("edited\n"),
            "tools/cli.toml": lambda tree: (tree / "tools/cli.toml").chmod(0o755),
            shim.CACHE_RECORD: lambda tree: (tree / shim.CACHE_RECORD).unlink(),
        }
        for path, damage in damages.items():
            with self.subTest(path=path):
                self.assertEqual(self.ensure()[0], 0)
                tree = self.cache / self.REF
                damage(tree)
                self.assertEqual(shim.damage(tree), path)
                code, message = self.ensure()
                self.assertEqual(code, 0, message)
                self.assertIn(
                    f"the cached standard {self.REF} was damaged ({path}); "
                    "fetched it again",
                    message,
                )
                self.assertIsNone(shim.damage(tree))
                self.assertEqual(self.leftovers(), [])
        (self.cache / self.REF / "tools/setup").write_text("edited\n")
        with patch.object(shim, "ARCHIVE", (self.base / "absent.tar.gz").as_uri()):
            code, message = self.ensure()
        self.assertEqual(code, 2)
        self.assertIn(
            f"the cached standard {self.REF} is damaged at tools/setup and could "
            "not be fetched again: ",
            message,
        )

    def fetcher(self, delay: float) -> subprocess.Popen[bytes]:
        process = subprocess.Popen(  # noqa: S603
            [
                sys.executable,
                "-c",
                FETCHER,
                *(str(SHIM), self.archive.as_uri(), str(self.count), self.REF),
                str(delay),
            ],
            cwd=self.project,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        self.addCleanup(process.wait)
        self.addCleanup(process.kill)
        return process

    def test_concurrent_fetches_download_once(self) -> None:
        # AC-010, SC-004: 20 races between two fetches of one version.
        for _ in range(20):
            shutil.rmtree(self.cache, ignore_errors=True)
            self.count.unlink(missing_ok=True)
            first, second = self.fetcher(0.2), self.fetcher(0.2)
            for process in (first, second):
                _, stderr = process.communicate(timeout=60)
                self.assertEqual(process.returncode, 0, stderr)
            self.assertEqual(self.count.read_text().count("download"), 1)
            self.assertIsNone(shim.damage(self.cache / self.REF))
            self.assertEqual(self.leftovers(), [])

    def test_dead_fetch_holder_does_not_block(self) -> None:
        # AC-011
        holder = self.fetcher(60)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and not self.leftovers():
            time.sleep(0.05)
        self.assertTrue(self.leftovers())
        holder.kill()
        holder.communicate()
        self.assertEqual(self.ensure(), (0, ""))
        self.assertIsNone(shim.damage(self.cache / self.REF))
        self.assertEqual(self.leftovers(), [])


class ReadmeUpdateTests(unittest.TestCase):
    """The README documents the update, retry and rollback paths (AC-024)."""

    def test_update_section_uses_only_real_commands(self) -> None:
        text = README.read_text()
        self.assertIn("### Updating the pinned version", text)
        section = text.split("### Updating the pinned version", 1)[1]
        section = section.split("\n## ", 1)[0].split("\n### ", 1)[0]
        for topic in (
            "ballast preview",
            "ballast setup",
            "ballast trust",
            "**Retry after a failed update.**",
            "**Roll back to the previous pin.**",
        ):
            self.assertIn(topic, section)
        sys.path.insert(0, str(ROOT / "tools/spec_workflow"))
        try:
            import launcher  # noqa: PLC0415
        finally:
            sys.path.pop(0)
        accepted = set(re.findall(r"\bballast ([a-z][a-z-]*)", shim.__doc__ or ""))
        accepted |= {*launcher.COMMANDS, "intake", "trust", "discard-runs"}
        shown = set(re.findall(r"\bballast ([a-z][a-z-]*)", section))
        self.assertIn("preview", accepted)
        self.assertTrue(shown)
        self.assertLessEqual(shown, accepted)


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
        # The line downloads into a fresh /tmp/tmp.* it never removes. Every
        # release this test serves carries this marker, so tearDown removes
        # only its own downloads, never another suite's in-flight one (#36).
        self.marker = f"# install test {uuid.uuid4().hex}\n".encode()
        self.publish(self.TAG)

    def tearDown(self) -> None:
        for path in Path("/tmp").glob("tmp.*/ballast"):  # noqa: S108
            with suppress(OSError):
                if self.marker in path.read_bytes():
                    shutil.rmtree(path.parent)
        self.directory.cleanup()

    def build(self, version: str) -> bytes:
        """release_build, marked as this test's: the marker survives truncation."""
        shebang, rest = release_build(version).split(b"\n", 1)
        return shebang + b"\n" + self.marker + rest

    def publish(self, tag: str, content: bytes | None = None) -> Path:
        release = self.releases / tag
        release.mkdir(parents=True, exist_ok=True)
        content = self.build(tag[1:]) if content is None else content
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
        good = self.build(self.TAG[1:])
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
        with self.subTest("missing download"):
            # The first download succeeds, so tearDown finds the marked copy
            # (an empty /tmp/tmp.* is never attributable to this test).
            (self.publish("v7.7.7") / "ballast.sha256").unlink()
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
        self.directory = TemporaryDirectory(dir=outside_temp())
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
        record = shim.cache_record(standard, "v0.1.0")
        (standard / shim.CACHE_RECORD).write_text(json.dumps(record))
        self.env = {
            **os.environ,
            "XDG_DATA_HOME": str(base / "data"),
            "XDG_STATE_HOME": str(operator_state(self) / "state"),
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
            "ballast: refusing: no trusted baseline for this checkout; review its "
            "protected inputs (ballast.toml, .ballast/spec_workflow), then run "
            "`ballast trust`\n",
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


class CheckoutGitConfigTests(unittest.TestCase):
    """Checkout git config an agent can write never runs a program."""

    def test_fsmonitor_never_runs(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            marker = Path(directory) / "ran"
            program = Path(directory) / "program"
            program.write_text(f"#!/bin/sh\ntouch {marker}\n")
            program.chmod(0o755)
            subprocess.run(["git", "init", "-q", str(root)], check=True)  # noqa: S603, S607
            (root / "ballast.toml").write_text("")
            subprocess.run(["git", "add", "ballast.toml"], cwd=root, check=True)  # noqa: S607
            subprocess.run(  # noqa: S603
                ["git", "config", "core.fsmonitor", str(program)],  # noqa: S607
                cwd=root,
                check=True,
            )
            self.assertEqual(shim.git_output(root, "ls-files"), "ballast.toml\n")
            self.assertFalse(marker.exists(), "core.fsmonitor ran a program")

    def test_every_git_call_is_hardened(self) -> None:
        for flag in ("--no-pager", "core.fsmonitor=false", "core.hooksPath=/dev/null"):
            self.assertIn(flag, shim.GIT)
        bare = [
            node.lineno
            for node in ast.walk(ast.parse(SHIM.read_text()))
            if isinstance(node, ast.List)
            and node.elts
            and isinstance(node.elts[0], ast.Constant)
            and node.elts[0].value == "git"
        ]
        self.assertEqual(bare, [], "git calls must start with *GIT")


# --- Preparing a new worktree (#15) ------------------------------------------

sys.path.insert(0, str(ROOT / "tests"))
import test_setup as setup_tests  # noqa: E402

sys.path.pop(0)
NOT_INSTALLED = (
    "ballast: refusing: nothing is installed in this checkout; run `ballast setup`, "
    "or `ballast run`, `ledger` or `intake` to prepare it from a verified "
    "installation on this machine\n"
)
NO_BASELINE = (
    "ballast: refusing: no trusted baseline for this checkout; review its protected "
    "inputs (ballast.toml, .ballast/spec_workflow, .specify, .git), then run "
    "`ballast trust`\n"
)


class PrepareTriggerTests(unittest.TestCase):
    """The first run, ledger or intake in a new worktree prepares it (#15)."""

    def setUp(self) -> None:
        directory = TemporaryDirectory(dir=outside_temp())
        self.addCleanup(directory.cleanup)
        self.base = Path(directory.name)
        self.data = self.base / "data"
        self.standard = self.data / "ballast/standard/vA"
        for part in ("tools", "templates"):
            shutil.copytree(
                ROOT / part,
                self.standard / part,
                symlinks=True,
                ignore=shutil.ignore_patterns("__pycache__"),
            )
        self.record_cache()
        state = operator_state(self)
        environment = patch.dict(
            os.environ, {"XDG_STATE_HOME": str(state), "XDG_DATA_HOME": str(self.data)}
        )
        environment.start()
        self.addCleanup(environment.stop)
        # Only git and python on PATH: no uvx, and any request fails fast.
        tools = self.base / "bin"
        tools.mkdir()
        for name in ("git", "python3"):
            (tools / name).symlink_to(shutil.which(name))
        proxy = "http://127.0.0.1:9"
        self.env = {
            **os.environ,
            "PATH": str(tools),
            "http_proxy": proxy,
            "https_proxy": proxy,
        }
        self.env.pop("BALLAST_STANDARD_DIR", None)
        self.primary = self.base / "project"
        self.primary.mkdir()
        setup_tests.git(self.primary, "init", "-q")
        files = {
            ".gitignore": setup_tests.setup.GITIGNORE,
            "ballast.toml": setup_tests.PIN.format("vA"),
            ".specify/memory/constitution.md": "project constitution\n",
            "docs/policies/project/security.md": "project rule\n",
        }
        for name, text in files.items():
            (self.primary / name).parent.mkdir(parents=True, exist_ok=True)
            (self.primary / name).write_text(text)
        out = io.StringIO()
        with setup_tests.fakes(), redirect_stdout(out):
            code = setup_tests.setup.cli(["--project", str(self.primary)])
        self.assertEqual(code, 0, out.getvalue())
        setup_tests.git(self.primary, "add", "-A")
        setup_tests.git(self.primary, "commit", "-q", "-m", "project")
        self.count = 0

    def record_cache(self) -> None:
        record = shim.cache_record(self.standard, "vA")
        (self.standard / shim.CACHE_RECORD).write_text(json.dumps(record))

    def worktree(self) -> Path:
        self.count += 1
        path = self.base / f"worktree-{self.count}"
        setup_tests.git(self.primary, "worktree", "add", "-q", "--detach", str(path))
        return path

    def ballast(self, root: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(  # noqa: S603
            [str(SHIM), *args],
            cwd=root,
            env=self.env,
            capture_output=True,
            text=True,
            check=False,
        )

    def state(self, root: Path) -> Path:
        return shim.operator_state(root)

    def everything(self, root: Path) -> dict[str, dict[str, str]]:
        return {
            "checkout": setup_tests.tree(root, (".git",)),
            "state": setup_tests.tree(self.state(root)),
            "data": setup_tests.tree(self.data),
        }

    def test_run_prepares_then_reaches_preflight(self) -> None:
        # AC-001, AC-002, SC-001: one command, no setup, no download.
        prepared = setup_tests.PREPARED.format(ref="vA", source=self.primary)
        cached = setup_tests.tree(self.data)
        for args in (("run", "start"), ("ledger", "report", "--all"), ("intake",)):
            with self.subTest(command=args[0]):
                worktree = self.worktree()
                result = self.ballast(worktree, *args)
                self.assertEqual(
                    (result.returncode, result.stdout, result.stderr),
                    (2, prepared, NO_BASELINE),
                )
                self.assertFalse((self.state(worktree) / "trusted.json").exists())
                record = json.loads(
                    (self.state(worktree) / "installation.json").read_text()
                )
                primary = json.loads(
                    (self.state(self.primary) / "installation.json").read_text()
                )
                self.assertEqual(record["files"], primary["files"])
                self.assertEqual(setup_tests.tree(self.data), cached)

    def test_doctor_trust_then_run(self) -> None:
        # AC-004: doctor sees a current installation; trust, then the run passes.
        worktree = self.worktree()
        self.assertEqual(
            self.ballast(worktree, "ledger", "report", "--all").returncode, 2
        )
        record = (self.state(worktree) / "installation.json").read_text()
        context = shim.context_for(worktree)
        self.assertEqual(
            shim._setup_current(context, {"setup-check"}),  # noqa: SLF001
            ("passing", "setup is current"),
        )
        status, detail, remedy = shim._trust(context, {"launcher-status"})  # noqa: SLF001
        self.assertEqual((status, remedy), ("missing", shim.TRUST))
        self.assertIn("launcher will refuse: no trusted baseline", detail)
        trusted = self.ballast(worktree, "trust")
        self.assertEqual(trusted.returncode, 0, trusted.stderr)
        report = self.ballast(worktree, "ledger", "report", "--all")
        self.assertEqual(report.returncode, 0, report.stderr)
        self.assertNotIn("Prepared", report.stdout)
        self.assertFalse((self.state(worktree) / "setup-attempt.json").exists())
        self.assertEqual(
            (self.state(worktree) / "installation.json").read_text(), record
        )

    def test_non_preparing_commands(self) -> None:
        # AC-005: trust and discard-runs refuse; status and doctor only read.
        worktree = self.worktree()
        before = self.everything(worktree)
        for command in ("trust", "discard-runs"):
            result = self.ballast(worktree, command)
            self.assertEqual(
                (result.returncode, result.stdout, result.stderr),
                (2, "", NOT_INSTALLED),
            )
        status = self.ballast(worktree, "status", "--json")
        self.assertEqual(
            json.loads(status.stdout), {"installed": False, "refusal": None}
        )
        context = shim.context_for(worktree)
        self.assertEqual(
            shim._trust(context, {"launcher-status"})[2],  # noqa: SLF001
            "ballast setup, or the first `ballast run`, `ledger` or `intake`, which "
            "prepares it from a verified installation on this machine",
        )
        self.assertEqual(self.everything(worktree), before)
        self.assertFalse(self.state(worktree).exists())

    def test_version_without_declaration(self) -> None:
        # AC-007: no `[setup] prepare` → today's refusal naming setup.
        manifest = self.standard / "tools/cli.toml"
        manifest.write_text(manifest.read_text().replace("prepare = true\n", ""))
        self.record_cache()
        worktree = self.worktree()
        before = self.everything(worktree)
        result = self.ballast(worktree, "run", "start")
        self.assertEqual(
            (result.returncode, result.stdout, result.stderr),
            (
                2,
                "",
                (
                    "ballast: refusing: nothing is installed in this checkout; run "
                    "`ballast setup`\n"
                ),
            ),
        )
        self.assertEqual(self.everything(worktree), before)
        # An installed checkout with only a journal left reaches the launcher.
        installed = self.worktree()
        with setup_tests.fakes(), redirect_stdout(io.StringIO()):
            setup_tests.setup.cli(["--project", str(installed)])
        (self.state(installed) / "setup-attempt.json").write_text("{}\n")
        result = self.ballast(installed, "run", "start")
        self.assertEqual(
            (result.returncode, result.stdout, result.stderr),
            (
                2,
                "",
                (
                    "ballast: refusing: setup did not finish in this checkout; run "
                    "`ballast setup` to recover\n"
                ),
            ),
        )

    def test_damaged_standard_refuses(self) -> None:
        # AC-013
        policy = self.standard / "templates/policies/workflow.md"
        policy.write_text(policy.read_text() + "altered\n")
        worktree = self.worktree()
        before = self.everything(worktree)
        result = self.ballast(worktree, "run", "start")
        self.assertEqual(
            (result.returncode, result.stdout, result.stderr),
            (
                2,
                "",
                (
                    "ballast: refusing: the cached standard vA is damaged at "
                    "templates/policies/workflow.md; run `ballast setup` to fetch it "
                    "again\n"
                ),
            ),
        )
        self.assertEqual(self.everything(worktree), before)
        self.assertFalse(self.state(worktree).exists())


if __name__ == "__main__":
    unittest.main()
