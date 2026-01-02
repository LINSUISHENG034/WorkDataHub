"""
Unit tests for Rich console abstraction layer.

Story: 7.5-4-rich-terminal-ux-enhancement
Tests: 6.1-6.5
"""

import sys
from unittest.mock import MagicMock, patch

import pytest

from work_data_hub.cli.etl.console import (
    BaseConsole,
    PlainConsole,
    RichConsole,
    get_console,
    RICH_AVAILABLE,
)


class TestRichImport:
    """Test 6.1: Test Rich import and version check."""

    def test_rich_is_available(self) -> None:
        """AC-1: Verify Rich library is importable."""
        # Rich should be available since we added it to dependencies
        assert RICH_AVAILABLE, "Rich library should be available"

    def test_rich_imports(self) -> None:
        """Test that Rich components can be imported."""
        if RICH_AVAILABLE:
            from rich.console import Console
            from rich.tree import Tree
            from rich.live import Live

            # Verify imports work
            assert Console is not None
            assert Tree is not None
            assert Live is not None


class TestConsoleFactory:
    """Test 6.2: Test is_rich_enabled() logic (TTY detection + flag)."""

    def test_get_console_returns_rich_when_available_and_tty(self) -> None:
        """Should return RichConsole when Rich is available and stdout is TTY."""
        with patch("sys.stdout.isatty", return_value=True):
            console = get_console(no_rich=False)
            assert isinstance(console, RichConsole)

    def test_get_console_returns_plain_when_no_rich_flag(self) -> None:
        """Should return PlainConsole when --no-rich flag is set."""
        with patch("sys.stdout.isatty", return_value=True):
            console = get_console(no_rich=True)
            assert isinstance(console, PlainConsole)

    def test_get_console_returns_plain_when_not_tty(self) -> None:
        """AC-6: Should auto-detect CI and return PlainConsole when not TTY."""
        with patch("sys.stdout.isatty", return_value=False):
            console = get_console(no_rich=False)
            assert isinstance(console, PlainConsole)

    def test_get_console_returns_plain_when_rich_unavailable(self) -> None:
        """Should return PlainConsole when Rich is not installed."""
        with patch("work_data_hub.cli.etl.console.RICH_AVAILABLE", False):
            console = get_console(no_rich=False)
            assert isinstance(console, PlainConsole)


class TestRichConsole:
    """Test Rich console implementation."""

    @pytest.mark.skipif(not RICH_AVAILABLE, reason="Rich not available")
    def test_rich_console_creation(self) -> None:
        """Should create RichConsole instance."""
        console = RichConsole()
        assert console.is_rich_enabled() is True

    @pytest.mark.skipif(not RICH_AVAILABLE, reason="Rich not available")
    def test_rich_tree_creation(self) -> None:
        """Should create Rich Tree for hierarchical display."""
        console = RichConsole()
        tree = console.tree("📂 Test Domain")
        assert tree is not None

    @pytest.mark.skipif(not RICH_AVAILABLE, reason="Rich not available")
    def test_rich_status_context_manager(self) -> None:
        """Should return context manager for status display."""
        console = RichConsole()
        status = console.status("Processing...")
        assert hasattr(status, "__enter__")
        assert hasattr(status, "__exit__")

    @pytest.mark.skipif(not RICH_AVAILABLE, reason="Rich not available")
    def test_rich_hyperlink_windows_path(self) -> None:
        """AC-3: Should create clickable hyperlinks with Windows paths."""
        console = RichConsole()
        result = console.hyperlink("C:\\Users\\Test\\data.xlsx")
        assert "[link=" in result
        assert "[/link]" in result
        assert "file:///C:/" in result

    @pytest.mark.skipif(not RICH_AVAILABLE, reason="Rich not available")
    def test_rich_hyperlink_with_custom_label(self) -> None:
        """Should create hyperlink with custom label."""
        console = RichConsole()
        result = console.hyperlink("/path/to/file.xlsx", label="My File")
        assert "[link=" in result
        assert "My File" in result


class TestPlainConsole:
    """Test plain console implementation for CI/CD."""

    def test_plain_console_creation(self) -> None:
        """Should create PlainConsole instance."""
        console = PlainConsole()
        assert console.is_rich_enabled() is False

    def test_plain_tree_returns_empty_list(self) -> None:
        """Should return empty list for tree (no-op)."""
        console = PlainConsole()
        tree = console.tree("📂 Test Domain")
        assert tree == []

    def test_plain_status_returns_null_context(self) -> None:
        """Should return null context manager for status."""
        from contextlib import nullcontext

        console = PlainConsole()
        status = console.status("Processing...")
        # nullcontext returns the same object
        assert isinstance(status, type(nullcontext()))

    def test_plain_hyperlink_returns_plain_text(self) -> None:
        """Should return plain text path without hyperlink formatting."""
        console = PlainConsole()
        result = console.hyperlink("/path/to/file.xlsx")
        assert "[link=" not in result
        assert "file.xlsx" in result

    def test_plain_hyperlink_with_label(self) -> None:
        """Should return label with path in parentheses."""
        console = PlainConsole()
        result = console.hyperlink("/path/to/file.xlsx", label="My File")
        assert "My File" in result
        assert "file.xlsx" in result


class TestConsoleOutput:
    """Test 6.3: Test --no-rich produces plain output."""

    def test_plain_console_print_filters_kwargs(self) -> None:
        """PlainConsole should filter Rich-specific kwargs."""
        console = PlainConsole()
        # Should not raise exception for Rich-specific kwargs
        console.print("Test", sep=" ", end="\n", file=None, flush=False)

    @pytest.mark.skipif(not RICH_AVAILABLE, reason="Rich not available")
    def test_rich_console_print_with_formatting(self) -> None:
        """RichConsole should support Rich markup."""
        console = RichConsole()
        # Should not raise exception
        console.print("[bold green]Success![/bold green]")


class TestConsoleAbstraction:
    """Test console abstraction interface."""

    def test_base_console_cannot_be_instantiated(self) -> None:
        """BaseConsole should not be instantiable (abstract class)."""
        with pytest.raises(TypeError):
            BaseConsole()  # type: ignore

    @pytest.mark.skipif(not RICH_AVAILABLE, reason="Rich not available")
    def test_rich_console_implements_base_interface(self) -> None:
        """RichConsole should implement all BaseConsole methods."""
        console = RichConsole()
        assert hasattr(console, "tree")
        assert hasattr(console, "status")
        assert hasattr(console, "print")
        assert hasattr(console, "hyperlink")
        assert hasattr(console, "is_rich_enabled")

    def test_plain_console_implements_base_interface(self) -> None:
        """PlainConsole should implement all BaseConsole methods."""
        console = PlainConsole()
        assert hasattr(console, "tree")
        assert hasattr(console, "status")
        assert hasattr(console, "print")
        assert hasattr(console, "hyperlink")
        assert hasattr(console, "is_rich_enabled")


class TestConsoleIntegration:
    """Integration tests for console with CLI arguments."""

    def test_console_factory_with_args_namespace(self) -> None:
        """Should work with argparse.Namespace from CLI."""
        from argparse import Namespace

        # Simulate --no-rich flag
        args = Namespace(no_rich=True)
        with patch("sys.stdout.isatty", return_value=True):
            console = get_console(no_rich=args.no_rich)
            assert isinstance(console, PlainConsole)

    def test_console_factory_without_flag(self) -> None:
        """Should default to Rich when flag is not set."""
        from argparse import Namespace

        args = Namespace()
        # If no_rich attribute doesn't exist, should use default (False)
        no_rich = getattr(args, "no_rich", False)
        with patch("sys.stdout.isatty", return_value=True):
            console = get_console(no_rich=no_rich)
            if RICH_AVAILABLE:
                assert isinstance(console, RichConsole)
