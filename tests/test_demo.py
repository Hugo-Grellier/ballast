"""Demo capture (#22): a real temporary Git repository, a scripted gh, no network.

No test dispatches a real workflow: `gh` is #17's scripted `_command` fake,
extended with the Actions calls of ADR-0012, and the clock and sleep of the
bounded wait are injected.
"""

from __future__ import annotations

import copy
import io
import json
import re
import sys
import unittest
import urllib.parse
from contextlib import redirect_stderr, redirect_stdout
from datetime import timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/spec_workflow"))

import demo  # noqa: E402
import draft_pr  # noqa: E402
import ledger  # noqa: E402
import packet  # noqa: E402
import run  # noqa: E402

sys.path.insert(0, str(ROOT / "tests"))
import test_draft_pr  # noqa: E402
from test_draft_pr import FEATURE, FIXED, RUN, FakeGitHub, http, pull  # noqa: E402
from test_packet import BEGIN, END, PR, PacketCase, section_of, sha  # noqa: E402

sys.path.pop(0)

TEMPLATE = ROOT / "templates/github/workflows/ballast-demo.yml"
INPUTS = (
    "request",
    "scenario",
    "commit",
    "command",
    "video",
    "timeout_minutes",
    "retention_days",
)
REQUEST = "0123456789abcdef"
OTHER = "fedcba9876543210"
COMMAND = "npm run demo:login"
ENVIRONMENT = "Chromium 1280x720, seeded fixtures"
SCENARIO = (
    "[[demo.scenarios]]\n"
    'name = "{name}"\n'
    "command = '{command}'\n"
    'video = "demo-output/{name}.webm"\n'
    "environment = '{environment}'\n"
)
WORKFLOW = "repos/o/r/actions/workflows/ballast-demo.yml"
CONTENTS = "repos/o/r/contents/.github/workflows/ballast-demo.yml?ref="
DEMO_STAGES = frozenset({"dispatch", "runs", "jobs", "artifacts", "workflow", "blob"})
TOKEN = "ghp_" + "t" * 36


def scenario(
    name: str = "login-journey",
    command: str = COMMAND,
    environment: str = ENVIRONMENT,
) -> str:
    """One `[[demo.scenarios]]` table."""
    return SCENARIO.format(name=name, command=command, environment=environment)


def workflow_run(
    request: str,
    number: int = 11,
    *,
    head: str,
    status: str = "completed",
    conclusion: str | None = "success",
) -> dict[str, Any]:
    """One entry of the workflow's runs list."""
    return {
        "id": number,
        "display_title": f"Ballast demo {request}",
        "event": "workflow_dispatch",
        "status": status,
        "conclusion": conclusion,
        "head_sha": head,
    }


def artifact(
    request: str, number: int = 22, *, expired: bool = False
) -> dict[str, Any]:
    """One entry of a run's artifacts list."""
    return {"id": number, "name": f"ballast-demo-{request}", "expired": expired}


def job(*failed: str) -> dict[str, Any]:
    """Build a job whose steps after the validation fail in this order."""
    steps = [{"name": demo.STEP_VALIDATE, "number": 1, "conclusion": "success"}]
    steps += [
        {"name": name, "number": index, "conclusion": "failure"}
        for index, name in enumerate(failed, start=2)
    ]
    return {"id": 5, "steps": steps}


def others(count: int, head: str, start: int = 0) -> list[dict[str, Any]]:
    """List runs of other requests: never a match."""
    return [
        workflow_run(f"{index:016x}", 1000 + index, head=head)
        for index in range(start + 1, start + count + 1)
    ]


class DemoGitHub(FakeGitHub):
    """#17's scripted gh plus the Actions calls of ADR-0012."""

    def __init__(self, gh: str, git_program: str) -> None:
        """Start with an active workflow whose copies match, and no run."""
        super().__init__(gh, git_program)
        self.workflow: dict[str, Any] | None = {"state": "active"}
        self.blob: str | None = "b" * 40
        self.blobs: dict[str, str | None] = {}  # per ref, else `blob`
        self.run_pages: list[list[dict[str, Any]]] = [[]]
        self.on_runs: Any = None
        self.jobs: dict[int, list[dict[str, Any]]] = {}
        self.artifacts: dict[int, list[dict[str, Any]]] = {}
        self.dispatched: list[dict[str, Any]] = []

    @staticmethod
    def stage(argv: list[str]) -> str:  # noqa: PLR0911 - One branch per stage.
        """Name the stage of a gh argv, the demo calls first."""
        path = argv[-1]
        if "--method" in argv:
            return "dispatch"
        if f"{WORKFLOW}/runs?" in path:
            return "runs"
        if re.search(r"/actions/runs/[0-9]+/jobs\?", path):
            return "jobs"
        if re.search(r"/actions/runs/[0-9]+/artifacts\?", path):
            return "artifacts"
        if path == WORKFLOW:
            return "workflow"
        if path.startswith(CONTENTS):
            return "blob"
        return FakeGitHub.stage(argv)

    def serve(self, argv: list[str], stdin: str | None) -> draft_pr.Result:  # noqa: PLR0911
        stage = self.stage(argv)
        if stage not in DEMO_STAGES:
            return super().serve(argv, stdin)
        if stage in self.failures:
            return self.failures[stage]
        path = argv[-1]
        if stage == "dispatch":
            self.dispatched.append(json.loads(stdin or "null"))
            return draft_pr.Result(0)
        if stage == "workflow":
            return self.ok(self.workflow) if self.workflow is not None else http(404)
        if stage == "blob":
            ref = urllib.parse.unquote(path.removeprefix(CONTENTS))
            blob = self.blobs.get(ref, self.blob)
            return self.ok({"type": "file", "sha": blob}) if blob else http(404)
        if stage == "runs":
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(path).query)
            page = int(query["page"][0])
            if self.on_runs is not None:
                self.on_runs(page)
            pages = self.run_pages
            entries = pages[page - 1] if page <= len(pages) else []
            return self.ok(
                {"total_count": len(entries), "workflow_runs": copy.deepcopy(entries)}
            )
        number = int(re.search(r"/actions/runs/([0-9]+)/", path).group(1))
        if stage == "jobs":
            return self.ok({"jobs": self.jobs.get(number, [])})
        return self.ok({"artifacts": self.artifacts.get(number, [])})


class DemoCase(PacketCase):
    """T002: a feature with an open Draft PR, one declared scenario, fake Actions."""

    def setUp(self) -> None:
        with patch.object(test_draft_pr, "FakeGitHub", DemoGitHub):
            super().setUp()
        self.configure(scenario())
        self.clock = [0.0]

        def sleep(seconds: float) -> None:
            self.clock[0] += seconds

        self.enterContext(patch.object(demo, "_monotonic", lambda: self.clock[0]))
        self.sleep = self.enterContext(patch.object(demo, "_sleep", side_effect=sleep))

    def configure(self, *tables: str, demo_table: str = "") -> None:
        """Write the protected ballast.toml with a `[demo]` table, or none."""
        text = '[github]\nrepository = "o/r"\n'
        if tables or demo_table:
            text += "\n[demo]\n" + demo_table + "\n" + "\n".join(tables)
        (self.root / "ballast.toml").write_text(text)

    def capture(self, request: str = REQUEST, **fields: object) -> None:
        """Append a `demo_capture` event as `ballast run demo` writes it.

        `fields` may set `name`, `commit`, `command` and `observed` (a datetime).
        """
        observed = fields.get("observed", FIXED - timedelta(hours=1))
        event = ledger.new_event(
            RUN,
            FEATURE,
            "demo_capture",
            "runner",
            {
                "scenario": fields.get("name", "login-journey"),
                "commit": fields.get("commit") or self.head,
                "request": request,
                "command_digest": sha(str(fields.get("command", COMMAND))),
                "pr_number": PR,
            },
        )
        event["observed_at"] = observed.isoformat()
        ledger.append(self.root, event)

    def lines(self) -> list[str]:
        """Return the demo section's lines from a direct packet collect."""
        return demo.lines(self.collect().demo, 1)

    def line(self, name: str = "login-journey") -> str:
        (found,) = [line for line in self.lines() if line.startswith(f"- {name}")]
        return found

    def label(self, name: str = "login-journey") -> str:
        return f"- {name} ({ENVIRONMENT}): "

    def job_link(self, number: int = 11) -> str:
        return f"[job](https://github.com/o/r/actions/runs/{number})"

    def reproduce(self, command: str = COMMAND) -> str:
        return f"reproduce: `{command}`"

    def captures(self) -> list[dict[str, Any]]:
        events, problems = ledger.read(self.root, RUN)
        self.assertEqual(problems, [])
        return [e["data"] for e in events if e["kind"] == "demo_capture"]

    def main(self, *args: str) -> tuple[int, str]:
        """`ballast run demo RUN_ID ...` through run.py, as the operator runs it."""
        out = io.StringIO()
        with (
            patch.object(run, "ROOT", self.root),
            redirect_stdout(out),
            redirect_stderr(io.StringIO()),
        ):
            status = run.main(["demo", RUN, *args])
        return status, out.getvalue()

    def request(self, *, wait: bool = False) -> demo.DemoOutcome:
        return demo.request(self.root, RUN, "login-journey", wait=wait)

    def requested(self) -> str:
        """Return the request ID of the last dispatch."""
        return self.fake.dispatched[-1]["inputs"]["request"]

    def runs_before_refresh(self) -> int:
        """Runs-list reads between the request's checkpoint and its refresh."""
        calls = self.fake.gh_calls()
        lists = [i for i, argv in enumerate(calls) if self.fake.stage(argv) == "pulls"]
        self.assertEqual(len(lists), 2)  # the checkpoint and exactly one refresh
        return sum(self.fake.stage(argv) == "runs" for argv in calls[: lists[1]])

    def demo_section(self, text: str) -> str:
        start = text.index("### Demo captures")
        return text[start : text.index("### Sources", start)]

    def assertNoDispatch(self) -> None:  # noqa: N802
        self.assertEqual(self.fake.gh_calls("dispatch"), [])
        self.assertEqual(self.captures(), [])
        self.assertEqual(self.fake.gh_calls("create"), [])


class RequestTests(DemoCase):
    """US1: a request dispatches on the feature branch, records it, refreshes."""

    def test_request_follows_adr_0012_on_the_feature_branch(self) -> None:
        """T007 (Q1) [AC-001, AC-010, AC-019]."""
        status, out = self.main("login-journey", "--no-wait")
        self.assertEqual(status, 0, out)
        first, draft, acceptance = out.splitlines()
        queued = "Demo capture: in progress (queued) login-journey at "
        self.assertEqual(first, queued + self.head[:12])
        self.assertEqual(draft, f"Draft PR: reused #{PR} https://github.com/o/r/pull/7")
        self.assertTrue(acceptance.startswith("Acceptance packet: "))
        calls = self.fake.gh_calls()
        (dispatch,) = self.fake.gh_calls("dispatch")
        self.assertEqual(
            dispatch,
            [
                self.fake.gh,
                "api",
                "--method",
                "POST",
                f"{WORKFLOW}/dispatches",
                "--input",
                "-",
            ],
        )
        index = calls.index(dispatch)
        self.assertEqual(
            calls[index - 5 : index],
            [
                [self.fake.gh, "api", path]
                for path in (
                    f"repos/o/r/pulls/{PR}",
                    "repos/o/r",
                    WORKFLOW,
                    CONTENTS + self.head,
                    CONTENTS + "main",
                )
            ],
        )
        (body,) = self.fake.dispatched
        self.assertEqual(body["ref"], "feat-x")
        self.assertNotEqual(body["ref"], "main")
        self.assertRegex(body["inputs"]["request"], r"^[0-9a-f]{16}$")
        self.assertEqual(
            body["inputs"],
            {
                "request": body["inputs"]["request"],
                "scenario": "login-journey",
                "commit": self.head,
                "command": COMMAND,
                "video": "demo-output/login-journey.webm",
                "timeout_minutes": "15",
                "retention_days": "14",
            },
        )
        self.assertTrue(all(isinstance(v, str) for v in body["inputs"].values()))
        self.assertEqual(
            self.captures(),
            [
                {
                    "scenario": "login-journey",
                    "commit": self.head,
                    "request": body["inputs"]["request"],
                    "command_digest": sha(COMMAND),
                    "pr_number": PR,
                }
            ],
        )
        events, _ = ledger.read(self.root, RUN)
        kinds = [event["kind"] for event in events]
        position = kinds.index("demo_capture")
        self.assertIn("pull_request", kinds[:position])
        self.assertIn("pull_request", kinds[position:])
        self.assertEqual(self.fake.gh_calls("create"), [])

    def test_repeated_request_shows_the_newer_one_in_one_section(self) -> None:
        """T012 (Q6) [AC-006, SC-003]."""
        self.capture(REQUEST)
        self.capture(OTHER)
        self.fake.run_pages = [
            [
                workflow_run(REQUEST, 11, head=self.head),
                workflow_run(OTHER, 12, head=self.head),
            ]
        ]
        self.fake.artifacts = {11: [artifact(REQUEST, 21)], 12: [artifact(OTHER, 22)]}
        for _ in range(2):
            outcome, text = self.packet()
            self.assertEqual(outcome.state, "reused")
        self.assertIn("/actions/runs/12/artifacts/22", text)
        self.assertNotIn("/actions/runs/11", text)
        body = self.body
        self.assertEqual((body.count(BEGIN), body.count(END)), (1, 1))
        self.assertEqual(body.count("### Demo captures"), 1)
        self.assertTrue(self.fake.gh_calls("edit"))
        self.assertEqual(self.fake.gh_calls("create"), [])

    def test_wait_stops_when_the_run_completes(self) -> None:
        """T013 (Q20) [FR-009]: completes on the third poll."""
        polls: list[int] = []

        def on_runs(page: int) -> None:
            polls.append(page)
            done = len(polls) >= 3  # noqa: PLR2004
            request = self.requested()
            self.fake.run_pages = [
                [
                    workflow_run(
                        request,
                        head=self.head,
                        status="completed" if done else "in_progress",
                        conclusion="success" if done else None,
                    )
                ]
            ]
            self.fake.artifacts = {11: [artifact(request)]}

        self.fake.on_runs = on_runs
        outcome = self.request(wait=True)
        self.assertEqual((outcome.state, outcome.reason), ("captured", None))
        video = "https://github.com/o/r/actions/runs/11/artifacts/22"
        self.assertEqual(outcome.link, video)
        self.assertEqual(self.runs_before_refresh(), 3)
        self.assertEqual(self.sleep.call_count, 3)

    def test_wait_is_bounded_then_refreshes_once(self) -> None:
        """T013 (Q20) [FR-009]: a run that never completes."""

        def on_runs(_: int) -> None:
            self.fake.run_pages = [
                [
                    workflow_run(
                        self.requested(),
                        head=self.head,
                        status="in_progress",
                        conclusion=None,
                    )
                ]
            ]

        self.fake.on_runs = on_runs
        outcome = self.request(wait=True)
        self.assertEqual((outcome.state, outcome.reason), ("in progress", "running"))
        self.assertEqual(outcome.link, "https://github.com/o/r/actions/runs/11")
        self.assertLessEqual(self.runs_before_refresh(), 12)
        self.assertEqual(self.clock[0], demo.WAIT_SECONDS)
        for argv in self.fake.gh_calls("runs"):
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(argv[-1]).query)
            self.assertEqual(query["page"], ["1"])

    def test_no_wait_reads_no_run_list_before_the_refresh(self) -> None:
        """T013 (Q20) [FR-009]: `--no-wait`."""
        self.request(wait=False)
        self.assertEqual(self.runs_before_refresh(), 0)
        self.sleep.assert_not_called()


class PacketLineTests(DemoCase):
    """US1: each scenario's newest capture as one packet line."""

    def test_captured_line_links_the_video(self) -> None:
        """T008 (Q2) [AC-002, AC-007]."""
        self.capture()
        self.fake.run_pages = [[workflow_run(REQUEST, head=self.head)]]
        self.fake.artifacts = {11: [artifact(REQUEST)]}
        self.assertEqual(
            self.line(),
            self.label() + f"captured at `{self.head[:12]}` · "
            "[video](https://github.com/o/r/actions/runs/11/artifacts/22) · "
            + self.reproduce(),
        )
        self.assertEqual(self.lines()[2], demo.INTRO)

    def test_stale_captures_show_their_commit_and_never_the_video(self) -> None:
        """T009 (Q3) [AC-003]."""
        old = self.base_sha
        self.capture(commit=old)
        cases = {
            "captured": ("success", [], [artifact(REQUEST)]),
            "failed (command-failed)": ("failure", [job(demo.STEP_FAILED)], []),
            "missing (artifact-absent)": ("success", [], []),
        }
        for state, (conclusion, jobs, artifacts) in cases.items():
            with self.subTest(state=state):
                self.fake.run_pages = [
                    [workflow_run(REQUEST, head=old, conclusion=conclusion)]
                ]
                self.fake.jobs = {11: jobs}
                self.fake.artifacts = {11: artifacts}
                line = self.line()
                self.assertEqual(
                    line,
                    self.label() + f"stale ({state} at `{old[:12]}`; head is "
                    f"`{self.head[:12]}`) · {self.job_link()} · " + self.reproduce(),
                )
                self.assertNotIn("[video]", line)

    def test_in_progress_queued_and_run_not_found(self) -> None:
        """T010 (Q4) [AC-004]."""
        self.capture()
        running = workflow_run(
            REQUEST, head=self.head, status="in_progress", conclusion=None
        )
        self.fake.run_pages = [[running]]
        self.assertEqual(
            self.line(),
            self.label() + f"in progress (running) at `{self.head[:12]}` · "
            f"{self.job_link()} · " + self.reproduce(),
        )
        self.fake.run_pages = [[workflow_run(REQUEST, head=self.head)]]
        self.fake.artifacts = {11: [artifact(REQUEST)]}
        self.assertIn("captured at", self.line())
        self.fake.run_pages = [[]]
        self.assertEqual(
            self.line(),
            self.label()
            + f"in progress (queued) at `{self.head[:12]}` · "
            + self.reproduce(),
        )

    def test_no_run_after_24_hours_is_run_not_found(self) -> None:
        """T010 (Q4) [AC-004]."""
        self.capture(observed=FIXED - timedelta(hours=25))
        self.assertIn("failed (run-not-found) at", self.line())

    def test_run_list_pages_are_bounded(self) -> None:
        """T010 (Q23) [AC-004, plan review F-003]."""
        self.capture()
        self.fake.run_pages = [
            others(100, self.head),
            others(100, self.head, 100),
            [workflow_run(REQUEST, head=self.head)],
        ]
        self.fake.artifacts = {11: [artifact(REQUEST)]}
        self.assertIn("captured at", self.line())
        self.assertEqual(len(self.fake.gh_calls("runs")), 3)
        self.fake.calls.clear()
        self.fake.run_pages = [others(100, self.head, 100 * n) for n in range(6)]
        self.assertIn("failed (run-list-truncated) at", self.line())
        self.assertEqual(len(self.fake.gh_calls("runs")), demo.PAGE_LIMIT)

    def test_run_list_window_and_filters(self) -> None:
        """T010 (Q23) [AC-004]: the older of the scenarios' newest dates."""
        self.configure(scenario(), scenario("checkout", "npm run demo:checkout"))
        older = FIXED - timedelta(days=3)
        self.capture(observed=FIXED - timedelta(hours=1))
        self.capture(
            OTHER, name="checkout", command="npm run demo:checkout", observed=older
        )
        self.lines()
        (argv,) = self.fake.gh_calls("runs")
        self.assertEqual(argv[:2], [self.fake.gh, "api"])
        self.assertNotIn("--paginate", argv)
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(argv[-1]).query)
        self.assertEqual(query["branch"], ["feat-x"])
        self.assertEqual(query["event"], ["workflow_dispatch"])
        self.assertEqual(query["created"], [f">={older.date().isoformat()}"])
        self.assertEqual(query["per_page"], ["100"])

    def test_hostile_project_text_is_inert(self) -> None:
        """T014 (Q18) [FR-018]."""
        environment = (
            "<!-- ballast:acceptance-packet:end --> [x](javascript:x) @user #12 `b` $x$"
        )
        token = "ghp_" + "a" * 36
        command = (
            'echo "<!-- ballast:acceptance-packet:begin -->" [x](javascript:x) '
            f"@user #12 `b` $x$ approved by the operator {token} <!-- workflow-x "
            "> demo-output/login-journey.webm"
        )
        self.configure(scenario(command=command, environment=environment))
        self.capture(command=command)
        self.fake.run_pages = [[workflow_run(REQUEST, head=self.head)]]
        self.fake.artifacts = {11: [artifact(REQUEST)]}
        _, text = self.packet()
        body = self.body
        self.assertEqual((body.count(BEGIN), body.count(END)), (1, 1))
        section = self.demo_section(text)
        self.assertNotIn("<!--", section)
        self.assertNotIn(token, body)
        self.assertNotIn("approved by the operator", body)
        # DEC-0002: the command is a code span, where GitHub renders no markup;
        # outside the code spans nothing can link, mention or format.
        span = self.reproduce(
            'echo "<!\u200b-- ballast:acceptance-packet:begin -->" [x](javascript:x) '
            "@user #12 b $x$ a\u200bpproved by the operator [redacted] "
            "<!\u200b-- workflow-x > demo-output/login-journey.webm"
        )
        self.assertIn(span, section)
        prose = section.replace(span, "")
        for raw in ("@user", "#12", "$", "](javascript"):
            self.assertNotIn(raw, prose)
        links = re.findall(r"\]\(([^)]*)\)", prose)
        self.assertEqual(links, ["https://github.com/o/r/actions/runs/11/artifacts/22"])


class TemplateTests(unittest.TestCase):
    """T020 (Q7) [AC-008, AC-017, SC-005]: the copy-once capture workflow."""

    def test_template_shape(self) -> None:
        text = TEMPLATE.read_text(encoding="utf-8")
        data = yaml.safe_load(text)
        triggers = data.get("on", data.get(True))  # YAML 1.1 reads `on` as true
        self.assertEqual(list(triggers), ["workflow_dispatch"])
        inputs = triggers["workflow_dispatch"]["inputs"]
        self.assertEqual(set(inputs), set(INPUTS))
        for name, spec in inputs.items():
            with self.subTest(input=name):
                self.assertEqual((spec["type"], spec["required"]), ("string", True))
        self.assertEqual(data["run-name"], "Ballast demo ${{ inputs.request }}")
        self.assertEqual(data["permissions"], {"contents": "read"})
        self.assertNotIn("secrets.", text)
        self.assertNotIn("environment:", text)
        (job_spec,) = data["jobs"].values()
        self.assertNotIn("permissions", job_spec)
        self.assertIs(type(job_spec["timeout-minutes"]), int)
        self.assertEqual(job_spec["timeout-minutes"], 65)
        steps = job_spec["steps"]
        for step in steps:
            self.assertNotIn("${{", step.get("run", ""), step.get("name"))
        names = [step.get("name") for step in steps]
        fixed = [name for name in names if name in demo.STEPS]
        self.assertEqual(fixed, list(demo.STEPS))
        command = steps[names.index(demo.STEP_RUN)]
        self.assertIn('timeout --kill-after=30s "${TIMEOUT}m"', command["run"])
        self.assertEqual(command["env"]["TIMEOUT"], "${{ inputs.timeout_minutes }}")
        validate = steps[names.index(demo.STEP_VALIDATE)]
        self.assertIn('[[ $GITHUB_SHA == "$COMMIT" ]]', validate["run"])
        self.assertEqual(validate["env"]["COMMIT"], "${{ inputs.commit }}")
        uses = [step["uses"] for step in steps if "uses" in step]
        self.assertEqual(
            [use.split("@")[0] for use in uses],
            ["actions/checkout", "actions/upload-artifact"],
        )
        for use in uses:
            self.assertRegex(use.split("@")[1], r"^[0-9a-f]{40}$")
        self.assertNotIn("actions/cache", text)
        for step in steps:
            self.assertNotIn("cache", step.get("with", {}))
        checkout = next(s for s in steps if s.get("uses", "").startswith("actions/c"))
        self.assertEqual(
            checkout["with"],
            {
                "ref": "${{ inputs.commit }}",
                "persist-credentials": False,
                "fetch-depth": 1,
            },
        )
        self.assertLess(names.index(demo.STEP_VALIDATE), steps.index(checkout))
        self.assertLess(steps.index(checkout), names.index(demo.STEP_RUN))
        upload = steps[-1]
        self.assertTrue(upload["uses"].startswith("actions/upload-artifact@"))
        self.assertEqual(upload["with"]["name"], "ballast-demo-${{ inputs.request }}")
        self.assertEqual(upload["with"]["path"], "${{ inputs.video }}")
        self.assertEqual(
            upload["with"]["retention-days"], "${{ inputs.retention_days }}"
        )
        self.assertEqual(upload["with"]["if-no-files-found"], "error")


class WorkflowIdentityTests(DemoCase):
    """US2: the definition that runs is the default branch's (DEC-0001)."""

    def test_differing_or_absent_head_copy_is_refused(self) -> None:
        """T021 (Q21) [AC-010]."""
        for blob in ("c" * 40, None):
            with self.subTest(blob=blob):
                self.fake.blobs = {self.head: blob}
                status, out = self.main("login-journey", "--no-wait")
                self.assertEqual(status, 1)
                self.assertEqual(
                    out.splitlines()[0],
                    "Demo capture: refused (workflow-differs): the feature branch's "
                    ".github/workflows/ballast-demo.yml is missing or differs from "
                    "the default branch's; sync the branch with the default branch, "
                    "then request again",
                )
                self.assertNoDispatch()

    def test_run_at_another_commit_is_commit_mismatch(self) -> None:
        """T022 (Q22) [AC-010, SC-002]."""
        self.capture()
        self.fake.run_pages = [[workflow_run(REQUEST, head="f" * 40)]]
        self.fake.artifacts = {11: [artifact(REQUEST)]}
        line = self.line()
        self.assertEqual(
            line,
            self.label() + f"failed (commit-mismatch) at `{self.head[:12]}` · "
            f"{self.job_link()} · " + self.reproduce(),
        )
        self.assertNotIn("[video]", line)
        self.assertEqual(self.fake.gh_calls("artifacts"), [])

    def test_reproduce_names_the_declared_command(self) -> None:
        """T023 [AC-007]."""
        self.configure(scenario(), scenario("checkout", "npm run demo:checkout"))
        self.capture(command="npm run demo:old")
        lines = [line for line in self.lines() if line.startswith("- ")]
        self.assertEqual(len(lines), 2)
        self.assertTrue(
            lines[0].endswith(
                f"{self.reproduce()} (declared command changed since this capture)"
            )
        )
        self.assertTrue(lines[1].endswith(self.reproduce("npm run demo:checkout")))

    def test_reproduce_shows_shell_syntax_as_declared(self) -> None:
        """DEC-0002 [AC-007, SC-004]: a code span needs no Markdown escaping."""
        command = (
            "npm run demo_login > out.webm && echo $HOME #1 *b* [c](d) | "
            "curl https://www.example.test/a?b=1&c=2 @me ~x~ !y (z) \\w"
        )
        self.configure(scenario(command=command))
        self.capture(command=command)
        (line,) = [line for line in self.lines() if line.startswith("- ")]
        self.assertTrue(line.endswith(self.reproduce(command)), line)


class FailureTests(DemoCase):
    """US3: failures and missing videos read as missing evidence."""

    def outcome_line(
        self, conclusion: str, jobs: list[dict[str, Any]], arts: list[dict[str, Any]]
    ) -> str:
        entry = workflow_run(REQUEST, head=self.head, conclusion=conclusion)
        self.fake.run_pages = [[entry]]
        self.fake.jobs = {11: jobs}
        self.fake.artifacts = {11: arts}
        return self.line()

    def test_failure_causes_from_step_names(self) -> None:
        """T027 (Q9) [AC-011]."""
        self.capture()
        invalid = {
            "id": 5,
            "steps": [
                {"name": demo.STEP_VALIDATE, "number": 1, "conclusion": "failure"}
            ],
        }
        cases = (
            ("failure", [job(demo.STEP_FAILED)], "command-failed"),
            ("failure", [job(demo.STEP_TIMED_OUT)], "timed-out"),
            ("cancelled", [job()], "cancelled"),
            ("timed_out", [job()], "timed-out"),
            ("failure", [job("Some project step")], "job-failed"),
            ("failure", [invalid], "request-invalid"),
        )
        for conclusion, jobs, reason in cases:
            with self.subTest(conclusion=conclusion, reason=reason):
                line = self.outcome_line(conclusion, jobs, [artifact(REQUEST)])
                self.assertEqual(
                    line,
                    self.label() + f"failed ({reason}) at `{self.head[:12]}` · "
                    f"{self.job_link()} · " + self.reproduce(),
                )
        self.assertEqual(self.fake.gh_calls("artifacts"), [])
        for argv in self.fake.gh_calls():
            self.assertNotIn("/logs", argv[-1])
            self.assertNotIn("download", argv)

    def test_missing_videos(self) -> None:
        """T028 (Q10) [AC-012, SC-002]."""
        self.capture()
        cases = (
            ("failure", [job(demo.STEP_MISSING)], [], "no-video"),
            ("success", [], [artifact(REQUEST, expired=True)], "expired"),
            ("success", [], [artifact(OTHER)], "artifact-absent"),
        )
        for conclusion, jobs, arts, reason in cases:
            with self.subTest(reason=reason):
                line = self.outcome_line(conclusion, jobs, arts)
                self.assertEqual(
                    line,
                    self.label() + f"missing ({reason}) at `{self.head[:12]}` · "
                    f"{self.job_link()} · " + self.reproduce(),
                )
                self.assertNotIn("[video]", line)

    def test_failures_are_published_in_place(self) -> None:
        """T029 (Q11) [AC-013]."""
        outcome, _ = self.packet()
        self.assertPacket(outcome, "published")
        self.capture()
        cases = (
            ("failure", [job(demo.STEP_FAILED)], "failed (command-failed)"),
            ("success", [], "missing (artifact-absent)"),
        )
        for conclusion, jobs, state in cases:
            with self.subTest(state=state):
                self.fake.run_pages = [
                    [workflow_run(REQUEST, head=self.head, conclusion=conclusion)]
                ]
                self.fake.jobs = {11: jobs}
                outcome, text = self.packet()
                self.assertPacket(outcome, "updated")
                self.assertIn(f"{state} at", self.demo_section(text))
                self.assertEqual(section_of(self.fake.body_of("edit")), text)
        self.assertEqual(self.fake.gh_calls("create"), [])

    def test_pr_states_refuse_without_dispatch(self) -> None:
        """T030 (Q12) [AC-014]."""
        head, base = self.head, self.base_sha
        cases = {
            "no-draft-pr": [],
            "pr-not-open several": [
                pull(PR, head_sha=head, base_sha=base),
                pull(PR + 1, head_sha=head, base_sha=base),
            ],
            "pr-not-open closed": [
                pull(PR, state="closed", closed_at="2026-10-01T00:00:00Z")
            ],
            "pr-not-open merged": [
                pull(PR, state="closed", merged=True, closed_at="2026-10-01T00:00:00Z")
            ],
        }
        remedies = {
            "no-draft-pr": f"ballast run publish {RUN} opens it once the run completes",
            "pr-not-open": (
                "the Draft PR line names the cause; a capture needs an open Ballast "
                "Draft PR"
            ),
        }
        for case, prs in cases.items():
            with self.subTest(case=case):
                self.fake.prs[:] = prs
                status, out = self.main("login-journey", "--no-wait")
                self.assertEqual(status, 1)
                reason = case.split()[0]
                self.assertEqual(
                    out.splitlines()[0],
                    f"Demo capture: refused ({reason}): {remedies[reason]}",
                )
                self.assertNoDispatch()


class ContractTests(DemoCase):
    """US4: the contract and its refusals."""

    def test_absent_contract_refuses_and_the_packet_still_publishes(self) -> None:
        """T032 (Q13) [AC-015]."""
        self.configure()
        status, out = self.main("login-journey", "--no-wait")
        self.assertEqual(status, 1)
        self.assertEqual(
            out,
            "Demo capture: refused (not-configured): declare [demo] with a scenario "
            "in ballast.toml, then run ballast trust\n",
        )
        self.assertEqual(self.fake.gh_calls(), [])
        outcome, text = self.packet()
        self.assertPacket(outcome, "published")
        self.assertIn("### Demo captures\n\nDemo captures: not configured.\n", text)

    def test_invalid_contract_names_a_fixed_reason(self) -> None:
        """T033 (Q14) [AC-016]."""
        errors = demo.ERRORS
        many = [scenario(f"s{index}") for index in range(21)]
        video = "demo-output/login-journey.webm"
        cases: list[tuple[tuple[str, ...], str, str | None]] = [
            ((scenario(),), "foo = 1\n", errors["key"]),
            ((scenario().replace(video, "../x"),), "", errors["video"]),
            ((scenario().replace(video, "/etc/x"),), "", errors["video"]),
            ((scenario(), scenario()), "", errors["unique"]),
            ((scenario("a" * 64),), "", None),
            ((scenario("a" * 65),), "", errors["name"]),
            ((scenario(command="x" * 1000),), "", None),
            ((scenario(command="x" * 1001),), "", errors["command"]),
            ((scenario(environment="e" * 80),), "", None),
            ((scenario(environment="e" * 81),), "", errors["environment"]),
            (tuple(many[:20]), "", None),
            (tuple(many), "", errors["scenarios"]),
            ((), "retention_days = 14\n", errors["scenarios"]),
        ]
        for key, low, high, error in (
            ("retention_days", 1, 90, errors["retention"]),
            ("timeout_minutes", 1, 60, errors["timeout"]),
        ):
            cases += [
                ((scenario(),), f"{key} = {low}\n", None),
                ((scenario(),), f"{key} = {high}\n", None),
                ((scenario(),), f"{key} = {low - 1}\n", error),
                ((scenario(),), f"{key} = {high + 1}\n", error),
                ((scenario(),), f'{key} = "{low}"\n', error),
            ]
        for tables, table, error in cases:
            with self.subTest(table=table, tables=len(tables), error=error):
                self.configure(*tables, demo_table=table)
                config = demo.demo_config(self.root)
                self.assertEqual(config.error, error)
                self.assertTrue(config.configured)
                if error is None:
                    continue
                self.assertEqual(config.scenarios, ())
                outcome = self.request()
                self.assertEqual(
                    (outcome.state, outcome.reason), ("refused", "config-invalid")
                )
                self.assertEqual(
                    outcome.remedy, f"fix [demo] ({error}), then run ballast trust"
                )
        self.assertNoDispatch()
        self.configure(scenario(), demo_table="foo = 1\n")
        outcome, text = self.packet()
        self.assertPacket(outcome, "published")
        self.assertIn(f"Demo captures: configuration invalid ({errors['key']}).", text)
        self.assertIn("### Sources", text)

    def test_undeclared_scenario_names_the_declared_ones(self) -> None:
        """T033 (Q14) [AC-016]."""
        self.configure(scenario(), scenario("checkout"))
        status, out = self.main("search", "--no-wait")
        self.assertEqual(status, 1)
        self.assertEqual(
            out,
            "Demo capture: refused (unknown-scenario): declared scenarios: "
            "login-journey, checkout\n",
        )
        self.assertNoDispatch()

    def test_defaults_and_overrides_reach_the_dispatch(self) -> None:
        """T034 (Q15) [AC-017]."""
        self.request()
        self.configure(
            scenario(), demo_table="retention_days = 30\ntimeout_minutes = 45\n"
        )
        self.request()
        self.assertEqual(
            [
                (body["inputs"]["retention_days"], body["inputs"]["timeout_minutes"])
                for body in self.fake.dispatched
            ],
            [("14", "15"), ("30", "45")],
        )

    def test_forge_failures_are_retryable_and_leak_no_token(self) -> None:
        """T035 (Q16) [AC-018, SC-006]."""
        failures = {
            "github-unreachable": draft_pr.Result(-1, "", TOKEN, timed_out=True),
            "gh-unauthenticated": draft_pr.Result(4, "", TOKEN),
            "gh-forbidden": draft_pr.Result(1, "", f"{TOKEN} (HTTP 403)"),
            "github-error": draft_pr.Result(1, "", f"{TOKEN} (HTTP 500)"),
        }
        unauthorized = (
            "gh-unauthenticated",
            draft_pr.Result(1, "", f"{TOKEN} (HTTP 401)"),
        )
        outputs = []
        for stage in ("repo", "pull", "workflow", "blob", "dispatch"):
            for cause, result in (*failures.items(), unauthorized):
                with self.subTest(stage=stage, cause=cause):
                    self.fake.failures = {stage: result}
                    status, out = self.main("login-journey", "--no-wait")
                    outputs.append(out)
                    self.assertEqual(status, 1)
                    first = out.splitlines()[0]
                    self.assertTrue(
                        first.startswith(f"Demo capture: failed-retryable ({cause}): "),
                        first,
                    )
                    if cause == "gh-forbidden":
                        self.assertIn("needs Actions write access", first)
        self.fake.failures = {}
        self.fake.workflow = None
        status, out = self.main("login-journey", "--no-wait")
        self.assertEqual(status, 1)
        self.assertTrue(
            out.startswith("Demo capture: refused (workflow-not-installed)")
        )
        self.fake.workflow = {"state": "disabled_manually"}
        status, out = self.main("login-journey", "--no-wait")
        self.assertEqual(status, 1)
        self.assertTrue(out.startswith("Demo capture: refused (workflow-disabled)"))
        self.assertEqual(self.captures(), [])
        records = ledger.ledger_path(self.root, RUN).read_text(encoding="utf-8")
        for text in (*outputs, records, self.body):
            self.assertIsNone(packet.TOKEN.search(text))

    def test_remaining_packet_states(self) -> None:
        """T037 (Q19) [FR-010, edge cases]."""
        self.configure(scenario(), scenario("checkout"))
        self.capture(name="old-scenario")
        lines = self.lines()
        self.assertIn("- old-scenario: no longer declared", lines)
        self.assertIn(self.label() + "not yet requested · " + self.reproduce(), lines)
        self.assertNotIn("Demo captures: not configured.", lines)
        self.capture()
        self.fake.run_pages = [
            [
                workflow_run(REQUEST, 11, head=self.head),
                workflow_run(REQUEST, 12, head=self.head),
            ]
        ]
        self.assertEqual(
            self.line(),
            self.label()
            + f"failed (run-ambiguous) at `{self.head[:12]}` · "
            + self.reproduce(),
        )


if __name__ == "__main__":
    unittest.main()
