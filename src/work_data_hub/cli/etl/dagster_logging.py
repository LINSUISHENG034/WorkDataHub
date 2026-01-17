"""Dagster logging configuration for CLI.

Story 7.5-6: Control Dagster log verbosity based on CLI flags.

This module provides utilities to configure Dagster's built-in console logger
to match the verbosity level requested via CLI flags (--debug, --verbose, --quiet).
"""

from typing import Any, Dict


def get_dagster_log_level(
    debug: bool = False, verbose: bool = False, quiet: bool = False
) -> str:
    """Determine Dagster log level based on CLI verbosity flags.

    Args:
        debug: If True, show all DEBUG logs including Dagster internals
        verbose: If True, show WARNING-level logs (diagnostics)
        quiet: If True, show only CRITICAL-level logs

    Returns:
        Log level string: "DEBUG", "WARNING", "ERROR", or "CRITICAL"

    Verbosity Levels (from quietest to loudest):
        - quiet:   CRITICAL only (silent except fatal errors)
        - default: CRITICAL only (clean UX, Dagster logs suppressed)
        - verbose: WARNING+ (show diagnostic warnings)
        - debug:   DEBUG+ (full output including Dagster internals)

    Story CLI-OUTPUT-CLEANUP: Default changed from ERROR to CRITICAL
    to prevent Dagster stack traces from mixing with spinner output.
    """
    if debug:
        return "DEBUG"
    elif verbose:
        return "WARNING"
    elif quiet:
        return "CRITICAL"
    else:
        # Default: suppress all Dagster logs to keep terminal clean
        # CLI user-facing output uses console.print() which is not affected
        return "CRITICAL"


def build_logger_config(
    debug: bool = False, verbose: bool = False, quiet: bool = False
) -> Dict[str, Any]:
    """Build Dagster run_config loggers section.

    Story 7.5-6: Suppress Dagster DEBUG logs in default mode.

    Args:
        debug: If True, enable full DEBUG output
        verbose: If True, enable INFO output
        quiet: If True, show only ERROR output

    Returns:
        Dictionary for run_config["loggers"] section

    Example:
        >>> config = build_logger_config(debug=False)
        >>> config
        {'console': {'config': {'log_level': 'WARNING'}}}
    """
    log_level = get_dagster_log_level(debug=debug, verbose=verbose, quiet=quiet)

    return {
        "console": {
            "config": {
                "log_level": log_level,
            }
        }
    }


def merge_logger_config(
    run_config: Dict[str, Any],
    debug: bool = False,
    verbose: bool = False,
    quiet: bool = False,
) -> Dict[str, Any]:
    """Merge logger configuration into existing run_config.

    Args:
        run_config: Existing Dagster run configuration
        debug, verbose, quiet: CLI verbosity flags

    Returns:
        Updated run_config with loggers section added
    """
    # Build logger config only if not in debug mode
    # (debug mode should show all logs)
    logger_config = build_logger_config(debug=debug, verbose=verbose, quiet=quiet)

    # Merge into run_config
    updated_config = dict(run_config)
    updated_config["loggers"] = logger_config

    return updated_config
