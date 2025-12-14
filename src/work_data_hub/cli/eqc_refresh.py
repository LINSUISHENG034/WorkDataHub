"""
CLI for EQC data refresh operations.

Story 6.2-P5: EQC Data Persistence & Legacy Table Integration
Task 2.3 & 5.1: CLI entry point for data refresh operations with checkpoint support

Usage:
    # Check freshness status
    PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli.eqc_refresh --status

    # Refresh stale data (interactive confirmation)
    PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli.eqc_refresh --refresh-stale

    # Refresh specific companies
    PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli.eqc_refresh --company-ids 1000065057,1000087994

    # Refresh all data (legacy alias; prefer --initial-full-refresh)
    PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli.eqc_refresh --refresh-all

    # Initial full refresh with checkpoint support (Phase 5)
    PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli.eqc_refresh --initial-full-refresh --yes --checkpoint-dir ./checkpoints

    # Resume from checkpoint (aliases: --resume / --resume-from-checkpoint)
    PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli.eqc_refresh --resume-from-checkpoint --yes --checkpoint-dir ./checkpoints

    # Dry run (show what would be refreshed)
    PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli.eqc_refresh --refresh-stale --dry-run
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

from sqlalchemy import create_engine, text

from work_data_hub.config.settings import get_settings
from work_data_hub.infrastructure.enrichment.data_refresh_service import (
    EqcDataRefreshService,
)
from work_data_hub.infrastructure.enrichment.refresh_checkpoint import (
    RefreshCheckpoint,
)
from work_data_hub.utils.logging import get_logger

logger = get_logger(__name__)


def print_freshness_status(service: EqcDataRefreshService) -> None:
    status = service.get_freshness_status()

    print("\n" + "=" * 60)
    print("EQC Data Freshness Status")
    print("=" * 60)
    print(f"Threshold: {status.threshold_days} days")
    print(f"Total Companies: {status.total_companies}")
    print(f"Fresh (within threshold): {status.fresh_companies}")
    print(f"Stale (older than threshold): {status.stale_companies}")
    print(f"Never Updated: {status.never_updated}")
    print("=" * 60)

    if status.stale_companies > 0 or status.never_updated > 0:
        total_needs_refresh = status.stale_companies + status.never_updated
        print(f"\n⚠️  {total_needs_refresh} companies need refresh")
        print("\nRun with --refresh-stale to refresh stale data")
    else:
        print("\n✅ All data is fresh!")

    print()


def confirm_refresh(count: int, dry_run: bool = False) -> bool:
    if dry_run:
        print(f"\n[DRY RUN] Would refresh {count} companies")
        return True

    print(f"\n⚠️  About to refresh {count} companies from EQC API")
    print("This operation may take some time and will consume API quota.")

    response = input("\nContinue? [y/N]: ").strip().lower()
    return response == "y"


def print_refresh_results(result) -> None:
    print("\n" + "=" * 60)
    print("Refresh Results")
    print("=" * 60)
    print(f"Total Requested: {result.total_requested}")
    print(f"✅ Successful: {result.successful}")
    print(f"❌ Failed: {result.failed}")
    print(f"⏭️  Skipped: {result.skipped}")
    print("=" * 60)

    if result.errors:
        print("\nErrors:")
        for error in result.errors[:10]:
            print(f"  - {error}")
        if len(result.errors) > 10:
            print(f"  ... and {len(result.errors) - 10} more errors")


def _parse_failed_company_ids(errors: list[str]) -> list[str]:
    failed_ids: list[str] = []
    for error in errors:
        if ":" not in error:
            continue
        cid = error.split(":", 1)[0].strip()
        if cid and cid not in failed_ids:
            failed_ids.append(cid)
    return failed_ids


def _run_post_refresh_verification(connection) -> dict:
    """
    Post-refresh verification queries (Story 6.2-P5 AC22).

    Best-effort: failures are captured in returned dict.
    """
    results: dict = {}
    checks = {
        "base_info_total": "SELECT COUNT(*) AS c FROM enterprise.base_info",
        "base_info_raw_data_present": "SELECT COUNT(*) AS c FROM enterprise.base_info WHERE raw_data IS NOT NULL",
        "base_info_updated_at_present": "SELECT COUNT(*) AS c FROM enterprise.base_info WHERE updated_at IS NOT NULL",
        "business_info_cleansing_status_present": "SELECT COUNT(*) AS c FROM enterprise.business_info WHERE _cleansing_status IS NOT NULL",
    }

    for key, sql in checks.items():
        try:
            row = connection.execute(text(sql)).fetchone()
            results[key] = int(row[0]) if row else 0
        except Exception as exc:
            results[key] = f"ERROR: {type(exc).__name__}: {exc}"

    return results


def generate_refresh_report(checkpoint: RefreshCheckpoint, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = output_dir / f"refresh_report_{timestamp}.txt"

    with report_file.open("w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("EQC Data Refresh Report\n")
        f.write("=" * 70 + "\n\n")

        f.write(f"Operation ID: {checkpoint.checkpoint_id}\n")
        f.write(f"Operation Type: {checkpoint.operation_type}\n")
        f.write(f"Started At: {checkpoint.started_at}\n")
        f.write(f"Completed At: {checkpoint.completed_at}\n\n")

        f.write("Summary:\n")
        f.write("-" * 70 + "\n")
        f.write(f"Total Companies: {checkpoint.total_companies}\n")
        f.write(f"Processed: {checkpoint.processed_companies}\n")
        f.write(f"✅ Successful: {checkpoint.successful_companies}\n")
        f.write(f"❌ Failed: {checkpoint.failed_companies}\n")
        f.write(f"Next Index: {checkpoint.next_index}\n")
        success_rate = (
            (checkpoint.successful_companies / checkpoint.total_companies * 100)
            if checkpoint.total_companies > 0
            else 0.0
        )
        f.write(f"Success Rate: {success_rate:.1f}%\n\n")

        if checkpoint.failed_company_ids:
            f.write("Failed Company IDs:\n")
            f.write("-" * 70 + "\n")
            for company_id in checkpoint.failed_company_ids[:100]:
                f.write(f"  - {company_id}\n")
            if len(checkpoint.failed_company_ids) > 100:
                f.write(f"  ... and {len(checkpoint.failed_company_ids) - 100} more\n")

        if checkpoint.verification:
            f.write("\nPost-Refresh Verification (AC22):\n")
            f.write("-" * 70 + "\n")
            for key, value in checkpoint.verification.items():
                f.write(f"  - {key}: {value}\n")

        f.write("\n" + "=" * 70 + "\n")
        f.write("End of Report\n")
        f.write("=" * 70 + "\n")

    logger.info("refresh_report.generated", report_file=str(report_file))
    return report_file


def _run_full_refresh_with_checkpoint(
    *,
    connection,
    service: EqcDataRefreshService,
    company_ids: list[str],
    checkpoint_dir: Path,
    batch_size: int,
    rate_limit: Optional[float],
) -> int:
    checkpoint = RefreshCheckpoint(
        checkpoint_id=f"full_refresh_{uuid4().hex[:8]}",
        operation_type="full_refresh",
        total_companies=len(company_ids),
        company_ids=company_ids,
        next_index=0,
    )
    checkpoint.save(checkpoint_dir)
    print(f"📋 Checkpoint initialized: {checkpoint.checkpoint_id}")

    for start in range(0, len(company_ids), batch_size):
        end = min(start + batch_size, len(company_ids))
        batch = company_ids[start:end]

        result = service.refresh_by_company_ids(company_ids=batch, rate_limit=rate_limit)
        connection.commit()
        print_refresh_results(result)

        checkpoint.update_progress(
            processed=result.total_requested,
            successful=result.successful,
            failed=result.failed,
            failed_ids=_parse_failed_company_ids(result.errors),
            batch=checkpoint.current_batch + 1,
            next_index=end,
        )
        checkpoint.failed_companies = len(checkpoint.failed_company_ids)
        checkpoint.save(checkpoint_dir)

    if checkpoint.next_index >= len(company_ids) and not checkpoint.failed_company_ids:
        checkpoint.mark_completed()

    checkpoint.verification = _run_post_refresh_verification(connection)
    checkpoint.save(checkpoint_dir)

    report_file = generate_refresh_report(checkpoint, checkpoint_dir)
    print(f"\n📄 Report saved to: {report_file}")
    return 0 if not checkpoint.failed_company_ids else 1


def handle_resume(
    checkpoint_dir: Path,
    connection,
    service: EqcDataRefreshService,
    *,
    yes: bool,
    batch_size: int,
    rate_limit: Optional[float],
) -> int:
    checkpoint = RefreshCheckpoint.find_latest(checkpoint_dir, "full_refresh")
    if not checkpoint:
        print("❌ No incomplete checkpoint found to resume from")
        return 1

    print(f"\n📋 Found checkpoint: {checkpoint.checkpoint_id}")
    print(
        f"Progress: {checkpoint.progress_percentage:.1f}% ({checkpoint.processed_companies}/{checkpoint.total_companies})"
    )
    print(f"Remaining: {checkpoint.remaining_companies} companies")

    if checkpoint.failed_company_ids:
        print(f"Failed companies: {len(checkpoint.failed_company_ids)}")

    if not yes:
        response = input("\nResume from this checkpoint? [y/N]: ").strip().lower()
        if response != "y":
            print("❌ Resume cancelled")
            return 0

    print("\n🔄 Resuming refresh operation...")

    if not checkpoint.company_ids:
        # Backward compatible reconstruction (best-effort)
        checkpoint.company_ids = [c.company_id for c in service.get_all_companies()]
        if checkpoint.next_index <= 0 and checkpoint.processed_companies > 0:
            checkpoint.next_index = min(checkpoint.processed_companies, len(checkpoint.company_ids))
        checkpoint.save(checkpoint_dir)

    # Phase 1: retry failures without moving next_index
    if checkpoint.failed_company_ids:
        print(f"\n🔁 Retrying {len(checkpoint.failed_company_ids)} failed companies...")
        retry_ids = list(checkpoint.failed_company_ids)
        for start in range(0, len(retry_ids), batch_size):
            batch = retry_ids[start : start + batch_size]
            result = service.refresh_by_company_ids(company_ids=batch, rate_limit=rate_limit)
            connection.commit()
            print_refresh_results(result)

            attempted = set(batch)
            still_failed = set(_parse_failed_company_ids(result.errors))
            succeeded = attempted - still_failed

            checkpoint.failed_company_ids = [
                cid for cid in checkpoint.failed_company_ids if cid not in attempted
            ]
            for cid in sorted(still_failed):
                if cid not in checkpoint.failed_company_ids:
                    checkpoint.failed_company_ids.append(cid)

            checkpoint.successful_companies += len(succeeded)
            checkpoint.failed_companies = len(checkpoint.failed_company_ids)
            checkpoint.current_batch += 1
            checkpoint.last_updated_at = datetime.now().isoformat()
            checkpoint.save(checkpoint_dir)

    # Phase 2: continue remaining companies from the stable list
    if checkpoint.next_index < len(checkpoint.company_ids):
        remaining = checkpoint.company_ids[checkpoint.next_index :]
        print(
            f"\n📊 Continuing from index {checkpoint.next_index} ({len(remaining)} remaining new companies)"
        )

        for start in range(checkpoint.next_index, len(checkpoint.company_ids), batch_size):
            end = min(start + batch_size, len(checkpoint.company_ids))
            batch = checkpoint.company_ids[start:end]

            result = service.refresh_by_company_ids(company_ids=batch, rate_limit=rate_limit)
            connection.commit()
            print_refresh_results(result)

            checkpoint.update_progress(
                processed=result.total_requested,
                successful=result.successful,
                failed=result.failed,
                failed_ids=_parse_failed_company_ids(result.errors),
                batch=checkpoint.current_batch + 1,
                next_index=end,
            )
            checkpoint.failed_companies = len(checkpoint.failed_company_ids)
            checkpoint.save(checkpoint_dir)

    if checkpoint.next_index >= len(checkpoint.company_ids) and not checkpoint.failed_company_ids:
        checkpoint.mark_completed()

    checkpoint.verification = _run_post_refresh_verification(connection)
    checkpoint.save(checkpoint_dir)

    report_file = generate_refresh_report(checkpoint, checkpoint_dir)
    print(f"\n📄 Report saved to: {report_file}")

    if checkpoint.failed_company_ids:
        print("\n⚠️  Some failures remain. Re-run --resume to retry.")
        return 1

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="EQC data refresh operations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--status", action="store_true", help="Show freshness status report")
    group.add_argument(
        "--refresh-stale",
        action="store_true",
        help="Refresh stale data (interactive confirmation)",
    )
    group.add_argument(
        "--refresh-all",
        action="store_true",
        help="Refresh all data (legacy alias; prefer --initial-full-refresh)",
    )
    group.add_argument(
        "--initial-full-refresh",
        action="store_true",
        help="Initial full refresh (Phase 5): checkpoint/resume + report + verification",
    )
    group.add_argument(
        "--company-ids",
        type=str,
        help="Refresh specific companies (comma-separated IDs)",
    )
    group.add_argument("--resume", action="store_true", help="Resume from last checkpoint (alias)")
    group.add_argument(
        "--resume-from-checkpoint",
        action="store_true",
        help="Resume from last checkpoint",
    )

    parser.add_argument(
        "--checkpoint",
        action="store_true",
        help="Enable checkpoint support for resumable operations (Phase 5)",
    )
    parser.add_argument(
        "--checkpoint-dir",
        type=str,
        default="./checkpoints",
        help="Directory for checkpoint files (default: ./checkpoints)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview mode - show what would be refreshed without making changes",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip interactive confirmation prompts (explicit opt-in)",
    )
    parser.add_argument(
        "--threshold-days",
        type=int,
        help="Custom freshness threshold in days (overrides settings)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        help="Batch size for refresh operations (overrides settings)",
    )
    parser.add_argument(
        "--rate-limit",
        type=float,
        help="Requests per second during refresh (overrides settings)",
    )
    parser.add_argument(
        "--max-companies",
        type=int,
        help="Maximum companies to refresh (for testing)",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        settings = get_settings()
    except Exception as e:
        print(f"❌ Failed to load settings: {e}", file=sys.stderr)
        return 1

    try:
        engine = create_engine(settings.get_database_connection_string())
    except Exception as e:
        print(f"❌ Failed to create database engine: {e}", file=sys.stderr)
        return 1

    try:
        with engine.connect() as connection:
            service = EqcDataRefreshService(connection)

            if args.status:
                print_freshness_status(service)
                connection.commit()
                return 0

            if args.company_ids:
                company_ids = [cid.strip() for cid in args.company_ids.split(",") if cid.strip()]
                if not company_ids:
                    print("❌ No valid company IDs provided")
                    return 1

                if args.dry_run:
                    print(f"\n[DRY RUN] Would refresh {len(company_ids)} companies: {company_ids[:10]}")
                    return 0

                if not args.yes and not confirm_refresh(len(company_ids), dry_run=False):
                    print("❌ Refresh cancelled")
                    return 0

                result = service.refresh_by_company_ids(company_ids=company_ids, rate_limit=args.rate_limit)
                connection.commit()
                print_refresh_results(result)
                return 0 if result.failed == 0 else 1

            if args.refresh_stale:
                stale_companies = service.get_stale_companies(
                    threshold_days=args.threshold_days,
                    limit=args.max_companies,
                )

                if not stale_companies:
                    print("\n✅ No stale companies found!")
                    return 0

                if args.dry_run:
                    print(f"\n[DRY RUN] Would refresh {len(stale_companies)} stale companies")
                    print("\nSample (first 10):")
                    for company in stale_companies[:10]:
                        days_str = f"{company.days_since_update} days" if company.days_since_update else "never"
                        print(
                            f"  - {company.company_id}: {company.company_full_name} (last updated: {days_str})"
                        )
                    if len(stale_companies) > 10:
                        print(f"  ... and {len(stale_companies) - 10} more companies")
                    return 0

                if not args.yes and not confirm_refresh(len(stale_companies), dry_run=False):
                    print("❌ Refresh cancelled")
                    return 0

                print(f"\n🔄 Refreshing {len(stale_companies)} stale companies...")
                result = service.refresh_stale_companies(
                    threshold_days=args.threshold_days,
                    batch_size=args.batch_size,
                    rate_limit=args.rate_limit,
                    max_companies=args.max_companies,
                )

                connection.commit()
                print_refresh_results(result)
                return 0 if result.failed == 0 else 1

            if args.refresh_all or args.initial_full_refresh:
                if args.initial_full_refresh:
                    args.checkpoint = True

                all_companies = service.get_all_companies(limit=args.max_companies)
                company_ids = [c.company_id for c in all_companies]
                total_companies = len(company_ids)

                if total_companies == 0:
                    print("\n⚠️  No companies found in base_info table")
                    return 0

                if args.dry_run:
                    print(f"\n[DRY RUN] Would refresh all {total_companies} companies")
                    if args.checkpoint:
                        print(f"[DRY RUN] Checkpoint would be saved to: {args.checkpoint_dir}")
                    return 0

                if not args.yes:
                    print(f"\n⚠️  WARNING: About to refresh ALL {total_companies} companies!")
                    print("This is a resource-intensive operation.")
                    if args.checkpoint:
                        print(f"Checkpoint support enabled. Progress will be saved to: {args.checkpoint_dir}")
                    if not confirm_refresh(total_companies, dry_run=False):
                        print("❌ Refresh cancelled")
                        return 0

                batch_size = args.batch_size or settings.eqc_data_refresh_batch_size

                if not args.checkpoint:
                    print(f"\n🔄 Refreshing all {total_companies} companies (no checkpoints)...")
                    result = service.refresh_by_company_ids(company_ids=company_ids, rate_limit=args.rate_limit)
                    connection.commit()
                    print_refresh_results(result)
                    verification = _run_post_refresh_verification(connection)
                    print("\nPost-Refresh Verification (AC22):")
                    for k, v in verification.items():
                        print(f"  - {k}: {v}")
                    return 0 if result.failed == 0 else 1

                print(f"\n🔄 Refreshing all {total_companies} companies with checkpoints...")
                checkpoint_dir = Path(args.checkpoint_dir)
                return _run_full_refresh_with_checkpoint(
                    connection=connection,
                    service=service,
                    company_ids=company_ids,
                    checkpoint_dir=checkpoint_dir,
                    batch_size=batch_size,
                    rate_limit=args.rate_limit,
                )

            if args.resume or args.resume_from_checkpoint:
                checkpoint_dir = Path(args.checkpoint_dir)
                batch_size = args.batch_size or settings.eqc_data_refresh_batch_size
                return handle_resume(
                    checkpoint_dir,
                    connection,
                    service,
                    yes=args.yes,
                    batch_size=batch_size,
                    rate_limit=args.rate_limit,
                )

        return 0

    except KeyboardInterrupt:
        print("\n\n❌ Operation cancelled by user")
        return 130

    except Exception as e:
        print(f"\n❌ Unexpected error: {e}", file=sys.stderr)
        logger.error(
            "eqc_refresh.unexpected_error",
            error=str(e),
            error_type=type(e).__name__,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())

