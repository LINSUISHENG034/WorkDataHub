"""
Unified CLI entry point for WorkDataHub.

Story 6.2-P6: CLI Architecture Unification & Multi-Domain Batch Processing
Task 1.1: Create unified entry framework with argparse subcommands

Usage:
    python -m work_data_hub.cli <command> [options]

Available commands:
    etl          - Run ETL jobs (single or multi-domain)
    auth         - Authentication operations
    eqc-refresh  - EQC data refresh operations
    cleanse      - Data cleansing operations

Examples:
    # Single domain ETL
    python -m work_data_hub.cli etl --domains annuity_performance --period 202411 --execute

    # Multi-domain ETL
    python -m work_data_hub.cli etl --domains annuity_performance,annuity_income --period 202411 --execute

    # All domains ETL
    python -m work_data_hub.cli etl --all-domains --period 202411 --execute

    # Authentication
    python -m work_data_hub.cli auth refresh

    # EQC refresh
    python -m work_data_hub.cli eqc-refresh --status

    # Data cleansing
    python -m work_data_hub.cli cleanse --table business_info --domain eqc_business_info
"""

import argparse
import sys
from typing import List, Optional


def main(argv: Optional[List[str]] = None) -> int:
    """
    Main CLI entry point with subcommand routing.

    Args:
        argv: Command line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    parser = argparse.ArgumentParser(
        prog="work_data_hub.cli",
        description="WorkDataHub CLI - Unified command-line interface",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single domain ETL
  python -m work_data_hub.cli etl --domains annuity_performance --period 202411 --execute

  # Multi-domain ETL
  python -m work_data_hub.cli etl --domains annuity_performance,annuity_income --period 202411 --execute

  # All domains ETL
  python -m work_data_hub.cli etl --all-domains --period 202411 --execute

  # Authentication
  python -m work_data_hub.cli auth refresh

  # EQC refresh
  python -m work_data_hub.cli eqc-refresh --status

  # Data cleansing
  python -m work_data_hub.cli cleanse --table business_info --domain eqc_business_info
        """,
    )

    # Create subparsers for commands
    subparsers = parser.add_subparsers(
        title="commands",
        description="Available commands",
        dest="command",
        required=True,
        help="Command to execute",
    )

    # ETL command (delegate all argument parsing to etl.py)
    etl_parser = subparsers.add_parser(
        "etl",
        help="Run ETL jobs (single or multi-domain)",
        description="Execute ETL jobs for one or more data domains",
        add_help=False,  # Let the delegated module handle help
    )

    # Auth command (delegate to auth module)
    auth_parser = subparsers.add_parser(
        "auth",
        help="Authentication operations",
        description="Manage authentication tokens and credentials",
        add_help=False,  # Let the delegated module handle help
    )

    # EQC refresh command (delegate to existing module)
    eqc_refresh_parser = subparsers.add_parser(
        "eqc-refresh",
        help="EQC data refresh operations",
        description="Refresh EQC data from API",
        add_help=False,  # Let the delegated module handle help
    )

    # Cleanse command (delegate to existing module)
    cleanse_parser = subparsers.add_parser(
        "cleanse",
        help="Data cleansing operations",
        description="Cleanse data in database tables",
        add_help=False,  # Let the delegated module handle help
    )

    # Parse arguments
    args, remaining_args = parser.parse_known_args(argv)

    # Route to appropriate command handler
    if args.command == "etl":
        # Delegate to etl module
        from work_data_hub.cli.etl import main as etl_main

        # Reconstruct argv for the delegated module
        delegated_argv = remaining_args if remaining_args else []
        return etl_main(delegated_argv)

    elif args.command == "auth":
        # Delegate to auth module
        from work_data_hub.cli.auth import main as auth_main

        # Reconstruct argv for the delegated module
        delegated_argv = remaining_args if remaining_args else []
        return auth_main(delegated_argv)

    elif args.command == "eqc-refresh":
        # Delegate to existing eqc_refresh module
        from work_data_hub.cli.eqc_refresh import main as eqc_refresh_main

        # Reconstruct argv for the delegated module
        delegated_argv = remaining_args if remaining_args else []
        return eqc_refresh_main(delegated_argv)

    elif args.command == "cleanse":
        # Delegate to existing cleanse_data module
        from work_data_hub.cli.cleanse_data import main as cleanse_main

        # Reconstruct argv for the delegated module
        delegated_argv = remaining_args if remaining_args else []
        return cleanse_main(delegated_argv)

    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
