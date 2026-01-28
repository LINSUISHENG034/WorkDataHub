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
    eqc-gui      - Launch EQC quick query GUI (Tkinter)
    eqc-gui-fluent - Launch EQC quick query GUI (Fluent/Modern)
    cleanse      - Data cleansing operations
    customer-mdm - Customer Master Data Management operations

Examples:
    # Single domain ETL
    python -m work_data_hub.cli etl --domains annuity_performance --period 202411 \
        --execute

    # Multi-domain ETL
    python -m work_data_hub.cli etl \
        --domains annuity_performance,annuity_income --period 202411 --execute

    # All domains ETL
    python -m work_data_hub.cli etl --all-domains --period 202411 --execute

    # Authentication
    python -m work_data_hub.cli auth refresh

    # EQC refresh
    python -m work_data_hub.cli eqc-refresh --status

    # EQC quick query GUI (Tkinter)
    python -m work_data_hub.cli eqc-gui

    # EQC quick query GUI (Fluent/Modern)
    python -m work_data_hub.cli eqc-gui-fluent

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
  python -m work_data_hub.cli etl --domains annuity_performance \\
      --period 202411 --execute

  # Multi-domain ETL
  python -m work_data_hub.cli etl \\
      --domains annuity_performance,annuity_income --period 202411 --execute

  # All domains ETL
  python -m work_data_hub.cli etl --all-domains --period 202411 --execute

  # Authentication
  python -m work_data_hub.cli auth refresh

  # EQC refresh
  python -m work_data_hub.cli eqc-refresh --status

  # Data cleansing
  python -m work_data_hub.cli cleanse --table business_info \\
      --domain eqc_business_info
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
    subparsers.add_parser(
        "etl",
        help="Run ETL jobs (single or multi-domain)",
        description="Execute ETL jobs for one or more data domains",
        add_help=False,  # Let the delegated module handle help
    )

    # Auth command (delegate to auth module)
    subparsers.add_parser(
        "auth",
        help="Authentication operations",
        description="Manage authentication tokens and credentials",
        add_help=False,  # Let the delegated module handle help
    )

    # EQC refresh command (delegate to existing module)
    subparsers.add_parser(
        "eqc-refresh",
        help="EQC data refresh operations",
        description="Refresh EQC data from API",
        add_help=False,  # Let the delegated module handle help
    )

    # EQC GUI command (Tkinter)
    subparsers.add_parser(
        "eqc-gui",
        help="Launch EQC quick query GUI (Tkinter version)",
        description="Launch Tkinter-based graphical interface for quick EQC lookups",
    )

    # EQC GUI Fluent command (PyQt)
    subparsers.add_parser(
        "eqc-gui-fluent",
        help="Launch EQC quick query GUI (Fluent/Modern version)",
        description="Launch modern Fluent-style GUI with dark mode support",
    )

    # Cleanse command (delegate to existing module)
    subparsers.add_parser(
        "cleanse",
        help="Data cleansing operations",
        description="Cleanse data in database tables",
        add_help=False,  # Let the delegated module handle help
    )

    # Customer MDM command (delegate to customer_mdm module)
    subparsers.add_parser(
        "customer-mdm",
        help="Customer Master Data Management operations",
        description="Manage customer master data synchronization",
        add_help=False,
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

    elif args.command == "eqc-gui":
        # Launch EQC Query GUI (Tkinter)
        from work_data_hub.gui.eqc_query.app import launch_gui

        launch_gui()
        return 0

    elif args.command == "eqc-gui-fluent":
        # Launch EQC Query GUI (Fluent/PyQt)
        from work_data_hub.gui.eqc_query_fluent.app import launch_gui

        launch_gui()
        return 0

    elif args.command == "cleanse":
        # Delegate to existing cleanse_data module
        from work_data_hub.cli.cleanse_data import main as cleanse_main

        # Reconstruct argv for the delegated module
        delegated_argv = remaining_args if remaining_args else []
        return cleanse_main(delegated_argv)

    elif args.command == "customer-mdm":
        # Delegate to customer_mdm module
        # Extract subcommand (e.g., "sync", "snapshot") from remaining_args
        if remaining_args and remaining_args[0] == "sync":
            from work_data_hub.cli.customer_mdm.sync import main as sync_main

            # Pass args after "sync" to the delegated module
            delegated_argv = remaining_args[1:] if len(remaining_args) > 1 else []
            return sync_main(delegated_argv)
        elif remaining_args and remaining_args[0] == "snapshot":
            from work_data_hub.cli.customer_mdm.snapshot import main as snapshot_main

            # Pass args after "snapshot" to the delegated module
            delegated_argv = remaining_args[1:] if len(remaining_args) > 1 else []
            return snapshot_main(delegated_argv)
        else:
            # No subcommand or unknown subcommand, show available options
            print("Customer MDM subcommands:")
            print("  sync      - Sync contract status from business.规模明细")
            print("  snapshot  - Refresh monthly snapshot data")
            print("\nUsage: customer-mdm <subcommand> [options]")
            return 1

    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
