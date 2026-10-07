"""The local zero-cost fallback (#23): fallback.py, the wrapper, ledger and CLI.

Offline only. A loopback stub Ollama (`http.server` on an ephemeral
127.0.0.1 port) records every request; fake `claude` and `codex` executables
record their argv, environment, CODEX_HOME and prompt. The wrapper runs in a
subprocess through a test driver that points `fallback.OLLAMA_ENDPOINT` at
the stub, as the real endpoint is a constant (DEC-0003). "Nothing sent" means
the stub saw only /api/version, /api/tags and /api/show, and the fake Codex
never ran with the prompt.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
import unittest
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_autonomous_artifacts import RecorderCase
from test_autonomous_run import RunCase, WrapperCase, _write, run
from test_autonomy import FEATURE, TOOLS, autonomy, ledger

sys.path.pop(0)
sys.path.insert(0, str(TOOLS))
try:
    import agent
    import fallback
finally:
    sys.path.pop(0)

MODEL = "qwen3:4b-16k"
RUN = "run42"
DIGEST = "a383baf4" * 8
# Redacted messages from the pilot (evaluation.md item 8).
CLAUDE_QUOTA = "You've hit your limit \u00b7 resets <time>\n"
CLAUDE_UNAVAILABLE = (
    "API Error: 503 status code (no body). This is a server-side issue, usually "
    "temporary \u2014 try again in a moment. If it persists, check your inference "
    "gateway (<host:port>).\n"
)
CODEX_QUOTA = (
    "ERROR: You\u2019ve hit your usage limit. Upgrade to Pro (<url>), visit <url> "
    "to purchase more credits or try again at <date> <time>.\n"
)
CODEX_UNAVAILABLE = (
    '{"type":"error","message":"unexpected status 503 Service Unavailable: '
    'Unknown error, url: <url>"}\n'
)
# The `codex exec --json` shape of pilot item 10 (qwen3:4b-16k answered `ok`).
EVENTS = "".join(
    json.dumps(event) + "\n"
    for event in (
        {"type": "thread.started", "thread_id": "01a110fe"},
        {
            "type": "item.completed",
            "item": {"id": "item_0", "type": "error", "message": "Model metadata"},
        },
        {"type": "turn.started"},
        {"type": "item.completed", "item": {"id": "item_1", "type": "reasoning"}},
        {
            "type": "item.completed",
            "item": {"id": "item_2", "type": "agent_message", "text": "ok"},
        },
        {
            "type": "turn.completed",
            "usage": {
                "input_tokens": 11905,
                "cached_input_tokens": 0,
                "cache_write_input_tokens": 0,
                "output_tokens": 110,
                "reasoning_output_tokens": 0,
            },
        },
    )
)
FAKE_PRIMARY = r"""#!/usr/bin/env python3
import json, os, subprocess, sys
with open(os.environ["FAKE_ARGV"], "w") as handle:
    json.dump({"argv": sys.argv[1:], "env": sorted(os.environ)}, handle)
touch = os.environ.get("FAKE_TOUCH")
if touch:
    with open(touch, "a") as handle:
        handle.write("x")
if os.environ.get("FAKE_COMMIT"):
    git = os.environ.get("BALLAST_GIT", "git")
    subprocess.run([git, "commit", "-q", "--allow-empty", "-m", "agent"], check=True)
drafts = os.environ.get("FAKE_DRAFTS")
if drafts:
    os.makedirs(drafts, exist_ok=True)
    with open(os.path.join(drafts, "plan.json"), "w") as handle:
        handle.write("{}")
sys.stdout.write(os.environ.get("FAKE_OUT", "done\n"))
sys.stderr.write(os.environ.get("FAKE_ERR", ""))
sys.exit(int(os.environ.get("FAKE_EXIT", "0")))
"""
FAKE_CODEX = r"""#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
if args[:2] == ["exec", "--help"]:
    flags = "" if os.environ.get("FAKE_NO_OSS") else "--oss --local-provider --json"
    print("Usage: codex exec [OPTIONS] [PROMPT] " + flags)
    sys.exit(0)
if args[:1] == ["sandbox"]:
    sys.exit(int(os.environ.get("FAKE_SANDBOX_EXIT", "0")))
home = os.environ.get("CODEX_HOME", "")
record = {
    "argv": args,
    "env": sorted(os.environ),
    "codex_home": home,
    "home_listing": sorted(os.listdir(home)) if os.path.isdir(home) else None,
    "stdin": sys.stdin.read(),
}
with open(os.environ["FAKE_CODEX_LOG"], "a") as log:
    log.write(json.dumps(record) + "\n")
drafts = os.environ.get("FAKE_CODEX_DRAFTS")
if drafts:
    os.makedirs(drafts, exist_ok=True)
    with open(os.path.join(drafts, "plan.json"), "w") as handle:
        handle.write("{}")
if os.environ.get("FAKE_CODEX_SLEEP"):
    import time
    time.sleep(float(os.environ["FAKE_CODEX_SLEEP"]))
sys.stdout.write(os.environ.get("FAKE_EVENTS", ""))
sys.exit(int(os.environ.get("FAKE_CODEX_EXIT", "0")))
"""
# Runs agent.main with the stub's endpoint (test-only; the real one is fixed).
DRIVER = """
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import fallback
for name, value in json.loads(sys.argv[2]).items():
    setattr(fallback, name, Path(value) if name == "CODEX_SYSTEM_DIR" else value)
import agent
sys.argv = [sys.argv[3], *sys.argv[4:]]
sys.exit(agent.main())
"""
PROBE_PATHS = {"/api/version", "/api/tags", "/api/show"}


class StubOllama:
    """A loopback Ollama stand-in that records every request."""

    def __init__(self) -> None:
        """Serve on an ephemeral loopback port until `close`."""
        self.requests: list[tuple[str, str, str | None]] = []
        self.reset()
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_: object) -> None:
                pass

            def answer(self, body: str | None) -> None:
                stub.requests.append((self.command, self.path, body))
                if stub.delay:
                    time.sleep(stub.delay)
                tags = (
                    stub.tags_script.pop(0)
                    if stub.tags_script and self.path == "/api/tags"
                    else stub.tags
                )
                data = {
                    "/api/version": stub.version,
                    "/api/tags": tags,
                    "/api/show": stub.show,
                }.get(self.path)
                if data is None:
                    self.send_error(404)
                    return
                raw = json.dumps(data).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_GET(self) -> None:
                self.answer(None)

            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                self.answer(self.rfile.read(length).decode())

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.endpoint = f"http://127.0.0.1:{self.server.server_address[1]}"

    def reset(self) -> None:
        """Answer as a healthy Ollama 0.35.1 serving MODEL with a 16k context."""
        self.version: dict = {"version": "0.35.1"}
        self.tags: dict = {
            "models": [
                {"name": MODEL, "model": MODEL, "size": 2620788019, "digest": DIGEST}
            ]
        }
        self.show: dict = {
            "parameters": "num_ctx 16384\ntemperature 0.6\ntop_k 20",
            "capabilities": ["completion", "tools", "thinking"],
        }
        self.delay = 0.0
        # One /api/tags answer per request, before `tags` applies again.
        self.tags_script: list[dict] = []

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    def paths(self) -> list[str]:
        return [path for _, path, _ in self.requests]


def closed_port() -> str:
    """Return a loopback endpoint nothing listens on."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    return f"http://127.0.0.1:{port}"


class FallbackCase(WrapperCase):
    """A checkout with the Codex skill, fakes, a stub Ollama and the driver."""

    def setUp(self) -> None:
        super().setUp()
        _write(self.bin / "claude", FAKE_PRIMARY)
        _write(self.bin / "codex", FAKE_CODEX)
        self.stub = StubOllama()
        self.addCleanup(self.stub.close)
        self.home = self.base / "home"
        self.home.mkdir()
        os.environ.update(
            {
                "HOME": str(self.home),
                "FAKE_CODEX_LOG": str(self.base / "codex.log"),
                "FAKE_EVENTS": EVENTS,
            }
        )
        runs = self.root / ".specify/workflows/runs" / RUN
        runs.mkdir(parents=True)
        (runs / "inputs.json").write_text(
            json.dumps({"inputs": {"feature_directory": FEATURE}})
        )
        skill = self.root / ".agents/skills/speckit-plan/SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("# speckit-plan\n")
        (self.root / FEATURE).mkdir(parents=True)
        (self.root / FEATURE / "spec.md").write_text("# Spec\n")
        with (self.root / ".gitignore").open("a") as ignore:
            ignore.write("build/\n.venv/\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "fixture")
        self.patches = {
            "OLLAMA_ENDPOINT": self.stub.endpoint,
            "CODEX_SYSTEM_DIR": str(self.base / "etc-codex"),
        }
        self.driver = self.base / "driver.py"
        self.driver.write_text(DRIVER)

    def enable(self, model: str = MODEL) -> None:
        fallback.write_setting(self.root, RUN, model, DIGEST)

    def step(
        self, prompt: str = "/speckit-plan", name: str = "claude", **env: str
    ) -> subprocess.CompletedProcess[str]:
        verb = "-p" if name == "claude" else "exec"
        return subprocess.run(  # noqa: S603
            [
                sys.executable,
                "-I",
                str(self.driver),
                str(TOOLS),
                json.dumps(self.patches),
                name,
                verb,
                prompt,
            ],
            cwd=self.root,
            env={**os.environ, **env},
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )

    def quota(self, **env: str) -> subprocess.CompletedProcess[str]:
        return self.step(FAKE_OUT=CLAUDE_QUOTA, FAKE_EXIT="1", **env)

    def codex_runs(self) -> list[dict]:
        log = self.base / "codex.log"
        if not log.exists():
            return []
        return [json.loads(line) for line in log.read_text().splitlines()]

    def events(self) -> list[dict]:
        found, problems = ledger.read(self.root, RUN)
        self.assertEqual(problems, [])
        return found

    def routes(self) -> list[dict]:
        return [event["data"] for event in self.events() if event["kind"] == "route"]

    def metas(self) -> list[dict]:
        agents = self.root / ".specify/workflow-state" / RUN / "agents"
        return [
            json.loads((path / "meta.json").read_text())
            for path in sorted(agents.iterdir())
        ]

    def assert_nothing_sent(self, result: subprocess.CompletedProcess[str]) -> None:
        self.assertLessEqual(set(self.stub.paths()), PROBE_PATHS)
        self.assertEqual(self.codex_runs(), [])
        self.assertNotIn(CLAUDE_QUOTA.strip(), result.stderr.split("refused")[-1])

    def refusal(self, result: subprocess.CompletedProcess[str]) -> str:
        (line,) = [
            line
            for line in result.stderr.splitlines()
            if "local fallback refused: " in line
        ]
        return line.split("local fallback refused: ", 1)[1]


# --- Units ---------------------------------------------------------------------


class SettingTests(FallbackCase):
    """T006 [AC-006, AC-020]: the operator setting."""

    def test_validate_model(self) -> None:
        self.assertEqual(fallback.validate_model("qwen3:4b"), "qwen3:4b")
        for bad in ("", "-m", "qwen3 4b", "a" * 80, "x;rm"):
            with self.subTest(bad=bad), self.assertRaises(fallback.SettingError) as hit:
                fallback.validate_model(bad)
            self.assertEqual(str(hit.exception), fallback.MODEL_HINT)
        for cloud in ("gemma4:cloud", "gpt-oss:120b-cloud"):
            with (
                self.subTest(cloud=cloud),
                self.assertRaises(fallback.SettingError) as hit,
            ):
                fallback.validate_model(cloud)
            self.assertEqual(
                str(hit.exception),
                f"--local-fallback refuses cloud model {cloud}: content would leave "
                "this machine",
            )

    def test_setting_has_no_endpoint(self) -> None:
        self.assertEqual(fallback.OLLAMA_ENDPOINT, "http://127.0.0.1:11434")
        self.assertNotIn("endpoint", fallback.write_setting.__code__.co_varnames)
        self.enable()
        path = fallback.setting_path(self.root, RUN)
        data = json.loads(path.read_text())
        self.assertNotIn("endpoint", data)
        for extra in ({"endpoint": "http://127.0.0.1:1"}, {"other": 1}):
            with self.subTest(extra=extra):
                path.write_text(json.dumps({**data, **extra}))
                with self.assertRaises(fallback.SettingError):
                    fallback.read_setting(self.root, RUN)

    def test_write_and_read(self) -> None:
        self.assertIsNone(fallback.read_setting(self.root, RUN))
        self.assertEqual(
            fallback.write_setting(self.root, RUN, MODEL, DIGEST).model, MODEL
        )
        path = fallback.setting_path(self.root, RUN)
        self.assertEqual(path.parent, autonomy.run_dir(self.root, RUN))
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        data = json.loads(path.read_text())
        self.assertEqual(
            {k: v for k, v in data.items() if k != "set_at"},
            {
                "version": 1,
                "enabled": True,
                "provider": "ollama",
                "model": MODEL,
                "digest": DIGEST,
                "set_by": "operator",
            },
        )
        self.assertEqual(
            fallback.read_setting(self.root, RUN),
            fallback.Setting(MODEL, digest=DIGEST),
        )
        self.assertIsNone(fallback.write_setting(self.root, RUN, None))
        data = json.loads(path.read_text())
        self.assertEqual(data["enabled"], 0)
        self.assertIsInstance(data["enabled"], bool)
        self.assertEqual(data["model"], MODEL)
        self.assertIsNone(fallback.read_setting(self.root, RUN))
        self.assertEqual(fallback.describe(self.root, RUN), "off")

    def test_invalid_setting_is_off(self) -> None:
        self.enable()
        path = fallback.setting_path(self.root, RUN)
        good = path.read_text()
        cases = {
            "bad json": "{",
            "not an object": "[]",
            "bad version": good.replace('"version": 1', '"version": 2'),
            "bad provider": good.replace('"ollama"', '"openai"'),
            "cloud model": good.replace(MODEL, "gemma4:cloud"),
            "enabled text": good.replace("true", '"yes"'),
        }
        for name, text in cases.items():
            with self.subTest(name=name):
                path.write_text(text)
                with self.assertRaises(fallback.SettingError):
                    fallback.read_setting(self.root, RUN)
                self.assertEqual(fallback.describe(self.root, RUN), "off")
        path.unlink()
        target = self.base / "elsewhere.json"
        target.write_text(good)
        path.symlink_to(target)
        with self.assertRaises(fallback.SettingError):
            fallback.read_setting(self.root, RUN)
        path.unlink()
        path.write_text(good)
        path.chmod(0)
        if os.geteuid() != 0:
            with self.assertRaises(fallback.SettingError):
                fallback.read_setting(self.root, RUN)

    def test_wrapper_treats_invalid_as_off(self) -> None:
        self.enable()
        fallback.setting_path(self.root, RUN).write_text("{")
        result = self.quota()
        self.assertEqual(result.returncode, 1)
        self.assertIn("local fallback off", result.stderr)
        self.assertEqual(self.stub.requests, [])
        self.assertEqual(self.codex_runs(), [])


class StateTests(FallbackCase):
    """T008 [AC-009]: ignored-path and ref digests, and the evidence."""

    def ignored(self) -> str | None:
        return autonomy.ignored_digest(self.root)

    def test_ignored_digest_sees_every_change(self) -> None:
        build = self.root / "build"
        build.mkdir()
        (build / "a.txt").write_text("a")
        steps = {
            "create": lambda: (build / "b.txt").write_text("b"),
            "write same size": self.rewrite,
            "chmod": lambda: (build / "a.txt").chmod(0o600),
            "rename": lambda: (build / "b.txt").rename(build / "c.txt"),
            "delete": (build / "c.txt").unlink,
            "directory": (build / "d").mkdir,
            "symlink": lambda: (build / "link").symlink_to("a.txt"),
            "symlink target": self.retarget,
            "feature.json": lambda: (self.root / ".specify/feature.json").write_text(
                "{}"
            ),
        }
        for name, change in steps.items():
            with self.subTest(change=name):
                before = self.ignored()
                self.assertIsNotNone(before)
                change()
                self.assertNotEqual(self.ignored(), before)

    def rewrite(self) -> None:
        path = self.root / "build/a.txt"
        status = path.stat()
        time.sleep(0.01)
        path.write_text("z")
        os.utime(path, ns=(status.st_atime_ns, status.st_mtime_ns))

    def retarget(self) -> None:
        link = self.root / "build/link"
        link.unlink()
        link.symlink_to("missing.txt")

    def test_ignored_digest_leaves_out_protected_and_logs(self) -> None:
        before = self.ignored()
        logs = self.root / ".specify/workflow-state" / RUN / "agents/x"
        logs.mkdir(parents=True)
        (logs / "stdout.log").write_text("log")
        (self.root / ".venv").mkdir()
        (self.root / ".venv/lib.py").write_text("x")
        self.assertEqual(self.ignored(), before)

    def test_ignored_digest_never_follows_a_link_out(self) -> None:
        outside = self.base / "outside"
        outside.mkdir()
        (self.root / "build").mkdir()
        (self.root / "build/out").symlink_to(outside)
        before = self.ignored()
        (outside / "secret.txt").write_text("changed")
        self.assertEqual(self.ignored(), before)

    def test_ignored_digest_unknown(self) -> None:
        (self.root / "build").mkdir()
        (self.root / "build/a").write_text("a")
        (self.root / "build/b").write_text("b")
        with patch.object(autonomy, "IGNORED_LIMIT", 1):
            self.assertIsNone(self.ignored())
        with patch.object(autonomy, "IGNORED_SECONDS", -1):
            self.assertIsNone(self.ignored())
        with patch.object(autonomy, "_entry_line", side_effect=PermissionError):
            self.assertIsNone(self.ignored())
        failing = autonomy.AutonomyError("git ls-files failed")
        with patch.object(autonomy, "git", side_effect=failing):
            self.assertIsNone(self.ignored())

    def test_refs_digest(self) -> None:
        steps = {
            "commit": lambda: self.git("commit", "-q", "--allow-empty", "-m", "x"),
            "branch": lambda: self.git("branch", "extra"),
            "tag": lambda: self.git("tag", "v0"),
            "detached": lambda: self.git("checkout", "-q", "--detach"),
        }
        for name, change in steps.items():
            with self.subTest(change=name):
                before = autonomy.refs_digest(self.root)
                self.assertIsNotNone(before)
                change()
                self.assertNotEqual(autonomy.refs_digest(self.root), before)
        failing = autonomy.AutonomyError("git failed")
        with patch.object(autonomy, "git", side_effect=failing):
            self.assertIsNone(autonomy.refs_digest(self.root))

    def test_state_evidence(self) -> None:
        evidence = fallback.state_evidence(self.root, FEATURE)
        self.assertEqual(
            set(evidence), {"tree", "reviews", "drafts", "ignored", "refs"}
        )
        self.assertEqual(fallback.state_evidence(self.root, FEATURE), evidence)
        self.assertIsNone(fallback.state_evidence(self.root, None))
        for piece in ("ignored_digest", "refs_digest"):
            with (
                self.subTest(piece=piece),
                patch.object(autonomy, piece, return_value=None),
            ):
                self.assertIsNone(fallback.state_evidence(self.root, FEATURE))
        self.assertEqual(
            fallback.changed_state(None, evidence).detail,
            "worktree state could not be checked",
        )
        self.assertEqual(
            fallback.changed_state(evidence, {**evidence, "refs": "x"}).detail,
            "worktree state changed",
        )
        self.assertIsNone(fallback.changed_state(evidence, dict(evidence)))


class ClassifyTests(unittest.TestCase):
    """T010, T015 [AC-001, AC-002, AC-010]: the normalized cause."""

    def cause(self, integration: str, code: int, text: str, **kw: object) -> str:
        return fallback.classify(
            integration,
            code,
            kw.get("blocked", False),  # type: ignore[arg-type]
            kw.get("contained", True),  # type: ignore[arg-type]
            (text.encode(), b""),
            cli_found=kw.get("cli_found", True),  # type: ignore[arg-type]
        )

    def test_recoverable(self) -> None:
        for integration, text, expected in (
            ("claude", CLAUDE_QUOTA, "quota-exhausted"),
            ("claude", "You've hit your monthly spend limit", "quota-exhausted"),
            (
                "claude",
                "API Error: Request rejected (429) · rate limited",
                "quota-exhausted",
            ),
            ("claude", CLAUDE_UNAVAILABLE, "provider-unavailable"),
            ("codex", CODEX_QUOTA, "quota-exhausted"),
            ("codex", CODEX_UNAVAILABLE, "provider-unavailable"),
            ("codex", "stream disconnected before completion", "provider-unavailable"),
        ):
            with self.subTest(integration=integration, text=text[:30]):
                self.assertEqual(self.cause(integration, 1, text), expected)
        self.assertEqual(
            self.cause("claude", 2, "", cli_found=False), "cli-unavailable"
        )
        # Stderr counts as well as stdout.
        stderr_only = fallback.classify(
            "codex",
            1,
            blocked=False,
            contained=True,
            tail=(b"", CODEX_QUOTA.encode()),
            cli_found=True,
        )
        self.assertEqual(stderr_only, "quota-exhausted")

    def test_non_recoverable(self) -> None:
        cases = {
            "blocked exit": (agent.EXIT_BLOCKED, CLAUDE_QUOTA, {}, "blocked"),
            "blocked status": (0, CLAUDE_QUOTA, {"blocked": True}, "blocked"),
            "tampered": (agent.EXIT_TAMPERED, CLAUDE_QUOTA, {}, "tampered"),
            "not contained": (1, CLAUDE_QUOTA, {"contained": False}, "tampered"),
            "limit": (agent.EXIT_LIMIT, CLAUDE_QUOTA, {}, "limit"),
            "interrupted": (agent.EXIT_INTERRUPTED, CLAUDE_QUOTA, {}, "interrupted"),
            "auth": (agent.EXIT_AUTH, CLAUDE_QUOTA, {}, "auth"),
            "success": (0, CLAUDE_QUOTA, {}, "success"),
            "unknown text": (1, "something else broke", {}, "unrecognized"),
            "other integration": (
                1,
                CODEX_QUOTA.replace("\u2019", "x"),
                {},
                "unrecognized",
            ),
        }
        for name, (code, text, kw, expected) in cases.items():
            with self.subTest(case=name):
                cause = self.cause("claude", code, text, **kw)
                self.assertEqual(cause, expected)
                self.assertNotIn(cause, fallback.RECOVERABLE)
        early = CLAUDE_QUOTA + "x" * (fallback.TAIL_BYTES + 10)
        self.assertEqual(self.cause("claude", 1, early), "unrecognized")

    def test_exit_codes_match_the_wrapper(self) -> None:
        for name in ("EXIT_BLOCKED", "EXIT_TAMPERED", "EXIT_LIMIT", "EXIT_AUTH"):
            self.assertEqual(getattr(fallback, name), getattr(agent, name))
        self.assertEqual(fallback.EXIT_INTERRUPTED, agent.EXIT_INTERRUPTED)


class InvocationTests(unittest.TestCase):
    """T010 [AC-004, AC-008]: prompt, argv, environment, events."""

    def test_codex_prompt(self) -> None:
        self.assertEqual(
            fallback.codex_prompt("/speckit-plan rest"), "$speckit-plan rest"
        )
        self.assertEqual(fallback.codex_prompt("/speckit.plan"), "$speckit-plan")
        self.assertEqual(fallback.codex_prompt("$speckit-plan x"), "$speckit-plan x")

    def test_fallback_argv_is_primary_codex_profile(self) -> None:
        argv = fallback.fallback_argv("/bin/codex", "$speckit-plan", MODEL)
        self.assertEqual(
            argv,
            [
                "/bin/codex",
                *agent.permission_args("codex", ["exec", "$speckit-plan"]),
                "--oss",
                "--local-provider",
                "ollama",
                "-m",
                MODEL,
                "--json",
            ],
        )
        self.assertFalse(any("model_providers" in token for token in argv))
        self.assertFalse(any("base_url" in token for token in argv))

    def test_fallback_argv_literal_tokens(self) -> None:
        # PD-0013 F-002: a widening inside permission_args fails here.
        self.assertEqual(
            fallback.fallback_argv("codex", "$speckit-plan", "qwen3:4b-16k"),
            [
                "codex",
                "exec",
                "--sandbox",
                "workspace-write",
                "--config",
                "sandbox_workspace_write.network_access=false",
                "--config",
                "sandbox_workspace_write.writable_roots=[]",
                "$speckit-plan",
                "--oss",
                "--local-provider",
                "ollama",
                "-m",
                "qwen3:4b-16k",
                "--json",
            ],
        )

    def test_fallback_env(self) -> None:
        parent = {
            "PATH": "/usr/bin",
            "HOME": "/home/x",
            "ANTHROPIC_API_KEY": "k",
            "OPENAI_API_KEY": "k",
            "GH_TOKEN": "t",
            "OLLAMA_HOST": "10.0.0.1",
            "CODEX_OSS_BASE_URL": "http://x",
            "CODEX_OSS_PORT": "1",
            "CODEX_HOME": "/home/x/.codex",
            "HTTPS_PROXY": "http://proxy.example:3128",
            "http_proxy": "http://proxy.example:3128",
            "ALL_PROXY": "socks5://proxy.example:1080",
        }
        env = fallback.fallback_env(parent, Path("/private/home"))
        # Codex itself reaches github.com and chatgpt.com at start-up (live
        # check): every proxy-aware request is sent to a closed local port.
        self.assertEqual(
            env,
            {
                "PATH": "/usr/bin",
                "HOME": "/home/x",
                "CODEX_HOME": "/private/home",
                **fallback.BLACKHOLE,
            },
        )
        for name in ("HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy"):
            self.assertEqual(env[name], "http://127.0.0.1:9")
        self.assertEqual(env["NO_PROXY"], "127.0.0.1,localhost,::1")
        argv = fallback.fallback_argv("codex", "$speckit-plan", MODEL)
        self.assertFalse(
            fallback.permission_mismatch(
                argv,
                env,
                Path("/private/home"),
                codex="codex",
                prompt="$speckit-plan",
                model=MODEL,
            )
        )

    def test_parse_events(self) -> None:
        events = fallback.parse_events(EVENTS.encode().splitlines())
        self.assertEqual(events.text, "ok\n")
        self.assertEqual(
            (events.input_tokens, events.cached_tokens, events.output_tokens),
            (11905, 0, 110),
        )
        self.assertTrue(events.complete)
        failed = EVENTS.replace('"turn.completed"', '"turn.failed"')
        self.assertFalse(fallback.parse_events(failed.splitlines()).complete)
        for broken in ("not json\n", "[1]\n", '{"no": "type"}\n'):
            with self.subTest(broken=broken), self.assertRaises(fallback.EventError):
                fallback.parse_events(broken.splitlines())


class PermissionTests(unittest.TestCase):
    """T015 [AC-008]: the exact-argv allowlist."""

    def setUp(self) -> None:
        self.home = Path("/private/codex-home")
        self.argv = fallback.fallback_argv("codex", "$speckit-plan", MODEL)
        self.env = fallback.fallback_env({"PATH": "/usr/bin"}, self.home)

    def mismatch(self, argv: list[str], env: dict[str, str] | None = None) -> bool:
        return fallback.permission_mismatch(
            argv,
            self.env if env is None else env,
            self.home,
            codex="codex",
            prompt="$speckit-plan",
            model=MODEL,
        )

    def test_wider_argv_refused(self) -> None:
        self.assertFalse(self.mismatch(list(self.argv)))
        widening = [
            ["--approve-for-me"],
            ["--enable", "x"],
            ["--disable", "x"],
            ["--worktree"],
            ["--ignore-user-config"],
            ["-p", "work"],
            ["--profile", "work"],
            ["--ignore-rules"],
            ["--strict-config"],
            ["--add-dir", "/"],
            ["--sandbox", "danger-full-access"],
            ["--dangerously-bypass-approvals-and-sandbox"],
            ["--dangerously-bypass-hook-trust"],
            ["-c", "sandbox_workspace_write.network_access=true"],
            ["--config", 'sandbox_workspace_write.writable_roots=["/"]'],
            ["-c", 'model_providers.ollama.base_url="http://10.0.0.1"'],
            ["--oss"],
            ["-m", "other"],
            ["--local-provider", "lmstudio"],
            ["--some-future-flag"],
        ]
        for extra in widening:
            with self.subTest(extra=extra):
                self.assertTrue(self.mismatch([*self.argv, *extra]))
                self.assertTrue(self.mismatch([*self.argv[:2], *extra, *self.argv[2:]]))
        removed = self.argv[:-1]
        reordered = [*self.argv[:-2], self.argv[-1], self.argv[-2]]
        changed = [item if item != MODEL else "qwen3:8b" for item in self.argv]
        for name, argv in (
            ("removed", removed),
            ("reordered", reordered),
            ("changed", changed),
        ):
            with self.subTest(case=name):
                self.assertTrue(self.mismatch(argv))

    def test_extra_env_refused(self) -> None:
        for extra in (
            {"ANTHROPIC_API_KEY": "k"},
            {"GH_TOKEN": "t"},
            {"SSH_AUTH_SOCK": "/s"},
            {"CODEX_HOME": "/home/x/.codex"},
            {"HTTPS_PROXY": "http://proxy.example:3128"},
            {"all_proxy": "socks5://proxy.example:1080"},
            {"FTP_PROXY": "http://127.0.0.1:9"},
            {"No_Proxy": "*"},
        ):
            with self.subTest(extra=sorted(extra)):
                self.assertTrue(self.mismatch(self.argv, {**self.env, **extra}))
        without = dict(self.env)
        del without["CODEX_HOME"]
        self.assertTrue(self.mismatch(self.argv, without))
        for name in fallback.BLACKHOLE:
            with self.subTest(removed=name):
                bare = {k: v for k, v in self.env.items() if k != name}
                self.assertTrue(self.mismatch(self.argv, bare))

    def test_endpoint_override_env_refused(self) -> None:
        for name in fallback.ENDPOINT_VARIABLES:
            with self.subTest(name=name):
                env = {**self.env, name: "http://10.0.0.1:1"}
                self.assertTrue(self.mismatch(self.argv, env))
                refused = fallback.probe(
                    fallback.Setting(MODEL, digest=DIGEST),
                    root=Path("/nonexistent"),
                    autonomous=False,
                    codex="codex",
                    prompt="/speckit-plan",
                    env=env,
                )
                self.assertEqual(refused.reason, "privacy-exclusion")
                self.assertNotIn(
                    name, fallback.fallback_env({"PATH": "/b", name: "x"}, self.home)
                )


class ProbeCase(FallbackCase):
    """Probes in process, against the stub."""

    def setUp(self) -> None:
        super().setUp()
        self.enterContext(patch.object(fallback, "OLLAMA_ENDPOINT", self.stub.endpoint))
        self.enterContext(
            patch.object(fallback, "CODEX_SYSTEM_DIR", self.base / "etc-codex")
        )
        self.codex_home = self.base / "codex-home"
        self.codex_home.mkdir()

    def probe(
        self, *, autonomous: bool = False, prompt: str = "/speckit-plan", **env: str
    ) -> fallback.Refused | None:
        base = fallback.fallback_env(dict(os.environ), self.codex_home)
        codex, _ = autonomy.trusted_program("codex", self.root)
        with patch.dict(os.environ, env):
            return fallback.probe(
                fallback.Setting(MODEL, digest=DIGEST),
                root=self.root,
                autonomous=autonomous,
                codex=codex,
                prompt=prompt,
                env={**base, **env},
            )

    def assert_refused(self, reason: str, detail: str, **kw: object) -> None:
        refused = self.probe(**kw)  # type: ignore[arg-type]
        self.assertEqual(refused, fallback.Refused(reason, detail))


class ProbeTests(ProbeCase):
    """T010, T015 [AC-005, AC-006, AC-007]."""

    def test_eligible_model_passes(self) -> None:
        for autonomous in (False, True):
            with self.subTest(autonomous=autonomous):
                self.assertIsNone(self.probe(autonomous=autonomous))
        self.assertLessEqual(set(self.stub.paths()), PROBE_PATHS)
        bodies = [body for _, _, body in self.stub.requests if body]
        self.assertTrue(bodies)
        self.assertTrue(all(json.loads(body) == {"model": MODEL} for body in bodies))

    def test_model_missing_refuses_unknown_free_status(self) -> None:
        self.stub.tags = {"models": []}
        self.assert_refused("unknown-free-status", f"model {MODEL} is not installed")
        self.stub.tags = {"models": [{"name": MODEL, "size": 0, "digest": ""}]}
        self.assert_refused(
            "unknown-free-status", f"model {MODEL} has no size or digest"
        )

    def test_model_digest_pinned_at_opt_in(self) -> None:
        """SEC2-002: a model replaced under the same name is refused."""
        self.assertEqual(fallback.served_digest(MODEL), DIGEST)
        self.stub.tags = {"models": []}
        self.assertIsNone(fallback.served_digest(MODEL))
        self.stub.reset()
        self.stub.tags["models"][0]["digest"] = "b" * 64
        self.assert_refused("incompatible-capability", "model changed since opt-in")
        self.assertEqual(fallback.served_digest(MODEL), "b" * 64)
        self.stub.reset()
        refused = fallback.probe(
            fallback.Setting(MODEL),
            root=self.root,
            autonomous=False,
            codex=None,
            prompt="/speckit-plan",
            env={},
        )
        self.assertEqual(
            refused,
            fallback.Refused("incompatible-capability", "model not pinned at opt-in"),
        )

    def test_recheck_closes_check_then_use(self) -> None:
        """Re-verified just before launch: digest, layers, skills, CODEX_HOME."""
        home = self.base / "recheck-home"
        home.mkdir()
        with patch.object(Path, "home", return_value=home):
            args = (fallback.Setting(MODEL, digest=DIGEST),)
            kw = {"root": self.root, "codex_home": self.codex_home}
            self.assertIsNone(fallback.recheck(*args, **kw))
            self.assertFalse(fallback.model_changed(*args))
            cases = []
            self.stub.tags["models"][0]["digest"] = "b" * 64
            cases.append(("model changed since opt-in", None))
            self.assertEqual(
                fallback.recheck(*args, **kw),
                fallback.Refused("incompatible-capability", cases[0][0]),
            )
            self.assertTrue(fallback.model_changed(*args))
            self.stub.reset()
            (self.codex_home / "config.toml").write_text("x")
            self.assertEqual(
                fallback.recheck(*args, **kw).detail, "codex home is not empty"
            )
            (self.codex_home / "config.toml").unlink()
            (self.root / ".codex").mkdir()
            (self.root / ".codex/hooks.json").write_text("{}")
            self.assertEqual(
                fallback.recheck(*args, **kw).detail,
                "codex configuration layer outside the private home",
            )
            (self.root / ".codex/hooks.json").unlink()
            (self.root / ".codex").rmdir()
            (home / ".agents/skills/x").mkdir(parents=True)
            self.assertEqual(
                fallback.recheck(*args, **kw).detail,
                "user skills directory is not empty",
            )

    def test_cloud_model_refuses_privacy(self) -> None:
        cloud = "gemma4:cloud"
        self.stub.tags = {"models": [{"name": cloud, "size": 1, "digest": "d"}]}
        refused = fallback.probe(
            fallback.Setting(cloud),
            root=self.root,
            autonomous=False,
            codex=None,
            prompt="/speckit-plan",
            env={},
        )
        self.assertEqual(refused.reason, "privacy-exclusion")

    def test_remote_host_refuses_privacy(self) -> None:
        entry = self.stub.tags["models"][0]
        for name, change in (
            ("tags host", lambda: entry.update(remote_host="https://ollama.com")),
            ("show model", lambda: self.stub.show.update(remote_model="x")),
        ):
            with self.subTest(case=name):
                change()
                self.assert_refused(
                    "privacy-exclusion", f"model {MODEL} is remote or cloud"
                )

    def test_server_down_refuses_capability(self) -> None:
        with patch.object(fallback, "OLLAMA_ENDPOINT", closed_port()):
            self.assert_refused("incompatible-capability", "server not answering")

    def test_codex_without_oss_refuses_capability(self) -> None:
        self.assert_refused(
            "incompatible-capability",
            "codex lacks --oss or --local-provider",
            FAKE_NO_OSS="1",
        )
        refused = fallback.probe(
            fallback.Setting(MODEL, digest=DIGEST),
            root=self.root,
            autonomous=False,
            codex=None,
            prompt="/speckit-plan",
            env={},
        )
        self.assertEqual(refused.detail, "codex is not installed")

    def test_codex_skill_missing_refuses_capability(self) -> None:
        skill = self.root / ".agents/skills/speckit-plan"
        (skill / "SKILL.md").unlink()
        self.assert_refused(
            "incompatible-capability", "codex skill speckit-plan is not installed"
        )
        skill.rmdir()
        outside = self.base / "outside-skill"
        outside.mkdir()
        (outside / "SKILL.md").write_text("x")
        skill.symlink_to(outside)
        self.assert_refused(
            "incompatible-capability", "codex skill speckit-plan is not installed"
        )

    def test_sandbox_not_nesting_refuses_capability(self) -> None:
        for autonomous in (False, True):
            with self.subTest(autonomous=autonomous):
                self.assert_refused(
                    "incompatible-capability",
                    "codex sandbox does not start",
                    autonomous=autonomous,
                    FAKE_SANDBOX_EXIT="1",
                )

    def test_probe_deadline_refuses(self) -> None:
        self.stub.delay = 0.05
        clock = iter([0.0, 1.0, 11.0, *[11.0] * 50])
        with patch.object(fallback, "_now", side_effect=lambda: next(clock)):
            self.assert_refused(
                "incompatible-capability", "eligibility checks timed out"
            )

    def test_proxy_does_not_redirect(self) -> None:
        proxy = closed_port()
        self.assertIsNone(self.probe(http_proxy=proxy, HTTP_PROXY=proxy))
        self.assertIn("/api/version", self.stub.paths())


class ProbeContextTests(ProbeCase):
    """T037 [AC-007, FR-004, DEC-0004]: served context and Ollama version."""

    def test_served_context(self) -> None:
        for parameters, detail in (
            ("num_ctx 16384", None),
            ("num_ctx 32768\ntemperature 0.6", None),
            ("num_ctx 4096", "served context below 16384"),
            ("temperature 0.6", "served context unknown"),
            ("num_ctx lots", "served context unknown"),
        ):
            with self.subTest(parameters=parameters):
                self.stub.show = {"parameters": parameters}
                refused = self.probe()
                if detail is None:
                    self.assertIsNone(refused)
                else:
                    self.assertEqual(
                        refused, fallback.Refused("incompatible-capability", detail)
                    )
        self.stub.show = {}
        self.assert_refused("incompatible-capability", "served context unknown")

    def test_context_check_runs_after_layers_and_skills(self) -> None:
        self.stub.show = {"parameters": "num_ctx 4096"}
        skills = self.home / ".agents/skills/mine"
        skills.mkdir(parents=True)
        self.assert_refused("permission-mismatch", "user skills directory is not empty")

    def test_old_ollama_refuses_capability(self) -> None:
        for version, detail in (
            ("0.6.8", "ollama older than 0.13.4"),
            ("0.13.3", "ollama older than 0.13.4"),
            ("0.13.4", None),
            ("0.35.1", None),
            ("unknown", "ollama version unknown"),
        ):
            with self.subTest(version=version):
                self.stub.version = {"version": version}
                refused = self.probe()
                self.assertEqual(
                    refused,
                    None
                    if detail is None
                    else fallback.Refused("incompatible-capability", detail),
                )


class LayerTests(ProbeCase):
    """T015 [AC-008]: configuration layers and the user's skills."""

    def test_user_skills_dir_refuses(self) -> None:
        skills = self.home / ".agents/skills"
        detail = "user skills directory is not empty"
        self.assertIsNone(self.probe())
        skills.mkdir(parents=True)
        self.assertIsNone(self.probe())
        (skills / "mine").mkdir()
        self.assert_refused("permission-mismatch", detail)
        (skills / "mine").rmdir()
        skills.rmdir()
        target = self.base / "skills-elsewhere"
        target.mkdir()
        skills.symlink_to(target)
        self.assert_refused("permission-mismatch", detail)
        skills.unlink()
        skills.mkdir()
        skills.chmod(0)
        if os.geteuid() != 0:
            self.assert_refused("permission-mismatch", detail)
        skills.chmod(0o700)
        # The project's own skills (check 9) do not count.
        self.assertTrue((self.root / ".agents/skills/speckit-plan").is_dir())
        self.assertIsNone(self.probe())

    def test_other_codex_config_layer_refuses(self) -> None:
        detail = "codex configuration layer outside the private home"
        system = self.base / "etc-codex"
        system.mkdir()
        self.assertIsNone(self.probe())
        (system / "config.toml").write_text('notify = ["x"]\n')
        self.assert_refused("permission-mismatch", detail)
        (system / "config.toml").unlink()
        system.chmod(0)
        if os.geteuid() != 0:
            self.assert_refused("permission-mismatch", detail)
        system.chmod(0o700)
        project = self.root / ".codex/config.toml"
        project.parent.mkdir()
        project.write_text('[mcp_servers.x]\ncommand = "x"\n')
        self.assert_refused("permission-mismatch", detail)
        # SEC2-003: any entry under a project .codex refuses, not just config.toml.
        project.unlink()
        self.assertIsNone(self.probe())
        (project.parent / "hooks.json").write_text("{}")
        self.assert_refused("permission-mismatch", detail)


class ModuleTests(unittest.TestCase):
    """T034 [FR-009, FR-011]: standard library only, no model list."""

    def test_stdlib_only_no_model_list(self) -> None:
        source = (TOOLS / "fallback.py").read_text()
        imported = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imported |= {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        # agent is the wrapper itself, imported lazily for permission_args.
        workflow = {"autonomy", "ledger", "agent"}
        self.assertLessEqual(imported - workflow, set(sys.stdlib_module_names))
        result = subprocess.run(  # noqa: S603
            [
                sys.executable,
                "-I",
                "-S",
                "-c",
                f"import sys; sys.path.insert(0, {str(TOOLS)!r}); import fallback",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        families = re.compile(
            r"\b(?:qwen|llama|gemma|mistral|phi\d|deepseek|gpt-oss|codellama)",
            re.IGNORECASE,
        )
        for name in ("fallback.py", "agent.py", "run.py"):
            text = (TOOLS / name).read_text().replace(fallback.MODEL_HINT, "")
            with self.subTest(file=name):
                self.assertIsNone(families.search(text))


class ConfinementCompositionTests(FallbackCase):
    """#89 per-CLI credentials: the fallback's Codex step gets only Codex's homes."""

    def test_fallback_step_shows_the_private_home_and_hides_claude(self) -> None:
        if autonomy.trusted_program("bwrap", self.root)[0] is None:
            _write(self.bin / "bwrap", "#!/bin/sh\n")
        claude = self.home / ".claude"
        claude.mkdir()
        (claude / ".credentials.json").write_text('{"claudeAiOauth": {"a": 1}}')
        (self.home / ".claude.json").write_text('{"apiKey": "secret"}')
        private_home = self.base / "codex-private"
        private_home.mkdir()
        private = self.base / "private"
        private.mkdir()
        argv = autonomy.confined_argv(
            self.root,
            ["codex", "exec"],
            private=private,
            home=self.home,
            env={"CODEX_HOME": str(private_home)},
            integration="codex",
        )
        joined = " ".join(argv)
        self.assertIn(f"--tmp-overlay {private_home}", joined)
        self.assertIn(f"--tmpfs {claude}", joined)
        self.assertNotIn(".credentials.json", joined.replace(f"--tmpfs {claude}", ""))
        self.assertIn(f"--ro-bind /dev/null {self.home / '.claude.json'}", joined)
        self.assertFalse(any(private.glob("credentials*")))
        self.assertEqual(list(private_home.iterdir()), [])

    def test_fallback_step_gets_no_codex_login(self) -> None:
        """SEC2-001: `--oss` needs no login; the operator's token is not copied."""
        codex = self.home / ".codex"
        codex.mkdir()
        (codex / "auth.json").write_text('{"tokens": {"access_token": "synthetic"}}')
        private_home = self.base / "codex-private"
        private_home.mkdir()
        for login, copies in ((True, 1), (False, 0)):
            with self.subTest(login=login):
                private = self.base / f"private-{login}"
                private.mkdir()
                joined = " ".join(
                    autonomy.confined_argv(
                        self.root,
                        ["codex", "exec"],
                        private=private,
                        home=self.home,
                        env={"CODEX_HOME": str(private_home)},
                        integration="codex",
                        **({} if login else {"with_login": False}),
                    )
                )
                self.assertEqual(len(list(private.glob("codex-auth-*"))), copies)
                self.assertEqual("auth.json" in joined, bool(copies))
                self.assertIn(f"--tmp-overlay {private_home}", joined)


# --- The wrapper -----------------------------------------------------------------


class WrapperFallbackTests(FallbackCase):
    """T010, T015, T018 [AC-001 to AC-004, AC-009, AC-010, AC-013 to AC-015]."""

    def assert_fallback_ran(self, result: subprocess.CompletedProcess[str]) -> dict:
        self.assertEqual(result.returncode, 0, result.stderr)
        (codex,) = self.codex_runs()
        self.assertEqual(codex["stdin"], "")
        self.assertIn("ok", result.stdout)
        return codex

    def test_quota_failure_completes_on_fallback(self) -> None:
        self.enable()
        codex = self.assert_fallback_ran(self.quota())
        self.assertEqual(
            codex["argv"], fallback.fallback_argv("codex", "$speckit-plan", MODEL)[1:]
        )
        primary, second = self.routes()
        self.assertEqual(
            (primary["failure_cause"], primary["fallback"]),
            ("quota-exhausted", "selected"),
        )
        self.assertEqual(
            (second["route_source"], second["outcome"]), ("fallback", "success")
        )

    def test_provider_unavailable_completes_on_fallback(self) -> None:
        self.enable()
        self.assert_fallback_ran(self.step(FAKE_OUT=CLAUDE_UNAVAILABLE, FAKE_EXIT="1"))
        self.assertEqual(self.routes()[0]["failure_cause"], "provider-unavailable")

    def without_claude(self) -> dict[str, str]:
        """Remove the fake claude, and keep any real one off PATH."""
        (self.bin / "claude").unlink()
        path = os.pathsep.join((str(self.bin), "/usr/bin", "/bin"))
        if any(Path(entry, "claude").exists() for entry in ("/usr/bin", "/bin")):
            self.skipTest("a claude CLI is installed in /usr/bin or /bin")
        return {"PATH": path}

    def test_cli_missing_completes_on_fallback(self) -> None:
        self.enable()
        self.assert_fallback_ran(self.step(**self.without_claude()))
        primary, _ = self.routes()
        self.assertEqual(primary["failure_cause"], "cli-unavailable")

    def test_setting_off_matches_today(self) -> None:
        keys = {
            "run_id",
            "feature_directory",
            "integration",
            "command",
            "argv",
            "started_at",
            "finished_at",
            "exit_code",
            "blocking_status",
            "protected_changes",
            "stopped_descendants",
        }
        for case in ("absent", "off"):
            with self.subTest(case=case):
                if case == "off":
                    fallback.write_setting(self.root, RUN, None)
                result = self.quota()
                self.assertEqual(result.returncode, 1)
                self.assertNotIn("local fallback", result.stderr)
                self.assertEqual(set(self.metas()[-1]), keys)
                self.assertEqual(
                    self.ran()["argv"],
                    agent.permission_args("claude", ["-p", "/speckit-plan"]),
                )
                self.assertEqual(self.stub.requests, [])
                self.assertEqual(self.codex_runs(), [])
                self.assertFalse(ledger.ledger_path(self.root, RUN).exists())
                logs = self.root / ".specify/workflow-state" / RUN / "agents"
                for log in logs.iterdir():
                    self.assertFalse((log / "usage.json").exists())
        record = self.make_run()
        del record
        fallback.setting_path(self.root, RUN).unlink()
        self.assertEqual(self.quota().returncode, 1)
        (step,) = self.steps()
        self.assertEqual(
            set(step),
            {
                "step",
                "ran",
                "command",
                "integration",
                "role",
                "set_aside",
                "tree_before",
                "reviews_before",
                "drafts",
                "exit_code",
                "blocking_status",
                "reason",
                "at",
                "attempt",
                "refusals",
            },
        )

    def test_fallback_argv_is_primary_codex_profile(self) -> None:
        self.enable()
        codex = self.assert_fallback_ran(self.quota())
        self.assertEqual(
            codex["argv"][: len(agent.permission_args("codex", ["exec", "x"])) - 1],
            agent.permission_args("codex", ["exec", "x"])[:-1],
        )
        env = set(codex["env"])
        self.assertFalse(
            env & {"ANTHROPIC_API_KEY", "GH_TOKEN", *fallback.ENDPOINT_VARIABLES}
        )

    def test_fallback_runs_under_same_confinement(self) -> None:
        self.make_run()
        self.enable()
        self.assert_fallback_ran(self.quota(OLLAMA_HOST="10.0.0.1"))
        commands = [
            json.loads(line)
            for line in (self.base / "bwrap.log").read_text().splitlines()
        ]
        # The agent steps; the sandbox probe runs `codex sandbox` instead.
        steps = [c for c in commands if "--new-session" in c and "sandbox" not in c]
        self.assertEqual(len(steps), 2)
        primary, second = steps
        cut = primary.index("--")
        self.assertEqual(primary[:3], second[:3])
        self.assertEqual(primary[cut + 1 :][:1], [str(self.bin / "claude")])
        self.assertEqual(Path(second[second.index("--") + 1]).name, "codex")
        (codex,) = self.codex_runs()
        self.assertNotIn("OLLAMA_HOST", codex["env"])
        self.assertNotIn("ANTHROPIC_API_KEY", codex["env"])

    def test_user_codex_config_not_read(self) -> None:
        user = self.home / ".codex"
        user.mkdir()
        (user / "config.toml").write_text(
            'profile = "work"\nnotify = ["/bin/notify"]\n'
            '[mcp_servers.x]\ncommand = "/bin/mcp"\n'
        )
        self.enable()
        codex = self.assert_fallback_ran(self.quota(CODEX_HOME=str(user)))
        self.assertNotEqual(codex["codex_home"], str(user))
        self.assertEqual(codex["home_listing"], [])
        self.assertFalse(Path(codex["codex_home"]).exists())

    def test_cli_missing_records_not_run(self) -> None:
        self.make_run()
        self.enable()
        self.assert_fallback_ran(self.step(**self.without_claude()))
        primary, second = self.steps()
        self.assertEqual(
            (primary["ran"], primary["failure_cause"], primary["fallback"]["decision"]),
            (False, "cli-unavailable", "selected"),
        )
        self.assertEqual(second["route"], "fallback")
        self.assertEqual(autonomy.read_run(self.root, RUN)["agent_steps"], 1)

    def test_fallback_counts_a_step(self) -> None:
        self.make_run()
        self.enable()
        self.assert_fallback_ran(self.quota())
        self.assertEqual(autonomy.read_run(self.root, RUN)["agent_steps"], 2)
        primary, second = self.steps()
        self.assertEqual(primary["failure_cause"], "quota-exhausted")
        self.assertEqual(primary["fallback"], {"decision": "selected", "reason": None})
        self.assertEqual(
            {k: second[k] for k in ("route", "provider", "model", "local_fallback")},
            {
                "route": "fallback",
                "provider": "ollama",
                "model": MODEL,
                "local_fallback": True,
            },
        )
        self.assertTrue(primary["local_fallback"])
        meta = self.metas()[-1]
        self.assertEqual(
            {k: meta[k] for k in ("route", "provider", "model", "local_fallback")},
            {
                "route": "fallback",
                "provider": "ollama",
                "model": MODEL,
                "local_fallback": True,
            },
        )

    def test_step_limit_blocks_fallback(self) -> None:
        record = self.make_run()
        record["limits"]["max_agent_steps"] = 1
        autonomy.write_run(self.root, record)
        self.enable()
        result = self.quota()
        self.assertEqual(result.returncode, agent.EXIT_LIMIT, result.stderr)
        self.assertIn("agent step limit exhausted", result.stderr)
        self.assertEqual(self.codex_runs(), [])
        (primary,) = self.routes()
        self.assertEqual(primary["fallback"], "selected")

    def test_failed_fallback_stops(self) -> None:
        self.enable()
        result = self.quota(FAKE_CODEX_EXIT="1", FAKE_EVENTS=CODEX_UNAVAILABLE)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(len(self.codex_runs()), 1)
        primary, second = self.routes()
        self.assertEqual(primary["fallback"], "selected")
        self.assertEqual(second["outcome"], "mechanical-failure")
        self.assertEqual(len(self.metas()), 2)

    def test_failed_fallback_timeout_is_incomplete(self) -> None:
        record = self.make_run()
        soon = datetime.now(UTC).replace(microsecond=0) + timedelta(seconds=10)
        record["limits"]["deadline"] = soon.isoformat()
        autonomy.write_run(self.root, record)
        self.enable()
        result = self.quota(FAKE_CODEX_SLEEP="60")
        self.assertEqual(result.returncode, agent.EXIT_LIMIT, result.stderr)
        _, second = self.routes()
        self.assertEqual(second["outcome"], "incomplete")
        self.assertEqual(len(self.codex_runs()), 1)

    def test_unparsable_stream_fails(self) -> None:
        self.enable()
        result = self.quota(FAKE_EVENTS="not json\n")
        self.assertEqual(result.returncode, 1)
        _, second = self.routes()
        self.assertEqual(second["outcome"], "mechanical-failure")
        self.assertNotIn("usage", [e["kind"] for e in self.events()])

    def test_blocked_status_in_events_fails(self) -> None:
        self.enable()
        blocked = EVENTS.replace(
            '"text": "ok"', '"text": "RECONCILE_STATUS: BLOCKED_X"'
        )
        result = self.quota(FAKE_EVENTS=blocked)
        self.assertEqual(result.returncode, agent.EXIT_BLOCKED, result.stderr)
        self.assertEqual(len(self.codex_runs()), 1)

    def test_refused_fallback_draft_not_retried(self) -> None:
        self.make_run()
        self.enable()
        skill = self.root / ".agents/skills/speckit-ballast-decide/SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("# decide\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "decide skill")
        drafts = self.root / FEATURE / "autonomous/drafts"
        result = self.step(
            "/speckit-ballast-decide plan",
            FAKE_OUT=CLAUDE_QUOTA,
            FAKE_EXIT="1",
            FAKE_CODEX_DRAFTS=str(drafts),
        )
        self.assertEqual(result.returncode, agent.EXIT_LIMIT, result.stderr)
        self.assertIn("draft refused after the local fallback", result.stderr)
        self.assertEqual(len(self.codex_runs()), 1)
        _, second = self.steps()
        self.assertEqual(second["limit"], "retries")
        self.assertEqual(self.routes()[-1]["outcome"], "rejected")
        self.assertEqual(autonomy.read_run(self.root, RUN)["agent_steps"], 2)

    def test_chat_step_never_falls_back(self) -> None:
        # AC-021: the interactive path never reads the setting, and a Chat
        # run's record turns it off for any headless step.
        source = (TOOLS / "agent.py").read_text()
        body = source[source.index("def run_interactive") : source.index("QUOTED =")]
        self.assertNotIn("fallback", body)
        self.enable()
        chat_record = {"workflow": autonomy.CHAT}
        with patch.object(autonomy, "find_run", return_value=chat_record):
            self.assertIsNone(agent._fallback_setting(self.root, RUN))  # noqa: SLF001
        self.assertEqual(
            agent._fallback_setting(self.root, RUN),  # noqa: SLF001
            fallback.Setting(MODEL, digest=DIGEST),
        )


class RefusalTests(FallbackCase):
    """T015 [AC-005 to AC-010, AC-013]: refusals send nothing."""

    def both_modes(self) -> list[bool]:
        return [False, True]

    def run_mode(
        self, *, autonomous: bool, **env: str
    ) -> subprocess.CompletedProcess[str]:
        if autonomous:
            self.make_run()
        self.enable()
        return self.quota(**env)

    def assert_refused(
        self, result: subprocess.CompletedProcess[str], reason: str, detail: str
    ) -> None:
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(self.refusal(result), f"{reason}: {detail}")
        self.assert_nothing_sent(result)
        self.assertNotIn("hit your limit", self.refusal(result))
        routes = self.routes()
        self.assertEqual(routes[-1]["fallback_reason"], reason)
        self.assertEqual(routes[-1]["fallback"], "refused")

    def reset(self) -> None:
        self.git("reset", "-q", "--hard")
        self.git("clean", "-qfdx", "-e", ".specify")

    def test_changed_tree_refuses(self) -> None:
        for autonomous in self.both_modes():
            with self.subTest(autonomous=autonomous):
                result = self.run_mode(
                    autonomous=autonomous, FAKE_TOUCH=str(self.root / "new.txt")
                )
                self.assert_refused(result, "changed-state", "worktree state changed")
                (self.root / "new.txt").unlink()

    def test_created_draft_refuses(self) -> None:
        drafts = self.root / FEATURE / "autonomous/drafts"
        for autonomous in self.both_modes():
            with self.subTest(autonomous=autonomous):
                result = self.run_mode(autonomous=autonomous, FAKE_DRAFTS=str(drafts))
                self.assert_refused(result, "changed-state", "worktree state changed")
                for path in drafts.iterdir():
                    path.unlink()

    def test_changed_reviews_refuses(self) -> None:
        review = self.root / FEATURE / "reviews/plan.md"
        review.parent.mkdir()
        for autonomous in self.both_modes():
            with self.subTest(autonomous=autonomous):
                result = self.run_mode(autonomous=autonomous, FAKE_TOUCH=str(review))
                self.assert_refused(result, "changed-state", "worktree state changed")

    def test_ignored_path_change_refuses(self) -> None:
        (self.root / "build").mkdir()
        for autonomous in self.both_modes():
            with self.subTest(autonomous=autonomous):
                result = self.run_mode(
                    autonomous=autonomous,
                    FAKE_TOUCH=str(self.root / "build/cache.bin"),
                )
                self.assert_refused(result, "changed-state", "worktree state changed")

    def test_primary_commit_refuses(self) -> None:
        for autonomous in self.both_modes():
            with self.subTest(autonomous=autonomous):
                result = self.run_mode(autonomous=autonomous, FAKE_COMMIT="1")
                self.assert_refused(result, "changed-state", "worktree state changed")

    def test_unverifiable_state_refuses(self) -> None:
        build = self.root / "build"
        build.mkdir()
        for index in range(5):
            (build / f"f{index}").write_text("x")
        self.patches["CODEX_SYSTEM_DIR"] = str(self.base / "etc-codex")
        driver = self.driver.read_text().replace(
            "import agent\n", "import agent, autonomy\nautonomy.IGNORED_LIMIT = 2\n"
        )
        self.driver.write_text(driver)
        result = self.run_mode(autonomous=False)
        self.assert_refused(
            result, "changed-state", "worktree state could not be checked"
        )

    def test_non_recoverable_never_falls_back(self) -> None:
        self.enable()
        for name, env in (
            ("unknown", {"FAKE_OUT": "boom\n", "FAKE_EXIT": "1"}),
            ("success", {}),
            ("blocked", {"FAKE_OUT": "RECONCILE_STATUS: BLOCKED_SPEC\n"}),
            ("auth", {"FAKE_OUT": "Invalid API key\n", "FAKE_EXIT": "1"}),
        ):
            with self.subTest(case=name):
                result = self.step(**env)
                self.assertNotIn("local fallback", result.stderr)
        self.assertEqual(self.stub.requests, [])
        self.assertEqual(self.codex_runs(), [])
        self.assertFalse(ledger.ledger_path(self.root, RUN).exists())

    def test_retry_attempt_never_falls_back(self) -> None:
        # A draft refused on attempt 1, then a quota failure on attempt 2.
        self.make_run()
        self.enable()
        script = self.bin / "claude"
        counter = self.base / "count"
        _write(
            script,
            FAKE_PRIMARY.replace(
                "sys.stdout.write(",
                "n = int(open(os.environ['COUNT']).read()) if os.path.exists("
                "os.environ['COUNT']) else 0\nopen(os.environ['COUNT'], 'w').write("
                "str(n + 1))\nif n:\n    sys.stdout.write(os.environ['QUOTA'])\n"
                "    sys.exit(1)\nsys.stdout.write(",
                1,
            ),
        )
        drafts = self.root / FEATURE / "autonomous/drafts"
        result = self.step(
            "/speckit-ballast-decide plan",
            COUNT=str(counter),
            QUOTA=CLAUDE_QUOTA,
            FAKE_DRAFTS=str(drafts),
        )
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertNotIn("local fallback", result.stderr)
        self.assertEqual(self.codex_runs(), [])
        self.assertEqual(self.stub.requests, [])
        first, second = self.steps()
        self.assertIn("refused", first)
        self.assertEqual(second["failure_cause"], "quota-exhausted")
        self.assertNotIn("fallback", second)
        (route,) = self.routes()
        self.assertEqual(route["attempt"], 2)
        self.assertNotIn("fallback", route)

    def test_replaced_model_refuses_before_any_prompt(self) -> None:
        self.enable()
        self.stub.tags["models"][0]["digest"] = "b" * 64
        self.assert_refused(
            self.quota(), "incompatible-capability", "model changed since opt-in"
        )
        self.assertEqual(self.codex_runs(), [])

    def test_model_swapped_after_the_probes_refuses_before_launch(self) -> None:
        self.enable()
        good = self.stub.tags
        bad = {"models": [{**good["models"][0], "digest": "b" * 64}]}
        self.stub.tags_script = [good, bad]  # the probe sees it, the recheck not
        result = self.quota()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("model changed since opt-in", result.stderr)
        self.assertEqual(self.codex_runs(), [])

    def test_model_swapped_during_the_run_fails_the_step(self) -> None:
        self.enable()
        good = self.stub.tags
        bad = {"models": [{**good["models"][0], "digest": "b" * 64}]}
        self.stub.tags_script = [good, good, bad]
        result = self.quota()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("local model changed during the step", result.stderr)

    def test_probe_refusal_returns_primary_code(self) -> None:
        self.enable()
        self.stub.tags = {"models": []}
        result = self.quota()
        self.assert_refused(
            result, "unknown-free-status", f"model {MODEL} is not installed"
        )


# --- Records ---------------------------------------------------------------------


class LedgerFallbackTests(FallbackCase):
    """T018 [AC-011, AC-012, AC-014, AC-016, AC-017]."""

    def test_selected_records_both_routes_and_usage(self) -> None:
        self.enable()
        self.assertEqual(self.quota().returncode, 0)
        events = self.events()
        primary, second = [e for e in events if e["kind"] == "route"]
        (usage,) = [e for e in events if e["kind"] == "usage"]
        step = primary["data"]["cause_id"]
        self.assertEqual(primary["event_id"], f"fallback:{step}:1:route")
        self.assertEqual(second["event_id"], f"fallback:{step}:2:route")
        self.assertEqual(usage["event_id"], f"fallback:{step}:2:usage")
        self.assertEqual(
            primary["data"],
            {
                "stage": "speckit-plan",
                "provider": "claude",
                "route_source": "operator-choice",
                "attempt": 1,
                "cause_id": step,
                "outcome": "mechanical-failure",
                "failure_cause": "quota-exhausted",
                "fallback": "selected",
            },
        )
        self.assertEqual(
            second["data"],
            {
                "stage": "speckit-plan",
                "provider": "ollama",
                "model": MODEL,
                "route_source": "fallback",
                "attempt": 2,
                "cause_id": step,
                "outcome": "success",
            },
        )
        log = self.root / ".specify/workflow-state" / RUN / "agents"
        (usage_file,) = list(log.glob("*/usage.json"))
        self.assertEqual(
            usage["data"]["counter_digest"],
            hashlib.sha256(usage_file.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            {
                k: usage["data"][k]
                for k in ("counter_source", "input_tokens", "output_tokens", "complete")
            },
            {
                "counter_source": "codex-exec-json",
                "input_tokens": 11905,
                "output_tokens": 110,
                "complete": True,
            },
        )
        self.assertEqual(
            (usage["source"], primary["source"]), ("client-counter", "runner")
        )

    def test_refusal_recorded_with_reason(self) -> None:
        self.enable()
        cases = {
            "unknown-free-status": lambda: self.stub.tags.update(models=[]),
            "privacy-exclusion": lambda: self.stub.show.update(remote_host="x"),
            "incompatible-capability": lambda: self.stub.version.update(
                version="0.1.0"
            ),
            "permission-mismatch": lambda: (self.home / ".agents/skills/x").mkdir(
                parents=True
            ),
        }
        for reason, change in cases.items():
            with self.subTest(reason=reason):
                change()
                self.quota()
                self.assertEqual(self.routes()[-1]["fallback_reason"], reason)
                self.stub.reset()
                for path in (self.home / ".agents").glob("skills/*"):
                    path.rmdir()
        result = self.quota(FAKE_TOUCH=str(self.root / "new.txt"))
        self.assertEqual(self.routes()[-1]["fallback_reason"], "changed-state")
        del result

    def test_repeated_record_is_idempotent(self) -> None:
        self.enable()
        self.quota()
        before = self.events()
        route = before[0]
        self.assertFalse(ledger.append(self.root, {**route}))
        problems = fallback.record(
            self.root,
            RUN,
            FEATURE,
            [(e["kind"], e["data"], e["event_id"]) for e in before],
        )
        self.assertEqual(problems, [])
        self.assertEqual(len(self.events()), len(before))

    def test_retried_step_single_effect(self) -> None:
        self.make_run()
        self.enable()
        self.quota()
        events, steps = self.events(), self.steps()
        self.assertEqual(len([e for e in events if e["kind"] == "usage"]), 1)
        self.assertEqual(len(steps), 2)
        self.assertEqual(len(self.codex_runs()), 1)

    def test_no_account_text_recorded(self) -> None:
        self.make_run()
        self.enable()
        self.quota(FAKE_ERR="account alice@example.test quota 5/5\n")
        recorded = json.dumps(self.events()) + json.dumps(self.steps())
        for text in ("alice", "hit your limit", "resets", "quota 5"):
            self.assertNotIn(text, recorded)

    def test_human_gated_review_by_fallback_not_cross_provider(self) -> None:
        for stage, expected in (("speckit-ballast-review", 0), ("speckit-plan", 1)):
            with self.subTest(stage=stage):
                run_id = f"run{len(stage)}"
                self.ledger_run(run_id, stage)
                routing = ledger.report(self.root, run_id)["routing"]
                self.assertEqual(routing["cross_provider_reviews"], expected)
                self.assertEqual(
                    routing["review_provider_availability"][0]["cross_provider"],
                    bool(expected),
                )
                self.assertEqual(routing["fallback_reviews"], 1 - expected)

    def ledger_run(self, run_id: str, stage: str) -> None:
        state = self.root / ".specify/workflows/runs" / run_id
        state.mkdir(parents=True)
        (state / "inputs.json").write_text(
            json.dumps({"inputs": {"feature_directory": FEATURE}})
        )
        (state / "workflow.yml").write_text(
            "workflow:\n  id: ballast-feature\n  version: 1.1.0\n"
            "steps:\n  - id: implement\n    command: speckit.intent.implement\n"
        )
        (state / "state.json").write_text(
            json.dumps({"workflow_id": "ballast-feature"})
        )
        (state / "log.jsonl").write_text("")
        ledger.import_run(self.root, run_id)
        records = [
            (
                "route",
                {
                    "stage": stage,
                    "provider": "ollama",
                    "model": MODEL,
                    "route_source": "fallback",
                    "attempt": 2,
                    "cause_id": "step1",
                    "outcome": "success",
                },
                "fallback:step1:2:route",
            )
        ]
        self.assertEqual(fallback.record(self.root, run_id, FEATURE, records), [])
        ledger.append(
            self.root,
            ledger.new_event(
                run_id,
                FEATURE,
                "review",
                "operator-attested",
                {
                    "review_id": "peer",
                    "kind": "implementation",
                    "verdict": "approved",
                    "author_id": "author",
                    "reviewer_id": "reviewer",
                    "author_provider": "Anthropic",
                    "reviewer_provider": "OpenAI",
                },
            ),
        )


class ArtifactsFallbackTests(RecorderCase):
    """T018 [AC-016]: an Autonomous review by the fallback is not cross-provider."""

    def test_review_by_fallback_not_cross_provider(self) -> None:
        draft = {**self.review_draft("plan-review", "plan"), "model": "claimed-model"}
        self.step(
            {"plan-review.json": draft},
            role="reviewer",
            integration="codex",
            route="fallback",
            provider="ollama",
            model=MODEL,
        )
        self.ok(self.record("plan-review"))
        (entry,) = self.decisions()
        self.assertFalse(entry["review"]["cross_provider"])
        self.assertEqual(
            (entry["agent"]["provider"], entry["agent"]["model"]), ("ollama", MODEL)
        )


# --- The operator CLI -------------------------------------------------------------


class RunCliTests(RunCase):
    """T024 [AC-019, AC-020, AC-021]."""

    def gated(self, *extra: str) -> tuple[int, str, str]:
        return self.main(
            "start",
            *extra,
            "-i",
            "idea=Issue #27: demo",
            "-i",
            f"feature_directory={FEATURE}",
        )

    def setting(self, run_id: str) -> dict | None:
        path = fallback.setting_path(self.root, run_id)
        return json.loads(path.read_text()) if path.exists() else None

    def test_start_and_resume_flags(self) -> None:
        for form in (("--local-fallback", MODEL), (f"--local-fallback={MODEL}",)):
            with self.subTest(form=form):
                self.launched.clear()
                code, out, err = self.gated(*form)
                self.assertEqual(code, 0, err)
                ((_, run_id),) = self.launched
                self.assertEqual(self.setting(run_id)["model"], MODEL)
                self.assertIn(
                    f"Local fallback: on (ollama {MODEL} at 127.0.0.1:11434); turn it "
                    f"off with ballast run resume {run_id} --local-fallback off",
                    out,
                )
                (command, _) = self.launched[0]
                self.assertNotIn("--local-fallback", " ".join(command))
        code, out, err = self.main("resume", run_id, "--local-fallback", "off")
        self.assertEqual(code, 0, err)
        self.assertIn("Local fallback: off", out)
        self.assertFalse(self.setting(run_id)["enabled"])
        code, out, err = self.main("resume", run_id, "--local-fallback", "qwen3:8b")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.setting(run_id)["model"], "qwen3:8b")
        before = fallback.setting_path(self.root, run_id).read_bytes()
        self.assertEqual(self.main("resume", run_id)[0], 0)
        self.assertEqual(fallback.setting_path(self.root, run_id).read_bytes(), before)
        # A value after -i is an input value, not the option.
        self.launched.clear()
        code, out, err = self.main(
            "start",
            "-i",
            "--local-fallback=x",
            "-i",
            f"feature_directory={FEATURE}",
        )
        self.assertEqual(code, 0, err)
        ((command, other),) = self.launched
        self.assertIn("--local-fallback=x", command)
        self.assertIsNone(self.setting(other))
        self.assertNotIn("Local fallback", out)

    def test_refusals_write_nothing(self) -> None:
        cases = {
            ("--local-fallback", "-bad"): fallback.MODEL_HINT,
            ("--local-fallback", "gemma4:cloud"): "refuses cloud model gemma4:cloud",
            ("--local-fallback", MODEL, "--local-fallback", MODEL): "given twice",
            ("--local-fallback-endpoint", "http://127.0.0.1:1"): "not an option",
            ("--local-fallback-endpoint=http://x",): "not an option",
        }
        for extra, message in cases.items():
            with self.subTest(extra=extra):
                code, _, err = self.gated(*extra)
                self.assertEqual(code, 2)
                self.assertIn(message, err)
                self.assertEqual(self.launched, [])
                self.assertEqual(self.run_ids(), [])
        for extra in (("--local-fallback-endpoint", "x"), ("--local-fallback", "-x")):
            with self.subTest(resume=extra):
                code, _, err = self.main("resume", "abc123", *extra)
                self.assertEqual(code, 2)
                self.assertEqual(self.run_ids(), [])

    def test_chat_refuses_flag(self) -> None:
        code, _, err = self.main(
            "start",
            "--mode",
            "chat",
            "--local-fallback",
            MODEL,
            "-i",
            f"feature_directory={FEATURE}",
        )
        self.assertEqual(code, 2)
        self.assertIn("not available in Chat runs", err)
        with patch.object(run, "_chat_run", return_value=True):
            code, _, err = self.main("resume", "abc123", "--local-fallback", MODEL)
        self.assertEqual(code, 2)
        self.assertIn("not available in Chat runs", err)
        self.assertEqual(self.run_ids(), [])

    def test_setting_outside_checkout(self) -> None:
        environ = dict(os.environ)
        code, _, err = self.gated("--local-fallback", MODEL)
        self.assertEqual(code, 0, err)
        ((_, run_id),) = self.launched
        path = fallback.setting_path(self.root, run_id)
        self.assertTrue(path.resolve().is_relative_to(self.state.resolve()))
        self.assertFalse(path.resolve().is_relative_to(self.root.resolve()))
        with (
            patch.dict(os.environ, {"XDG_STATE_HOME": str(self.root / "state")}),
            self.assertRaises(OSError),
        ):
            fallback.write_setting(self.root, run_id, MODEL)
        self.assertNotIn("fallback", (self.root / "ballast.toml").read_text())
        self.assertEqual(dict(os.environ), environ)

    def test_opt_in_records_the_served_digest(self) -> None:
        """SEC2-002: the launcher pins the model's digest; unreachable is null."""
        for served in (DIGEST, None):
            with self.subTest(served=served):
                self.launched.clear()
                with patch.object(fallback, "served_digest", return_value=served):
                    code, out, err = self.gated("--local-fallback", MODEL)
                self.assertEqual(code, 0, err)
                ((_, run_id),) = self.launched
                self.assertEqual(self.setting(run_id)["digest"], served)
                self.assertEqual("not pinned" in out, served is None)

    def test_status_shows_setting(self) -> None:
        code, _, err = self.gated("--local-fallback", MODEL)
        self.assertEqual(code, 0, err)
        ((_, run_id),) = self.launched
        code, out, err = self.main("status", run_id)
        self.assertEqual(code, 0, err)
        self.assertIn(f"Local fallback: on (ollama {MODEL})", out)
        fallback.write_setting(self.root, run_id, None)
        self.assertIn("Local fallback: off", self.main("status", run_id)[1])
        # The engine stand-in leaves nothing to publish; only the run matters.
        self.launched.clear()
        self.start("--local-fallback", MODEL)
        ((_, auto),) = self.launched
        code, out, err = self.main("status", auto)
        self.assertEqual(code, 0, err)
        self.assertIn(f"Autonomous run {auto}", out)
        self.assertIn(f"Local fallback: on (ollama {MODEL})", out)
        fallback.setting_path(self.root, run_id).unlink()
        code, out, err = self.main("status", run_id)
        self.assertNotIn("Local fallback", out + err)


class HumanGatedMetaTests(FallbackCase):
    """T024 [AC-020]: a human-gated step's meta.json records the setting."""

    def test_human_gated_meta_records_setting(self) -> None:
        self.assertEqual(self.step().returncode, 0)
        self.assertNotIn("local_fallback", self.metas()[-1])
        self.enable()
        self.assertEqual(self.step().returncode, 0)
        self.assertTrue(self.metas()[-1]["local_fallback"])
        self.assertEqual(self.stub.requests, [])


if __name__ == "__main__":
    unittest.main()
