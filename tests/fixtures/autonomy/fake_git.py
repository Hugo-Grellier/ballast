#!/usr/bin/env python3
"""Fake `git`: records argv in $FAKE_GIT_LOG, then runs the real git."""

import json
import os
import sys
from pathlib import Path

with Path(os.environ["FAKE_GIT_LOG"]).open("a", encoding="utf-8") as log:
    log.write(json.dumps(sys.argv[1:]) + "\n")
real = os.environ["FAKE_REAL_GIT"]
os.execv(real, [real, *sys.argv[1:]])  # noqa: S606 - the real git, argv as given
