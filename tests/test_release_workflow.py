"""The release publishes the unchanged CLI and its checksum; only that job writes."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/release-please.yml"
# Runs after the upload: what the release serves is the reviewed file.
VERIFY = (
    'gh release download "$TAG" -p ballast -p ballast.sha256 -D uploaded\n'
    "cmp uploaded/ballast tools/ballast\n"
    "test \"$(cut -d' ' -f1 uploaded/ballast.sha256)\""
    " = \"$(sha256sum <uploaded/ballast | cut -d' ' -f1)\"\n"
)


class ReleaseWorkflowTests(unittest.TestCase):
    """AC-002 (build side), FR-002, FR-007."""

    def setUp(self) -> None:
        self.workflow = yaml.safe_load(WORKFLOW.read_text())
        self.jobs = self.workflow["jobs"]

    def test_default_permission_is_read_only(self) -> None:
        self.assertEqual(self.workflow["permissions"], {"contents": "read"})
        self.assertNotIn("permissions", self.jobs["release-please"])

    def test_release_please_exposes_its_outputs(self) -> None:
        job = self.jobs["release-please"]
        (step,) = [s for s in job["steps"] if "release-please-action" in s["uses"]]
        self.assertEqual(step["id"], "release")
        self.assertEqual(
            job["outputs"],
            {
                "release_created": "${{ steps.release.outputs.release_created }}",
                "tag_name": "${{ steps.release.outputs.tag_name }}",
            },
        )

    def test_publish_cli_uploads_the_unchanged_file(self) -> None:
        job = self.jobs["publish-cli"]
        self.assertEqual(job["needs"], "release-please")
        self.assertEqual(
            job["if"], "needs.release-please.outputs.release_created == 'true'"
        )
        self.assertEqual(job["permissions"], {"contents": "write"})
        checkout, *steps = job["steps"]
        self.assertTrue(checkout["uses"].startswith("actions/checkout@"))
        self.assertEqual(
            checkout["with"]["ref"], "${{ needs.release-please.outputs.tag_name }}"
        )
        commands = [step["run"] for step in steps]
        self.assertEqual(
            commands,
            [
                "cp tools/ballast ballast",
                "sha256sum ballast > ballast.sha256",
                "sha256sum -c ballast.sha256",
                'gh release upload "$TAG" ballast ballast.sha256',
                VERIFY,
            ],
        )
        # The upload and the check of what was uploaded both need the token.
        for step in steps[-2:]:
            self.assertEqual(step["env"]["GH_TOKEN"], "${{ github.token }}")
            self.assertEqual(
                step["env"]["TAG"], "${{ needs.release-please.outputs.tag_name }}"
            )

    def test_release_bumps_the_cli_and_readme_versions(self) -> None:
        config = json.loads((ROOT / "release-please-config.json").read_text())
        extra = config["packages"]["."]["extra-files"]
        self.assertIn("tools/ballast", extra)
        self.assertIn("README.md", extra)


if __name__ == "__main__":
    unittest.main()
