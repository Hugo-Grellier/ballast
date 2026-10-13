"""#146 T024: the standard-library per-module parallel runner."""

from __future__ import annotations

import io
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent))
import parallel

sys.path.pop(0)

PASSING = """import unittest


class Passing(unittest.TestCase):
    def test_one(self):
        self.assertTrue(True)
"""
FAILING = """import unittest


class Failing(unittest.TestCase):
    def test_one(self):
        self.fail("planted failure")
"""


class ParallelRunnerTests(unittest.TestCase):
    """Every module runs; any failure fails the run; output stays per module."""

    def setUp(self) -> None:
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.base = Path(directory.name)

    def module(self, name: str, source: str) -> str:
        path = self.base / name
        path.write_text(source)
        return str(path)

    def run_main(self, *argv: str) -> tuple[int, str]:
        out = io.StringIO()
        with redirect_stdout(out):
            code = parallel.main(list(argv))
        return code, out.getvalue()

    def test_all_passing_modules_pass(self) -> None:
        first = self.module("test_a.py", PASSING)
        second = self.module("test_b.py", PASSING)
        code, out = self.run_main("-j", "2", first, second)
        self.assertEqual(code, 0, out)
        self.assertIn("==> test_a.py: ok", out)
        self.assertIn("==> test_b.py: ok", out)
        self.assertEqual(out.count("Ran 1 test"), 2)
        self.assertIn("OK (2 modules in ", out)

    def test_one_failing_module_fails_the_run(self) -> None:
        passing = self.module("test_a.py", PASSING)
        failing = self.module("test_b.py", FAILING)
        code, out = self.run_main("-j", "2", passing, failing)
        self.assertEqual(code, 1, out)
        self.assertIn("==> test_a.py: ok", out)
        self.assertIn("==> test_b.py: FAILED (exit 1)", out)
        self.assertIn("planted failure", out)
        self.assertIn("FAILED: test_b.py (2 modules in ", out)
        # Output keeps the order the modules were given, whatever finished first.
        self.assertLess(out.index("test_a.py"), out.index("test_b.py"))

    def test_default_is_every_test_module(self) -> None:
        tests = Path(parallel.__file__).resolve().parent
        self.assertEqual(parallel.modules([]), sorted(tests.glob("test_*.py")))
        self.assertIn(tests / "test_parallel.py", parallel.modules([]))

    def test_jobs_must_be_positive(self) -> None:
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            parallel.main(["-j", "0"])
        self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
