"""
Main entry point for ETL CLI.

Story 7.4: CLI Layer Modularization - CLI argument parsing and main function.

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

import argparse
import sys
import warnings
from pathlib import Path
from typing import List, Optional

# Story CLI-OUTPUT-CLEANUP: Suppress third-party library warnings that clutter terminal output
# These warnings are not actionable by users and interfere with spinner display
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")
warnings.filterwarnings("ignore", message="DataFrame columns are not unique")

# Import the package module for dynamic lookup of patchable functions.
# This allows tests to patch work_data_hub.cli.etl._execute_single_domain etc.
import work_data_hub.cli.etl as etl_module
from work_data_hub.utils.logging import reconfigure_for_console

from .auth import _validate_and_refresh_token
from .diagnostics import _check_database_connection
from .domain_validation import SPECIAL_DOMAINS, validate_domain_registry


def main(argv: Optional[List[str]] = None) -> int:  # noqa: PLR0911, PLR0912, PLR0915 - CLI entry point
    """
    Main CLI entry point for ETL operations.

    Args:
        argv: Command line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    parser = argparse.ArgumentParser(
        description="Run WorkDataHub ETL job",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Core arguments
    parser.add_argument(
        "--domains",
        help="Domain(s) to process (single domain or comma-separated list)",
    )
    parser.add_argument(
        "--all-domains",
        action="store_true",
        help="Process all configured data domains from config/data_sources.yml",
    )
    parser.add_argument(
        "--mode",
        choices=["delete_insert", "append"],
        default="delete_insert",
        help="Load mode for database operations",
    )
    parser.add_argument(
        "--plan-only",
        action="store_true",
        default=False,
        help="Generate execution plan without database connection (default unless --execute)",
    )

    # Pipeline framework toggle
    parser.add_argument(
        "--use-pipeline",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "Use shared pipeline framework for annuity performance processing "
            "(overrides WDH_ANNUITY_PIPELINE_ENABLED setting)"
        ),
    )

    parser.add_argument(
        "--sheet",
        type=str,
        default=None,
        help="Excel sheet to process (index like '0' or name like '规模明细'). If not provided, uses sheet_name from data_sources.yml for Epic 3 domains.",
    )

    # Period parameter for Epic 3 schema domains
    parser.add_argument(
        "--period",
        type=str,
        help="Period in YYYYMM format for Epic 3 domains (e.g., '202510')",
    )

    # Sprint Change Proposal 2026-01-08: Direct file processing
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help=(
            "Process a specific file directly (bypasses automatic discovery). "
            "Supports Excel (.xlsx, .xls, .xlsm) and CSV (.csv) formats. "
            "Must be used with --domains for a single domain. "
            "Mutually exclusive with --period."
        ),
    )

    parser.add_argument(
        "--execute",
        action="store_true",
        default=False,
        help="Execute against database (default: plan-only mode for safety)",
    )

    parser.add_argument(
        "--max-files",
        type=int,
        default=1,
        help="Maximum number of discovered files to process (default: 1)",
    )

    # Story 6.2-P16 AC-1: File selection strategy for ambiguous matches
    parser.add_argument(
        "--file-selection",
        choices=["error", "newest", "oldest", "first"],
        default="error",
        help=(
            "Strategy when multiple files match patterns. "
            "'error' (default) raises an error, 'newest' selects most recently modified, "
            "'oldest' selects oldest, 'first' selects alphabetically first."
        ),
    )

    # Runtime override for composite key
    parser.add_argument(
        "--pk",
        type=str,
        help=(
            "Override composite key for delete_insert mode. Comma or semicolon "
            "separated (e.g., '月度,计划代码,company_id')."
        ),
    )

    # Reference backfill arguments
    parser.add_argument(
        "--backfill-refs",
        choices=["plans", "portfolios", "all"],
        help="Enable reference backfill for missing plan/portfolio references",
    )
    parser.add_argument(
        "--backfill-mode",
        choices=["insert_missing", "fill_null_only"],
        default="insert_missing",
        help="Backfill mode: insert_missing (default) or fill_null_only",
    )
    parser.add_argument(
        "--skip-facts",
        action="store_true",
        default=False,
        help="Skip fact loading, run backfill only",
    )
    parser.add_argument(
        "--no-post-hooks",
        action="store_true",
        default=False,
        help="Disable Post-ETL hooks (e.g., customer MDM sync)",
    )

    # Queue processing arguments
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Batch size for queue processing operations (default: 50)",
    )

    # Enrichment arguments
    # Default behavior: enabled (so EQC sync lookups can run) unless explicitly disabled.
    parser.add_argument(
        "--enrichment",
        dest="enrichment_enabled",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable company enrichment/EQC lookups (default: enabled)",
    )
    # Backward-compatible alias (kept for existing scripts/docs)
    parser.add_argument(
        "--enrichment-enabled",
        dest="enrichment_enabled",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--enrichment-sync-budget",
        type=int,
        default=500,
        help=(
            "Budget for synchronous EQC lookups per processing session "
            "(default: 500; set 0 to disable)"
        ),
    )
    parser.add_argument(
        "--export-unknown-names",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Export unknown company names to CSV for manual review",
    )

    # Story 7.5-6: Verbosity levels for CLI output optimization
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        default=False,
        help="Show diagnostic information (INFO-level logs)",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        default=False,
        help="Minimal output (errors and final summary only)",
    )

    # Data sampling for quick validation
    parser.add_argument(
        "--sample",
        type=str,
        default=None,
        help=(
            "Sample data slice in 'index/count' format (1-indexed). "
            "Example: '1/10' reads the first 10%% of rows, "
            "'3/10' reads rows 20%%-30%%. Useful for quick ETL validation."
        ),
    )

    # Advanced options
    parser.add_argument(
        "--debug",
        action="store_true",
        help=(
            "Enable debug logging with verbose console output and persist run in Dagster UI. "
            "In Rich mode, also enables structlog ConsoleRenderer for human-readable logs."
        ),
    )
    parser.add_argument(
        "--no-rich",
        action="store_true",
        help=(
            "Disable Rich rendering, produce plain text output. "
            "Automatically enabled in non-TTY environments (CI/CD)."
        ),
    )
    parser.add_argument(
        "--raise-on-error",
        action="store_true",
        help="Raise exceptions immediately (useful for testing)",
    )

    # Story 6.2-P11 T3.3: Token auto-refresh control
    parser.add_argument(
        "--no-auto-refresh-token",
        action="store_true",
        default=False,
        help="Disable automatic EQC token refresh at startup",
    )

    # Story 6.2-P16 AC-2: Database connection diagnostics
    parser.add_argument(
        "--check-db",
        action="store_true",
        default=False,
        help="Test database connection and exit (diagnostic mode)",
    )

    args = parser.parse_args(argv)

    # Story 7.5-4 AC-4: Reconfigure logging for console mode based on --debug flag
    # Story 7.5-6: Add verbosity levels (--verbose, --quiet)
    # Must be called early, before any logging occurs
    debug_mode = getattr(args, "debug", False)
    verbose_mode = getattr(args, "verbose", False)
    quiet_mode = getattr(args, "quiet", False)
    reconfigure_for_console(debug=debug_mode, verbose=verbose_mode, quiet=quiet_mode)

    # Story 6.2-P16 AC-2: --check-db diagnostic mode
    if getattr(args, "check_db", False):
        return _check_database_connection()

    # Sprint Change Proposal 2026-01-08: --file parameter validation
    file_path = getattr(args, "file", None)
    if file_path:
        # --file requires --domains (single domain only)
        if not args.domains:
            parser.error("--file requires --domains with exactly one domain")
        # Check if single domain (not comma-separated)
        if "," in args.domains:
            parser.error(
                "--file only supports a single domain (no comma-separated list)"
            )
        # --file mutually exclusive with --period
        if args.period:
            parser.error("--file and --period are mutually exclusive")
        # --file mutually exclusive with --all-domains
        if args.all_domains:
            parser.error("--file cannot be used with --all-domains")
        # File must exist
        if not Path(file_path).exists():
            parser.error(f"File not found: {file_path}")

    # Validate domain arguments
    if not args.domains and not args.all_domains:
        parser.error("Either --domains or --all-domains must be specified")

    if args.domains and args.all_domains:
        parser.error("Cannot specify both --domains and --all-domains")

    # Story 6.2-P11 T3.1-T3.2: Token validation at CLI startup
    # Only validate for domains that may use EQC enrichment (annuity_performance).
    # `--no-auto-refresh-token` disables auto-refresh, but still performs a pre-check so
    # users can see token status and intentionally proceed without EQC lookups.
    auto_refresh_enabled = not getattr(args, "no_auto_refresh_token", False)
    enrichment_enabled = bool(getattr(args, "enrichment_enabled", False))

    domains_for_check: List[str] = []
    if args.domains:
        domains_for_check = [d.strip() for d in args.domains.split(",")]
    elif args.all_domains:
        domains_for_check = etl_module._load_configured_domains()

    enrichment_domains = {"annuity_performance", "annual_award"}
    if enrichment_enabled and any(d in enrichment_domains for d in domains_for_check):
        _validate_and_refresh_token(auto_refresh=auto_refresh_enabled)

    # Story 7.4-4: Validate that configured domains have corresponding job definitions
    validate_domain_registry()

    # Story 7.5-5: Generate session_id for unified failure logging
    from work_data_hub.infrastructure.validation import generate_session_id

    session_id = generate_session_id()

    # Determine domains to process
    domains_to_process: List[str] = []

    if args.all_domains:
        # Task 2.3: Process all configured data domains
        configured_domains = etl_module._load_configured_domains()
        if not configured_domains:
            print("❌ No configured domains found in config/data_sources.yml")
            return 1

        # Exclude special orchestration domains from --all-domains
        # Note: company_mapping removed in Story 7.1-4 (Zero Legacy)
        # SPECIAL_DOMAINS imported from domain_validation module
        domains_to_process = [d for d in configured_domains if d not in SPECIAL_DOMAINS]

        print(f"📋 Processing all configured domains: {', '.join(domains_to_process)}")
        print(f"   Total: {len(domains_to_process)} domains")
        print("=" * 50)

    elif args.domains:
        # Parse comma-separated domain list
        domains_to_process = [d.strip() for d in args.domains.split(",") if d.strip()]

        if not domains_to_process:
            parser.error("No valid domains specified")

        # Task 2.1: Validate domains based on count
        if len(domains_to_process) > 1:
            # Multi-domain: Only allow configured data domains
            valid, invalid = etl_module._validate_domains(
                domains_to_process, allow_special=False
            )

            if invalid:
                print(
                    f"❌ Invalid domains for multi-domain processing: {', '.join(invalid)}"
                )
                print(
                    "   Multi-domain runs only support configured data domains from config/data_sources.yml"
                )
                print(
                    "   Special orchestration domains (company_lookup_queue, reference_sync)"
                )
                print("   can only be used in single-domain runs")
                return 1

            domains_to_process = valid
            print(f"📋 Multi-domain batch processing: {', '.join(domains_to_process)}")
            print(f"   Total: {len(domains_to_process)} domains")
            print("=" * 50)

        else:
            # Single domain: Allow both configured and special domains
            valid, invalid = etl_module._validate_domains(
                domains_to_process, allow_special=True
            )

            if invalid:
                print(f"❌ Unknown domain: {invalid[0]}")
                configured = etl_module._load_configured_domains()
                print(f"   Available configured domains: {', '.join(configured)}")
                print(
                    "   Special orchestration domains: company_lookup_queue, reference_sync"
                )
                return 1

            domains_to_process = valid

    # Task 2.2: Execute domains sequentially
    # Story 7.5-5: Attach session_id to args for unified failure logging
    args.session_id = session_id

    if len(domains_to_process) == 1:
        # Single domain execution
        return etl_module._execute_single_domain(args, domains_to_process[0])

    else:
        # Multi-domain batch execution
        print("🚀 Starting multi-domain batch processing...")
        print("   Execution mode: Sequential")
        print("   Continue on failure: Yes")
        print("=" * 50)

        results = {}
        failed_domains = []

        for i, domain in enumerate(domains_to_process, 1):
            print(f"\n{'=' * 50}")
            print(f"Processing domain {i}/{len(domains_to_process)}: {domain}")
            print(f"{'=' * 50}")

            try:
                exit_code = etl_module._execute_single_domain(args, domain)
                results[domain] = "SUCCESS" if exit_code == 0 else "FAILED"

                if exit_code != 0:
                    failed_domains.append(domain)
                    print(f"⚠️  Domain {domain} failed with exit code {exit_code}")
                else:
                    print(f"✅ Domain {domain} completed successfully")

            except KeyboardInterrupt:
                print(
                    f"\n⚠️  Multi-domain processing interrupted by user at domain {domain}"
                )
                results[domain] = "INTERRUPTED"
                return 130

            except Exception as e:
                print(f"❌ Unexpected error processing domain {domain}: {e}")
                results[domain] = "ERROR"
                failed_domains.append(domain)

                if args.raise_on_error:
                    raise

        # Print summary
        print(f"\n{'=' * 50}")
        print("📊 MULTI-DOMAIN BATCH PROCESSING SUMMARY")
        print(f"{'=' * 50}")
        print(f"Total domains: {len(domains_to_process)}")
        print(f"Successful: {sum(1 for r in results.values() if r == 'SUCCESS')}")
        print(f"Failed: {len(failed_domains)}")
        print()

        print("Per-domain results:")
        for domain, status in results.items():
            status_icon = "✅" if status == "SUCCESS" else "❌"
            print(f"  {status_icon} {domain}: {status}")

        print(f"{'=' * 50}")

        # Return exit code 1 if any domain failed
        if failed_domains:
            print(
                f"❌ Multi-domain processing completed with {len(failed_domains)} failure(s)"
            )
            return 1
        else:
            print("🎉 Multi-domain processing completed successfully")
            return 0


if __name__ == "__main__":
    sys.exit(main())
