"""Run the unittest suite with one process per test class, in parallel (#146).

`python tests/parallel.py tests/test_*.py` runs the same TestCase classes as
`python -m unittest tests/test_*.py` (each class a module defines or imports),
each in its own `python -m unittest` process, and exits 1 when any fails.
Classes keep their own setUpModule; nothing is skipped or shared.
"""

from __future__ import annotations

import importlib
import os
import re
import subprocess
import sys
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RAN = re.compile(r"^Ran (\d+) tests? in", re.MULTILINE)
SKIPPED = re.compile(r"skipped=(\d+)")


def test_classes(paths: list[str]) -> list[tuple[int, str]]:
    """Return (test count, dotted name) for every class unittest would run."""
    sys.path.insert(0, str(Path.cwd()))
    loader = unittest.TestLoader()
    found = []
    for path in paths:
        name = Path(path).with_suffix("").as_posix().replace("/", ".")
        module = importlib.import_module(name)
        for attribute, value in sorted(vars(module).items()):
            if isinstance(value, type) and issubclass(value, unittest.TestCase):
                count = len(loader.getTestCaseNames(value))
                if count:
                    found.append((count, f"{name}.{attribute}"))
    return found


def run(name: str) -> tuple[str, int, int, int, str, float]:
    """Run one class in its own process: name, exit, run, skipped, output, seconds."""
    started = time.monotonic()
    done = subprocess.run(  # noqa: S603 - this interpreter, a discovered class
        [sys.executable, "-m", "unittest", name],
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
    )
    ran = RAN.search(done.stderr)
    skipped = SKIPPED.search(done.stderr)
    return (
        name,
        done.returncode,
        int(ran.group(1)) if ran else 0,
        int(skipped.group(1)) if skipped else 0,
        done.stdout + done.stderr,
        time.monotonic() - started,
    )


def main(paths: list[str]) -> int:
    """Run every class of `paths`, a worker per CPU; 1 when any failed."""
    # Most tests first, so the long classes start before the short ones.
    classes = [name for _, name in sorted(test_classes(paths), reverse=True)]
    started = time.monotonic()
    failed, total, skips = [], 0, 0
    with ThreadPoolExecutor(os.cpu_count() or 1) as pool:
        for name, code, ran, skipped, output, seconds in pool.map(run, classes):
            total += ran
            skips += skipped
            if code:
                failed.append(name)
                sys.stdout.write(f"\n=== {name} (exit {code}) ===\n{output}")
            elif seconds > 60:  # noqa: PLR2004 - report the slow classes
                sys.stdout.write(f"slow: {name} {seconds:.0f}s\n")
    elapsed = time.monotonic() - started
    sys.stdout.write(
        f"\nRan {total} tests ({skips} skipped) in {len(classes)} classes "
        f"in {elapsed:.0f}s: "
        + (f"FAILED ({', '.join(failed)})\n" if failed else "OK\n")
    )
    return 1 if failed or not classes else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
