"""Run each test module in its own process, a bounded number at a time (#146).

`python -m unittest tests/test_*.py` stays the whole suite in one process and
is what CI runs. This runs the same modules, each as `python -m unittest
<module>`, in parallel, prints each module's output in order and exits 1 when
any module fails. Usage: `python tests/parallel.py [-j N] [MODULE ...]`.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JOBS = 4


def modules(paths: list[str]) -> list[Path]:
    """Return the modules to run: the given ones, or every tests/test_*.py."""
    if paths:
        return [Path(path).resolve() for path in paths]
    return sorted((ROOT / "tests").glob("test_*.py"))


def run_module(path: Path) -> tuple[str, int, str, float]:
    """Run one module as CI does, from the checkout root when it is inside it."""
    cwd = ROOT if path.is_relative_to(ROOT) else path.parent
    started = time.monotonic()
    done = subprocess.run(  # noqa: S603 - this interpreter, one test module
        [sys.executable, "-m", "unittest", str(path.relative_to(cwd))],
        cwd=cwd,
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
    )
    seconds = time.monotonic() - started
    return path.name, done.returncode, done.stdout + done.stderr, seconds


def main(argv: list[str] | None = None) -> int:
    """Run the modules and report each; non-zero when any module failed."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-j", "--jobs", type=int, default=JOBS)
    parser.add_argument("paths", nargs="*", metavar="MODULE")
    arguments = parser.parse_args(argv)
    if arguments.jobs < 1:
        parser.error("--jobs must be at least 1")
    selected = modules(arguments.paths)
    started = time.monotonic()
    failed = []
    with ThreadPoolExecutor(max_workers=arguments.jobs) as pool:
        for name, code, output, seconds in pool.map(run_module, selected):
            status = "ok" if code == 0 else f"FAILED (exit {code})"
            sys.stdout.write(f"==> {name}: {status} in {seconds:.1f} s\n{output}\n")
            if code != 0:
                failed.append(name)
    total = time.monotonic() - started
    summary = f"{len(selected)} modules in {total:.1f} s"
    if failed:
        sys.stdout.write(f"FAILED: {', '.join(failed)} ({summary})\n")
        return 1
    sys.stdout.write(f"OK ({summary})\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
