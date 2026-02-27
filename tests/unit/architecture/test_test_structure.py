"""Architecture guardrail: enforce canonical test directory structure.

After migration completes, this test prevents regression by ensuring
no new test files are added to legacy top-level directories.

These directories should only contain tests under tests/unit/<layer>/,
tests/integration/, tests/e2e/, etc.
"""

from __future__ import annotations

from pathlib import Path

import pytest

TESTS_ROOT = Path(__file__).parent.parent.parent  # tests/

# Legacy directories that should be emptied after migration.
# Tests in these dirs should live under tests/unit/<name>/ instead.
LEGACY_DIRS = [
    "domain",
    "io",
    "orchestration",
    "infrastructure",
    "architecture",
    "auth",
    "cli",
    "config",
]

# Canonical directories that SHOULD contain tests.
CANONICAL_DIRS = [
    "unit",
    "integration",
    "e2e",
    "slice_tests",
    "performance",
    "smoke",
]


@pytest.mark.parametrize("legacy_dir", LEGACY_DIRS)
def test_no_tests_in_legacy_directories(legacy_dir: str) -> None:
    """Legacy top-level test dirs must not contain test files.

    After migration, all unit tests should live under tests/unit/<layer>/.
    This guardrail prevents new tests from being added to the old locations.
    """
    target = TESTS_ROOT / legacy_dir
    if not target.exists():
        return  # Already cleaned up

    test_files = sorted(target.rglob("test_*.py"))
    assert len(test_files) == 0, (
        f"Legacy directory tests/{legacy_dir}/ still contains "
        f"{len(test_files)} test file(s). "
        f"Move them to tests/unit/{legacy_dir}/:\n"
        + "\n".join(f"  - {f.relative_to(TESTS_ROOT)}" for f in test_files[:10])
    )


def test_unit_subdirs_have_init_py() -> None:
    """Every subdirectory under tests/unit/ must have __init__.py.

    pytest uses __init__.py for proper test discovery and to avoid
    module name collisions between files in different directories.
    """
    unit_root = TESTS_ROOT / "unit"
    if not unit_root.exists():
        pytest.skip("tests/unit/ does not exist yet")

    missing = []
    for d in sorted(unit_root.rglob("*")):
        if not d.is_dir():
            continue
        if d.name == "__pycache__":
            continue
        if not (d / "__init__.py").exists():
            missing.append(d.relative_to(TESTS_ROOT))

    assert len(missing) == 0, (
        f"{len(missing)} directories under tests/unit/ missing __init__.py:\n"
        + "\n".join(f"  - {m}" for m in missing)
    )
