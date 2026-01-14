"""
Configuration building for ETL CLI.

Story 7.4: CLI Layer Modularization - Run config construction utilities.
"""

import argparse
import re
from typing import Any, Dict, List


def _parse_pk_override(pk_arg: Any) -> List[str]:
    """
    Parse CLI --pk override into a clean list of column names.

    Accepts comma/semicolon separated string or list-like; ignores empty items.

    Args:
        pk_arg: Primary key override argument (string or list)

    Returns:
        List of column names
    """
    if pk_arg is None:
        return []
    # If already a list, normalize and return
    if isinstance(pk_arg, list):
        return [str(x).strip() for x in pk_arg if str(x).strip()]
    # Otherwise split by comma/semicolon
    text = str(pk_arg)
    parts = re.split(r"[,;]", text)
    return [p.strip() for p in parts if p.strip()]


def build_run_config(args: argparse.Namespace, domain: str) -> Dict[str, Any]:  # noqa: PLR0912, PLR0915 - CLI config builder
    """
    Build Dagster run_config from CLI arguments for a specific domain.

    Args:
        args: Parsed command line arguments
        domain: Domain name to process

    Returns:
        Dictionary with nested configuration for all ops
    """
    # Single source of truth calculation - execute takes precedence over plan-only
    effective_plan_only = (
        not args.execute
        if hasattr(args, "execute")
        else getattr(args, "plan_only", True)
    )

    # Load table/pk from data_sources.yml with proper defaults inheritance
    # Story 6.2-P14: Use get_domain_config_v2() for defaults/overrides
    from work_data_hub.config.settings import get_settings
    from work_data_hub.infrastructure.settings.data_source_schema import (
        DataSourcesValidationError,
        get_domain_config_v2,
    )

    settings = get_settings()

    try:
        # Story 6.2-P14: Use get_domain_config_v2 for proper defaults inheritance
        domain_cfg = get_domain_config_v2(
            domain, config_path=str(settings.data_sources_config)
        )

        # Extract table/schema/pk from validated config with inheritance
        if domain_cfg.output:
            table_name = domain_cfg.output.table
            schema_name = (
                domain_cfg.output.schema_name
            )  # ✅ Now inherits from defaults!
            # Use schema-qualified table name with proper SQL identifier quoting
            table = (
                f'"{schema_name}"."{table_name}"' if schema_name else f'"{table_name}"'
            )

            # Try to get pk from output config (may not exist in all configs)
            pk = getattr(domain_cfg.output, "pk", [])
        else:
            # Fallback for legacy domains without output config
            table = f'"{domain}"'
            pk = []

        # Runtime override via --pk (only affects delete_insert mode)
        pk_override = _parse_pk_override(getattr(args, "pk", None))
        if pk_override:
            pk = pk_override

    except DataSourcesValidationError as e:
        print(f"Warning: Could not load domain config for {domain}: {e}")
        table = f'"{domain}"'
        pk = []
    except Exception as e:
        print(f"Warning: Unexpected error loading config for {domain}: {e}")
        table = f'"{domain}"'
        pk = []

    # Build discover_files_op config with optional period and selection strategy
    discover_config: Dict[str, Any] = {"domain": domain}
    if hasattr(args, "period") and args.period:
        discover_config["period"] = args.period
    # Story 6.2-P16: Pass file selection strategy from CLI to op
    if hasattr(args, "file_selection") and args.file_selection:
        discover_config["selection_strategy"] = args.file_selection
    # Sprint Change Proposal 2026-01-08: Direct file processing
    if hasattr(args, "file") and args.file:
        discover_config["file_path"] = args.file

    # Story 7.5-5: Extract session_id for unified failure logging
    session_id = getattr(args, "session_id", None)

    run_config: Dict[str, Any] = {
        "ops": {
            "discover_files_op": {"config": discover_config},
            "load_op": {
                "config": {
                    "table": table,
                    "mode": args.mode,
                    "pk": pk,
                    "plan_only": effective_plan_only,
                    "skip": getattr(args, "skip_facts", False),
                    # session_id only used by processing ops, not LoadConfig
                }
            },
        }
    }

    # Add max_files parameter and conditionally configure ops
    max_files = getattr(args, "max_files", 1)

    # Determine sheet configuration
    sheet_value = getattr(args, "sheet", None)
    sheet_names_list = None

    if sheet_value is None:
        # Check if domain is Epic 3 schema and has sheet_name/sheet_names configured
        # Story 6.2-P14: Try to get sheet_name from domain config
        try:
            if domain_cfg:
                # Check for sheet_names (multi-sheet)
                if hasattr(domain_cfg, "sheet_names") and domain_cfg.sheet_names:
                    sheet_names_list = domain_cfg.sheet_names

                # Check for sheet_name (single fallback)
                if hasattr(domain_cfg, "sheet_name"):
                    sheet_value = domain_cfg.sheet_name
                else:
                    sheet_value = "0"
            else:
                sheet_value = "0"
        except (NameError, AttributeError):
            # domain_cfg might not be defined if exception occurred during loading
            sheet_value = "0"

    if max_files > 1:
        # Use new combined op for multi-file processing
        run_config["ops"]["read_and_process_sandbox_trustee_files_op"] = {
            "config": {"sheet": sheet_value, "max_files": max_files}
        }
    else:
        # Phase 4 Refactor: Use read_data_op for unified data loading
        # (replaces legacy read_excel_op)
        sheet_cfg: Any
        try:
            sheet_cfg = int(sheet_value) if sheet_value is not None else 0
        except Exception:
            sheet_cfg = sheet_value

        # Build read_data_op config (Phase 0: unified data loading)
        read_data_config: Dict[str, Any] = {
            "domain": domain,
            "sheet": sheet_cfg,
        }

        # Add sheet_names if configured (multi-sheet support)
        if sheet_names_list:
            read_data_config["sheet_names"] = sheet_names_list

        sample_value = getattr(args, "sample", None)
        if sample_value:
            read_data_config["sample"] = sample_value
        run_config["ops"]["read_data_op"] = {"config": read_data_config}

    # Phase 4 Enhancement: Always pass domain to backfill op
    # The op internally checks requires_backfill and FK configs
    # We must always pass the correct domain to prevent default value issues
    run_config["ops"]["generic_backfill_refs_op"] = {
        "config": {
            "domain": domain,
            "plan_only": effective_plan_only,
            "add_tracking_fields": False,  # mapping tables lack these
        }
    }

    # Phase 4 Refactor: Generic domain op configuration
    # Replaces all per-domain ops (process_annuity_performance_op, etc.)
    # with unified process_domain_op_v2 that uses DomainServiceProtocol
    run_config["ops"]["process_domain_op_v2"] = {
        "config": {
            "domain": domain,
            "plan_only": effective_plan_only,
            "session_id": session_id,
        }
    }

    return run_config
