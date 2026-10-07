"""Offline checks for `ballast doctor`: every check, the project probes, read-only.

Missing prerequisites are simulated with a controlled PATH of stub executables.
Every doctor run is wrapped in a before/after digest snapshot of the project,
XDG_DATA_HOME, XDG_STATE_HOME and ~/.local/bin (AC-012).
"""

from __future__ import annotations

import contextlib
import hashlib
import http.server
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
import urllib.error
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import ClassVar
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SHIM = ROOT / "tools/ballast"
SCHEMA = ROOT / "specs/12-cli-install-doctor/contracts/doctor-report.schema.json"

sys.path.insert(0, str(ROOT / "tests"))
from test_autonomy import operator_state, outside_temp  # noqa: E402

sys.path.pop(0)
_loader = SourceFileLoader("ballast_doctor", str(SHIM))
shim = module_from_spec(spec_from_loader("ballast_doctor", _loader))
_loader.exec_module(shim)

STUBS = ("git", "uvx", "patch", "systemctl", "systemd-run", "specify")
STUBS += ("claude", "codex", "gh")
MACHINE = [name for name, *_ in shim.MACHINE_CHECKS]
PROJECT = list(shim.PROJECT_GATES)
TOKEN = "ghp_FAKEtoken0123456789"  # noqa: S105 - a fake, token-shaped string


def snapshot(*roots: Path) -> dict[str, str]:
    """Every path under the roots with its content digest or link target."""
    found = {}
    for root in roots:
        if not os.path.lexists(root):
            found[str(root)] = "absent"
            continue
        for path in [root, *root.rglob("*")]:
            if path.is_symlink():
                found[str(path)] = "link:" + str(path.readlink())
            elif path.is_dir():
                found[str(path)] = "dir"
            else:
                found[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return found


KINDS = {"object": dict, "array": list, "string": str, "boolean": bool}
KINDS["null"] = type(None)


def _scalar_errors(value: object, schema: dict, where: str) -> list[str]:
    errors = []
    if "const" in schema and value != schema["const"]:
        errors.append(f"{where}: {value!r} != {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{where}: {value!r} not in enum")
    if "pattern" in schema and not re.search(schema["pattern"], value):
        errors.append(f"{where}: {value!r} does not match {schema['pattern']}")
    if "minLength" in schema and len(value) < schema["minLength"]:
        errors.append(f"{where}: too short")
    return errors


def validate(value: object, schema: dict, where: str = "$") -> list[str]:
    """Check the JSON Schema subset doctor-report.schema.json uses."""
    if "type" in schema:
        allowed = schema["type"]
        allowed = allowed if isinstance(allowed, list) else [allowed]
        if not any(isinstance(value, KINDS[kind]) for kind in allowed):
            return [f"{where}: {value!r} is not {allowed}"]
    errors = _scalar_errors(value, schema, where)
    if isinstance(value, dict):
        errors += [
            f"{where}: missing {k}"
            for k in schema.get("required", [])
            if k not in value
        ]
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            errors += [f"{where}: extra {k}" for k in value if k not in properties]
        for key, sub in properties.items():
            if key in value:
                errors += validate(value[key], sub, f"{where}.{key}")
    if isinstance(value, list) and "items" in schema:
        errors += [
            error
            for index, item in enumerate(value)
            for error in validate(item, schema["items"], f"{where}[{index}]")
        ]
    rules = schema.get("allOf", [])
    errors += [
        error
        for rule in rules
        if not validate(value, rule["if"], where)
        for error in validate(value, rule["then"], where)
    ]
    return errors


class FakeOpener:
    """Stands in for the HEAD-only opener and records each request's method."""

    def __init__(self) -> None:
        """Answer every request until told to fail."""
        self.methods: list[str] = []
        self.fail = False
        self.status: int | None = None

    def open(self, request: object, timeout: float) -> io.BytesIO:  # noqa: ARG002
        self.methods.append(request.get_method())
        if self.fail:
            reason = "network is unreachable"
            raise urllib.error.URLError(reason)
        if self.status is not None:
            url = request.full_url
            raise urllib.error.HTTPError(url, self.status, "status", {}, None)
        return io.BytesIO()


class DoctorCase(unittest.TestCase):
    """A home, a stub bin directory, data and state directories and a project."""

    def setUp(self) -> None:
        self.directory = TemporaryDirectory(dir=outside_temp())
        self.base = Path(self.directory.name)
        self.home = self.base / "home"
        self.local_bin = self.home / ".local/bin"
        self.local_bin.mkdir(parents=True)
        shutil.copy2(SHIM, self.local_bin / "ballast")
        self.bin = self.base / "bin"
        self.bin.mkdir()
        for name in STUBS:
            self.stub(name)
        self.stub("git", 'echo "git version 2.43.0"')
        self.data = self.base / "data"
        # Not yet created: doctor must not write it.
        self.state = operator_state(self) / "state"
        self.project = self.base / "project"
        self.project.mkdir()
        self.sentinel = self.base / "executed"
        self.env = {
            "HOME": str(self.home),
            "PATH": f"{self.bin}{os.pathsep}{self.local_bin}",
            "XDG_DATA_HOME": str(self.data),
            "XDG_STATE_HOME": str(self.state),
            "LANG": "C.UTF-8",
        }
        self.python = shim.PYTHON
        self.platform = "linux"
        self.opener = FakeOpener()
        self.tmp = self.base / "tmp"
        self.tmp.mkdir()
        self.env["TMPDIR"] = str(self.tmp)

    def tearDown(self) -> None:
        self.directory.cleanup()

    def fresh(self) -> None:
        """Start again from every prerequisite present."""
        self.tearDown()
        self.setUp()

    def stub(self, name: str, body: str = "exit 0", where: Path | None = None) -> Path:
        path = (where or self.bin) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"#!/bin/sh\n{body}\n")
        path.chmod(0o755)
        return path

    def pin(self, ref: str = "v0.1.0") -> None:
        (self.project / "ballast.toml").write_text(f'[standard]\nref = "{ref}"\n')

    def roots(self) -> tuple[Path, ...]:
        return (self.project, self.data, self.state, self.home, self.tmp)

    def doctor(self, *args: str, cwd: Path | None = None) -> tuple[int, str]:
        """Run doctor in-process; assert it wrote nothing anywhere."""
        before = snapshot(*self.roots())
        output = io.StringIO()
        with (
            patch.dict(os.environ, self.env, clear=True),
            patch.object(shim, "PYTHON", self.python),
            patch.object(sys, "platform", self.platform),
            patch.object(shim, "_OPENER", self.opener),
            patch.object(tempfile, "tempdir", str(self.tmp)),
            contextlib.chdir(cwd or self.project),
            contextlib.redirect_stdout(output),
        ):
            try:
                code = shim.main(["doctor", *args])
            except SystemExit as error:
                code = error.code
        self.assertEqual(snapshot(*self.roots()), before)
        self.assertFalse(self.sentinel.exists(), "doctor executed a planted file")
        return code, output.getvalue()

    def report(self, cwd: Path | None = None) -> tuple[int, dict]:
        code, output = self.doctor("--json", cwd=cwd)
        report = json.loads(output)
        self.assertEqual(validate(report, json.loads(SCHEMA.read_text())), [])
        return code, report

    def checks(self, cwd: Path | None = None) -> tuple[int, dict[str, dict]]:
        code, report = self.report(cwd)
        self.assertEqual([c["name"] for c in report["checks"]], MACHINE + PROJECT)
        return code, {check["name"]: check for check in report["checks"]}

    def assert_gap(self, check: dict, *statuses: str) -> None:
        self.assertIn(check["status"], statuses or ("missing", "unsupported"), check)
        self.assertTrue(check["gates"], check)
        self.assertTrue(check["remedy"], check)


class MachineTests(DoctorCase):
    """Each machine prerequisite is named, gated and given a remedy."""

    def test_everything_present_passes(self) -> None:
        code, checks = self.checks()
        for name in MACHINE:
            expected = "skipped" if name == "network" else "passing"
            self.assertEqual(checks[name]["status"], expected, checks[name])
        code, text = self.doctor()
        self.assertEqual(code, 0)
        self.assertTrue(text.endswith("\nEverything Ballast needs is in place.\n"))

    def test_installed_command_runs_doctor(self) -> None:
        before = snapshot(*self.roots())
        result = subprocess.run(  # noqa: S603
            [str(self.local_bin / "ballast"), "doctor", "--json"],
            cwd=self.project,
            env=self.env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(snapshot(*self.roots()), before)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(validate(report, json.loads(SCHEMA.read_text())), [])
        self.assertEqual(report["verdict"], "ok")

    def test_each_missing_prerequisite(self) -> None:
        removals = {
            "python": lambda: setattr(self, "python", str(self.base / "no-python")),
            # Lambdas: each subtest starts from fresh directories.
            "cli-on-path": lambda: (self.local_bin / "ballast").unlink(),  # noqa: PLW0108
            "systemd-user": lambda: (self.bin / "systemctl").unlink(),  # noqa: PLW0108
            "agent-cli": lambda: [(self.bin / n).unlink() for n in ("claude", "codex")],
            "linux": lambda: setattr(self, "platform", "darwin"),
            "network": lambda: setattr(self.opener, "fail", True),
        }
        stub_of = {"systemd-run": "systemd-run", "specify": "specify", "gh": "gh"}
        stub_of |= {"git": "git", "uvx": "uvx", "patch": "patch"}
        self.assertEqual(set(removals) | set(stub_of), set(MACHINE))
        for name in MACHINE:
            with self.subTest(name):
                self.fresh()
                if name == "network":
                    self.pin("v0.1.0")  # not fetched, so setup would download
                if name in removals:
                    removals[name]()
                else:
                    (self.bin / stub_of[name]).unlink()
                code, checks = self.checks()
                self.assertEqual(code, 1)
                self.assert_gap(checks[name])
                text_code, text = self.doctor()
                self.assertEqual(text_code, 1)
                (final,) = [x for x in text.splitlines() if x.startswith("Blocked: ")]
                for gate in checks[name]["gates"]:
                    self.assertIn(gate, final)
                self.assertRegex(text, rf"\n  \w+ +{re.escape(name)} ")
                # Restoring the prerequisite makes the check pass.
                self.fresh()
                if name == "network":
                    self.pin("v0.1.0")
                self.assertEqual(self.checks()[1][name]["status"], "passing")

    def test_non_linux_host(self) -> None:
        self.platform = "darwin"
        _, checks = self.checks()
        self.assert_gap(checks["linux"], "unsupported")
        for name in ("systemd-user", "systemd-run"):
            self.assert_gap(checks[name], "unsupported")
            self.assertEqual(checks[name]["detail"], "headless steps need Linux")
            self.assertIn("ballast run (headless steps)", checks[name]["gates"])
        for name in ("git", "uvx", "patch", "gh", "agent-cli"):
            self.assertEqual(checks[name]["status"], "passing")

    def test_git_older_than_the_sync_floor(self) -> None:
        """T027 [DEC-0001, N-02, Q36]: branch synchronization needs git 2.41."""
        self.stub("git", 'echo "git version 2.40.1"')
        code, checks = self.checks()
        self.assertEqual(code, 1)
        self.assert_gap(checks["git"])
        self.assertIn("git 2.40 is older than 2.41", checks["git"]["detail"])
        self.assertIn("2.41 or later", checks["git"]["remedy"])
        self.stub("git", 'echo "git version 2.41.0"')
        self.assertEqual(self.checks()[1]["git"]["status"], "passing")

    def test_no_systemd_user_session(self) -> None:
        self.stub("systemctl", "exit 1")
        code, checks = self.checks()
        self.assertEqual(code, 1)
        self.assert_gap(checks["systemd-user"])
        self.assertEqual(
            checks["systemd-user"]["gates"], ["ballast run (headless steps)"]
        )

    def test_scope_that_does_not_start_blocks(self) -> None:
        self.stub("systemd-run", "exit 1")
        code, report = self.report()
        checks = {c["name"]: c for c in report["checks"]}
        self.assert_gap(checks["systemd-run"], "unsupported")
        self.assertEqual((code, report["verdict"]), (1, "blocked"))
        self.assertIn("ballast run (headless steps)", report["blocked"])
        self.stub("systemd-run", "exec /bin/sleep 30")
        code, checks = self.checks()
        self.assertEqual(checks["systemd-run"]["status"], "inconclusive")
        self.assertEqual(code, 0)

    def test_network_status_codes(self) -> None:
        self.pin("v0.1.0")
        expected = {200: "passing", 302: "passing", 404: "missing"}
        expected |= {403: "inconclusive", 429: "inconclusive", 500: "inconclusive"}
        for status, outcome in expected.items():
            with self.subTest(status):
                self.opener.status = None if status == 200 else status  # noqa: PLR2004
                _, checks = self.checks()
                self.assertEqual(checks["network"]["status"], outcome)
                if outcome != "passing":
                    self.assertTrue(checks["network"]["remedy"])

    def test_missing_agent_and_unauthenticated_gh(self) -> None:
        for name in ("claude", "codex"):
            (self.bin / name).unlink()
        self.stub(
            "gh", f'[ "$1" = auth ] && {{ echo {TOKEN}; echo {TOKEN} >&2; exit 1; }}'
        )
        code, checks = self.checks()
        self.assertEqual(code, 1)
        self.assert_gap(checks["agent-cli"])
        self.assertIn("ballast run (agent steps)", checks["agent-cli"]["gates"])
        self.assert_gap(checks["gh"])
        self.assertEqual(checks["gh"]["remedy"], "gh auth login")
        _, text = self.doctor()
        _, as_json = self.doctor("--json")
        self.assertNotIn(TOKEN, text)
        self.assertNotIn(TOKEN, as_json)

    def test_outside_a_project(self) -> None:
        code, checks = self.checks()
        self.assertEqual(code, 0)
        for name in PROJECT:
            self.assertEqual(checks[name]["status"], "skipped")
            self.assertEqual(checks[name]["detail"], "no ballast.toml found")
        (self.bin / "patch").unlink()
        self.assertEqual(self.checks()[0], 1)

    def test_network_probe_only_sends_head(self) -> None:
        self.pin("v0.1.0")
        _, checks = self.checks()
        self.assertEqual(checks["network"]["status"], "passing")
        self.assertIn("unverified", checks["network"]["detail"])
        self.assertTrue(self.opener.methods)
        self.assertEqual(set(self.opener.methods), {"HEAD"})

    def test_json_report_and_usage(self) -> None:
        self.pin("v0.1.0")
        (self.bin / "uvx").unlink()
        code, report = self.report()
        self.assertEqual((code, report["verdict"], report["schema"]), (1, "blocked", 1))
        self.assertEqual(report["cli_version"], shim.VERSION)
        self.assertEqual(report["project"], str(self.project))
        self.assertEqual(report["standard"]["ref"], "v0.1.0")
        self.assertIn("ballast setup", report["blocked"])
        self.assertEqual(report["blocked"], sorted(report["blocked"]))
        # The validator itself rejects a gap without a remedy or an unknown name.
        schema = json.loads(SCHEMA.read_text())
        uvx = next(c for c in report["checks"] if c["name"] == "uvx")
        uvx["remedy"] = None
        report["checks"].append({**uvx, "name": "other", "remedy": "x"})
        self.assertEqual(len(validate(report, schema)), 2)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self.doctor("--bogus")[0], 2)

    def test_hung_probe_is_bounded(self) -> None:
        self.stub("systemctl", "exec /bin/sleep 30")
        started = time.monotonic()
        _, checks = self.checks()
        self.assertLess(time.monotonic() - started, 10)
        self.assertEqual(checks["systemd-user"]["status"], "inconclusive")
        self.assertIn("did not answer within 3 s", checks["systemd-user"]["detail"])
        self.assertTrue(checks["systemd-user"]["remedy"])

    def test_hung_resolver_is_bounded(self) -> None:
        self.pin("v0.1.0")
        driver = (
            "import contextlib, socket, sys, threading\n"
            "from importlib.machinery import SourceFileLoader\n"
            "from importlib.util import module_from_spec, spec_from_loader\n"
            f"loader = SourceFileLoader('b', {str(SHIM)!r})\n"
            "module = module_from_spec(spec_from_loader('b', loader))\n"
            "loader.exec_module(module)\n"
            "socket.getaddrinfo = lambda *a, **k: threading.Event().wait()\n"
            "sys.exit(module.main(['doctor', '--json']))\n"
        )
        started = time.monotonic()
        result = subprocess.run(  # noqa: S603
            [sys.executable, "-c", driver],
            cwd=self.project,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        self.assertLess(time.monotonic() - started, 10)
        network = next(
            c for c in json.loads(result.stdout)["checks"] if c["name"] == "network"
        )
        self.assertEqual(network["status"], "inconclusive", network)

    def test_programs_in_another_working_tree_never_run(self) -> None:
        other = self.base / "other-checkout"
        (other / ".git").mkdir(parents=True)
        (self.bin / "gh").unlink()
        self.stub("gh", f"touch {self.sentinel}", other / "bin")
        link = self.base / "linked"
        link.mkdir()
        (self.bin / "systemctl").unlink()
        self.stub("systemctl", f"touch {self.sentinel}", other / "tools")
        (link / "systemctl").symlink_to(other / "tools/systemctl")
        self.env["PATH"] = os.pathsep.join(
            [str(other / "bin"), str(link), self.env["PATH"]]
        )
        _, checks = self.checks()
        for name, check in (("gh", "gh"), ("systemctl", "systemd-user")):
            self.assertEqual(checks[check]["status"], "missing")
            self.assertIn(f"ignored {name} found only in", checks[check]["detail"])

    def test_programs_in_a_temp_directory_never_run(self) -> None:
        # Codex agents can write $TMPDIR and /tmp; the runtime never trusts a
        # program there, and doctor now agrees (#34).
        (self.bin / "gh").unlink()
        self.stub("gh", f"touch {self.sentinel}", self.tmp / "bin")
        self.env["PATH"] = os.pathsep.join([str(self.tmp / "bin"), self.env["PATH"]])
        _, checks = self.checks()
        self.assertEqual(checks["gh"]["status"], "missing")
        self.assertIn("a temp directory", checks["gh"]["detail"])
        boundary = checks["agent-cli"]["detail"]
        self.assertIn("agents can write the checkout and ", boundary)
        self.assertIn(str(self.tmp.resolve()), boundary)
        self.assertFalse(self.sentinel.exists())

    def test_safe_program_later_on_path_is_used(self) -> None:
        other = self.base / "other-checkout"
        (other / ".git").mkdir(parents=True)
        self.stub("gh", f"touch {self.sentinel}", other / "bin")
        link = self.base / "linked"
        link.mkdir()
        (link / "gh").symlink_to(other / "bin/gh")
        self.env["PATH"] = os.pathsep.join([str(link), self.env["PATH"]])
        _, checks = self.checks()
        self.assertEqual(checks["gh"]["status"], "passing")
        self.assertFalse(self.sentinel.exists())

    def test_agent_cli_only_in_the_checkout(self) -> None:
        for name in ("claude", "codex"):
            (self.bin / name).unlink()
        self.stub("claude", f"touch {self.sentinel}", self.project / "bin")
        self.pin("v0.1.0")
        self.env["PATH"] = f"{self.project / 'bin'}{os.pathsep}{self.env['PATH']}"
        _, checks = self.checks()
        self.assert_gap(checks["agent-cli"])
        self.assertIn(
            "ignored claude found only in the checkout", checks["agent-cli"]["detail"]
        )

    def test_programs_in_the_checkout_never_run(self) -> None:
        self.pin("v0.1.0")
        for name in ("gh", "systemctl"):
            (self.bin / name).unlink()
            self.stub(name, f"touch {self.sentinel}", self.project / "bin")
            self.stub(name, f"touch {self.sentinel}", self.project / "relative")
        self.env["PATH"] = os.pathsep.join(
            [str(self.project / "bin"), "relative", self.env["PATH"]]
        )
        _, checks = self.checks()
        for name, check in (("gh", "gh"), ("systemctl", "systemd-user")):
            self.assertEqual(checks[check]["status"], "missing")
            self.assertIn(
                f"ignored {name} found only in the checkout", checks[check]["detail"]
            )
        # A PATH entry outside that links into the checkout is also refused.
        link = self.base / "linked-bin"
        link.symlink_to(self.project / "bin")
        self.env["PATH"] = f"{link}{os.pathsep}{self.bin}{os.pathsep}{self.local_bin}"
        _, checks = self.checks()
        self.assertEqual(checks["gh"]["status"], "missing")

    def test_readme_summarises_every_check(self) -> None:
        readme = (ROOT / "README.md").read_text()
        summary = readme.split("## Installing the Ballast CLI", 1)[1].split("\n## ", 1)[
            0
        ]
        self.assertIn("`ballast doctor`", summary)
        self.assertIn("authoritative", summary)
        for name in MACHINE:
            self.assertIn(f"`{name}`", summary)


class ProjectTests(DoctorCase):
    """Inside a project doctor names the next command for each state."""

    REF = "v0.1.0"

    def test_checks_claude_agents_cannot_run_are_reported(self) -> None:
        # Issue #37: an uncovered [checks] command leaves a Claude agent unable
        # to verify its own work; a leading VAR=value never matches a rule.
        (self.project / "ballast.toml").write_text(
            '[standard]\nref = "v0.1.0"\n'
            "[agents.permissions]\n"
            'extra_allow = ["Bash(uvx ruff check*)", "Bash(npm test:*)"]\n'
            "[checks]\n"
            'commands = ["uvx ruff check", "npm test -- --ci", "TOKEN=x make test"]\n'
        )
        _, checks = self.checks()
        check = checks["checks-allowed"]
        self.assert_gap(check)
        self.assertEqual(
            check["detail"],
            "extra_allow does not cover: TOKEN=x make test"
            " (a leading VAR=value never matches an allow rule)",
        )
        self.assertEqual(check["remedy"], shim.CHECKS_REMEDY)

    def test_creates_venv_reads_uv_options(self) -> None:
        # #114 review: only uv's own options exempt a command, global options
        # may precede the subcommand, and the CLI's copy matches the launcher's.
        loader = SourceFileLoader(
            "launcher_for_doctor", str(ROOT / "tools/spec_workflow/launcher.py")
        )
        launcher = module_from_spec(spec_from_loader("launcher_for_doctor", loader))
        loader.exec_module(launcher)
        for command, creates in (
            ("uv run --locked pytest", True),
            ("uv sync --locked", True),
            ("Bash(uv run pytest *)", True),
            ("uv --quiet run pytest", True),
            ("/usr/bin/uv run x", True),
            ("uv run echo --no-project", True),
            ("uv run --python=3.13 x --isolated", True),
            ("uv --directory . run pytest", True),
            ("uv run --locked echo --no-project", True),
            ("uv run --python 3.13 --with pyyaml --no-project python", False),
            ("uv run --python 3.13 --no-project x", False),
            ("uv run --isolated x", False),
            ("uv sync --dry-run", False),
            ("uvx ruff check", False),
            ("uv pip list", False),
            ("make test", False),
        ):
            with self.subTest(command=command):
                self.assertEqual(shim.creates_venv(command), creates)
                self.assertEqual(launcher.creates_venv(command), creates)

    def test_uv_check_without_venv_is_reported(self) -> None:
        # Issue #114: an agent's first `uv run` creates .venv, a protected
        # input, so the run stops as tampered; doctor says so beforehand.
        (self.project / "pyproject.toml").write_text("[project]\nname = 'x'\n")
        (self.project / "ballast.toml").write_text(
            '[standard]\nref = "v0.1.0"\n'
            "[agents.permissions]\n"
            'extra_allow = ["Bash(uv run --locked *)"]\n'
            "[checks]\n"
            'commands = ["uv run --locked pytest"]\n'
        )
        _, checks = self.checks()
        check = checks["checks-venv"]
        self.assert_gap(check)
        self.assertIn("uv run --locked pytest creates .venv", check["detail"])
        self.assertEqual(
            check["remedy"], "run `uv sync --locked` before `ballast trust`"
        )
        (self.project / ".venv").mkdir()
        _, checks = self.checks()
        self.assertEqual(checks["checks-venv"]["status"], "passing")

    def test_text_report_escapes_control_characters(self) -> None:
        # A checkout's ballast.toml must not forge a doctor line or emit
        # terminal escapes through a [checks] command.
        (self.project / "ballast.toml").write_text(
            '[standard]\nref = "v0.1.0"\n[checks]\n'
            'commands = ["x\\n  ok           trust            \\u001b[2K"]\n'
        )
        _, output = self.doctor()
        self.assertNotIn("\x1b", output)
        self.assertNotRegex(output, r"(?m)^  ok +trust ")
        self.assertIn(r"x\n  ok", output)

    def test_rule_matching(self) -> None:
        for rule, command, allowed in (
            ("Bash(uv run *)", "uv run pytest -q", True),
            ("Bash(uv run *)", "uvx run", False),
            ("Bash(make test)", "make test", True),
            ("Bash(make test)", "make test-all", False),
            ("Bash(npm test:*)", "npm test", True),
            ("Read(./x)", "x", False),
        ):
            with self.subTest(rule=rule, command=command):
                self.assertEqual(shim.rule_allows(rule, command), allowed)

    def standard(self, ref: str | None = None) -> Path:
        """Fetch this repository's tools as the pinned version, as setup would."""
        standard = self.data / "ballast/standard" / (ref or self.REF)
        shutil.copytree(ROOT / "tools", standard / "tools")
        return standard

    def install(self, standard: Path) -> None:
        """Put the workflow in the project and stamp it, as setup would."""
        loader = SourceFileLoader("fetched_setup", str(standard / "tools/setup"))
        module = module_from_spec(spec_from_loader("fetched_setup", loader))
        loader.exec_module(module)
        shutil.copytree(
            standard / "tools/spec_workflow", self.project / ".ballast/spec_workflow"
        )
        for path in module.PROMISED:
            (self.project / path).parent.mkdir(parents=True, exist_ok=True)
            (self.project / path).touch()
        stamp = self.project / ".ballast/.setup-version"
        stamp.write_text(module.Setup(self.project).fingerprint() + "\n")

    def trust(self, standard: Path) -> None:
        subprocess.run(  # noqa: S603
            [
                *(sys.executable, "-I", "-S"),
                *(str(standard / "tools/spec_workflow/launcher.py"), "trust"),
            ],
            cwd=self.project,
            env={**os.environ, **self.env},
            check=True,
            capture_output=True,
        )

    def sentinel_tools(self, standard: Path, manifest: str | None) -> None:
        """Probe files that record their execution."""
        for relative in ("tools/setup", "tools/spec_workflow/launcher.py"):
            path = standard / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"open({str(self.sentinel)!r}, 'w').write('ran')\n")
        if manifest is not None:
            (standard / "tools/cli.toml").write_text(manifest)

    def test_invalid_pin(self) -> None:
        cases = {
            "no ref": "[standard]\n",
            "../x": '[standard]\nref = "../x"\n',
            "-x": '[standard]\nref = "-x"\n',
            "a/b": '[standard]\nref = "a/b"\n',
            "unparsable": "[standard\n",
            "array of tables": '[[standard]]\nref = "v0.1.0"\n',
            "standard is a string": 'standard = "v0.1.0"\n',
            "ref is a table": "[standard.ref]\nx = 1\n",
        }
        for name, content in cases.items():
            with self.subTest(name):
                (self.project / "ballast.toml").write_text(content)
                code, checks = self.checks()
                self.assertEqual(code, 1)
                self.assert_gap(checks["ballast-toml"])
                self.assertEqual(
                    checks["ballast-toml"]["detail"], shim.read_pin(self.project)[1]
                )
                for later in PROJECT[1:]:
                    self.assertEqual(checks[later]["status"], "skipped")
                for machine in MACHINE:
                    self.assertIn(machine, checks)

    def test_not_fetched_names_setup(self) -> None:
        self.pin(self.REF)
        code, checks = self.checks()
        self.assertEqual(code, 1)
        self.assert_gap(checks["standard-fetched"])
        self.assertEqual(checks["standard-fetched"]["remedy"], "ballast setup")
        for later in ("cli-version", "setup-current", "trust"):
            self.assertEqual(checks[later]["status"], "skipped")
            self.assertEqual(checks[later]["detail"], "after `ballast setup`")

    def test_setup_then_trust(self) -> None:
        self.pin(self.REF)
        standard = self.standard()
        _, checks = self.checks()
        self.assertEqual(checks["setup-current"]["detail"], "setup is absent")
        self.assert_gap(checks["setup-current"])
        self.assertEqual(checks["setup-current"]["remedy"], "ballast setup")
        # #15 plan review F-005: a version that prepares also names the first
        # run, ledger or intake; one that cannot names setup alone.
        self.assertEqual(
            checks["trust"]["remedy"],
            "ballast setup, or the first `ballast run`, `ledger` or `intake`, which "
            "prepares it from a verified installation on this machine",
        )
        manifest = standard / "tools/cli.toml"
        declared = manifest.read_text()
        manifest.write_text(declared.replace("prepare = true\n", ""))
        _, checks = self.checks()
        self.assertEqual(checks["trust"]["remedy"], "ballast setup")
        manifest.write_text(declared)
        self.install(standard)
        (self.project / ".ballast/.setup-version").write_text("stale\n")
        _, checks = self.checks()
        self.assertEqual(checks["setup-current"]["detail"], "setup is stale")
        self.install_stamp_again(standard)
        code, checks = self.checks()
        self.assertEqual(code, 1)
        self.assertEqual(checks["setup-current"]["status"], "passing")
        self.assert_gap(checks["trust"])
        self.assertIn(
            "launcher will refuse: no trusted baseline", checks["trust"]["detail"]
        )
        self.assertEqual(checks["trust"]["remedy"], shim.TRUST)
        self.assertFalse(self.state.exists())
        self.trust(standard)
        code, checks = self.checks()
        self.assertEqual(code, 0)
        for name in MACHINE + PROJECT:
            expected = "skipped" if name == "network" else "passing"
            self.assertEqual(checks[name]["status"], expected, checks[name])
        (self.project / "BALLAST_TAMPERED").write_text("x\n")
        _, checks = self.checks()
        self.assertIn("delete BALLAST_TAMPERED", checks["trust"]["remedy"])

    def record(self, ref: str, *, stamp: str = "fp") -> Path:
        """Leave an installation record of `ref`, as setup would (#14)."""
        key = hashlib.sha256(str(self.project.resolve()).encode()).hexdigest()[:16]
        state = self.state / "ballast" / key
        state.mkdir(parents=True)
        record = {"schema": 1, "ref": ref, "fingerprint": "fp", "files": {}}
        (state / "installation.json").write_text(json.dumps(record))
        (self.project / ".ballast").mkdir(exist_ok=True)
        (self.project / ".ballast/.setup-version").write_text(stamp + "\n")
        return state

    def test_pinned_and_installed_versions_are_named(self) -> None:
        # AC-008: the pinned version failed to fetch or to set up.
        self.pin("v0.2.0")
        state = self.record(self.REF)
        detail = (
            'installed v0.1.0, pinned v0.2.0: restore ref = "v0.1.0" in '
            "ballast.toml, or fix the cause and rerun `ballast setup`"
        )
        _, checks = self.checks()
        self.assertEqual(
            checks["standard-fetched"]["detail"],
            f"standard v0.2.0 is not fetched; {detail}",
        )
        standard = self.standard("v0.2.0")
        self.install(standard)
        stamp = (self.project / ".ballast/.setup-version").read_text().strip()
        record = json.loads((state / "installation.json").read_text())
        record["fingerprint"] = stamp
        (state / "installation.json").write_text(json.dumps(record))
        _, checks = self.checks()
        self.assertIn(
            'stale: pinned v0.2.0, installed v0.1.0; restore ref = "v0.1.0"',
            checks["setup-current"]["detail"],
        )
        self.assertIn("pinned v0.2.0, installed v0.1.0", checks["trust"]["detail"])
        self.assertEqual(
            checks["trust"]["remedy"],
            "restore the previous pin in ballast.toml, or fix the cause and rerun "
            "`ballast setup`",
        )
        (state / "setup-attempt.json").write_text("{}\n")
        _, checks = self.checks()
        self.assertEqual(
            checks["setup-current"]["detail"],
            "setup is interrupted: run `ballast setup`",
        )
        self.assertEqual(checks["trust"]["remedy"], "ballast setup")

    def install_stamp_again(self, standard: Path) -> None:
        shutil.rmtree(self.project / ".ballast")
        self.install(standard)

    def test_cli_older_than_the_pin_needs(self) -> None:
        for ref in (self.REF, "0123456789abcdef0123456789abcdef01234567"):
            with self.subTest(ref):
                self.pin(ref)
                standard = self.standard(ref)
                (standard / "tools/cli.toml").write_text(
                    '[cli]\nminimum = "99.0.0"\n[doctor]\nprobes = []\n'
                )
                code, checks = self.checks()
                self.assertEqual(code, 1)
                self.assert_gap(checks["cli-version"])
                self.assertIn(
                    shim.install_line("v99.0.0"), checks["cli-version"]["remedy"]
                )
                self.assertIn("pin a release instead", checks["cli-version"]["remedy"])

    def test_older_standard_runs_no_probe(self) -> None:
        self.pin(self.REF)
        standard = self.data / "ballast/standard" / self.REF
        self.sentinel_tools(standard, None)
        _, checks = self.checks()
        self.assertEqual(checks["cli-version"]["status"], "passing")
        for name in ("setup-current", "trust"):
            self.assert_gap(checks[name], "inconclusive")
            self.assertIn("predates doctor", checks[name]["detail"])

    def test_malformed_manifest_runs_no_probe(self) -> None:
        self.pin(self.REF)
        standard = self.data / "ballast/standard" / self.REF
        self.sentinel_tools(standard, "[cli\n")
        _, checks = self.checks()
        self.assert_gap(checks["cli-version"], "inconclusive")
        for name in ("setup-current", "trust"):
            self.assertEqual(checks[name]["status"], "inconclusive")

    def test_local_standard_that_is_not_a_standard(self) -> None:
        self.pin(self.REF)
        empty = self.base / "empty"
        empty.mkdir()
        for path in (self.base / "absent", empty):
            with self.subTest(path.name):
                self.env["BALLAST_STANDARD_DIR"] = str(path)
                code, checks = self.checks()
                self.assertEqual(code, 1)
                check = checks["standard-fetched"]
                self.assert_gap(check)
                self.assertIn(str(path), check["detail"])
                self.assertEqual(
                    check["remedy"],
                    "set BALLAST_STANDARD_DIR to a checkout of the standard,"
                    " or unset it",
                )

    def test_local_standard_is_read_not_run(self) -> None:
        self.pin(self.REF)
        self.sentinel_tools(
            self.project, '[doctor]\nprobes = ["setup-check", "launcher-status"]\n'
        )
        self.env["BALLAST_STANDARD_DIR"] = str(self.project)
        _, report = self.report()
        self.assertTrue(report["standard"]["local"])
        checks = {c["name"]: c for c in report["checks"]}
        self.assertIn("using local standard", checks["standard-fetched"]["detail"])
        for name in ("setup-current", "trust"):
            self.assert_gap(checks[name], "inconclusive")
            self.assertEqual(
                checks[name]["detail"], "local standard: probes not executed"
            )
        _, text = self.doctor()
        self.assertIn("using local standard", text)

    def test_standard_inside_a_working_tree_is_not_run(self) -> None:
        manifest = '[doctor]\nprobes = ["setup-check", "launcher-status"]\n'
        self.pin(self.REF)
        inside = self.project / "fetched"
        self.sentinel_tools(inside, manifest)
        linked = self.data / "ballast/standard" / self.REF
        linked.parent.mkdir(parents=True)
        linked.symlink_to(inside)
        variants = {"linked into the checkout": self.data}
        variants["XDG_DATA_HOME inside the checkout"] = self.project / ".data"
        self.sentinel_tools(
            self.project / ".data/ballast/standard" / self.REF, manifest
        )
        # $TMPDIR is agent-writable too (#34).
        variants["XDG_DATA_HOME in a temp directory"] = self.tmp / "data"
        self.sentinel_tools(self.tmp / "data/ballast/standard" / self.REF, manifest)
        for name, data in variants.items():
            with self.subTest(name):
                self.env["XDG_DATA_HOME"] = str(data)
                _, checks = self.checks()
                for check in ("setup-current", "trust"):
                    self.assert_gap(checks[check], "inconclusive")
                    self.assertEqual(
                        checks[check]["detail"],
                        "standard directory resolves into a working tree or temp"
                        " directory",
                    )


class TrustSourceTests(DoctorCase):
    """#55 AC-003: doctor shows who recorded the baseline, from the launcher alone."""

    REF = ProjectTests.REF
    standard = ProjectTests.standard
    install = ProjectTests.install
    trust = ProjectTests.trust

    def answer(self, **status: object) -> dict:
        """Run doctor against a launcher that prints the given status."""
        document = self.base / "answer.json"
        if not document.exists():
            self.pin(self.REF)
            standard = self.standard()
            self.install(standard)
            (standard / "tools/spec_workflow/launcher.py").write_text(
                f"import sys; sys.stdout.write(open({str(document)!r}).read())\n"
            )
        document.write_text(json.dumps(status) + "\n")
        return self.checks()[1]["trust"]

    def test_an_accepted_baseline_names_its_source(self) -> None:
        for source in ("setup", "trust"):
            with self.subTest(source):
                check = self.answer(
                    installed=True, refusal=None, baseline_source=source
                )
                self.assertEqual(check["status"], "passing")
                self.assertEqual(
                    check["detail"],
                    "the launcher accepts this checkout; baseline recorded by "
                    f"ballast {source}",
                )

    def test_a_refusal_names_the_source_of_the_current_baseline(self) -> None:
        refusal = (
            "workflow inputs changed since `trust`: x; review them, then run `trust`"
        )
        for source in ("setup", "trust"):
            with self.subTest(source):
                check = self.answer(
                    installed=True, refusal=refusal, baseline_source=source
                )
                self.assert_gap(check)
                self.assertEqual(
                    check["detail"],
                    f"launcher will refuse: {refusal}; the current baseline was "
                    f"recorded by ballast {source}",
                )
                self.assertEqual(check["remedy"], shim.TRUST)

    def test_an_older_launcher_or_no_baseline_reads_as_before(self) -> None:
        for extra in (
            {},
            {"baseline_source": None},
            {"baseline_source": "other"},
            {"baseline_source": ["setup"]},
        ):
            with self.subTest(extra):
                check = self.answer(installed=True, refusal=None, **extra)
                self.assertEqual(check["detail"], "the launcher accepts this checkout")
                check = self.answer(
                    installed=True, refusal="no trusted baseline for x", **extra
                )
                self.assertEqual(
                    check["detail"], "launcher will refuse: no trusted baseline for x"
                )

    def test_the_trust_check_lists_the_reviewed_repositories(self) -> None:
        # SEC2-003: the machine-wide record is visible, never silent
        self.pin(self.REF)
        standard = self.standard()
        self.install(standard)
        (standard / "tools/spec_workflow/launcher.py").write_text(
            "import sys\n"
            "if sys.argv[1] == 'reviewed':\n"
            '    print(\'{"repositories": ["a/b", "c/d"]}\')\n'
            "else:\n"
            '    print(\'{"installed": true, "refusal": null}\')\n'
        )
        check = self.checks()[1]["trust"]
        self.assertEqual(check["status"], "passing")
        self.assertEqual(
            check["detail"],
            "the launcher accepts this checkout; reviewed repositories on this "
            "machine: a/b, c/d",
        )

    def test_the_real_launcher_reports_each_source(self) -> None:
        self.pin(self.REF)
        standard = self.standard()
        self.install(standard)
        self.trust(standard)
        _, checks = self.checks()
        self.assertIn("baseline recorded by ballast trust", checks["trust"]["detail"])
        self.assertEqual(checks["trust"]["status"], "passing")


class RedirectHandler(http.server.BaseHTTPRequestHandler):
    """Answers HEAD with the status in the path; /redirect points at /body."""

    requests: ClassVar[list[str]] = []

    def do_HEAD(self) -> None:
        self.requests.append(f"{self.command} {self.path}")
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/body")
        else:
            self.send_response(int(self.path.strip("/")))
        self.end_headers()

    do_GET = do_HEAD  # noqa: N815

    def log_message(self, *_: object) -> None:
        return


class ReachTests(unittest.TestCase):
    """The real opener sends one HEAD and never follows a redirect."""

    def setUp(self) -> None:
        self.server = http.server.HTTPServer(("127.0.0.1", 0), RedirectHandler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        RedirectHandler.requests.clear()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    def test_redirect_is_not_followed(self) -> None:
        self.assertEqual(shim.reach(self.url + "/redirect")[0], "reachable")
        self.assertEqual(RedirectHandler.requests, ["HEAD /redirect"])

    def test_status_classes(self) -> None:
        expected = {200: "reachable", 404: "missing", 403: "inconclusive"}
        expected |= {429: "inconclusive", 503: "inconclusive"}
        for status, outcome in expected.items():
            with self.subTest(status):
                self.assertEqual(shim.reach(f"{self.url}/{status}")[0], outcome)


if __name__ == "__main__":
    unittest.main()
