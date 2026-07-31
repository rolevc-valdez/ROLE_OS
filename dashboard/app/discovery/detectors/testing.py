"""Test presence: a `tests`/`test` folder, or filenames matching common
test-file conventions across Python/JS/TS. Named `testing.py` (not
`tests.py`) to avoid any ambiguity with the repo's top-level `tests/`
directory during test collection."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.discovery.detectors.inventory import FolderInventory

TEST_FILE_RE = re.compile(r"(^test_.+\.py$|.+_test\.py$|.+\.test\.[jt]sx?$|.+\.spec\.[jt]sx?$)", re.I)
TEST_DIR_NAMES = {"tests", "test"}


@dataclass
class TestingFindings:
    has_tests: bool = False
    test_file_count: int = 0


def detect(inventory: FolderInventory) -> TestingFindings:
    findings = TestingFindings()

    for d in inventory.dirs:
        if d.name_lower in TEST_DIR_NAMES:
            findings.has_tests = True

    for f in inventory.files:
        if TEST_FILE_RE.match(f.name):
            findings.has_tests = True
            findings.test_file_count += 1

    return findings
