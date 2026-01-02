"""
Rich console abstraction layer for CLI output.

Provides unified interface for Rich and Plain console modes, supporting:
- Rich Tree visualization for file discovery
- Live status context managers for progress tracking
- Clickable hyperlinks for file paths
- Graceful fallback for non-TTY environments

Story: 7.5-4-rich-terminal-ux-enhancement
"""

from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from contextlib import nullcontext
from pathlib import Path
from typing import TYPE_CHECKING, Any, ContextManager

if TYPE_CHECKING:
    from rich.console import Console as RichConsoleType
    from rich.tree import Tree as RichTreeType

# Graceful fallback if rich is not installed
try:
    from rich.console import Console
    from rich.tree import Tree

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    Console = None  # type: ignore
    Tree = None  # type: ignore


class BaseConsole(ABC):
    """Abstract base class for console implementations."""

    @abstractmethod
    def tree(self, label: str) -> Any:
        """Create a tree structure for hierarchical display.

        Args:
            label: Root label for the tree

        Returns:
            Tree object (Rich Tree or empty list for plain mode)
        """
        ...

    @abstractmethod
    def status(self, message: str) -> ContextManager[Any]:
        """Create a status context manager for long-running operations.

        Args:
            message: Status message to display

        Returns:
            Context manager for the status display
        """
        ...

    @abstractmethod
    def print(self, *args: Any, **kwargs: Any) -> None:
        """Print output to console.

        Args:
            *args: Positional arguments to print
            **kwargs: Keyword arguments for formatting
        """
        ...

    @abstractmethod
    def hyperlink(self, path: str, label: str | None = None) -> str:
        """Create a clickable file hyperlink.

        Args:
            path: File path to link to
            label: Optional display label (defaults to filename)

        Returns:
            Formatted hyperlink string
        """
        ...

    @abstractmethod
    def is_rich_enabled(self) -> bool:
        """Check if Rich rendering is enabled.

        Returns:
            True if Rich mode is active, False for plain mode
        """
        ...


class RichConsole(BaseConsole):
    """Rich console implementation with colored output and progress indicators."""

    def __init__(self) -> None:
        """Initialize Rich console."""
        if not RICH_AVAILABLE:
            raise RuntimeError(
                "Rich library is not available. Install with: uv add rich"
            )
        self._console: RichConsoleType = Console()

    def tree(self, label: str) -> RichTreeType:
        """Create a Rich Tree for hierarchical display.

        Args:
            label: Root label for the tree

        Returns:
            Rich Tree object for adding nodes
        """
        return Tree(label)

    def status(self, message: str) -> ContextManager[Any]:
        """Create a Rich status context manager.

        Args:
            message: Status message to display

        Returns:
            Rich status context manager
        """
        return self._console.status(message)

    def print(self, *args: Any, **kwargs: Any) -> None:
        """Print using Rich console with formatting support.

        Args:
            *args: Positional arguments to print
            **kwargs: Keyword arguments for Rich formatting
        """
        self._console.print(*args, **kwargs)

    def hyperlink(self, path: str, label: str | None = None) -> str:
        """Create a clickable file hyperlink using Rich markup.

        Args:
            path: File path to link to
            label: Optional display label (defaults to filename)

        Returns:
            Rich-formatted hyperlink string with [link=...] markup
        """
        abs_path = Path(path).resolve()
        # Windows: file:///C:/Users/... (forward slashes)
        uri = abs_path.as_uri()
        display = label or abs_path.name
        return f"[link={uri}]{display}[/link]"

    def is_rich_enabled(self) -> bool:
        """Check if Rich rendering is enabled.

        Returns:
            Always True for RichConsole
        """
        return True

    def get_console(self) -> RichConsoleType:
        """Get the underlying Rich Console instance.

        Returns:
            Rich Console object
        """
        return self._console


class PlainConsole(BaseConsole):
    """Plain text console implementation for non-TTY and CI environments."""

    def tree(self, label: str) -> list:
        """Create a no-op tree (returns empty list).

        Args:
            label: Root label (ignored in plain mode)

        Returns:
            Empty list (no-op for plain mode)
        """
        return []

    def status(self, message: str) -> ContextManager[Any]:
        """Print status message and return null context manager.

        Args:
            message: Status message to display

        Returns:
            Null context manager (no live updates)
        """
        print(message)
        return nullcontext()

    def print(self, *args: Any, **kwargs: Any) -> None:
        """Print to stdout using standard print.

        Args:
            *args: Positional arguments to print
            **kwargs: Keyword arguments (filtered for print compatibility)
        """
        # Filter out Rich-specific kwargs
        safe_kwargs = {
            k: v for k, v in kwargs.items() if k in {"sep", "end", "file", "flush"}
        }
        print(*args, **safe_kwargs)

    def hyperlink(self, path: str, label: str | None = None) -> str:
        """Return plain text path (no hyperlink support).

        Args:
            path: File path
            label: Optional display label

        Returns:
            Plain text path or label
        """
        if label:
            return f"{label} ({path})"
        return str(Path(path).resolve())

    def is_rich_enabled(self) -> bool:
        """Check if Rich rendering is enabled.

        Returns:
            Always False for PlainConsole
        """
        return False


def get_console(no_rich: bool = False) -> BaseConsole:
    """Factory function to get appropriate console implementation.

    Selection logic:
    1. If --no-rich flag is set → PlainConsole
    2. If Rich is not installed → PlainConsole
    3. If stdout is not a TTY (CI/CD) → PlainConsole
    4. Otherwise → RichConsole

    Args:
        no_rich: Force plain mode (from --no-rich CLI flag)

    Returns:
        BaseConsole instance (RichConsole or PlainConsole)

    Example:
        >>> console = get_console(no_rich=False)
        >>> console.print("[bold green]Success![/bold green]")
        >>> tree = console.tree("📂 Files")
        >>> tree.add("📄 data.xlsx")
    """
    if no_rich:
        return PlainConsole()
    if not RICH_AVAILABLE:
        return PlainConsole()
    if not sys.stdout.isatty():
        return PlainConsole()
    return RichConsole()


__all__ = [
    "BaseConsole",
    "RichConsole",
    "PlainConsole",
    "get_console",
    "RICH_AVAILABLE",
]
