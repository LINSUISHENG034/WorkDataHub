"""
ETL CLI for WorkDataHub.

Story 7.4: CLI Layer Modularization - Package facade.

This module is the facade for the cli/etl/ package, re-exporting all
public symbols for backward compatibility with existing imports and tests.

Story 6.2-P6: CLI Architecture Unification & Multi-Domain Batch Processing
Task 1.2: Extract jobs.py main() to cli/etl.py with single & multi-domain support

Story 6.2-P11: Token auto-refresh on CLI startup (T3.1-T3.3)

This module provides the CLI interface for running ETL jobs, supporting:
- Single domain processing (backward compatible)
- Multi-domain batch processing (new in Story 6.2-P6)
- Token validation and auto-refresh at startup (new in Story 6.2-P11)
- All existing CLI options from jobs.py

Usage:
    # Single domain
    python -m work_data_hub.cli etl --domains annuity_performance --period 202411 --execute

    # Multi-domain (Phase 2)
    python -m work_data_hub.cli etl --domains annuity_performance,annuity_income --period 202411 --execute

    # All domains (Phase 2)
    python -m work_data_hub.cli etl --all-domains --period 202411 --execute

    # Disable auto-refresh token (if you want to skip token check)
    python -m work_data_hub.cli etl --domains annuity_performance --no-auto-refresh-token --execute
"""

# Re-export all public symbols for backward compatibility
# Re-export dependencies needed for test patching (Story 7.4 test compatibility)
from work_data_hub.config.settings import get_settings

from .config import build_run_config
from .diagnostics import _check_database_connection
from .domain_validation import _load_configured_domains, _validate_domains
from .executors import _execute_single_domain
from .main import main

__all__ = [
    "main",
    "build_run_config",
    "_load_configured_domains",
    "_validate_domains",
    "_execute_single_domain",
    "_check_database_connection",
    "get_settings",
]
