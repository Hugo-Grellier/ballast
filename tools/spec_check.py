"""Check the living specs under docs/specs/ and compute canonical delta hashes.

Read-only and offline: reads files and the local Git repository, never the
network. The format and the delta are defined in docs/spec-format.md and
ADR-0027. Exit 0 when every spec conforms, 1 on a defect, 2 on a usage error.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

SPECS = "docs/specs"
WORKFLOW = "project/workflow.md"
HEADING = re.compile(r"^(#{1,6})[ \t]+(.*?)[ \t]*$")
REQUIREMENT = re.compile(r"^Requirement:[ \t]*(.*)$")
SCENARIO = re.compile(r"^Scenario:[ \t]*(.*)$")
COVERS = re.compile(r"^Covers:[ \t]*(\S*)[ \t]*$")
EXEMPT = re.compile(r"^Coverage-exempt:[ \t]*(\S+)[ \t]*$", re.MULTILINE)
TEST = re.compile(r"^(?:[-*][ \t]+)?Test:[ \t]*(.*?)[ \t]*$")
REQUIREMENT_LEVEL = 3  # `### Requirement: NAME`
SCENARIO_LEVEL = 4  # `#### Scenario: NAME`
SHALL = re.compile(r"\bSHALL\b")
WHEN = re.compile(r"\bWHEN\b")
THEN = re.compile(r"\bTHEN\b")
ITEM = re.compile(r"^(?:[-*+]|\d+[.)])[ \t]")
DELTA_FILE = re.compile(r"^Capability:[ \t]*(\S+)$")
DELTA_ENTRY = re.compile(
    r"^(?:(Added|Modified|Removed)[ \t]+)?(Requirement|Scenario):[ \t]*(.*)$"
)
BASE_MARK = re.compile(r"^Base:[ \t]*$")
RESULT_MARK = re.compile(r"^Result:[ \t]*$")


class SpecError(Exception):
    """A spec or delta document that cannot be read as the format requires."""


def normalize(lines: list[str]) -> str:
    """Join wrapped lines of a paragraph; keep list items and paragraphs apart.

    LF only, trailing whitespace dropped, a blank line ends a paragraph and a
    list marker starts a new line, so rewrapping text never changes its hash.
    """
    blocks: list[list[str]] = []
    current: list[str] = []
    for raw in lines:
        line = raw.rstrip()
        if not line:
            if current:
                blocks.append(current)
                current = []
            continue
        stripped = line.strip()
        if current and ITEM.match(stripped):
            current.append("\n" + stripped)
        elif current:
            current.append(" " + stripped)
        else:
            current = [stripped]
    if current:
        blocks.append(current)
    return "\n\n".join("".join(block) for block in blocks)


def split_lines(text: str) -> list[str]:
    """Return the lines of text with CRLF and CR read as LF."""
    return text.replace("\r\n", "\n").replace("\r", "\n").split("\n")


def body_text(lines: list[str]) -> str:
    """Normalize a requirement or scenario body without Test: or Covers: lines."""
    kept = [
        line
        for line in lines
        if not (TEST.match(line.strip()) or COVERS.match(line.strip()))
    ]
    return normalize(kept)


def sections(text: str) -> list[tuple[int, int, str, list[str]]]:
    """Split text at headings into (line number, level, title, body lines).

    The first block is the preamble before any heading, with level 0. A `#`
    line inside a fenced code block is body text, not a heading.
    """
    out: list[tuple[int, int, str, list[str]]] = [(0, 0, "", [])]
    fenced = False
    for number, line in enumerate(split_lines(text), 1):
        fenced ^= line.lstrip().startswith(("```", "~~~"))
        heading = None if fenced else HEADING.match(line)
        if heading:
            out.append((number, len(heading.group(1)), heading.group(2), []))
        else:
            out[-1][3].append(line)
    return out


def parse_covers(text: str, name: str) -> tuple[list[str], list[str]]:
    """Return (globs, defects) of the Covers: lines that must open a spec file."""
    covers: list[str] = []
    defects: list[str] = []
    opened = False
    for number, line in enumerate(split_lines(text), 1):
        heading = HEADING.match(line)
        opened = opened or bool(heading and REQUIREMENT.match(heading.group(2)))
        cover = COVERS.match(line.strip())
        if not cover:
            continue
        if opened:
            defects.append(f"{name}:{number}: Covers: lines must open the file")
        elif not cover.group(1):
            defects.append(f"{name}:{number}: Covers: without a glob")
        else:
            covers.append(cover.group(1))
    if not covers:
        defects.append(f"{name}: no `Covers: GLOB` line")
    return covers, defects


def add_named(table: dict, name: str, value: object, where: str) -> list[str]:
    """Insert value under name; return a defect for an empty or repeated name."""
    kind = "requirement" if isinstance(value, dict) else "scenario"
    defect = []
    if not name:
        defect = [f"{where}: {kind} without a name"]
    elif name in table:
        defect = [f"{where}: duplicate {kind}: {name}"]
    table[name] = value
    return defect


def parse_spec(text: str, name: str) -> tuple[list[str], dict, list[str]]:
    """Parse one spec file into (covers, requirements, defects).

    requirements maps a name to {"lines", "scenarios": {name: lines}}.
    """
    covers, defects = parse_covers(text, name)
    requirements: dict = {}
    requirement = None
    for number, level, title, body in sections(text)[1:]:
        where = f"{name}:{number}"
        req, scen = REQUIREMENT.match(title), SCENARIO.match(title)
        if level == REQUIREMENT_LEVEL and req:
            requirement = req.group(1)
            value = {"lines": body, "scenarios": {}}
            defects += add_named(requirements, requirement, value, where)
        elif level == SCENARIO_LEVEL and scen and requirement is not None:
            scenarios = requirements[requirement]["scenarios"]
            defects += add_named(scenarios, scen.group(1), body, where)
        elif level == SCENARIO_LEVEL and scen:
            defects.append(f"{where}: scenario outside a requirement")
        elif level >= REQUIREMENT_LEVEL:
            defects.append(
                f"{where}: `###` must be `Requirement: NAME` and `####`"
                f" must be `Scenario: NAME`, found: {title}"
            )
        else:
            requirement = None
    return covers, requirements, defects


def test_tree(path: str, root: Path, cache: dict) -> ast.Module | str:
    """Return the parsed test file, or why it cannot be read."""
    if path not in cache:
        target = (root / path).resolve()
        if Path(path).is_absolute() or not target.is_relative_to(root.resolve()):
            cache[path] = f"test reference outside the repository: {path}"
        elif not target.is_file():
            cache[path] = f"test file not found: {path}"
        else:
            try:
                cache[path] = ast.parse(target.read_text(encoding="utf-8"))
            except (OSError, SyntaxError, UnicodeDecodeError) as error:
                cache[path] = f"test file unreadable: {path}: {error}"
    return cache[path]


def test_defect(reference: str, root: Path, cache: dict) -> str | None:
    """Return why a `path::Class::method` reference does not resolve, or None."""
    parts = reference.split("::")
    if len(parts) != len(("path", "Class", "method")) or not all(parts):
        return f"malformed test reference (want path::Class::method): {reference}"
    path, cls, method = parts
    tree = test_tree(path, root, cache)
    if isinstance(tree, str):
        return tree
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls]
    if not classes:
        return f"test class not found: {reference}"
    functions = (ast.FunctionDef, ast.AsyncFunctionDef)
    if any(isinstance(n, functions) and n.name == method for n in classes[0].body):
        return None
    return f"test method not found: {reference}"


def check_spec(text: str, name: str, root: Path, cache: dict) -> list[str]:
    """Return every defect of one spec file, test references included."""
    _, requirements, defects = parse_spec(text, name)
    for req_name, requirement in requirements.items():
        if not SHALL.search(body_text(requirement["lines"])):
            defects.append(f"{name}: requirement without a SHALL: {req_name}")
        for scen_name, lines in requirement["scenarios"].items():
            label = f"{name}: scenario {req_name} / {scen_name}"
            text_only = body_text(lines)
            if not (WHEN.search(text_only) and THEN.search(text_only)):
                defects.append(f"{label}: needs a WHEN line and a THEN line")
            tests = [m.group(1) for m in map(TEST.match, map(str.strip, lines)) if m]
            if not tests:
                defects.append(f"{label}: no `Test: path::Class::method` reference")
            for reference in tests:
                defect = test_defect(reference, root, cache)
                if defect:
                    defects.append(f"{label}: {defect}")
    return defects


def glob_regex(pattern: str) -> re.Pattern[str]:
    """Translate a path glob: `**` crosses directories, `*` and `?` do not."""
    out = []
    index = 0
    while index < len(pattern):
        if pattern.startswith("**/", index):
            out.append("(?:.*/)?")
            index += 3
        elif pattern.startswith("**", index):
            out.append(".*")
            index += 2
        elif pattern[index] == "*":
            out.append("[^/]*")
            index += 1
        elif pattern[index] == "?":
            out.append("[^/]")
            index += 1
        else:
            out.append(re.escape(pattern[index]))
            index += 1
    return re.compile("".join(out) + r"\Z")


def matches(path: str, globs: list[str]) -> bool:
    """Return whether any glob matches the repository-relative path."""
    return any(glob_regex(glob).match(path) for glob in globs)


def git(root: Path, *args: str) -> str:
    """Run a read-only git command in root and return its stdout."""
    result = subprocess.run(  # noqa: S603 -- fixed git argv, no shell
        ["git", "-C", str(root), *args],  # noqa: S607 -- git from PATH
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        message = f"git {' '.join(args)} failed: {result.stderr.strip()}"
        raise SpecError(message)
    return result.stdout


def tracked(root: Path) -> list[str]:
    """Return the tracked paths of the repository."""
    return [p for p in git(root, "ls-files", "-z").split("\0") if p]


def overlap_defects(covers: dict[str, list[str]], paths: list[str]) -> list[str]:
    """Return one defect per tracked path two spec files both cover."""
    defects = []
    for path in paths:
        owners = [
            name for name, globs in sorted(covers.items()) if matches(path, globs)
        ]
        if len(owners) > 1:
            defects.append(
                f"{path}: covered by more than one spec: {', '.join(owners)}"
            )
    return defects


def exempt_globs(root: Path) -> list[str]:
    """Return the coverage-exempt globs that project/workflow.md lists."""
    try:
        text = (root / WORKFLOW).read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    return EXEMPT.findall(text)


def uncovered(root: Path, base: str, covers: dict[str, list[str]]) -> list[str]:
    """Return the paths changed since merge-base(base, HEAD) that nothing covers."""
    changed = git(root, "diff", "--name-only", "-z", f"{base}...HEAD").split("\0")
    globs = [glob for spec in covers.values() for glob in spec]
    globs += [*exempt_globs(root), f"{SPECS}/**"]
    return [p for p in changed if p and not matches(p, globs)]


def check(root: Path, changed_from: str | None) -> int:
    """Validate every spec, the coverage overlap and report uncovered paths."""
    specs = root / SPECS
    if not specs.is_dir():
        sys.stderr.write(f"notice: no {SPECS}/ directory, nothing to check\n")
        return 0
    defects: list[str] = []
    covers: dict[str, list[str]] = {}
    cache: dict = {}
    names = sorted(p.relative_to(root).as_posix() for p in specs.rglob("*"))
    files = [name for name in names if (root / name).is_file()]
    stray = stray_specs(files)
    defects += [f"{name}: {SPECS}/ holds only flat *.md spec files" for name in stray]
    for name in (name for name in files if name not in stray):
        text = (root / name).read_text(encoding="utf-8")
        covers[name] = parse_spec(text, name)[0]
        defects += check_spec(text, name, root, cache)
    defects += overlap_defects(covers, tracked(root))
    for defect in defects:
        sys.stderr.write(defect + "\n")
    if changed_from:
        for path in uncovered(root, changed_from, covers):
            sys.stdout.write(f"uncovered: {path}\n")
    return 1 if defects else 0


def entry(key: tuple, change: str, text: str | None, base: str | None) -> dict:
    """Build one canonical delta entry from (file, requirement, scenario)."""
    file, requirement, scenario = key
    return {
        "file": file,
        "requirement": requirement,
        "scenario": scenario,
        "change": change,
        "text": text,
        "base": base,
    }


def spec_texts(text: str) -> dict:
    """Return {(requirement, scenario or None): normalized text} for a spec."""
    _, requirements, defects = parse_spec(text, "spec")
    structural = [d for d in defects if "Covers:" not in d]
    if structural:
        raise SpecError("; ".join(structural))
    out = {}
    for req_name, requirement in requirements.items():
        out[req_name, None] = body_text(requirement["lines"])
        for scen_name, lines in requirement["scenarios"].items():
            out[req_name, scen_name] = body_text(lines)
    return out


def diff_entries(file: str, base: str | None, head: str | None) -> list[dict]:
    """Return the delta entries between two versions of one spec file."""
    old = spec_texts(base) if base is not None else {}
    new = spec_texts(head) if head is not None else {}
    entries = []
    for key in sorted(old.keys() | new.keys(), key=lambda k: (k[0], k[1] or "")):
        if key not in old:
            entries.append(entry((file, *key), "added", new[key], None))
        elif key not in new:
            entries.append(entry((file, *key), "removed", None, old[key]))
        elif old[key] != new[key]:
            entries.append(entry((file, *key), "modified", new[key], old[key]))
    return entries


def stray_specs(names: list[str]) -> list[str]:
    """Return the paths under docs/specs/ that are not flat *.md spec files."""
    prefix = len(SPECS) + 1
    return [n for n in names if not n.endswith(".md") or "/" in n[prefix:]]


def specs_at(root: Path, revision: str) -> dict[str, str]:
    """Return {path: text} of every spec file at a revision; refuse stray files."""
    listing = git(root, "ls-tree", "-r", "-z", "--name-only", revision, f"{SPECS}/")
    names = [name for name in listing.split("\0") if name]
    stray = stray_specs(names)
    if stray:
        message = f"{SPECS}/ holds only flat *.md spec files at {revision}: {stray}"
        raise SpecError(message)
    return {name: git(root, "show", f"{revision}:{name}") for name in names}


def git_delta(root: Path, base: str, head: str) -> list[dict]:
    """Return the delta of docs/specs/ between merge-base(base, head) and head."""
    merge_base = git(root, "merge-base", base, head).strip()
    old, new = specs_at(root, merge_base), specs_at(root, head)
    entries = []
    for name in sorted(old.keys() | new.keys()):
        entries += diff_entries(name, old.get(name), new.get(name))
    return entries


def delta_entry(key: tuple, change: str, body: list[str]) -> dict:
    """Build an entry from its delta-document body (`Base:` then `Result:`)."""
    parts: dict[str, list[str]] = {"text": []}
    part = "text"
    for line in body:
        if BASE_MARK.match(line.strip()):
            part = "base"
        elif RESULT_MARK.match(line.strip()):
            part = "text"
        else:
            parts.setdefault(part, []).append(line)
    text = body_text(parts["text"])
    base = body_text(parts["base"]) if "base" in parts else None
    if change == "added":
        return entry(key, change, text, None)
    if change == "removed":
        return entry(key, change, None, text if base is None else base)
    if base is None:
        message = f"modified entry without a Base: block: {key}"
        raise SpecError(message)
    return entry(key, change, text, base)


def check_key(key: tuple, title: str, seen: set, *, is_entry: bool) -> None:
    """Refuse an empty name, and an entry key the document already holds."""
    if not (key[1] if key[2] is None else key[2]):
        message = f"heading without a name: {title}"
        raise SpecError(message)
    if is_entry and key in seen:
        message = f"duplicate delta entry: {title} in {key[0]}"
        raise SpecError(message)
    if is_entry:
        seen.add(key)


def parse_delta(text: str) -> list[dict]:
    """Read a delta document into canonical entries.

    `## Capability: PATH` opens a file. `### [Added|Modified|Removed]
    Requirement: NAME` and `#### [Added|Modified|Removed] Scenario: NAME` open
    entries (no change word: context only). A modified entry's body is `Base:`
    then `Result:`; an added entry's body is its text; a removed entry's body is
    its base text. Any other `#`/`##` section (questions, risk) is ignored.
    """
    entries: list[dict] = []
    file = requirement = None
    kinds = {REQUIREMENT_LEVEL: "Requirement", SCENARIO_LEVEL: "Scenario"}
    seen: set[tuple] = set()
    for _, level, title, body in sections(text)[1:]:
        if level < REQUIREMENT_LEVEL:
            capability = DELTA_FILE.match(title)
            file = capability.group(1) if capability else None
            requirement = None
            continue
        if file is None:
            continue
        found = DELTA_ENTRY.match(title)
        if not found or found.group(2) != kinds.get(level):
            message = f"unexpected heading in a capability: {title}"
            raise SpecError(message)
        change, name = found.group(1), found.group(3)
        if level == REQUIREMENT_LEVEL:
            requirement, scenario = name, None
        elif requirement is None:
            message = f"scenario outside a requirement: {title}"
            raise SpecError(message)
        else:
            scenario = name
        key = (file, requirement, scenario)
        check_key(key, title, seen, is_entry=bool(change))
        if change:
            entries.append(delta_entry(key, change.lower(), body))
    return entries


def delta_hash(entries: list[dict]) -> str:
    """Return the SHA-256 of the canonical JSON of the sorted delta."""
    ordered = sorted(
        entries,
        key=lambda e: (e["file"], e["requirement"], e["scenario"] or "", e["change"]),
    )
    canonical = json.dumps(
        ordered, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def main(argv: list[str] | None = None) -> int:
    """Check the specs, or print a delta hash."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path())
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--changed-from",
        metavar="REF",
        help="also list paths changed since merge-base(REF, HEAD) no spec covers",
    )
    mode.add_argument(
        "--delta-hash", type=Path, metavar="FILE", help="hash a delta document"
    )
    mode.add_argument(
        "--diff-hash",
        metavar="BASE",
        help="hash the docs/specs/ change from merge-base(BASE, --head) to --head",
    )
    parser.add_argument("--head", default="HEAD")
    args = parser.parse_args(argv)
    try:
        if args.delta_hash:
            text = args.delta_hash.read_text(encoding="utf-8")
            sys.stdout.write(delta_hash(parse_delta(text)) + "\n")
            return 0
        if args.diff_hash:
            entries = git_delta(args.root, args.diff_hash, args.head)
            sys.stdout.write(delta_hash(entries) + "\n")
            return 0
        return check(args.root, args.changed_from)
    except (SpecError, OSError) as error:
        sys.stderr.write(f"{error}\n")
        return 2


if __name__ == "__main__":
    sys.exit(main())
