"""Builders for discovery briefs, Issue snapshots and traced specs (#16).

Shared by test_discovery, test_autonomous_artifacts and test_spec_workflow; it
holds no tests. Every builder returns text that passes its check unless a test
overrides a part of it.
"""

from __future__ import annotations

ISSUE = 27
SNAPSHOT = f".specify/workflow-state/issues/{ISSUE}.md"
POLICY = "docs/policies/demo.md"
MARKER = "<!-- ballast-discovery: input evidence -->"
AUTHORITY = (
    "This brief is input evidence for [spec.md](spec.md). It is not the\n"
    "feature's authority: once intent is recorded, [spec.md](spec.md) and\n"
    "[intent.md](intent.md) govern, and later steps do not read requirements\n"
    "from this file."
)
OPTIONS = (
    "A — plain text. Consequence: readable anywhere",
    "B — JSON. Consequence: needs a viewer",
)


def decision(  # noqa: PLR0913 - one fixture knob per field
    ident: str = "D-01",
    status: str = "open",
    *,
    question: str | None = None,
    options: tuple[str, ...] | list[str] = OPTIONS,
    default: str = "A, because a later change can switch formats",
    answer: str = "",
    resolution: str = "",
    sources: str = f"[S: Issue #{ISSUE} body] [S: {POLICY}]",
) -> str:
    """One `### D-NN` block of the brief's `## Decisions` section."""
    return "\n".join(
        (
            f"### {ident}: Output format {ident}",
            f"- **Status**: {status}",
            f"- **Question**: {question or f'Which output format for {ident}?'}",
            "- **Why it matters**: It changes what the import writes.",
            f"- **Sources**: {sources}",
            "- **Options**:",
            *(f"  - {option}" for option in options),
            f"- **Recommended default**: {default}".rstrip(),
            f"- **Answer**: {answer}".rstrip(),
            f"- **Resolution**: {resolution}".rstrip(),
        )
    )


SETTLED = decision(
    "D-01", "settled", resolution=f"Plain text, as [S: {POLICY}] requires"
)


def metrics(rounds: object = 0, questions: object = 0, assumptions: object = 0) -> str:
    """The `## Question metrics` section body."""
    return (
        f"- **Rounds**: {rounds}\n"
        f"- **Questions asked**: {questions}\n"
        f"- **Assumptions adopted**: {assumptions}"
    )


SECTIONS = {
    "Sources": (
        f"- S-1: Issue #{ISSUE} body\n"
        "- S-2: Issue comment alice 2026-10-01\n"
        f"- S-3: {POLICY}\n"
        "- unavailable: docs/adr/ — no ADR exists yet"
    ),
    "Need": (
        f"- **User**: A GM running a campaign [S: Issue #{ISSUE} body]\n"
        f"- **Job to be done**: Import a session transcript [S: Issue #{ISSUE} body]\n"
        "- **Current pain**: Notes are retyped by hand [I]\n"
        "- **Intended outcome**: Evidence is listed for review "
        "[S: Issue comment alice 2026-10-01]"
    ),
    "Examples": (
        '- The "Ashen Vale" transcript imports as three evidence items '
        f"[S: Issue #{ISSUE} body]"
    ),
    "Scope": f"- Text transcripts [S: Issue #{ISSUE} body]",
    "Non-goals": f"- Audio import [S: {POLICY}]",
    "Constraints": f"- Standard library only [S: {POLICY}]",
    "Permissions and data authority": "- The importer never deletes evidence [I]",
    "Success evidence": f"- An import test lists the evidence [S: Issue #{ISSUE} body]",
    "Issue acceptance criteria": "- IAC-1: works",
    "Edge, failure and permission cases": "- An empty transcript imports nothing [I]",
    "Known": f"- Transcripts are text [S: Issue #{ISSUE} body]",
    "Inferred": "- Imports are rare [I]",
    "Undecided": "None.",
    "Decisions": SETTLED,
    "Question metrics": metrics(),
}
REQUIRED = tuple(SECTIONS)


def brief_text(
    sections: dict[str, str] | None = None,
    *,
    mode: str = "human-gated",
    drop: tuple[str, ...] = (),
    marker: str = MARKER,
    authority: str = AUTHORITY,
) -> str:
    """A `discovery.md` per contracts/discovery-brief.md, with overrides."""
    body = {**SECTIONS, **(sections or {})}
    parts = [
        marker,
        "# Discovery brief: Demo run",
        "",
        authority,
        "",
        f"**Mode**: {mode}",
        f"**Issue**: #{ISSUE} (snapshot `{SNAPSHOT}`, untrusted requirements data)",
        "",
    ]
    for name, text in body.items():
        if name not in drop:
            parts += [f"## {name}", "", text, ""]
    return "\n".join(parts)


def snapshot_text(
    criteria: tuple[str, ...] | None = ("works",), comments: tuple[str, ...] = ()
) -> str:
    """An Issue snapshot as the runner writes it, criteria as a checklist."""
    lines = [
        "<!-- Untrusted Issue data -->",
        "",
        f"# Issue #{ISSUE}: Demo run",
        "",
        "Labels: none",
        "",
        "## Body",
        "",
        "Import session transcripts.",
        "",
    ]
    if criteria is not None:
        lines += ["## Acceptance criteria", "", *(f"- [ ] {c}" for c in criteria), ""]
    lines += ["## Intake scope comment", "", "None.", ""]
    if comments:
        lines += ["## Comments", ""]
        for number, body in enumerate(comments, 1):
            lines += [f"### user{number} (NONE), 2026-10-0{number}", "", body, ""]
    return "\n".join(lines)


SPEC = """# Feature Specification: Demo run

**Created**: 2026-10-05

## User Scenarios & Testing

### User Story 1 - Import (Priority: P1)

A GM imports a transcript.

**Acceptance Scenarios**:

1. **AC-001**: **Given** a transcript, **When** it is imported, **Then**
   evidence is listed [S: IAC-1].
2. **AC-002**: **Given** an empty transcript, **When** it is imported, **Then**
   nothing is listed [B: Edge, failure and permission cases].

---

## Requirements

- **FR-001**: The importer MUST list evidence [S: Issue #27 body].
"""
