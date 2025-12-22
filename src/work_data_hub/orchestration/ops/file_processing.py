"""File discovery and Excel reading ops (Story 7.1).

This module contains ops for file discovery and Excel reading:
- DiscoverFilesConfig: Configuration for file discovery
- discover_files_op: Discover files for specified domain
- ReadExcelConfig: Configuration for Excel reading
- read_excel_op: Read Excel file and return rows
- ReadProcessConfig: Configuration for multi-file processing
- read_and_process_sandbox_trustee_files_op: Process multiple trustee files
"""

import logging
from typing import Any, Dict, List, Optional

import yaml
from dagster import Config, OpExecutionContext, op
from pydantic import field_validator

from work_data_hub.config.settings import get_settings
from work_data_hub.domain.sandbox_trustee_performance.service import process
from work_data_hub.io.connectors.file_connector import (
    FileDiscoveryService,
)
from work_data_hub.io.readers.excel_reader import read_excel_rows

from ._internal import _load_valid_domains

logger = logging.getLogger(__name__)


class DiscoverFilesConfig(Config):
    """Configuration for file discovery operation."""

    domain: str = "sandbox_trustee_performance"
    period: Optional[str] = None  # YYYYMM format for Epic 3 schema domains
    # Story 6.2-P16: File selection strategy when multiple files match
    selection_strategy: str = "error"  # error, newest, oldest, first

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, v: str) -> str:
        """Validate domain exists in data_sources.yml configuration."""
        valid_domains = _load_valid_domains()
        if v not in valid_domains:
            raise ValueError(f"Domain '{v}' not supported. Valid: {valid_domains}")
        return v

    @field_validator("selection_strategy")
    @classmethod
    def validate_selection_strategy(cls, v: str) -> str:
        """Validate selection strategy is valid."""
        valid = ["error", "newest", "oldest", "first"]
        if v not in valid:
            raise ValueError(f"Strategy '{v}' not valid. Valid: {valid}")
        return v


@op
def discover_files_op(
    context: OpExecutionContext, config: DiscoverFilesConfig
) -> List[str]:
    """
    Discover files for specified domain, return file paths as strings.

    Supports dual-schema routing:
    - Epic 3 schema (base_path, file_patterns, version_strategy) → FileDiscoveryService
    - Legacy schema (pattern, select) → DataSourceConnector

    Args:
        context: Dagster execution context
        config: Configuration with domain and optional period parameters

    Returns:
        List of file paths (JSON-serializable strings)
    """
    settings = get_settings()

    # Load domain configuration to detect schema type
    try:
        with open(settings.data_sources_config, "r", encoding="utf-8") as f:
            data_sources = yaml.safe_load(f) or {}
        if not isinstance(data_sources, dict):
            data_sources = {}

        domain_config = data_sources.get("domains", {}).get(config.domain, {})

        # Detect schema type based on keys present
        is_epic3_schema = (
            "base_path" in domain_config and "file_patterns" in domain_config
        )
        is_legacy_schema = "pattern" in domain_config and "select" in domain_config

        if is_epic3_schema:
            # Route to Epic 3 FileDiscoveryService
            context.log.info(
                f"Using Epic 3 schema discovery for domain '{config.domain}'"
            )

            # Validate period is provided if base_path contains template variables
            base_path = domain_config.get("base_path", "")
            if "{YYYYMM}" in base_path or "{YYYY}" in base_path or "{MM}" in base_path:
                if not config.period:
                    raise ValueError(
                        f"Domain '{config.domain}' requires --period parameter "
                        f"(base_path contains template variables: {base_path})"
                    )

            # Use FileDiscoveryService for Epic 3 schema
            file_discovery = FileDiscoveryService()

            try:
                # Call discover_file (discovery-only, no Excel loading)
                template_vars = {}
                if config.period:
                    template_vars["YYYYMM"] = config.period

                # Story 6.2-P16: Convert strategy string to enum
                from work_data_hub.io.connectors.file_pattern_matcher import (
                    SelectionStrategy,
                )

                strategy = SelectionStrategy(config.selection_strategy)

                context.log.info(f"Discovery with selection_strategy={strategy.value}")

                match_result = file_discovery.discover_file(
                    domain=config.domain, selection_strategy=strategy, **template_vars
                )

                context.log.info(
                    f"Epic 3 discovery completed - domain: {config.domain}, "
                    f"file: {match_result.file_path}, "
                    f"version: {match_result.version}, "
                    f"sheet: {match_result.sheet_name}"
                )

                # Return as list for backward compatibility
                return [str(match_result.file_path)]

            except Exception as e:
                # Use str(e) for message, e.to_dict() for structured logging (AC6)
                error_msg = str(e)
                error_details = (
                    e.to_dict() if hasattr(e, "to_dict") else {"error": error_msg}
                )
                context.log.error(
                    f"Epic 3 discovery failed for domain '{config.domain}': {error_msg}",
                    extra={"discovery_error": error_details},
                )
                raise

        else:
            # Route to Epic 3 FileDiscoveryService even for legacy config structure if possible,
            # but strictly speaking we only support Epic 3 schema now.
            # However, existing domains might not have been fully migrated in config.
            # Since User enforces "Zero Legacy Policy" for CODE, we assume config matches or we fail.
            raise ValueError(
                f"Domain '{config.domain}' configuration does not match Epic 3 schema (base_path, file_patterns). "
                f"Legacy DataSourceConnector support has been removed."
            )

    except Exception as e:
        context.log.error(f"File discovery failed for domain '{config.domain}': {e}")
        raise


class ReadExcelConfig(Config):
    """Configuration for Excel reading operation."""

    # Accept sheet index (int) or sheet name (str)
    sheet: Any = 0

    @field_validator("sheet")
    @classmethod
    def validate_sheet(cls, v: Any) -> Any:
        """Validate sheet index/name."""
        # Allow string sheet names as-is
        if isinstance(v, str) and v.strip():
            return v.strip()
        # Allow non-negative integers
        try:
            iv = int(v)
        except Exception:
            raise ValueError(
                "Sheet must be a non-negative integer or a non-empty string name"
            )
        if iv < 0:
            raise ValueError("Sheet index must be non-negative")
        return iv


@op
def read_excel_op(
    context: OpExecutionContext, config: ReadExcelConfig, file_paths: List[str]
) -> List[Dict[str, Any]]:
    """
    Read Excel file from first discovered path and return rows as list of dictionaries.

    Args:
        context: Dagster execution context
        config: Configuration with sheet parameter
        file_paths: List of discovered file paths (uses first one for MVP)

    Returns:
        List of row dictionaries (JSON-serializable)
    """
    if not file_paths:
        context.log.warning("No file paths provided to read_excel_op")
        return []

    # For MVP: process first file only
    file_path = file_paths[0]

    try:
        rows = read_excel_rows(file_path, sheet=config.sheet)

        context.log.info(
            f"Excel reading completed - file: {file_path}, "
            f"sheet: {config.sheet}, rows: {len(rows)}, "
            f"columns: {list(rows[0].keys()) if rows else []}"
        )

        return rows

    except Exception as e:
        context.log.error(f"Excel reading failed for '{file_path}': {e}")
        raise


class ReadProcessConfig(Config):
    """Configuration for reading and processing multiple trustee files."""

    sheet: int = 0
    max_files: int = 1

    @field_validator("sheet")
    @classmethod
    def validate_sheet(cls, v: int) -> int:
        """Validate sheet index is non-negative."""
        if v < 0:
            raise ValueError("Sheet index must be non-negative")
        return v

    @field_validator("max_files")
    @classmethod
    def validate_max_files(cls, v: int) -> int:
        """Validate max_files is positive and reasonable."""
        if v < 1:
            raise ValueError("max_files must be at least 1")
        if v > 20:  # Reasonable upper bound
            raise ValueError("max_files cannot exceed 20")
        return v


@op
def read_and_process_sandbox_trustee_files_op(
    context: OpExecutionContext, config: ReadProcessConfig, file_paths: List[str]
) -> List[Dict[str, Any]]:
    """
    Process multiple trustee files and return accumulated results.

    Args:
        context: Dagster execution context
        config: Configuration with sheet and max_files parameters
        file_paths: List of discovered file paths

    Returns:
        List of processed record dictionaries (JSON-serializable)
    """
    # Limit files like existing MVP approach
    paths_to_process = (file_paths or [])[: min(len(file_paths), config.max_files)]
    all_processed: List[Dict[str, Any]] = []

    for file_path in paths_to_process:
        try:
            # Follow existing read_excel_op approach
            rows = read_excel_rows(file_path, sheet=config.sheet)

            # Follow existing process_trustee_performance_op approach
            models = process(rows, data_source=file_path)

            # JSON-serializable accumulation (use mode="json" for friendly types)
            processed_dicts = [
                model.model_dump(mode="json", by_alias=True, exclude_none=True)
                for model in models
            ]
            all_processed.extend(processed_dicts)

            # Structured logging like existing ops
            context.log.info(
                "Processed %s: %s rows -> %s records",
                file_path,
                len(rows),
                len(processed_dicts),
            )

        except Exception as e:
            context.log.error(f"Failed to process file {file_path}: {e}")
            raise

    context.log.info(
        "Multi-file processing completed: %s files, %s total records",
        len(paths_to_process),
        len(all_processed),
    )
    return all_processed
