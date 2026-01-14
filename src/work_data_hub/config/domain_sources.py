"""Domain Source Configuration Loader.

Story: Orchestration Layer Refactor - Phase 1
Location: config/domain_sources.py

加载 domain_sources.yaml 配置，提供 DOMAIN_SOURCE_REGISTRY。
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml


@dataclass
class DiscoveryConfig:
    """文件发现配置."""

    path_pattern: str
    sheet_name: Optional[str] = None
    sheet_names: Optional[List[str]] = None


@dataclass
class TableConfig:
    """Single table configuration for multi-table loading."""

    schema: str
    table: str
    role: str  # "primary" | "detail"


@dataclass
class JoinStrategy:
    """Table merge strategy configuration."""

    type: str  # "merge_on_key" | "left_join" | "union"
    key_columns: List[str] = field(default_factory=list)


@dataclass
class DomainSourceConfig:
    """Domain 数据源配置."""

    source_type: str  # "single_file" or "multi_table"
    discovery: Optional[DiscoveryConfig] = None
    tables: Optional[List[TableConfig]] = None
    join_strategy: Optional[JoinStrategy] = None
    output_format: str = "flattened"


def _load_config() -> Dict[str, DomainSourceConfig]:
    """从 YAML 文件加载配置."""
    config_path = (
        Path(__file__).parent.parent.parent.parent / "config" / "domain_sources.yaml"
    )

    if not config_path.exists():
        return {}

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    result = {}
    for domain, cfg in raw.items():
        # Parse discovery config
        discovery = None
        if "discovery" in cfg:
            discovery = DiscoveryConfig(**cfg["discovery"])

        # Parse tables config (for multi_table source type)
        tables = None
        if "tables" in cfg:
            tables = [TableConfig(**t) for t in cfg["tables"]]

        # Parse join strategy
        join_strategy = None
        if "join_strategy" in cfg:
            join_strategy = JoinStrategy(**cfg["join_strategy"])

        result[domain] = DomainSourceConfig(
            source_type=cfg.get("source_type", "single_file"),
            discovery=discovery,
            tables=tables,
            join_strategy=join_strategy,
            output_format=cfg.get("output_format", "flattened"),
        )
    return result


DOMAIN_SOURCE_REGISTRY: Dict[str, DomainSourceConfig] = _load_config()
