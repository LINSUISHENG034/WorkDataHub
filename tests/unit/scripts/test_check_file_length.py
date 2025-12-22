"""Unit tests for scripts/quality/check_file_length.py.

Tests edge cases: empty files, exactly 800 lines, 801 lines (violation).
Added during Story 7.6 Code Review (M1 issue).
"""

import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


class TestCheckFileLength:
    """Test suite for file length validation script."""

    @pytest.fixture
    def script_path(self) -> Path:
        """Return path to the check_file_length.py script."""
        return (
            Path(__file__).parents[3] / "scripts" / "quality" / "check_file_length.py"
        )

    def _run_script(
        self, script_path: Path, files: list[str], max_lines: int = 800
    ) -> subprocess.CompletedProcess[str]:
        """Run the check_file_length.py script with given arguments."""
        cmd = [
            sys.executable,
            str(script_path),
            f"--max-lines={max_lines}",
            *files,
        ]
        return subprocess.run(cmd, capture_output=True, text=True)

    def test_empty_file_passes(self, script_path: Path, tmp_path: Path) -> None:
        """Empty file should pass (counts as 1 line)."""
        empty_file = tmp_path / "empty.py"
        empty_file.write_text("", encoding="utf-8")

        result = self._run_script(script_path, [str(empty_file)])

        assert result.returncode == 0

    def test_file_exactly_at_limit_passes(
        self, script_path: Path, tmp_path: Path
    ) -> None:
        """File with exactly 800 lines should pass."""
        file_800 = tmp_path / "exact_800.py"
        # 800 lines = 799 newlines + 1 final line
        content = "\n".join([f"# line {i}" for i in range(1, 801)])
        file_800.write_text(content, encoding="utf-8")

        result = self._run_script(script_path, [str(file_800)])

        assert result.returncode == 0

    def test_file_one_over_limit_fails(self, script_path: Path, tmp_path: Path) -> None:
        """File with 801 lines should fail."""
        file_801 = tmp_path / "over_801.py"
        # 801 lines = 800 newlines + 1 final line
        content = "\n".join([f"# line {i}" for i in range(1, 802)])
        file_801.write_text(content, encoding="utf-8")

        result = self._run_script(script_path, [str(file_801)])

        assert result.returncode == 1
        assert "over_801.py" in result.stderr
        assert "801 lines" in result.stderr

    def test_multiple_files_mixed_results(
        self, script_path: Path, tmp_path: Path
    ) -> None:
        """When one file passes and one fails, overall should fail."""
        good_file = tmp_path / "good.py"
        good_file.write_text("# short file\n", encoding="utf-8")

        bad_file = tmp_path / "bad.py"
        content = "\n".join([f"# line {i}" for i in range(1, 850)])
        bad_file.write_text(content, encoding="utf-8")

        result = self._run_script(script_path, [str(good_file), str(bad_file)])

        assert result.returncode == 1
        assert "bad.py" in result.stderr
        assert "good.py" not in result.stderr

    def test_custom_max_lines_parameter(
        self, script_path: Path, tmp_path: Path
    ) -> None:
        """Custom --max-lines should be respected."""
        test_file = tmp_path / "custom.py"
        # 50 lines
        content = "\n".join([f"# line {i}" for i in range(1, 51)])
        test_file.write_text(content, encoding="utf-8")

        # Should pass with max 100
        result_pass = self._run_script(script_path, [str(test_file)], max_lines=100)
        assert result_pass.returncode == 0

        # Should fail with max 40
        result_fail = self._run_script(script_path, [str(test_file)], max_lines=40)
        assert result_fail.returncode == 1

    def test_no_files_passes(self, script_path: Path) -> None:
        """Running with no files should pass (no violations)."""
        result = self._run_script(script_path, [])
        assert result.returncode == 0

    def test_utf8_chinese_content(self, script_path: Path, tmp_path: Path) -> None:
        """File with Chinese content should be handled correctly."""
        chinese_file = tmp_path / "chinese.py"
        content = "# 这是中文注释\n变量 = '测试'\n"
        chinese_file.write_text(content, encoding="utf-8")

        result = self._run_script(script_path, [str(chinese_file)])

        assert result.returncode == 0
