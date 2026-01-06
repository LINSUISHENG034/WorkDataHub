"""Structured logging framework using structlog.

This module provides centralized logging configuration with:
- ISO-8601 timestamps
- JSON rendering for structured logs
- Automatic sanitization of sensitive fields
- Context binding support
- Dual output (stdout + optional file logging)

Configuration is loaded from work_data_hub.config.settings:
- LOG_LEVEL: Set log level (DEBUG, INFO, WARNING, ERROR, CRITICAL). Default: INFO
- LOG_TO_FILE: Enable file logging (1, true, yes). Default: disabled
- LOG_FILE_DIR: Directory for log files. Default: logs/

Usage:
    >>> from work_data_hub.utils.logging import get_logger
    >>> logger = get_logger(__name__)
    >>> logger.info("processing_started", domain="annuity", execution_id="exec_123")
"""

import logging
import os
import re
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any, Dict, MutableMapping

import structlog
from structlog.types import EventDict, Processor

from work_data_hub.config import get_settings

# Sensitive key patterns for sanitization
SENSITIVE_PATTERNS = [
    re.compile(r".*password.*", re.IGNORECASE),
    re.compile(r".*token.*", re.IGNORECASE),
    re.compile(r".*api_key.*", re.IGNORECASE),
    re.compile(r".*secret.*", re.IGNORECASE),
    re.compile(r"^DATABASE_URL$", re.IGNORECASE),
    re.compile(r"^WDH_.*_SALT$", re.IGNORECASE),
]

REDACTED_VALUE = "[REDACTED]"


def sanitize_for_logging(data: Dict[str, Any]) -> Dict[str, Any]:
    """Redact sensitive values from a dictionary before logging.

    Redacts values for keys matching:
    - password, token, api_key, secret (case-insensitive, substring match)
    - DATABASE_URL (exact match)
    - WDH_*_SALT (pattern match)

    Args:
        data: Dictionary that may contain sensitive data

    Returns:
        New dictionary with sensitive values replaced by [REDACTED]

    Example:
        >>> sanitize_for_logging({"password": "secret123", "user": "admin"})
        {"password": "[REDACTED]", "user": "admin"}
    """
    sanitized: Dict[str, Any] = {}
    for key, value in data.items():
        if any(pattern.match(key) for pattern in SENSITIVE_PATTERNS):
            sanitized[key] = REDACTED_VALUE
        elif isinstance(value, dict):
            sanitized[key] = sanitize_for_logging(value)
        else:
            sanitized[key] = value
    return sanitized


def sanitization_processor(
    logger: logging.Logger, method_name: str, event_dict: EventDict
) -> MutableMapping[str, Any]:
    """Structlog processor that sanitizes sensitive fields in event_dict.

    This processor runs in the structlog chain and automatically redacts
    sensitive data before rendering.
    """
    # Sanitize all keys in event_dict except structlog internals
    sanitized: MutableMapping[str, Any] = {}
    for key, value in event_dict.items():
        if any(pattern.match(key) for pattern in SENSITIVE_PATTERNS):
            sanitized[key] = REDACTED_VALUE
        elif isinstance(value, dict):
            sanitized[key] = sanitize_for_logging(value)
        else:
            sanitized[key] = value
    return sanitized


def _get_log_level() -> int:
    """Get log level from settings.

    Uses centralized configuration management (Story 1.4) to retrieve
    the LOG_LEVEL setting instead of direct environment variable access.

    Returns:
        Logging level constant (e.g., logging.INFO, logging.DEBUG)
    """
    try:
        # Try to get settings, which requires DATABASE_URL
        settings_instance = get_settings()
        level_name = settings_instance.LOG_LEVEL.upper()
    except Exception:
        # Fallback to environment variable if settings can't be loaded
        # This allows logging to work even when DATABASE_URL isn't configured
        level_name = os.getenv("LOG_LEVEL", "INFO").upper()

    return getattr(logging, level_name, logging.INFO)


def _should_log_to_file() -> bool:
    """Check if file logging is enabled via environment."""
    log_to_file = os.getenv("LOG_TO_FILE", "").lower()
    return log_to_file in ("1", "true", "yes")


def _get_log_file_path() -> Path:
    """Get the log file path with date-based naming."""
    log_dir = Path(os.getenv("LOG_FILE_DIR", "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)

    # Format: workdatahub-YYYYMMDD.log
    date_str = datetime.now().strftime("%Y%m%d")
    return log_dir / f"workdatahub-{date_str}.log"


def _configure_structlog() -> None:
    """Configure structlog with JSON rendering and sanitization.

    Sets up:
    - ISO-8601 timestamps
    - Logger name
    - Log level
    - JSON renderer
    - Sanitization processor
    - Dual output (stdout + optional file)
    """
    # Configure stdlib logging first
    logging.basicConfig(
        format="%(message)s",
        level=_get_log_level(),
        handlers=[],  # We'll add handlers below
    )

    # Add stdout handler (always enabled)
    stdout_handler = logging.StreamHandler()
    stdout_handler.setLevel(_get_log_level())
    logging.root.addHandler(stdout_handler)

    # Add file handler if enabled
    if _should_log_to_file():
        log_file = _get_log_file_path()
        file_handler = TimedRotatingFileHandler(
            filename=str(log_file),
            when="midnight",
            interval=1,
            backupCount=30,  # 30-day retention
            encoding="utf-8",
        )
        file_handler.setLevel(_get_log_level())
        logging.root.addHandler(file_handler)

    # Configure structlog processors
    processors: list[Processor] = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        sanitization_processor,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


# Configure structlog on module import
_configure_structlog()


def get_logger(name: str) -> Any:
    """Get a structlog BoundLogger instance.

    Args:
        name: Logger name (typically __name__ of the calling module)

    Returns:
        A structlog BoundLogger configured with JSON rendering and sanitization

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("event_occurred", user_id=123, action="login")
    """
    # Ensure the underlying stdlib logger propagates to the root logger so
    # pytest's caplog and other root handlers can consistently capture output.
    stdlib_logger = logging.getLogger(name)
    if stdlib_logger.propagate is False:
        stdlib_logger.propagate = True
    # Let loggers inherit from root logger - don't override with DEBUG
    # This allows reconfigure_for_console() to control verbosity
    return structlog.get_logger(name)


def bind_context(**kwargs: Any) -> Any:
    """Create a logger with bound context fields.

    This is a convenience function that creates a logger and immediately
    binds context to it. Useful for adding domain, execution_id, step, etc.

    Args:
        **kwargs: Context fields to bind (e.g., domain="annuity",
            execution_id="exec_123")

    Returns:
        A BoundLogger with the specified context already bound

    Example:
        >>> logger = bind_context(
        ...     domain="annuity", execution_id="exec_123", step="transform"
        ... )
        >>> logger.info("processing_row", row_id=456)
        # Emits: {"domain": "annuity", "execution_id": "exec_123", "step": "transform",
        #         "row_id": 456, "event": "processing_row", ...}
    """
    return structlog.get_logger().bind(**kwargs)


def reconfigure_for_console(
    debug: bool = False, verbose: bool = False, quiet: bool = False
) -> None:
    """Reconfigure structlog for console mode (Rich) vs JSON mode.

    This function allows switching between JSON rendering (default) and
    human-readable ConsoleRenderer for debug mode. Must be called early in
    CLI startup, before first log emission.

    Story: 7.5-4-rich-terminal-ux-enhancement (AC-4: Console Mode)
    Story: 7.5-6-cli-output-ux-optimization (AC-1, AC-2: Verbosity levels)

    Args:
        debug: If True, use ConsoleRenderer for human-readable colored output
               and enable DEBUG-level logging including Dagster internals.
        verbose: If True, show INFO-level diagnostic logs (structlog).
                 If False (default), suppress INFO logs for clean UX.
        quiet: If True, show only ERROR-level logs (minimal output mode).
               Errors and final summary only.

    Verbosity Levels:
        - Quiet (quiet=True): ERROR+ only, minimal output
        - Default (debug=False, verbose=False): WARNING+ only, Dagster suppressed
        - Verbose (verbose=True): INFO+ structlog logs shown
        - Debug (debug=True): Full DEBUG output including Dagster internals

    Example:
        >>> from work_data_hub.utils.logging import reconfigure_for_console
        >>> # In CLI main() before logging
        >>> reconfigure_for_console(
        ...     debug=args.debug, verbose=args.verbose, quiet=args.quiet
        ... )
        >>> logger = get_logger(__name__)
        >>> logger.info("Processing started")  # Only shown if verbose/debug
    """
    # Story 7.5-6 AC-1: Suppress Dagster DEBUG in default mode
    # Configure Dagster's logging level based on debug mode
    dagster_logger = logging.getLogger("dagster")
    if debug:
        dagster_logger.setLevel(logging.DEBUG)
    else:
        # Suppress Dagster DEBUG/INFO to reduce terminal noise
        dagster_logger.setLevel(logging.WARNING)

    # Determine root log level based on verbosity
    # Priority: debug > verbose > default > quiet
    # Story 7.5-6: Aligned with dagster_logging.py levels
    if debug:
        root_level = logging.DEBUG
    elif verbose:
        # verbose: Show WARNING+ for diagnostic information
        root_level = logging.WARNING
    elif quiet:
        # quiet: Show only CRITICAL for silent operation
        root_level = logging.CRITICAL
    else:
        # Default: Only ERROR+ for clean terminal output
        # Suppresses WARNING-level structlog messages (e.g., columns_not_found)
        root_level = logging.ERROR

    # Update root logger level
    logging.root.setLevel(root_level)

    # Clear and replace all root handlers with properly configured ones
    # This ensures any handlers added during module init use the CLI-specified level
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    # Add a single StreamHandler with the correct level
    new_handler = logging.StreamHandler()
    new_handler.setLevel(root_level)
    new_handler.setFormatter(logging.Formatter("%(message)s"))
    logging.root.addHandler(new_handler)

    # Also update work_data_hub logger and all its children to ensure suppression
    for name in list(logging.Logger.manager.loggerDict):
        if name.startswith("work_data_hub"):
            child_logger = logging.getLogger(name)
            child_logger.setLevel(root_level)
            for handler in child_logger.handlers[:]:
                child_logger.removeHandler(handler)

    # Get existing processors minus the renderer
    base_processors: list[Processor] = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        sanitization_processor,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # Choose renderer based on debug mode
    if debug:
        # Human-readable colored output for development
        # Story 7.5-4 AC-4: --debug enables verbose console output
        renderer: Processor = structlog.dev.ConsoleRenderer(colors=True)
    else:
        # JSON for machine parsing (default)
        # Story 7.5-4 AC-4: Default mode hides INFO-level structlog output
        renderer = structlog.processors.JSONRenderer()

    # Reconfigure structlog with new renderer
    structlog.configure(
        processors=[*base_processors, renderer],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=False,  # Allow reconfiguration
    )
