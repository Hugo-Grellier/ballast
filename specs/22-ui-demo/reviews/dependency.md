# Dependency review: 22-ui-demo

- Kind: dependency
- Reviewer: claude/claude-opus-5-5, agent-provisional, same provider as the author
- Scope: working tree against the implementation baseline. The engineering review (`implementation-review.json`) declared `dependency` in `required_kinds`; the dependency evaluation of `actions/checkout` and `actions/upload-artifact` is a workflow-owned step in `tasks.md` and `plan.md`.
- Recommendation: accept, with the pin update applied in this review

## What was reviewed

- `templates/github/workflows/ballast-demo.yml`: the only place the feature adds a third-party component.
- `tools/spec_workflow/demo.py` and the other changed tools: imports only the standard library (`contextlib`, `hashlib`, `json`, `re`, `secrets`, `time`, `tomllib`, `urllib.parse`, `dataclasses`, `datetime`, `typing`) and Ballast's own modules. No manifest, lockfile or `requirements*.txt` changed.
- Policies: `docs/policies/dependencies.md`, `docs/policies/project/dependencies.md`, constitution principle 6 (no third-party dependency in the shipped tools).

## Need and class

Both components are GitHub-maintained first-party Actions, used inside the copy-once template that projects commit. Ballast never runs or downloads them.

- `actions/checkout` checks out the requested commit. A hand-written `git fetch` would need the token that `persist-credentials: false` keeps out of the job, so the action is the simplest option here.
- `actions/upload-artifact` publishes the video as an Actions artifact, which is the only storage FR-013 allows. There is no standard-library or `gh` alternative inside a job that holds only a read-only token.

## Provenance and pinning

- Both are pinned by full 40-hex commit SHA with a version comment. `git ls-remote` against `github.com/actions/*` shows that each tag is lightweight and points at that commit.
- As implemented, the pins were `actions/checkout` v4.2.2 (`11bd719…`) and `actions/upload-artifact` v4.6.2 (`ea165f8…`). Both run on `node20`. The current releases are v7.0.1 for both (`3d3c42e5aac5ba805825da76410c181273ba90b1` and `043fb46d1a93c77aae656e7c1c64a875d1fc6a0a`), which run on `node24`. `tasks.md` asks for "the full commit SHA of their current release tag", and Ballast's own `ci.yml` already uses checkout v7.0.1. This review moved both pins to v7.0.1.
- Compatibility between v4 and v7, from the upstream release notes and the v7.0.1 `action.yml`:
  - checkout v5 moved to Node 24, and v6 stores persisted credentials in a separate file (irrelevant with `persist-credentials: false`). v7 refuses to check out fork PRs under `pull_request_target` and `workflow_run`, and the template uses neither. `ref`, `persist-credentials` and `fetch-depth` are unchanged.
  - upload-artifact v5 and v6 moved to Node 24. v7 adds `archive` (default `true`, so the artifact is still a zip and is named by `name`) and moves to ESM. `name`, `path`, `retention-days`, `if-no-files-found` and `compression-level` are unchanged.
  - Both need runner 2.327.1 or newer, which GitHub-hosted runners meet. The template targets `ubuntu-latest`.
- `tests/test_demo.py` passes after the update (26 tests). Its template test pins the action names and the SHA form, not a version.

## Maintenance, advisories, license

- Both repositories are active and not archived: upstream pushes on 2026-09-29 and 2026-10-06.
- The GitHub Advisory Database lists no advisory for either action, and neither repository publishes a security advisory. The known risk class for upload-artifact is an uploaded `.git` directory that leaks a persisted token. The template rules it out twice: `persist-credentials: false`, and an upload `path` limited to one file inside `$GITHUB_WORKSPACE`.
- Both are MIT, which is compatible with any project that copies the template.

## Footprint, privacy, exit

- The actions run only on the forge runner in a job with `contents: read` and no secrets. They add nothing to Ballast's own runtime, filesystem or process footprint.
- Privacy: the video is stored on GitHub under the repository's read access with bounded retention (1 to 90 days), as the security review and the template header already state. The scenario command, and any browser or recorder it installs, belongs to the project and is evaluated under that project's own dependency policy. Ballast pins and downloads neither.
- Exit cost is low: two `uses:` lines in a copy-once file that a project owns after copying.

## Update path

A project that copies the template to `.github/workflows/` gets SHA-pin updates from the `github-actions` entry in `templates/github/dependabot.yml`. Ballast's own source copy lives under `templates/github/workflows/`, which its Dependabot entry (`directory: "/"`, `.github/workflows` only) does not scan. Nothing therefore keeps the shipped pins current, which is how they fell three major versions behind.

Same-provider review: independence is reduced. Upstream data (tags, `action.yml`, releases, advisories, license) was read live from GitHub on 2026-10-06.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (medium, implementation-bug, resolved): The template pinned actions/checkout v4.2.2 and actions/upload-artifact v4.6.2 (node20, three majors behind) although tasks.md requires the current release tag and ci.yml already uses checkout v7.0.1. Both are now pinned to the v7.0.1 commit SHAs; inputs are unchanged and tests/test_demo.py passes.
- F-002 (low, architecture-issue, open): Dependabot scans only .github/workflows, so the shipped templates/github/workflows/ballast-demo.yml pins never get update PRs. Add the template directory to Ballast's own Dependabot config or a release-time check that template pins match their current release.
<!-- ballast-findings: end -->
