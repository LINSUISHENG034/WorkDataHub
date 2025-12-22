"""
Tests for configuration loader edge cases and performance characteristics.
"""

from __future__ import annotations

import statistics
import time
from pathlib import Path

import pytest
import yaml

from work_data_hub.domain.reference_backfill.config_loader import (
    load_foreign_keys_config,
)


def _write_config(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


class TestConfigLoaderEdgeCases:
    """Edge-case behavior for load_foreign_keys_config."""

    def test_empty_foreign_keys_returns_empty_list(self, tmp_path: Path):
        config_path = _write_config(
            tmp_path / "data_sources.yml",
            """
schema_version: "1.0"
domains:
  annuity_performance:
    foreign_keys: []
""",
        )

        result = load_foreign_keys_config(config_path, "annuity_performance")
        assert result == []

    def test_missing_domain_returns_empty_list(self, tmp_path: Path):
        config_path = _write_config(
            tmp_path / "data_sources.yml",
            """
schema_version: "1.0"
domains:
  other_domain:
    foreign_keys: []
""",
        )

        result = load_foreign_keys_config(config_path, "annuity_performance")
        assert result == []

    def test_invalid_yaml_raises_value_error_with_prefix(self, tmp_path: Path):
        # Invalid YAML (unterminated list)
        config_path = _write_config(
            tmp_path / "data_sources.yml",
            """
schema_version: "1.0"
domains:
  annuity_performance:
    foreign_keys:
      - name: "fk_plan"
        source_column: "计划代码"
        target_table: "年金计划"
        target_key: "年金计划号"
        backfill_columns:
          - source: "计划代码"
            target: "年金计划号"
      - name: "fk_portfolio"
        source_column: "组合代码"
        target_table: "组合计划"
        target_key: "组合代码"
        backfill_columns:
          - source: "组合代码"
            target: "组合代码"
        depends_on: [fk_plan
""",
        )

        with pytest.raises(ValueError) as exc_info:
            load_foreign_keys_config(config_path, "annuity_performance")

        msg = str(exc_info.value)
        assert "Failed to load foreign_keys configuration" in msg

    def test_duplicate_names_raises_value_error_with_message(self, tmp_path: Path):
        config_path = _write_config(
            tmp_path / "data_sources.yml",
            """
schema_version: "1.0"
domains:
  annuity_performance:
    foreign_keys:
      - name: "fk_dup"
        source_column: "a"
        target_table: "t1"
        target_key: "k1"
        backfill_columns:
          - source: "a"
            target: "b"
      - name: "fk_dup"
        source_column: "c"
        target_table: "t2"
        target_key: "k2"
        backfill_columns:
          - source: "c"
            target: "d"
""",
        )

        with pytest.raises(ValueError) as exc_info:
            load_foreign_keys_config(config_path, "annuity_performance")

        msg = str(exc_info.value)
        assert "Duplicate foreign key names" in msg

    def test_missing_dep_in_same_domain_rejected(self, tmp_path: Path):
        config_path = _write_config(
            tmp_path / "data_sources.yml",
            """
schema_version: "1.0"
domains:
  annuity_performance:
    foreign_keys:
      - name: "fk_child"
        source_column: "a"
        target_table: "t1"
        target_key: "k1"
        depends_on: ["fk_parent"]
        backfill_columns:
          - source: "a"
            target: "b"
""",
        )

        with pytest.raises(ValueError) as exc_info:
            load_foreign_keys_config(config_path, "annuity_performance")

        assert "depends_on must reference same-domain FK" in str(exc_info.value)

    def test_invalid_config_type_raises_value_error(self, tmp_path: Path):
        """Invalid config type (string instead of list) should raise ValueError."""
        config_path = _write_config(
            tmp_path / "data_sources.yml",
            """
schema_version: "1.0"
domains:
  annuity_performance:
    foreign_keys: "invalid"
""",
        )

        with pytest.raises(ValueError):
            load_foreign_keys_config(config_path, "annuity_performance")

    def test_circular_dependency_detected(self, tmp_path: Path):
        config_path = _write_config(
            tmp_path / "data_sources.yml",
            """
schema_version: "1.0"
domains:
  annuity_performance:
    foreign_keys:
      - name: "fk_a"
        source_column: "a"
        target_table: "t1"
        target_key: "k1"
        depends_on: ["fk_b"]
        backfill_columns:
          - source: "a"
            target: "b"
      - name: "fk_b"
        source_column: "b"
        target_table: "t2"
        target_key: "k2"
        depends_on: ["fk_a"]
        backfill_columns:
          - source: "c"
            target: "d"
""",
        )

        with pytest.raises(ValueError) as exc_info:
            load_foreign_keys_config(config_path, "annuity_performance")

        assert "circular dependency" in str(exc_info.value)

    def test_triangular_circular_dependency_detected(self, tmp_path: Path):
        """Three-node circular dependency (A→B→C→A) should be detected."""
        config_path = _write_config(
            tmp_path / "data_sources.yml",
            """
schema_version: "1.0"
domains:
  annuity_performance:
    foreign_keys:
      - name: "fk_a"
        source_column: "a"
        target_table: "t1"
        target_key: "k1"
        depends_on: ["fk_c"]
        backfill_columns:
          - source: "a"
            target: "b"
      - name: "fk_b"
        source_column: "b"
        target_table: "t2"
        target_key: "k2"
        depends_on: ["fk_a"]
        backfill_columns:
          - source: "c"
            target: "d"
      - name: "fk_c"
        source_column: "c"
        target_table: "t3"
        target_key: "k3"
        depends_on: ["fk_b"]
        backfill_columns:
          - source: "e"
            target: "f"
""",
        )

        with pytest.raises(ValueError) as exc_info:
            load_foreign_keys_config(config_path, "annuity_performance")

        assert "circular dependency" in str(exc_info.value)

    def test_self_reference_dependency_rejected(self, tmp_path: Path):
        """Self-referencing dependency (A→A) should be rejected."""
        config_path = _write_config(
            tmp_path / "data_sources.yml",
            """
schema_version: "1.0"
domains:
  annuity_performance:
    foreign_keys:
      - name: "fk_self"
        source_column: "a"
        target_table: "t1"
        target_key: "k1"
        depends_on: ["fk_self"]
        backfill_columns:
          - source: "a"
            target: "b"
""",
        )

        with pytest.raises(ValueError) as exc_info:
            load_foreign_keys_config(config_path, "annuity_performance")

        assert "circular dependency" in str(exc_info.value)
        assert "self reference" in str(exc_info.value)


class TestMultiDomainConfiguration:
    """Multi-domain configuration validation tests."""

    def test_multi_domain_isolation(self, tmp_path: Path):
        """FK configs from different domains should be isolated."""
        config_path = _write_config(
            tmp_path / "data_sources.yml",
            """
schema_version: "1.0"
domains:
  annuity_performance:
    foreign_keys:
      - name: "fk_plan"
        source_column: "计划代码"
        target_table: "年金计划"
        target_key: "年金计划号"
        backfill_columns:
          - source: "计划代码"
            target: "年金计划号"
  annuity_income:
    foreign_keys:
      - name: "fk_income_plan"
        source_column: "收入计划代码"
        target_table: "收入计划"
        target_key: "收入计划号"
        backfill_columns:
          - source: "收入计划代码"
            target: "收入计划号"
""",
        )

        # Load annuity_performance domain - should only get fk_plan
        perf_fks = load_foreign_keys_config(config_path, "annuity_performance")
        assert len(perf_fks) == 1
        assert perf_fks[0].name == "fk_plan"
        assert perf_fks[0].source_column == "计划代码"

        # Load annuity_income domain - should only get fk_income_plan
        income_fks = load_foreign_keys_config(config_path, "annuity_income")
        assert len(income_fks) == 1
        assert income_fks[0].name == "fk_income_plan"
        assert income_fks[0].source_column == "收入计划代码"

    def test_multi_domain_no_cross_contamination(self, tmp_path: Path):
        """Verify different domains don't interfere with each other."""
        config_path = _write_config(
            tmp_path / "data_sources.yml",
            """
schema_version: "1.0"
domains:
  annuity_performance:
    foreign_keys:
      - name: "fk_plan"
        source_column: "计划代码"
        target_table: "年金计划"
        target_key: "年金计划号"
        backfill_columns:
          - source: "计划代码"
            target: "年金计划号"
      - name: "fk_portfolio"
        source_column: "组合代码"
        target_table: "组合计划"
        target_key: "组合代码"
        depends_on: ["fk_plan"]
        backfill_columns:
          - source: "组合代码"
            target: "组合代码"
  annuity_income:
    foreign_keys:
      - name: "fk_income_plan"
        source_column: "收入计划代码"
        target_table: "收入计划"
        target_key: "收入计划号"
        backfill_columns:
          - source: "收入计划代码"
            target: "收入计划号"
""",
        )

        # Load both domains
        perf_fks = load_foreign_keys_config(config_path, "annuity_performance")
        income_fks = load_foreign_keys_config(config_path, "annuity_income")

        # Verify counts
        assert len(perf_fks) == 2
        assert len(income_fks) == 1

        # Verify names don't cross over
        perf_names = {fk.name for fk in perf_fks}
        income_names = {fk.name for fk in income_fks}
        assert perf_names == {"fk_plan", "fk_portfolio"}
        assert income_names == {"fk_income_plan"}
        assert perf_names.isdisjoint(income_names)


class TestSchemaVersionCompatibility:
    """Schema version compatibility tests."""

    def test_missing_foreign_keys_section_returns_empty(self, tmp_path: Path):
        """Missing foreign_keys section should return empty list (no-op behavior)."""
        config_path = _write_config(
            tmp_path / "data_sources.yml",
            """
schema_version: "1.0"
domains:
  annuity_performance:
    base_path: "tests/fixtures/real_data/{YYYYMM}/收集数据/数据采集"
    file_patterns:
      - "*年金终稿*.xlsx"
    sheet_name: "规模明细"
""",
        )

        result = load_foreign_keys_config(config_path, "annuity_performance")
        assert result == []

    def test_schema_version_1_0_with_foreign_keys(self, tmp_path: Path):
        """Schema version 1.0 should support foreign_keys section."""
        config_path = _write_config(
            tmp_path / "data_sources.yml",
            """
schema_version: "1.0"
domains:
  annuity_performance:
    foreign_keys:
      - name: "fk_plan"
        source_column: "计划代码"
        target_table: "年金计划"
        target_key: "年金计划号"
        backfill_columns:
          - source: "计划代码"
            target: "年金计划号"
""",
        )

        result = load_foreign_keys_config(config_path, "annuity_performance")
        assert len(result) == 1
        assert result[0].name == "fk_plan"

    def test_domain_without_foreign_keys_key(self, tmp_path: Path):
        """Domain config without foreign_keys key should return empty list."""
        config_path = _write_config(
            tmp_path / "data_sources.yml",
            """
schema_version: "1.0"
domains:
  annuity_performance:
    base_path: "tests/fixtures"
  annuity_income:
    foreign_keys:
      - name: "fk_income"
        source_column: "col"
        target_table: "table"
        target_key: "key"
        backfill_columns:
          - source: "col"
            target: "key"
""",
        )

        # annuity_performance has no foreign_keys key
        result = load_foreign_keys_config(config_path, "annuity_performance")
        assert result == []

        # annuity_income has foreign_keys
        result = load_foreign_keys_config(config_path, "annuity_income")
        assert len(result) == 1


class TestConfigLoaderPerformance:
    """Performance smoke for config loader (target <100ms median with 4-6 FKs, <10MB memory)."""

    def test_load_foreign_keys_config_median_under_threshold(self, tmp_path: Path):
        config_path = tmp_path / "data_sources.yml"
        base_fk = {
            "source_column": "计划代码",
            "target_table": "年金计划",
            "target_key": "年金计划号",
            "mode": "insert_missing",
            "backfill_columns": [
                {"source": "计划代码", "target": "年金计划号"},
                {"source": "计划名称", "target": "计划名称", "optional": True},
            ],
        }
        fk_names = ["fk_plan", "fk_portfolio", "fk_policy", "fk_channel"]
        payload = {
            "schema_version": "1.0",
            "domains": {
                "annuity_performance": {
                    "foreign_keys": [
                        {**base_fk, "name": fk_names[0]},
                        {
                            **base_fk,
                            "name": fk_names[1],
                            "depends_on": [fk_names[0]],
                            "source_column": "组合代码",
                            "target_table": "组合计划",
                            "target_key": "组合代码",
                        },
                        {
                            **base_fk,
                            "name": fk_names[2],
                            "depends_on": [fk_names[1]],
                            "source_column": "保单号",
                            "target_table": "保单",
                            "target_key": "保单号",
                        },
                        {
                            **base_fk,
                            "name": fk_names[3],
                            "depends_on": [fk_names[2]],
                            "source_column": "渠道代码",
                            "target_table": "渠道",
                            "target_key": "渠道代码",
                        },
                    ]
                }
            },
        }
        config_path.write_text(
            yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8"
        )

        durations = []
        for _ in range(5):
            start = time.perf_counter()
            load_foreign_keys_config(config_path, "annuity_performance")
            durations.append((time.perf_counter() - start) * 1000)

        median_ms = statistics.median(durations)
        # Target 100ms per AC; retain minimal cushion only for CI jitter
        assert median_ms < 100, f"median load time too high: {median_ms}ms"

    def test_load_foreign_keys_config_memory_under_threshold(self, tmp_path: Path):
        """Memory usage should be under 10MB for config loading."""
        import tracemalloc

        config_path = tmp_path / "data_sources.yml"
        base_fk = {
            "source_column": "计划代码",
            "target_table": "年金计划",
            "target_key": "年金计划号",
            "mode": "insert_missing",
            "backfill_columns": [
                {"source": "计划代码", "target": "年金计划号"},
                {"source": "计划名称", "target": "计划名称", "optional": True},
            ],
        }
        # Create 6 FKs to test upper bound of typical config
        fk_names = [
            "fk_plan",
            "fk_portfolio",
            "fk_policy",
            "fk_channel",
            "fk_org",
            "fk_product",
        ]
        payload = {
            "schema_version": "1.0",
            "domains": {
                "annuity_performance": {
                    "foreign_keys": [
                        {**base_fk, "name": name, "source_column": f"col_{i}"}
                        for i, name in enumerate(fk_names)
                    ]
                }
            },
        }
        config_path.write_text(
            yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8"
        )

        tracemalloc.start()
        load_foreign_keys_config(config_path, "annuity_performance")
        _, peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        peak_mb = peak_bytes / (1024 * 1024)
        # Target <10MB per story Performance Requirements
        assert peak_mb < 10, f"peak memory too high: {peak_mb:.2f}MB"
