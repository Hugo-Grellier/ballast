# Living spec format

`docs/specs/` describes what the system does now, one Markdown file per
capability. It is authoritative for current behavior
([ADR-0027](adr/0027-spec-approval-living-specs-merge-verdict.md)). Specs state
behavior only: plans stay in issues and `docs/plans/`, decisions in ADRs,
progress on GitHub. `specs/` at the repository root is v1 history.

`tools/spec_check.py` (stdlib, `python3 -I -S`, read-only, no network) checks
this format in the fast gate and CI.

## A spec file

```markdown
# Queue admission

Covers: tools/admission.py
Covers: tools/queue/**

### Requirement: Admission
The queue SHALL admit an issue while a slot is free.

#### Scenario: Free slot
- WHEN a slot is free
- THEN the issue is admitted
- Test: tests/test_queue.py::QueueTests::test_admits
```

- The file opens with one or more `Covers: GLOB` lines, before the first
  requirement, naming the tracked paths whose behavior it describes. `*` and
  `?` stay within one directory; `**` crosses directories.
- `### Requirement: NAME` carries a statement with `SHALL`. Names are unique
  within the file.
- `#### Scenario: NAME` belongs to the requirement above it, carries a `WHEN`
  line and a `THEN` line, and one or more `Test: path::Class::method`
  references. Names are unique within the requirement.
- Any other `###` or `####` heading is a defect. `#` and `##` headings are free
  prose sections and end the current requirement. Inside a fenced code block
  (CommonMark rules: up to three spaces of indent, three or more backticks or
  tildes, closed by the same character at least as long with nothing after it)
  headings and `Covers:` lines are text. A fence left open at the end of a spec
  or delta document is refused.
- `docs/specs/` holds only flat `*.md` spec files: a subdirectory or another
  file type there is refused, by the check and by `--diff-hash`.
- A `Test:` reference names a repository-relative file and a test method
  defined directly in a top-level class of it.

## What the checker refuses

`python3 -I -S tools/spec_check.py` exits 1, one line per defect, on:

- a requirement without a name or without `SHALL`, a scenario without a name,
  outside a requirement, or without a `WHEN` and a `THEN` line;
- a scenario without a `Test:` reference, a malformed reference, or one whose
  file, class or method does not exist or lies outside the repository;
- a duplicate requirement name in a file or scenario name in a requirement;
- a file without `Covers:`, or with a `Covers:` line after a requirement;
- a tracked file (`git ls-files`) matched by the `Covers:` globs of two spec
  files. Globs that overlap only on untracked paths pass.

A repository without `docs/specs/` passes with a notice.

`--changed-from REF` also prints `uncovered: PATH` for each path changed since
`merge-base(REF, HEAD)` that no `Covers:` glob matches. It is a report, not a
refusal. `docs/specs/` is always exempt; other exemptions come only from
`Coverage-exempt: GLOB` lines in `project/workflow.md`. This report reads that
file from the working tree; the merge verdict
([#269](https://github.com/Hugo-Grellier/ballast/issues/269)) must read it from
the target branch, never the PR head, and owns its syntax, which this form
anticipates.

## The canonical delta

The approved object is the normalized delta of a change: a list of entries,
each keyed by capability file, requirement name and scenario name (none for the
requirement itself), with a change type (`added`, `modified`, `removed`), the
resulting text, and, for modified and removed entries, the base text. Removing
a requirement lists it and each of its scenarios; moving a scenario is a
removal plus an addition. Text is normalized: LF line endings, trailing
whitespace removed, wrapped lines of one paragraph joined by one space (a list
item starts a new line). `Test:` and `Covers:` lines, open questions and risk
are not part of it. The hash is SHA-256 over the JSON of the list sorted by its
keys (`sort_keys`, no whitespace, UTF-8).

`--diff-hash BASE [--head REF]` hashes the `docs/specs/` change from
`merge-base(BASE, head)` to head, the three-dot diff. `--delta-hash FILE`
hashes a delta document. Both print the same hash exactly when they describe
the same behavior change.

`--conformance BASE [--head REF] --body-file FILE` (or `--event-file` with a
GitHub `pull_request` payload) compares the `--diff-hash` of a PR with the
`Spec hash:` line of its body's `## Spec` section, which states the approved
hash. It exits 1 on drift, or when the section states two hashes, and 0 with a
notice when it states none (`pr_body.py` requires one for R1 and R2). A PR
changing no spec hashes to the empty delta's hash, so an R1/R2 PR without a
spec change needs an approved empty delta; a reviewer cannot waive it. CI runs
this as early feedback only: the body is untrusted, and the merge verdict
([#269](https://github.com/Hugo-Grellier/ballast/issues/269)) recomputes the
hash from the reviewed head and checks it against the approval itself.

## A delta document

```markdown
## Capability: docs/specs/queue.md

### Requirement: Admission

#### Modified Scenario: Full queue
Base:
- WHEN no slot is free
- THEN the issue waits
Result:
- WHEN no slot is free
- THEN the issue waits in arrival order

#### Added Scenario: Cancelled issue
- WHEN an admitted issue is cancelled
- THEN its slot is freed

## Open questions

- Ignored by the hash, as is any other `#` or `##` section.
```

- `## Capability: PATH` opens a spec file.
- `### Added|Modified|Removed Requirement: NAME` and `#### Added|Modified|Removed
  Scenario: NAME` are entries. Without the change word the heading only names
  the requirement its scenarios belong to.
- An added entry's body is its text, a removed entry's body is its base text,
  and a modified entry's body is a `Base:` block then a `Result:` block.
- A heading without a name, or an entry key (file, requirement, scenario) that
  appears twice, is refused.
