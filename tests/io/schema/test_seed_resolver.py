"""Unit tests for seed_resolver module."""

from __future__ import annotations

from pathlib import Path
from typing import Generator

import pytest


@pytest.fixture
def temp_seeds_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a temporary seeds directory with version subdirectories."""
    seeds_dir = tmp_path / "seeds"
    seeds_dir.mkdir()
    yield seeds_dir


class TestGetVersionsContainingFile:
    """Tests for get_versions_containing_file function."""

    def test_returns_versions_with_file(self, temp_seeds_dir: Path) -> None:
        """Should return only version dirs containing the specified file."""
        from work_data_hub.io.schema.seed_resolver import get_versions_containing_file

        # Create version dirs with different files
        (temp_seeds_dir / "001").mkdir()
        (temp_seeds_dir / "001" / "test.csv").touch()
        (temp_seeds_dir / "002").mkdir()  # Empty - should be ignored
        (temp_seeds_dir / "003").mkdir()
        (temp_seeds_dir / "003" / "test.csv").touch()

        result = get_versions_containing_file(temp_seeds_dir, "test.csv")
        assert sorted(result) == ["001", "003"]

    def test_returns_empty_for_missing_file(self, temp_seeds_dir: Path) -> None:
        """Should return empty list if no version has the file."""
        from work_data_hub.io.schema.seed_resolver import get_versions_containing_file

        (temp_seeds_dir / "001").mkdir()
        (temp_seeds_dir / "001" / "other.csv").touch()

        result = get_versions_containing_file(temp_seeds_dir, "test.csv")
        assert result == []

    def test_returns_empty_for_nonexistent_dir(self, tmp_path: Path) -> None:
        """Should return empty list for non-existent directory."""
        from work_data_hub.io.schema.seed_resolver import get_versions_containing_file

        result = get_versions_containing_file(tmp_path / "nonexistent", "test.csv")
        assert result == []


class TestGetSeedFilePath:
    """Tests for get_seed_file_path function."""

    def test_selects_highest_version_with_file(self, temp_seeds_dir: Path) -> None:
        """Should select highest version containing the specific file."""
        from work_data_hub.io.schema.seed_resolver import get_seed_file_path

        # 001 has file, 002 is empty, 003 has file
        (temp_seeds_dir / "001").mkdir()
        (temp_seeds_dir / "001" / "test.csv").touch()
        (temp_seeds_dir / "002").mkdir()  # Empty - ignored
        (temp_seeds_dir / "003").mkdir()
        (temp_seeds_dir / "003" / "test.csv").touch()

        result = get_seed_file_path("test.csv", temp_seeds_dir)
        assert result == temp_seeds_dir / "003" / "test.csv"

    def test_ignores_empty_higher_versions(self, temp_seeds_dir: Path) -> None:
        """Empty directories should not affect version selection."""
        from work_data_hub.io.schema.seed_resolver import get_seed_file_path

        # 001 has file, 002 and 003 are empty
        (temp_seeds_dir / "001").mkdir()
        (temp_seeds_dir / "001" / "test.csv").touch()
        (temp_seeds_dir / "002").mkdir()
        (temp_seeds_dir / "003").mkdir()

        result = get_seed_file_path("test.csv", temp_seeds_dir)
        assert result == temp_seeds_dir / "001" / "test.csv"

    def test_different_files_resolve_independently(self, temp_seeds_dir: Path) -> None:
        """Each file should resolve to its own highest version."""
        from work_data_hub.io.schema.seed_resolver import get_seed_file_path

        # 001 has both files, 002 only has file_b
        (temp_seeds_dir / "001").mkdir()
        (temp_seeds_dir / "001" / "file_a.csv").touch()
        (temp_seeds_dir / "001" / "file_b.csv").touch()
        (temp_seeds_dir / "002").mkdir()
        (temp_seeds_dir / "002" / "file_b.csv").touch()

        result_a = get_seed_file_path("file_a.csv", temp_seeds_dir)
        result_b = get_seed_file_path("file_b.csv", temp_seeds_dir)

        assert result_a == temp_seeds_dir / "001" / "file_a.csv"
        assert result_b == temp_seeds_dir / "002" / "file_b.csv"

    def test_explicit_version_override(self, temp_seeds_dir: Path) -> None:
        """Given explicit version, should use that version."""
        from work_data_hub.io.schema.seed_resolver import get_seed_file_path

        (temp_seeds_dir / "001").mkdir()
        (temp_seeds_dir / "002").mkdir()

        result = get_seed_file_path("test.csv", temp_seeds_dir, version="001")
        assert result == temp_seeds_dir / "001" / "test.csv"

    def test_fallback_to_base_dir(self, temp_seeds_dir: Path) -> None:
        """Without version dirs containing file, should fall back to base."""
        from work_data_hub.io.schema.seed_resolver import get_seed_file_path

        result = get_seed_file_path("test.csv", temp_seeds_dir)
        assert result == temp_seeds_dir / "test.csv"


class TestGetLatestSeedVersion:
    """Tests for get_latest_seed_version function (backward compatibility)."""

    def test_returns_highest_version(self, temp_seeds_dir: Path) -> None:
        """Given multiple version dirs, should return the highest."""
        from work_data_hub.io.schema.seed_resolver import get_latest_seed_version

        (temp_seeds_dir / "001").mkdir()
        (temp_seeds_dir / "002").mkdir()
        (temp_seeds_dir / "010").mkdir()

        result = get_latest_seed_version(temp_seeds_dir)
        assert result == "010"

    def test_returns_none_for_empty_dir(self, temp_seeds_dir: Path) -> None:
        """Given empty directory, should return None."""
        from work_data_hub.io.schema.seed_resolver import get_latest_seed_version

        result = get_latest_seed_version(temp_seeds_dir)
        assert result is None


class TestGetVersionedSeedsDir:
    """Tests for get_versioned_seeds_dir function (backward compatibility)."""

    def test_returns_latest_version_path(self, temp_seeds_dir: Path) -> None:
        """Should return path to latest version directory."""
        from work_data_hub.io.schema.seed_resolver import get_versioned_seeds_dir

        (temp_seeds_dir / "001").mkdir()
        (temp_seeds_dir / "002").mkdir()

        result = get_versioned_seeds_dir(temp_seeds_dir)
        assert result == temp_seeds_dir / "002"

    def test_fallback_to_base_dir(self, temp_seeds_dir: Path) -> None:
        """Without version dirs, should return base directory."""
        from work_data_hub.io.schema.seed_resolver import get_versioned_seeds_dir

        result = get_versioned_seeds_dir(temp_seeds_dir)
        assert result == temp_seeds_dir


class TestEdgeCases:
    """Edge case tests for seed_resolver functions."""

    def test_ignores_non_numeric_directories(self, temp_seeds_dir: Path) -> None:
        """Non-numeric directories should be ignored in version detection."""
        from work_data_hub.io.schema.seed_resolver import get_versions_containing_file

        # Create non-numeric dirs that should be ignored
        (temp_seeds_dir / "backup").mkdir()
        (temp_seeds_dir / "backup" / "test.csv").touch()
        (temp_seeds_dir / "old").mkdir()
        (temp_seeds_dir / "old" / "test.csv").touch()
        # Create valid version dir
        (temp_seeds_dir / "001").mkdir()
        (temp_seeds_dir / "001" / "test.csv").touch()

        result = get_versions_containing_file(temp_seeds_dir, "test.csv")
        assert result == ["001"]  # Only numeric dir

    def test_numeric_sorting_not_lexicographic(self, temp_seeds_dir: Path) -> None:
        """Version sorting should be numeric, not lexicographic (009 < 010)."""
        from work_data_hub.io.schema.seed_resolver import get_seed_file_path

        # Create versions where lexicographic != numeric order
        (temp_seeds_dir / "009").mkdir()
        (temp_seeds_dir / "009" / "test.csv").touch()
        (temp_seeds_dir / "010").mkdir()
        (temp_seeds_dir / "010" / "test.csv").touch()
        (temp_seeds_dir / "2").mkdir()  # Would be "highest" lexicographically
        (temp_seeds_dir / "2" / "test.csv").touch()

        result = get_seed_file_path("test.csv", temp_seeds_dir)
        # Numeric: 2 < 9 < 10, so 010 is highest
        assert result == temp_seeds_dir / "010" / "test.csv"

    def test_ignores_files_in_base_dir(self, temp_seeds_dir: Path) -> None:
        """Files directly in base dir should not affect version detection."""
        from work_data_hub.io.schema.seed_resolver import get_versions_containing_file

        # File in base dir (not in version subdir)
        (temp_seeds_dir / "test.csv").touch()
        # File in version dir
        (temp_seeds_dir / "001").mkdir()
        (temp_seeds_dir / "001" / "test.csv").touch()

        result = get_versions_containing_file(temp_seeds_dir, "test.csv")
        assert result == ["001"]  # Only version dir, not base
