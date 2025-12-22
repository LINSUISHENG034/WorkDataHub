"""
Authentication CLI for WorkDataHub.

Story 6.2-P6: CLI Architecture Unification & Multi-Domain Batch Processing
Task 3.1: Create cli/auth.py from auto_eqc_auth.py

This module provides CLI interface for authentication operations, primarily
for refreshing EQC (平安E企查) authentication tokens.

Usage:
    # Refresh EQC token (interactive QR code login)
    python -m work_data_hub.cli auth refresh

    # Refresh with custom timeout
    python -m work_data_hub.cli auth refresh --timeout 300

    # Refresh without saving to .env file
    python -m work_data_hub.cli auth refresh --no-save
"""

import argparse
import sys
from typing import List, Optional

from work_data_hub.io.auth.auto_eqc_auth import (
    DEFAULT_ENV_FILE,
    DEFAULT_TIMEOUT_SECONDS,
    run_get_token_auto_qr,
)


def main(argv: Optional[List[str]] = None) -> int:
    """
    Main CLI entry point for authentication operations.

    Args:
        argv: Command line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    parser = argparse.ArgumentParser(
        prog="work_data_hub.cli auth",
        description="WorkDataHub Authentication CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Refresh EQC token (interactive QR code login)
  python -m work_data_hub.cli auth refresh

  # Refresh with custom timeout (5 minutes)
  python -m work_data_hub.cli auth refresh --timeout 300

  # Refresh without saving to .env file
  python -m work_data_hub.cli auth refresh --no-save

  # Specify custom .env file location
  python -m work_data_hub.cli auth refresh --env-file /path/to/.env
        """,
    )

    # Create subparsers for auth operations
    subparsers = parser.add_subparsers(
        title="operations",
        description="Available authentication operations",
        dest="operation",
        required=True,
        help="Authentication operation to perform",
    )

    # Refresh command
    refresh_parser = subparsers.add_parser(
        "refresh",
        help="Refresh EQC authentication token via QR code login",
        description="Launch automated QR code login flow to refresh EQC authentication token",
    )
    refresh_parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"Maximum time to wait for authentication in seconds (default: {DEFAULT_TIMEOUT_SECONDS})",
    )
    refresh_parser.add_argument(
        "--no-save",
        action="store_true",
        help="Do not save token to .env file (only display it)",
    )
    refresh_parser.add_argument(
        "--env-file",
        type=str,
        default=DEFAULT_ENV_FILE,
        help=f"Path to .env file for saving token (default: {DEFAULT_ENV_FILE})",
    )

    args = parser.parse_args(argv)

    # Route to appropriate operation handler
    if args.operation == "refresh":
        return _execute_refresh(args)
    else:
        parser.print_help()
        return 1


def _execute_refresh(args: argparse.Namespace) -> int:
    """
    Execute EQC token refresh operation.

    Args:
        args: Parsed command line arguments

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    print("🔐 Starting EQC Authentication Token Refresh...")
    print(f"   Timeout: {args.timeout} seconds")
    print(f"   Save to file: {'No' if args.no_save else 'Yes'}")
    if not args.no_save:
        print(f"   Target file: {args.env_file}")
    print("=" * 50)
    print()
    print("📱 A QR code window will appear shortly.")
    print("   Please scan it with the '快乐平安' mobile app.")
    print()

    try:
        # Call the authentication function
        token = run_get_token_auto_qr(
            timeout_seconds=args.timeout,
            save_to_env=not args.no_save,
            env_file=args.env_file,
        )

        if token:
            print()
            print("=" * 50)
            print("🎉 Authentication successful!")
            print("=" * 50)

            if args.no_save:
                print()
                print("📋 Token (not saved to file):")
                print(f"   {token}")
                print()
                print("💡 To save this token, run without --no-save flag")

            return 0
        else:
            print()
            print("=" * 50)
            print("❌ Authentication failed or was cancelled")
            print("=" * 50)
            print()
            print("Possible reasons:")
            print("  • QR code window was closed manually")
            print("  • Authentication timeout exceeded")
            print("  • Network connection issues")
            print("  • Browser automation failed")
            print()
            print("💡 Try running the command again")
            return 1

    except KeyboardInterrupt:
        print()
        print("⚠️  Authentication cancelled by user (Ctrl+C)")
        return 130

    except Exception as e:
        print()
        print("=" * 50)
        print("❌ Unexpected error during authentication")
        print("=" * 50)
        print(f"Error: {e}")
        print()
        print("💡 Please check:")
        print("  • Network connection is stable")
        print("  • Playwright browser dependencies are installed")
        print("  • No firewall blocking browser automation")
        return 1


if __name__ == "__main__":
    sys.exit(main())
