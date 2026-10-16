"""ADR numbers from 0022 on are unique; the historical 0019/0021 duplicates stay."""

from __future__ import annotations

import collections
import unittest
from pathlib import Path

ADR_DIR = Path(__file__).resolve().parent.parent / "docs" / "adr"
FIRST_UNIQUE = 22


class AdrNumberTests(unittest.TestCase):
    """Refuse two ADR files sharing a number from 0022 on."""

    def test_numbers_from_0022_are_unique(self) -> None:
        by_number = collections.defaultdict(list)
        for path in sorted(ADR_DIR.glob("[0-9][0-9][0-9][0-9]-*.md")):
            number = int(path.name[:4])
            if number >= FIRST_UNIQUE:
                by_number[number].append(path.name)
        duplicates = {n: names for n, names in by_number.items() if len(names) > 1}
        self.assertEqual(duplicates, {}, "ADR numbers must be unique from 0022 on")


if __name__ == "__main__":
    unittest.main()
