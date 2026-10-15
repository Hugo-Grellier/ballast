"""Orca discovery fixtures only: never start Orca or an agent in CI."""

from __future__ import annotations

import io
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import codex, orca


def status(**changes: object) -> dict:
    """Include sensitive extras to catch accidental raw publication."""
    runtime = {
        "state": "ready",
        "reachable": True,
        "appVersion": "1.4.220",
        "runtimeId": "private-runtime",
        "private": "secret-account",
        "capabilities": [*orca.CAPABILITIES, "private-capability"],
    }
    runtime.update(changes)
    return {
        "ok": True,
        "result": {"target": {"kind": "local"}, "runtime": runtime},
        "private": "/private/machine",
    }


def schema(**changes: object) -> dict:
    """Advertise routing preferences without a session validation contract."""
    value = {
        "schemaVersion": 1,
        "commands": [
            {
                "command": "orchestration worker-start",
                "flags": ["agent", "model", "effort", "terminal"],
            }
        ],
    }
    value.update(changes)
    return value


class OrcaQualificationTests(unittest.TestCase):
    """Exercise the actual entry gate with every native call replaced."""

    def setUp(self) -> None:
        self.environment = patch.dict(orca.os.environ, {}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.which = patch.object(orca.shutil, "which", return_value="/chosen/orca")
        self.which.start()
        self.addCleanup(self.which.stop)

    def inspect(
        self,
        native_status: dict | None = None,
        native_schema: dict | None = None,
        provider: str = "openai",
    ) -> dict:
        """Run discovery against serialized native fixtures."""
        values = [
            "cli guide",
            "orchestration guide",
            json.dumps(native_status or status()),
            json.dumps(native_schema or schema()),
        ]
        with patch.object(orca, "read", side_effect=values) as reads:
            result = orca.inspect(
                "selected-orca", Path.cwd(), provider, "test-model", "low"
            )
        self.assertEqual(
            [call.args[2] for call in reads.call_args_list],
            [
                ("skills", "get", "orca-cli"),
                ("skills", "get", "orchestration"),
                ("status", "--json"),
                ("agent-context", "--json"),
            ],
        )
        return result

    def test_launch_preferences_and_hold_capability_never_authorize_dispatch(
        self,
    ) -> None:
        result = self.inspect()
        self.assertEqual(result["dispatch"], "blocked")
        self.assertIsNone(result["observed"])
        self.assertFalse(result["task_started"])
        self.assertFalse(result["resources_created"])
        self.assertTrue(all(result["launch_options"].values()))
        self.assertEqual(result["verification"], "unverified")
        self.assertEqual(len(result["guide_sha256"]["orca-cli"]), 64)
        self.assertNotIn("private", json.dumps(result))
        self.assertNotIn("secret-account", json.dumps(result))

    def test_future_version_and_unknown_capabilities_do_not_auto_enable(self) -> None:
        self.assertEqual(
            self.inspect(status(appVersion="99.0.0"))["dispatch"], "blocked"
        )

    def test_requested_provider_is_explicit_and_never_inferred(self) -> None:
        result = self.inspect(provider="anthropic")
        self.assertEqual(result["requested"]["provider"], "anthropic")
        self.assertIsNone(result["observed"])
        self.assertEqual(result["dispatch"], "blocked")

    def test_missing_routing_options_remain_unverified(self) -> None:
        result = self.inspect(native_schema=schema(commands=[]))
        self.assertFalse(any(result["launch_options"].values()))
        self.assertEqual(result["dispatch"], "blocked")

    def test_ci_remote_and_bad_routes_refuse_before_native_calls(self) -> None:
        environments = [{marker: "true"} for marker in codex.CI_MARKERS]
        environments += [
            {"ORCA_ENVIRONMENT": "remote"},
            {"ORCA_PAIRING_CODE": "private-code"},
        ]
        for environment in environments:
            with (
                self.subTest(environment=next(iter(environment))),
                patch.dict(orca.os.environ, environment, clear=True),
                patch.object(orca, "read") as read,
            ):
                with self.assertRaises(codex.QualificationError):
                    orca.inspect(
                        "selected-orca", Path.cwd(), "openai", "test-model", "low"
                    )
                read.assert_not_called()
        for model, effort in [
            ("", "low"),
            ("test-model", ""),
            ("test-model", "inherit"),
        ]:
            with (
                self.subTest(model=model, effort=effort),
                patch.object(orca, "read") as read,
            ):
                with self.assertRaises(codex.QualificationError):
                    orca.inspect("selected-orca", Path.cwd(), "openai", model, effort)
                read.assert_not_called()

    def test_malformed_status_and_schema_fail_closed(self) -> None:
        for broken in [
            status(state="starting"),
            status(capabilities=[{}]),
            status(appVersion="private-version"),
            {"ok": False},
            {"ok": True, "result": {"target": {"kind": "remote"}}},
        ]:
            with (
                self.subTest(status=broken),
                self.assertRaises(codex.QualificationError),
            ):
                self.inspect(broken)
        for broken in [
            schema(schemaVersion=2),
            schema(commands=[None]),
            schema(
                commands=[{"command": "orchestration worker-start", "flags": "model"}]
            ),
        ]:
            with (
                self.subTest(schema=broken),
                self.assertRaises(codex.QualificationError),
            ):
                self.inspect(native_schema=broken)

    def test_read_allowlist_forbids_mutation_before_process_creation(self) -> None:
        with patch.object(orca.subprocess, "run") as run:
            with self.assertRaises(codex.QualificationError):
                orca.read("/chosen/orca", Path.cwd(), ("orchestration", "worker-start"))
            run.assert_not_called()

    def test_selected_executable_failure_never_tries_an_alternate(self) -> None:
        with (
            patch.object(orca.shutil, "which", return_value=None) as which,
            patch.object(orca, "read") as read,
        ):
            with self.assertRaises(codex.QualificationError):
                orca.inspect("missing-orca", Path.cwd(), "openai", "test-model", "low")
            which.assert_called_once_with("missing-orca")
            read.assert_not_called()

    def test_discovery_process_is_fixed_and_failures_do_not_expose_output(self) -> None:
        for result in [
            subprocess.CompletedProcess([], 1, "secret-account", "private-error"),
            subprocess.CompletedProcess([], 0, "", ""),
            subprocess.CompletedProcess([], 0, "x" * (orca.MAX_OUTPUT + 1), ""),
        ]:
            with patch.object(orca.subprocess, "run", return_value=result) as run:
                with self.assertRaises(codex.QualificationError) as raised:
                    orca.read("/chosen/orca", Path.cwd(), ("status", "--json"))
                self.assertNotIn("secret-account", str(raised.exception))
                self.assertNotIn("private-error", str(raised.exception))
                self.assertEqual(
                    run.call_args.args[0], ["/chosen/orca", "status", "--json"]
                )
                self.assertEqual(run.call_args.kwargs["timeout"], 30)
                self.assertNotIn("shell", run.call_args.kwargs)

    def test_cli_error_is_a_sanitized_block_and_never_success(self) -> None:
        args = [
            "orca.py",
            "--executable",
            "selected-orca",
            "--provider",
            "openai",
            "--model",
            "test-model",
            "--effort",
            "low",
        ]
        with (
            patch.object(orca.sys, "argv", args),
            patch.object(orca.sys, "stdout", new_callable=io.StringIO) as output,
            patch.object(
                orca,
                "inspect",
                side_effect=RuntimeError("secret-account /private/path"),
            ),
        ):
            self.assertEqual(orca.main(), 1)
            report = json.loads(output.getvalue())
        self.assertEqual(report["dispatch"], "blocked")
        self.assertFalse(report["task_started"])
        self.assertNotIn("secret-account", json.dumps(report))
        self.assertNotIn("/private/path", json.dumps(report))


if __name__ == "__main__":
    unittest.main()
