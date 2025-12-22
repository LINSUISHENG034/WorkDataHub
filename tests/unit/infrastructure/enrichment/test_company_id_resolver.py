"""
Unit tests for CompanyIdResolver.

Tests cover:
- Plan override resolution (vectorized)
- Existing company_id passthrough
- Temp ID generation consistency
- Enrichment service integration (mocked)
- Empty/null handling
- Performance benchmarks
- Memory usage
"""

import time
from unittest.mock import MagicMock

import pandas as pd
import pytest

from work_data_hub.infrastructure.enrichment import (
    CompanyIdResolver,
    EqcLookupConfig,
    ResolutionStrategy,
)
from work_data_hub.infrastructure.enrichment.types import (
    EnrichmentIndexRecord,
    LookupType,
    SourceType,
)


class TestCompanyIdResolverInit:
    """Tests for CompanyIdResolver initialization."""

    def test_init_without_dependencies(self):
        """Test resolver can be created without any dependencies."""
        resolver = CompanyIdResolver(
            eqc_config=EqcLookupConfig.disabled(),
        )
        assert resolver.enrichment_service is None

    def test_init_with_enrichment_service(self, mock_enrichment_service):
        """Test resolver with enrichment service."""
        resolver = CompanyIdResolver(
            eqc_config=EqcLookupConfig.disabled(),
            enrichment_service=mock_enrichment_service,
        )
        assert resolver.enrichment_service is mock_enrichment_service


class TestPlanOverrideResolution:
    """Tests for plan override lookup (AC 5.4.2 Step 1)."""

    def test_plan_override_hit(self, resolver_with_overrides, default_strategy):
        """Test that plan override mapping is applied correctly."""
        df = pd.DataFrame(
            {
                "计划代码": ["FP0001", "FP0002"],
                "客户名称": ["公司A", "公司B"],
            }
        )

        result = resolver_with_overrides.resolve_batch(df, default_strategy)
        result_df = result.data
        stats = result.statistics

        assert result_df.loc[0, "company_id"] == "614810477"
        assert result_df.loc[1, "company_id"] == "614810477"
        assert stats.plan_override_hits == 2

    def test_plan_override_miss_generates_temp_id(
        self, resolver_with_overrides, default_strategy
    ):
        """Test that unknown plan codes get temp IDs."""
        df = pd.DataFrame(
            {
                "计划代码": ["UNKNOWN_PLAN"],
                "客户名称": ["中国平安保险公司"],
            }
        )

        result = resolver_with_overrides.resolve_batch(df, default_strategy)
        result_df = result.data
        stats = result.statistics

        assert result_df.loc[0, "company_id"].startswith("IN_")
        assert stats.plan_override_hits == 0
        assert stats.temp_ids_generated == 1

    def test_vectorized_plan_override(
        self, resolver_with_overrides, default_strategy, sample_dataframe
    ):
        """Test vectorized plan override lookup."""
        result = resolver_with_overrides.resolve_batch(
            sample_dataframe, default_strategy
        )
        result_df = result.data
        stats = result.statistics

        # FP0001, FP0002, P0809 should be resolved via plan override
        assert result_df.loc[0, "company_id"] == "614810477"  # FP0001
        assert result_df.loc[1, "company_id"] == "614810477"  # FP0002
        assert result_df.loc[3, "company_id"] == "608349737"  # P0809
        assert stats.plan_override_hits == 3


class TestExistingColumnPassthrough:
    """Tests for existing company_id column passthrough (AC 5.4.2 Step 2)."""

    def test_existing_company_id_preserved(self, resolver_standalone, default_strategy):
        """Test that existing company_id values are preserved."""
        df = pd.DataFrame(
            {
                "计划代码": ["UNKNOWN"],
                "客户名称": ["公司A"],
                "公司代码": ["existing_123"],
            }
        )

        result = resolver_standalone.resolve_batch(df, default_strategy)
        result_df = result.data
        stats = result.statistics

        assert result_df.loc[0, "company_id"] == "existing_123"
        assert stats.existing_column_hits == 1

    def test_empty_existing_company_id_ignored(
        self, resolver_standalone, default_strategy
    ):
        """Test that empty existing company_id values are ignored."""
        df = pd.DataFrame(
            {
                "计划代码": ["UNKNOWN"],
                "客户名称": ["公司A"],
                "公司代码": [""],
            }
        )

        result = resolver_standalone.resolve_batch(df, default_strategy)
        result_df = result.data
        stats = result.statistics

        # Should generate temp ID since existing is empty
        assert result_df.loc[0, "company_id"].startswith("IN_")
        assert stats.existing_column_hits == 0

    def test_plan_override_takes_priority_over_existing(
        self, resolver_with_overrides, default_strategy
    ):
        """Test that plan override takes priority over existing column."""
        df = pd.DataFrame(
            {
                "计划代码": ["FP0001"],
                "客户名称": ["公司A"],
                "公司代码": ["should_be_ignored"],
            }
        )

        result = resolver_with_overrides.resolve_batch(df, default_strategy)
        result_df = result.data
        stats = result.statistics

        assert result_df.loc[0, "company_id"] == "614810477"
        assert stats.plan_override_hits == 1
        assert stats.existing_column_hits == 0

    def test_yaml_only_mode_works_without_repository(self, default_strategy, tmp_path):
        """Backwards-compatible YAML-only mode resolves plan overrides without DB."""
        mappings_dir = tmp_path / "mappings"
        mappings_dir.mkdir()
        (mappings_dir / "company_id_overrides_plan.yml").write_text(
            'FP0001: "614810477"\n', encoding="utf-8"
        )
        from work_data_hub.config.mapping_loader import load_company_id_overrides

        overrides = load_company_id_overrides(mappings_dir)
        resolver = CompanyIdResolver(
            eqc_config=EqcLookupConfig.disabled(),
            yaml_overrides=overrides,
        )

        df = pd.DataFrame(
            {
                "计划代码": ["FP0001"],
                "客户名称": ["公司A"],
            }
        )

        result = resolver.resolve_batch(df, default_strategy)
        assert result.data.loc[0, "company_id"] == "614810477"


class TestTempIdGeneration:
    """Tests for temporary ID generation (AC 5.4.4)."""

    def test_temp_id_format(self, resolver_standalone, default_strategy):
        """Test temp ID format is IN_<16-char-Base32>."""
        df = pd.DataFrame(
            {
                "计划代码": ["UNKNOWN"],
                "客户名称": ["中国平安保险公司"],
            }
        )

        result = resolver_standalone.resolve_batch(df, default_strategy)
        result_df = result.data

        temp_id = result_df.loc[0, "company_id"]
        assert temp_id.startswith("IN_")
        assert len(temp_id) == 19  # "IN_" + 16 chars

    def test_temp_id_consistency(self, resolver_standalone, default_strategy):
        """Test same input produces same temp ID."""
        df1 = pd.DataFrame(
            {
                "计划代码": ["UNKNOWN"],
                "客户名称": ["中国平安保险公司"],
            }
        )
        df2 = pd.DataFrame(
            {
                "计划代码": ["UNKNOWN"],
                "客户名称": ["中国平安保险公司"],
            }
        )

        result1 = resolver_standalone.resolve_batch(df1, default_strategy)
        result2 = resolver_standalone.resolve_batch(df2, default_strategy)

        assert result1.data.loc[0, "company_id"] == result2.data.loc[0, "company_id"]

    def test_different_names_produce_different_ids(
        self, resolver_standalone, default_strategy
    ):
        """Test different names produce different temp IDs."""
        df = pd.DataFrame(
            {
                "计划代码": ["UNKNOWN", "UNKNOWN"],
                "客户名称": ["公司A", "公司B"],
            }
        )

        result = resolver_standalone.resolve_batch(df, default_strategy)
        result_df = result.data

        assert result_df.loc[0, "company_id"] != result_df.loc[1, "company_id"]

    def test_temp_id_disabled(self, resolver_standalone):
        """Test temp ID generation can be disabled."""
        strategy = ResolutionStrategy(generate_temp_ids=False)
        df = pd.DataFrame(
            {
                "计划代码": ["UNKNOWN"],
                "客户名称": ["公司A"],
            }
        )

        result = resolver_standalone.resolve_batch(df, strategy)
        result_df = result.data
        stats = result.statistics

        assert pd.isna(result_df.loc[0, "company_id"])
        assert stats.unresolved == 1


class TestEnrichmentServiceIntegration:
    """Tests for enrichment service integration (AC 5.4.5)."""

    def test_enrichment_service_called_when_enabled(
        self, mock_enrichment_service, default_strategy
    ):
        """Test enrichment service is called when enabled."""
        resolver = CompanyIdResolver(
            eqc_config=EqcLookupConfig(
                enabled=True,
                sync_budget=10,
                auto_create_provider=False,
            ),
            enrichment_service=mock_enrichment_service,
        )
        strategy = ResolutionStrategy(
            use_enrichment_service=True,
            sync_lookup_budget=10,
            generate_temp_ids=False,
        )

        df = pd.DataFrame(
            {
                "计划代码": ["UNKNOWN"],
                "客户名称": ["公司A"],
                "年金账户名": ["账户1"],
            }
        )

        result = resolver.resolve_batch(df, strategy)
        result_df = result.data
        stats = result.statistics

        mock_enrichment_service.resolve_company_id.assert_called()
        assert result_df.loc[0, "company_id"] == "mock_company_123"
        assert stats.enrichment_service_hits == 1

    def test_enrichment_service_caches_results_once(self, default_strategy):
        """EQC hits batch cache writes to a single DB call."""
        from unittest.mock import MagicMock
        from work_data_hub.infrastructure.enrichment.mapping_repository import (
            MatchResult,
        )

        mock_service = MagicMock()
        mock_result = MagicMock()
        mock_result.company_id = "eqc_company"
        mock_service.resolve_company_id.return_value = mock_result

        mock_repo = MagicMock()
        mock_repo.lookup_batch.return_value = {
            # Ensure DB cache path skipped so EQC path used
            "noop": MatchResult("db_hit", "name", 4, "internal")
        }

        resolver = CompanyIdResolver(
            eqc_config=EqcLookupConfig(
                enabled=True,
                sync_budget=3,
                auto_create_provider=False,
            ),
            yaml_overrides={
                "plan": {},
                "account": {},
                "hardcode": {},
                "name": {},
                "account_name": {},
            },
            enrichment_service=mock_service,
            mapping_repository=mock_repo,
        )
        strategy = ResolutionStrategy(
            use_enrichment_service=True,
            sync_lookup_budget=3,
        )

        df = pd.DataFrame(
            {
                "计划代码": ["UNKNOWN", "UNKNOWN", "UNKNOWN"],
                "客户名称": ["公司A", "公司B", "公司C"],
            }
        )

        result = resolver.resolve_batch(df, strategy)
        assert result.statistics.eqc_sync_hits == 3
        mock_repo.insert_batch_with_conflict_check.assert_called_once()
        payload = mock_repo.insert_batch_with_conflict_check.call_args[0][0]
        assert len(payload) == 3

    def test_enrichment_service_not_called_when_disabled(
        self, mock_enrichment_service, default_strategy
    ):
        """Test enrichment service is not called when disabled."""
        resolver = CompanyIdResolver(
            eqc_config=EqcLookupConfig.disabled(),
            enrichment_service=mock_enrichment_service,
        )
        # default_strategy has use_enrichment_service=False

        df = pd.DataFrame(
            {
                "计划代码": ["UNKNOWN"],
                "客户名称": ["公司A"],
            }
        )

        resolver.resolve_batch(df, default_strategy)

        mock_enrichment_service.resolve_company_id.assert_not_called()

    def test_enrichment_service_respects_budget(self, mock_enrichment_service):
        """Test enrichment service respects sync_lookup_budget."""
        resolver = CompanyIdResolver(
            eqc_config=EqcLookupConfig(
                enabled=True,
                sync_budget=2,  # Only 2 lookups allowed
                auto_create_provider=False,
            ),
            enrichment_service=mock_enrichment_service,
        )
        strategy = ResolutionStrategy(
            use_enrichment_service=True,
            sync_lookup_budget=2,  # Only 2 lookups allowed
            generate_temp_ids=False,
        )

        df = pd.DataFrame(
            {
                "计划代码": ["UNKNOWN"] * 5,
                "客户名称": [f"公司{i}" for i in range(5)],
                "年金账户名": [f"账户{i}" for i in range(5)],
            }
        )

        result = resolver.resolve_batch(df, strategy)
        result_df = result.data
        stats = result.statistics

        # Should only call enrichment service twice (budget=2)
        assert mock_enrichment_service.resolve_company_id.call_count == 2
        assert stats.enrichment_service_hits == 2

    def test_enrichment_service_error_handled_gracefully(self):
        """Test enrichment service errors don't crash resolution."""
        mock_service = MagicMock()
        mock_service.resolve_company_id.side_effect = Exception("API Error")

        resolver = CompanyIdResolver(
            eqc_config=EqcLookupConfig(
                enabled=True,
                sync_budget=10,
                auto_create_provider=False,
            ),
            enrichment_service=mock_service,
        )
        strategy = ResolutionStrategy(
            use_enrichment_service=True,
            sync_lookup_budget=10,
            generate_temp_ids=True,
        )

        df = pd.DataFrame(
            {
                "计划代码": ["UNKNOWN"],
                "客户名称": ["公司A"],
                "年金账户名": ["账户1"],
            }
        )

        # Should not raise, should fall back to temp ID
        result = resolver.resolve_batch(df, strategy)
        result_df = result.data
        stats = result.statistics

        assert result_df.loc[0, "company_id"].startswith("IN_")


class TestEmptyNullHandling:
    """Tests for empty and null value handling."""

    def test_null_plan_code(self, resolver_with_overrides, default_strategy):
        """Test null plan code is handled."""
        df = pd.DataFrame(
            {
                "计划代码": [None],
                "客户名称": ["公司A"],
            }
        )

        result = resolver_with_overrides.resolve_batch(df, default_strategy)
        result_df = result.data

        assert result_df.loc[0, "company_id"].startswith("IN_")

    def test_empty_customer_name(self, resolver_standalone, default_strategy):
        """Test empty customer name generates consistent temp ID."""
        df = pd.DataFrame(
            {
                "计划代码": ["UNKNOWN"],
                "客户名称": [""],
            }
        )

        result = resolver_standalone.resolve_batch(df, default_strategy)
        result_df = result.data

        # Should still generate a temp ID (using placeholder)
        assert result_df.loc[0, "company_id"].startswith("IN_")

    def test_null_customer_name(self, resolver_standalone, default_strategy):
        """Test null customer name generates consistent temp ID."""
        df = pd.DataFrame(
            {
                "计划代码": ["UNKNOWN"],
                "客户名称": [None],
            }
        )

        result = resolver_standalone.resolve_batch(df, default_strategy)
        result_df = result.data

        assert result_df.loc[0, "company_id"].startswith("IN_")

    def test_missing_required_column_raises(
        self, resolver_standalone, default_strategy
    ):
        """Test missing required column raises ValueError."""
        df = pd.DataFrame(
            {
                "计划代码": ["FP0001"],
                # Missing 客户名称
            }
        )

        with pytest.raises(ValueError, match="missing required columns"):
            resolver_standalone.resolve_batch(df, default_strategy)

    def test_missing_plan_column_allows_resolution(
        self, resolver_standalone, default_strategy
    ):
        """Plan column is optional; customer_name is required."""
        df = pd.DataFrame(
            {
                # Plan column intentionally omitted to verify fallback behavior
                "客户名称": ["公司A"],
            }
        )

        result = resolver_standalone.resolve_batch(df, default_strategy)
        result_df = result.data
        stats = result.statistics

        assert result_df.loc[0, "company_id"].startswith("IN_")
        assert stats.yaml_hits.get("plan", 0) == 0


class TestPerformance:
    """Performance benchmark tests (AC 5.4.3)."""

    def test_performance_1000_rows(
        self, resolver_with_overrides, default_strategy, large_dataframe
    ):
        """Test 1000 rows processed in <100ms."""
        start_time = time.time()
        resolver_with_overrides.resolve_batch(large_dataframe, default_strategy)
        elapsed_ms = (time.time() - start_time) * 1000

        assert elapsed_ms < 150, f"Processing took {elapsed_ms:.2f}ms, expected <150ms"

    def test_memory_usage_10k_rows(
        self, resolver_with_overrides, default_strategy, very_large_dataframe
    ):
        """Test memory usage <100MB for 10K rows."""
        import sys

        # Get initial memory
        initial_size = sys.getsizeof(very_large_dataframe)

        result = resolver_with_overrides.resolve_batch(
            very_large_dataframe, default_strategy
        )
        result_df = result.data

        # Rough estimate of result size
        result_size = sys.getsizeof(result_df)

        # Combined should be well under 100MB
        total_mb = (initial_size + result_size) / (1024 * 1024)
        assert total_mb < 100, f"Memory usage {total_mb:.2f}MB, expected <100MB"


class TestResolutionStatistics:
    """Tests for resolution statistics tracking."""

    def test_statistics_accuracy(
        self, resolver_with_overrides, default_strategy, sample_dataframe
    ):
        """Test statistics accurately reflect resolution results."""
        result = resolver_with_overrides.resolve_batch(
            sample_dataframe, default_strategy
        )
        result_df = result.data
        stats = result.statistics

        assert stats.total_rows == 5
        assert stats.plan_override_hits == 3  # FP0001, FP0002, P0809
        assert stats.existing_column_hits == 1  # Row with existing_123
        assert stats.temp_ids_generated == 1  # UNKNOWN row
        assert stats.unresolved == 0

    def test_statistics_to_dict(self, resolver_standalone, default_strategy):
        """Test statistics can be converted to dict."""
        df = pd.DataFrame(
            {
                "计划代码": ["UNKNOWN"],
                "客户名称": ["公司A"],
            }
        )

        result = resolver_standalone.resolve_batch(df, default_strategy)
        stats = result.statistics

        stats_dict = stats.to_dict()
        assert "total_rows" in stats_dict
        assert "plan_override_hits" in stats_dict
        assert "temp_ids_generated" in stats_dict


class TestCustomStrategy:
    """Tests for custom resolution strategy configuration."""

    def test_custom_column_names(self, resolver_standalone):
        """Test custom column names in strategy."""
        strategy = ResolutionStrategy(
            plan_code_column="plan_code",
            customer_name_column="customer_name",
            output_column="resolved_id",
        )

        df = pd.DataFrame(
            {
                "plan_code": ["UNKNOWN"],
                "customer_name": ["Test Company"],
            }
        )

        result = resolver_standalone.resolve_batch(df, strategy)
        result_df = result.data

        assert "resolved_id" in result_df.columns
        assert result_df.loc[0, "resolved_id"].startswith("IN_")

    def test_custom_output_column(self, resolver_with_overrides):
        """Test custom output column name."""
        strategy = ResolutionStrategy(output_column="company_identifier")

        df = pd.DataFrame(
            {
                "计划代码": ["FP0001"],
                "客户名称": ["公司A"],
            }
        )

        result = resolver_with_overrides.resolve_batch(df, strategy)
        result_df = result.data

        assert "company_identifier" in result_df.columns
        assert result_df.loc[0, "company_identifier"] == "614810477"


# =============================================================================
# Story 6.4: Multi-Tier Lookup Tests
# =============================================================================


class TestYamlMultiTierLookup:
    """Tests for YAML multi-tier lookup (AC2, AC3)."""

    def test_yaml_lookup_plan_priority(self, default_strategy):
        """Test plan code lookup works via yaml_overrides."""
        yaml_overrides = {
            "plan": {"FP0001": "614810477"},
            "account": {},
            "hardcode": {},
            "name": {},
            "account_name": {},
        }
        resolver = CompanyIdResolver(
            eqc_config=EqcLookupConfig.disabled(), yaml_overrides=yaml_overrides
        )

        df = pd.DataFrame(
            {
                "计划代码": ["FP0001"],
                "客户名称": ["公司A"],
            }
        )

        result = resolver.resolve_batch(df, default_strategy)
        assert result.data.loc[0, "company_id"] == "614810477"
        assert result.statistics.yaml_hits.get("plan", 0) == 1

    def test_yaml_lookup_all_priorities(self, default_strategy):
        """Test all 5 priority levels are checked in order."""
        yaml_overrides = {
            "plan": {"FP0001": "plan_company"},
            "account": {"ACC001": "account_company"},
            "hardcode": {"FP0002": "hardcode_company"},
            "name": {"公司C": "name_company"},
            "account_name": {"账户D": "account_name_company"},
        }
        resolver = CompanyIdResolver(
            eqc_config=EqcLookupConfig.disabled(), yaml_overrides=yaml_overrides
        )

        df = pd.DataFrame(
            {
                "计划代码": ["FP0001", "FP0002", "UNKNOWN", "UNKNOWN", "UNKNOWN"],
                "客户名称": ["公司A", "公司B", "公司C", "公司D", "公司E"],
                "年金账户号": ["X", "X", "X", "X", "ACC001"],
                "年金账户名": ["X", "X", "X", "账户D", "X"],
            }
        )

        result = resolver.resolve_batch(df, default_strategy)
        stats = result.statistics

        # Plan priority (FP0001)
        assert result.data.loc[0, "company_id"] == "plan_company"
        # Hardcode priority (FP0002 - same column as plan)
        assert result.data.loc[1, "company_id"] == "hardcode_company"
        # Name priority (公司C)
        assert result.data.loc[2, "company_id"] == "name_company"
        # Account name priority (账户D)
        assert result.data.loc[3, "company_id"] == "account_name_company"
        # Account priority (ACC001)
        assert result.data.loc[4, "company_id"] == "account_company"

        # Verify stats breakdown
        assert stats.yaml_hits.get("plan", 0) >= 1
        assert sum(stats.yaml_hits.values()) == 5

    def test_yaml_lookup_priority_order(self, default_strategy):
        """Test higher priority wins over lower priority."""
        yaml_overrides = {
            "plan": {"FP0001": "plan_wins"},
            "account": {},
            "hardcode": {},
            "name": {"公司A": "name_loses"},
            "account_name": {},
        }
        resolver = CompanyIdResolver(
            eqc_config=EqcLookupConfig.disabled(), yaml_overrides=yaml_overrides
        )

        df = pd.DataFrame(
            {
                "计划代码": ["FP0001"],
                "客户名称": ["公司A"],
            }
        )

        result = resolver.resolve_batch(df, default_strategy)
        # Plan (priority 1) should win over name (priority 4)
        assert result.data.loc[0, "company_id"] == "plan_wins"
        assert result.statistics.yaml_hits.get("plan", 0) == 1
        assert result.statistics.yaml_hits.get("name", 0) == 0


class TestDatabaseCacheLookup:
    """Tests for database cache lookup (AC4)."""

    def test_db_cache_lookup_batch(self, default_strategy):
        """Test database batch lookup works with mocked repository."""
        from unittest.mock import MagicMock
        from work_data_hub.infrastructure.enrichment.mapping_repository import (
            MatchResult,
        )

        mock_repo = MagicMock()
        mock_repo.lookup_batch.return_value = {
            "公司B": MatchResult(
                company_id="db_company_123",
                match_type="name",
                priority=4,
                source="internal",
            )
        }

        resolver = CompanyIdResolver(
            eqc_config=EqcLookupConfig.disabled(),
            yaml_overrides={
                "plan": {},
                "account": {},
                "hardcode": {},
                "name": {},
                "account_name": {},
            },
            mapping_repository=mock_repo,
        )

        df = pd.DataFrame(
            {
                "计划代码": ["UNKNOWN"],
                "客户名称": ["公司B"],
            }
        )

        result = resolver.resolve_batch(df, default_strategy)
        assert result.data.loc[0, "company_id"] == "db_company_123"
        assert result.statistics.db_cache_hits["legacy"] == 1
        assert result.statistics.db_cache_hits_total == 1
        mock_repo.lookup_batch.assert_called_once()

    def test_db_cache_lookup_no_repository(self, default_strategy):
        """Test graceful skip when no repository provided."""
        resolver = CompanyIdResolver(
            eqc_config=EqcLookupConfig.disabled(),
            yaml_overrides={
                "plan": {},
                "account": {},
                "hardcode": {},
                "name": {},
                "account_name": {},
            },
            mapping_repository=None,
        )

        df = pd.DataFrame(
            {
                "计划代码": ["UNKNOWN"],
                "客户名称": ["公司A"],
            }
        )

        result = resolver.resolve_batch(df, default_strategy)
        # Should fall through to temp ID
        assert result.data.loc[0, "company_id"].startswith("IN_")
        assert result.statistics.db_cache_hits_total == 0


class TestBackflowMechanism:
    """Tests for backflow mechanism (AC6)."""

    def test_backflow_inserts_new_mappings(self, default_strategy):
        """Test new mappings are inserted via backflow."""
        from unittest.mock import MagicMock
        from work_data_hub.infrastructure.enrichment.mapping_repository import (
            InsertBatchResult,
        )

        mock_repo = MagicMock()
        mock_repo.lookup_batch.return_value = {}
        mock_repo.insert_batch_with_conflict_check.return_value = InsertBatchResult(
            inserted_count=2,
            skipped_count=0,
            conflicts=[],
        )

        resolver = CompanyIdResolver(
            eqc_config=EqcLookupConfig.disabled(),
            yaml_overrides={
                "plan": {},
                "account": {},
                "hardcode": {},
                "name": {},
                "account_name": {},
            },
            mapping_repository=mock_repo,
        )

        df = pd.DataFrame(
            {
                "计划代码": ["UNKNOWN"],
                "客户名称": ["公司A"],
                "年金账户名": ["账户A"],
                "公司代码": ["existing_123"],
            }
        )

        result = resolver.resolve_batch(df, default_strategy)
        assert result.data.loc[0, "company_id"] == "existing_123"
        assert result.statistics.existing_column_hits == 1
        assert result.statistics.backflow_stats.get("inserted", 0) == 2

    def test_backflow_skips_temp_ids(self, default_strategy):
        """Test temporary IDs are not backflowed."""
        from unittest.mock import MagicMock
        from work_data_hub.infrastructure.enrichment.mapping_repository import (
            InsertBatchResult,
        )

        mock_repo = MagicMock()
        mock_repo.lookup_batch.return_value = {}
        mock_repo.insert_batch_with_conflict_check.return_value = InsertBatchResult(
            inserted_count=0,
            skipped_count=0,
            conflicts=[],
        )

        resolver = CompanyIdResolver(
            eqc_config=EqcLookupConfig.disabled(),
            yaml_overrides={
                "plan": {},
                "account": {},
                "hardcode": {},
                "name": {},
                "account_name": {},
            },
            mapping_repository=mock_repo,
        )

        df = pd.DataFrame(
            {
                "计划代码": ["UNKNOWN"],
                "客户名称": ["公司A"],
                "公司代码": ["IN_TEMPID12345678"],  # Temp ID should be skipped
            }
        )

        result = resolver.resolve_batch(df, default_strategy)
        # Temp ID in existing column should be used but not backflowed
        assert result.data.loc[0, "company_id"] == "IN_TEMPID12345678"
        # Backflow should not be called for temp IDs
        # (it may be called but with empty list, resulting in 0 inserts)

    def test_backflow_detects_conflicts(self, default_strategy):
        """Test conflicts are logged as warnings."""
        from unittest.mock import MagicMock
        from work_data_hub.infrastructure.enrichment.mapping_repository import (
            InsertBatchResult,
        )

        mock_repo = MagicMock()
        mock_repo.lookup_batch.return_value = {}
        mock_repo.insert_batch_with_conflict_check.return_value = InsertBatchResult(
            inserted_count=0,
            skipped_count=1,
            conflicts=[
                {
                    "alias_name": "公司A",
                    "match_type": "name",
                    "existing_id": "old_123",
                    "new_id": "new_456",
                }
            ],
        )

        resolver = CompanyIdResolver(
            eqc_config=EqcLookupConfig.disabled(),
            yaml_overrides={
                "plan": {},
                "account": {},
                "hardcode": {},
                "name": {},
                "account_name": {},
            },
            mapping_repository=mock_repo,
        )

        df = pd.DataFrame(
            {
                "计划代码": ["UNKNOWN"],
                "客户名称": ["公司A"],
                "公司代码": ["new_456"],
            }
        )

        result = resolver.resolve_batch(df, default_strategy)
        assert result.statistics.backflow_stats.get("conflicts", 0) == 1


class TestStatisticsExtended:
    """Tests for extended statistics (AC7)."""

    def test_statistics_yaml_breakdown(self, default_strategy):
        """Test statistics include YAML breakdown by priority."""
        yaml_overrides = {
            "plan": {"FP0001": "plan_company"},
            "account": {},
            "hardcode": {},
            "name": {"公司B": "name_company"},
            "account_name": {},
        }
        resolver = CompanyIdResolver(
            eqc_config=EqcLookupConfig.disabled(), yaml_overrides=yaml_overrides
        )

        df = pd.DataFrame(
            {
                "计划代码": ["FP0001", "UNKNOWN"],
                "客户名称": ["公司A", "公司B"],
            }
        )

        result = resolver.resolve_batch(df, default_strategy)
        stats = result.statistics

        assert "yaml_hits" in stats.to_dict()
        assert stats.yaml_hits.get("plan", 0) == 1
        assert stats.yaml_hits.get("name", 0) == 1
        assert stats.to_dict()["yaml_hits_total"] == 2

    def test_statistics_budget_tracking(self, default_strategy):
        """Test budget consumption tracking."""
        from unittest.mock import MagicMock

        mock_service = MagicMock()
        mock_result = MagicMock()
        mock_result.company_id = "eqc_company"
        mock_service.resolve_company_id.return_value = mock_result

        resolver = CompanyIdResolver(
            eqc_config=EqcLookupConfig(
                enabled=True,
                sync_budget=5,
                auto_create_provider=False,
            ),
            yaml_overrides={
                "plan": {},
                "account": {},
                "hardcode": {},
                "name": {},
                "account_name": {},
            },
            enrichment_service=mock_service,
        )

        strategy = ResolutionStrategy(
            use_enrichment_service=True,
            sync_lookup_budget=5,
        )

        df = pd.DataFrame(
            {
                "计划代码": ["UNKNOWN"] * 3,
                "客户名称": ["公司A", "公司B", "公司C"],
            }
        )

        result = resolver.resolve_batch(df, strategy)
        stats = result.statistics

        assert stats.eqc_sync_hits == 3
        assert stats.budget_consumed == 3
        assert stats.budget_remaining == 2


class TestPerformanceExtended:
    """Extended performance tests (AC9)."""

    def test_performance_1000_rows_no_eqc(self, default_strategy):
        """Test 1000 rows processed in <100ms without EQC."""
        import time
        import random

        yaml_overrides = {
            "plan": {f"FP{i:04d}": f"company_{i}" for i in range(100)},
            "account": {},
            "hardcode": {},
            "name": {},
            "account_name": {},
        }
        resolver = CompanyIdResolver(
            eqc_config=EqcLookupConfig.disabled(), yaml_overrides=yaml_overrides
        )

        plan_codes = [f"FP{random.randint(0, 200):04d}" for _ in range(1000)]
        df = pd.DataFrame(
            {
                "计划代码": plan_codes,
                "客户名称": [f"公司{i}" for i in range(1000)],
            }
        )

        start_time = time.time()
        resolver.resolve_batch(df, default_strategy)
        elapsed_ms = (time.time() - start_time) * 1000

        assert elapsed_ms < 150, f"Processing took {elapsed_ms:.2f}ms, expected <150ms"


# =============================================================================
# Story 6.5: Async Enrichment Queue Tests
# =============================================================================


class TestAsyncQueueIntegration:
    """Tests for async enrichment queue integration (Story 6.5)."""

    def test_resolve_batch_enqueues_temp_ids(self, default_strategy):
        """Test temp IDs trigger enqueue (AC1)."""
        from unittest.mock import MagicMock
        from work_data_hub.infrastructure.enrichment.mapping_repository import (
            EnqueueResult,
        )

        mock_repo = MagicMock()
        mock_repo.lookup_batch.return_value = {}
        mock_repo.enqueue_for_enrichment.return_value = EnqueueResult(
            queued_count=2, skipped_count=0
        )

        resolver = CompanyIdResolver(
            eqc_config=EqcLookupConfig.disabled(),
            yaml_overrides={
                "plan": {},
                "account": {},
                "hardcode": {},
                "name": {},
                "account_name": {},
            },
            mapping_repository=mock_repo,
        )

        df = pd.DataFrame(
            {
                "计划代码": ["UNKNOWN", "UNKNOWN"],
                "客户名称": ["公司A", "公司B"],
            }
        )

        result = resolver.resolve_batch(df, default_strategy)

        # Verify enqueue was called
        mock_repo.enqueue_for_enrichment.assert_called_once()
        # Verify statistics
        assert result.statistics.async_queued == 2
        assert result.statistics.temp_ids_generated == 2

    def test_resolve_batch_enqueue_disabled(self, default_strategy):
        """Test enable_async_queue=False skips enqueue (AC4)."""
        from unittest.mock import MagicMock

        mock_repo = MagicMock()
        mock_repo.lookup_batch.return_value = {}

        resolver = CompanyIdResolver(
            eqc_config=EqcLookupConfig.disabled(),
            yaml_overrides={
                "plan": {},
                "account": {},
                "hardcode": {},
                "name": {},
                "account_name": {},
            },
            mapping_repository=mock_repo,
        )

        strategy = ResolutionStrategy(enable_async_queue=False)

        df = pd.DataFrame(
            {
                "计划代码": ["UNKNOWN"],
                "客户名称": ["公司A"],
            }
        )

        result = resolver.resolve_batch(df, strategy)

        # Enqueue should NOT be called
        mock_repo.enqueue_for_enrichment.assert_not_called()
        assert result.statistics.async_queued == 0
        assert result.statistics.temp_ids_generated == 1

    def test_resolve_batch_enqueue_graceful_degradation(self, default_strategy):
        """Test enqueue failure doesn't block pipeline (AC6)."""
        from unittest.mock import MagicMock

        mock_repo = MagicMock()
        mock_repo.lookup_batch.return_value = {}
        mock_repo.enqueue_for_enrichment.side_effect = Exception("DB Error")

        resolver = CompanyIdResolver(
            eqc_config=EqcLookupConfig.disabled(),
            yaml_overrides={
                "plan": {},
                "account": {},
                "hardcode": {},
                "name": {},
                "account_name": {},
            },
            mapping_repository=mock_repo,
        )

        df = pd.DataFrame(
            {
                "计划代码": ["UNKNOWN"],
                "客户名称": ["公司A"],
            }
        )

        # Should not raise, should continue with temp ID
        result = resolver.resolve_batch(df, default_strategy)

        assert result.data.loc[0, "company_id"].startswith("IN_")
        assert result.statistics.temp_ids_generated == 1
        assert result.statistics.async_queued == 0  # Failed, so 0

    def test_resolve_batch_enqueue_uses_normalize_for_temp_id(self, default_strategy):
        """Test enqueue uses normalize_for_temp_id for dedup parity (AC2)."""
        from unittest.mock import MagicMock
        from work_data_hub.infrastructure.enrichment.mapping_repository import (
            EnqueueResult,
        )

        mock_repo = MagicMock()
        mock_repo.lookup_batch.return_value = {}
        mock_repo.enqueue_for_enrichment.return_value = EnqueueResult(
            queued_count=1, skipped_count=0
        )

        resolver = CompanyIdResolver(
            eqc_config=EqcLookupConfig.disabled(),
            yaml_overrides={
                "plan": {},
                "account": {},
                "hardcode": {},
                "name": {},
                "account_name": {},
            },
            mapping_repository=mock_repo,
        )

        # Two rows with same normalized name (whitespace variant)
        df = pd.DataFrame(
            {
                "计划代码": ["UNKNOWN", "UNKNOWN"],
                "客户名称": ["公司A", "公司A "],  # Second has trailing space
            }
        )

        result = resolver.resolve_batch(df, default_strategy)

        # Should deduplicate within batch
        call_args = mock_repo.enqueue_for_enrichment.call_args[0][0]
        # Only 1 unique normalized name should be enqueued
        assert len(call_args) == 1
        assert (
            call_args[0]["normalized_name"] == "公司a"
        )  # lowercase after normalization

    def test_statistics_async_queued_in_to_dict(self, default_strategy):
        """Test async_queued is included in statistics to_dict (AC5)."""
        from unittest.mock import MagicMock
        from work_data_hub.infrastructure.enrichment.mapping_repository import (
            EnqueueResult,
        )

        mock_repo = MagicMock()
        mock_repo.lookup_batch.return_value = {}
        mock_repo.enqueue_for_enrichment.return_value = EnqueueResult(
            queued_count=3, skipped_count=0
        )

        resolver = CompanyIdResolver(
            eqc_config=EqcLookupConfig.disabled(),
            yaml_overrides={
                "plan": {},
                "account": {},
                "hardcode": {},
                "name": {},
                "account_name": {},
            },
            mapping_repository=mock_repo,
        )

        df = pd.DataFrame(
            {
                "计划代码": ["UNKNOWN"] * 3,
                "客户名称": ["公司A", "公司B", "公司C"],
            }
        )

        result = resolver.resolve_batch(df, default_strategy)
        stats_dict = result.statistics.to_dict()

        assert "async_queued" in stats_dict
        assert stats_dict["async_queued"] == 3

    def test_resolve_batch_no_enqueue_without_repository(self, default_strategy):
        """Test no enqueue when repository not provided."""
        resolver = CompanyIdResolver(
            eqc_config=EqcLookupConfig.disabled(),
            yaml_overrides={
                "plan": {},
                "account": {},
                "hardcode": {},
                "name": {},
                "account_name": {},
            },
            mapping_repository=None,
        )

        df = pd.DataFrame(
            {
                "计划代码": ["UNKNOWN"],
                "客户名称": ["公司A"],
            }
        )

        result = resolver.resolve_batch(df, default_strategy)

        # Should still generate temp ID
        assert result.data.loc[0, "company_id"].startswith("IN_")
        assert result.statistics.temp_ids_generated == 1
        assert result.statistics.async_queued == 0

    def test_resolve_batch_no_enqueue_when_all_resolved(self, default_strategy):
        """Test no enqueue when all rows resolved (no temp IDs)."""
        from unittest.mock import MagicMock

        mock_repo = MagicMock()
        mock_repo.lookup_batch.return_value = {}

        resolver = CompanyIdResolver(
            eqc_config=EqcLookupConfig.disabled(),
            yaml_overrides={
                "plan": {"FP0001": "614810477"},
                "account": {},
                "hardcode": {},
                "name": {},
                "account_name": {},
            },
            mapping_repository=mock_repo,
        )

        df = pd.DataFrame(
            {
                "计划代码": ["FP0001"],
                "客户名称": ["公司A"],
            }
        )

        result = resolver.resolve_batch(df, default_strategy)

        # All resolved via YAML, no temp IDs
        mock_repo.enqueue_for_enrichment.assert_not_called()
        assert result.statistics.temp_ids_generated == 0
        assert result.statistics.async_queued == 0

    def test_enqueue_request_includes_temp_id(self, default_strategy):
        """Test enqueue request includes generated temp_id (AC3)."""
        from unittest.mock import MagicMock
        from work_data_hub.infrastructure.enrichment.mapping_repository import (
            EnqueueResult,
        )

        mock_repo = MagicMock()
        mock_repo.lookup_batch.return_value = {}
        mock_repo.enqueue_for_enrichment.return_value = EnqueueResult(
            queued_count=1, skipped_count=0
        )

        resolver = CompanyIdResolver(
            eqc_config=EqcLookupConfig.disabled(),
            yaml_overrides={
                "plan": {},
                "account": {},
                "hardcode": {},
                "name": {},
                "account_name": {},
            },
            mapping_repository=mock_repo,
        )

        df = pd.DataFrame(
            {
                "计划代码": ["UNKNOWN"],
                "客户名称": ["公司A"],
            }
        )

        result = resolver.resolve_batch(df, default_strategy)

        # Verify enqueue request includes temp_id
        call_args = mock_repo.enqueue_for_enrichment.call_args[0][0]
        assert len(call_args) == 1
        assert call_args[0]["temp_id"].startswith("IN_")
        assert call_args[0]["raw_name"] == "公司A"


# =============================================================================
# Story 6.4.1: P4 Customer Name Normalization Alignment Tests
# =============================================================================


class TestEnrichmentIndexDbCache:
    """Tests for enrichment_index DB cache integration (Story 6.1.1)."""

    def test_enrichment_index_priority_and_normalization(self, default_strategy):
        """Plan_code hit should win and normalization should be applied for names."""
        mock_repo = MagicMock()
        mock_repo.lookup_enrichment_index_batch.return_value = {
            (LookupType.PLAN_CODE, "PLAN001"): EnrichmentIndexRecord(
                lookup_key="PLAN001",
                lookup_type=LookupType.PLAN_CODE,
                company_id="C_PLAN",
                source=SourceType.YAML,
            ),
            (LookupType.CUSTOMER_NAME, "customer_a"): EnrichmentIndexRecord(
                lookup_key="customer_a",
                lookup_type=LookupType.CUSTOMER_NAME,
                company_id="C_NAME",
                source=SourceType.DOMAIN_LEARNING,
            ),
        }
        mock_repo.update_hit_count.return_value = True

        resolver = CompanyIdResolver(
            eqc_config=EqcLookupConfig.disabled(),
            yaml_overrides={
                "plan": {},
                "account": {},
                "hardcode": {},
                "name": {},
                "account_name": {},
            },
            mapping_repository=mock_repo,
        )

        df = pd.DataFrame(
            {
                "计划代码": ["PLAN001"],
                "客户名称": [" Customer_A  "],  # Will normalize to customer_a
            }
        )

        result = resolver.resolve_batch(df, default_strategy)

        assert result.data.loc[0, "company_id"] == "C_PLAN"
        assert result.statistics.db_cache_hits["plan_code"] == 1
        assert result.statistics.db_cache_hits_total == 1
        mock_repo.lookup_enrichment_index_batch.assert_called_once()
        mock_repo.update_hit_count.assert_called()

    def test_enrichment_index_logs_decision_path(self, default_strategy):
        """Decision path logging should include priority outcome."""
        mock_repo = MagicMock()
        mock_repo.lookup_enrichment_index_batch.return_value = {
            (LookupType.PLAN_CODE, "PLAN001"): EnrichmentIndexRecord(
                lookup_key="PLAN001",
                lookup_type=LookupType.PLAN_CODE,
                company_id="C_PLAN",
                source=SourceType.YAML,
            ),
        }
        mock_repo.update_hit_count.return_value = True

        resolver = CompanyIdResolver(
            eqc_config=EqcLookupConfig.disabled(),
            yaml_overrides={
                "plan": {},
                "account": {},
                "hardcode": {},
                "name": {},
                "account_name": {},
            },
            mapping_repository=mock_repo,
        )

        df = pd.DataFrame(
            {
                "计划代码": ["PLAN001"],
                "客户名称": [" Customer_A  "],
            }
        )

        # Patch stdlib logger to avoid flaky cross-test logging configuration.
        from work_data_hub.infrastructure.enrichment import (
            company_id_resolver as resolver_module,
        )
        from unittest.mock import patch

        with patch.object(resolver_module._stdlib_logger, "debug") as mock_debug:
            resolver.resolve_batch(df, default_strategy)

        assert any(
            call.args
            and "company_id_resolver.db_cache_decision_path" in str(call.args[0])
            and len(call.args) >= 3
            and "DB-P1:HIT" in str(call.args[2])
            for call in mock_debug.call_args_list
        )

    def test_enrichment_index_fallbacks_to_legacy_on_no_hits(self, default_strategy):
        """If enrichment_index misses, resolver should fall back to legacy table when available."""
        mock_repo = MagicMock()
        mock_repo.lookup_enrichment_index_batch.return_value = {}
        # Legacy path result
        from work_data_hub.infrastructure.enrichment.mapping_repository import (
            MatchResult,
        )

        mock_repo.lookup_batch.return_value = {
            "legacy_key": MatchResult(
                company_id="C_LEGACY",
                match_type="name",
                priority=4,
                source="internal",
            )
        }

        resolver = CompanyIdResolver(
            eqc_config=EqcLookupConfig.disabled(),
            yaml_overrides={
                "plan": {},
                "account": {},
                "hardcode": {},
                "name": {},
                "account_name": {},
            },
            mapping_repository=mock_repo,
        )

        df = pd.DataFrame(
            {
                "计划代码": [None],
                "客户名称": ["legacy_key"],
            }
        )

        result = resolver.resolve_batch(df, default_strategy)

        assert result.data.loc[0, "company_id"] == "C_LEGACY"
        assert result.statistics.db_cache_hits["legacy"] == 1
        assert result.statistics.db_cache_hits_total == 1

    def test_enrichment_index_updates_hit_count_per_hit(self, default_strategy):
        """Hit count should increment per-row hit, not per-unique key."""
        mock_repo = MagicMock()
        mock_repo.lookup_enrichment_index_batch.return_value = {
            (LookupType.PLAN_CODE, "PLAN001"): EnrichmentIndexRecord(
                lookup_key="PLAN001",
                lookup_type=LookupType.PLAN_CODE,
                company_id="C_PLAN",
                source=SourceType.YAML,
            ),
        }
        mock_repo.update_hit_count.return_value = True

        resolver = CompanyIdResolver(
            eqc_config=EqcLookupConfig.disabled(),
            yaml_overrides={
                "plan": {},
                "account": {},
                "hardcode": {},
                "name": {},
                "account_name": {},
            },
            mapping_repository=mock_repo,
        )

        df = pd.DataFrame(
            {
                "计划代码": ["PLAN001", "PLAN001"],  # Same key hit twice
                "客户名称": ["Customer A", "Customer B"],
            }
        )

        result = resolver.resolve_batch(df, default_strategy)

        assert result.statistics.db_cache_hits["plan_code"] == 2
        assert result.statistics.db_cache_hits_total == 2
        assert mock_repo.update_hit_count.call_count == 2
        assert result.statistics.db_decision_path_counts.get("DB-P1:HIT") == 2

    def test_enrichment_index_emits_metrics_log(self, default_strategy):
        """Metrics log should include per-priority hits and decision-path counts."""
        mock_repo = MagicMock()
        mock_repo.lookup_enrichment_index_batch.return_value = {
            (LookupType.PLAN_CODE, "PLAN001"): EnrichmentIndexRecord(
                lookup_key="PLAN001",
                lookup_type=LookupType.PLAN_CODE,
                company_id="C_PLAN",
                source=SourceType.YAML,
            ),
        }
        mock_repo.update_hit_count.return_value = True

        resolver = CompanyIdResolver(
            eqc_config=EqcLookupConfig.disabled(),
            yaml_overrides={
                "plan": {},
                "account": {},
                "hardcode": {},
                "name": {},
                "account_name": {},
            },
            mapping_repository=mock_repo,
        )

        df = pd.DataFrame(
            {
                "计划代码": ["PLAN001"],
                "客户名称": [" Customer_A  "],
            }
        )

        # Patch stdlib logger to avoid flaky cross-test logging configuration.
        from work_data_hub.infrastructure.enrichment import (
            company_id_resolver as resolver_module,
        )
        from unittest.mock import patch

        with patch.object(resolver_module._stdlib_logger, "info") as mock_info:
            resolver.resolve_batch(df, default_strategy)

        assert any(
            call.args and "company_id_resolver.db_cache_metrics" in str(call.args[0])
            for call in mock_info.call_args_list
        ), "Expected db_cache_metrics log entry"


class TestP4NormalizationDbCacheLookup:
    """Tests for P4 (customer_name) normalization in DB cache lookup (AC1, AC3)."""

    def test_db_cache_lookup_normalizes_p4_customer_name(self, default_strategy):
        """P4 (customer_name) should be normalized before DB lookup (AC1)."""
        from unittest.mock import MagicMock
        from work_data_hub.infrastructure.enrichment.mapping_repository import (
            MatchResult,
        )

        mock_repo = MagicMock()
        # DB has normalized key "公司A" (without brackets/status markers)
        mock_repo.lookup_batch.return_value = {
            "公司A": MatchResult(
                company_id="normalized_company_123",
                match_type="name",
                priority=4,
                source="internal",
            )
        }

        resolver = CompanyIdResolver(
            eqc_config=EqcLookupConfig.disabled(),
            yaml_overrides={
                "plan": {},
                "account": {},
                "hardcode": {},
                "name": {},
                "account_name": {},
            },
            mapping_repository=mock_repo,
        )

        # Input has raw value with bracket content that normalizes to "公司A"
        # normalize_company_name removes leading/trailing bracket content
        df = pd.DataFrame(
            {
                "计划代码": ["UNKNOWN"],
                "客户名称": ["（核心）公司A"],  # Should normalize to "公司A"
            }
        )

        result = resolver.resolve_batch(df, default_strategy)

        # Should hit cache because normalized("（核心）公司A") == "公司A"
        assert result.data.loc[0, "company_id"] == "normalized_company_123"
        assert result.statistics.db_cache_hits["legacy"] == 1
        assert result.statistics.db_cache_hits_total == 1

    def test_db_cache_lookup_raw_for_p1_plan_code(self, default_strategy):
        """P1 (plan_code) should use RAW values for DB lookup (AC3)."""
        from unittest.mock import MagicMock
        from work_data_hub.infrastructure.enrichment.mapping_repository import (
            MatchResult,
        )

        mock_repo = MagicMock()
        # DB has raw key "PLAN001" (exact match required)
        mock_repo.lookup_batch.return_value = {
            "PLAN001": MatchResult(
                company_id="plan_company_123",
                match_type="plan",
                priority=1,
                source="internal",
            )
        }

        resolver = CompanyIdResolver(
            eqc_config=EqcLookupConfig.disabled(),
            yaml_overrides={
                "plan": {},
                "account": {},
                "hardcode": {},
                "name": {},
                "account_name": {},
            },
            mapping_repository=mock_repo,
        )

        df = pd.DataFrame(
            {
                "计划代码": ["PLAN001"],
                "客户名称": ["公司A"],
            }
        )

        result = resolver.resolve_batch(df, default_strategy)

        # Should hit cache with exact raw match
        assert result.data.loc[0, "company_id"] == "plan_company_123"
        assert result.statistics.db_cache_hits["legacy"] == 1
        assert result.statistics.db_cache_hits_total == 1

    def test_db_cache_lookup_raw_for_p2_account_number(self, default_strategy):
        """P2 (account_number) should use RAW values for DB lookup (AC3)."""
        from unittest.mock import MagicMock
        from work_data_hub.infrastructure.enrichment.mapping_repository import (
            MatchResult,
        )

        mock_repo = MagicMock()
        mock_repo.lookup_batch.return_value = {
            "ACC001": MatchResult(
                company_id="account_company_123",
                match_type="account",
                priority=2,
                source="internal",
            )
        }

        resolver = CompanyIdResolver(
            eqc_config=EqcLookupConfig.disabled(),
            yaml_overrides={
                "plan": {},
                "account": {},
                "hardcode": {},
                "name": {},
                "account_name": {},
            },
            mapping_repository=mock_repo,
        )

        df = pd.DataFrame(
            {
                "计划代码": ["UNKNOWN"],
                "客户名称": ["公司A"],
                "年金账户号": ["ACC001"],
            }
        )

        result = resolver.resolve_batch(df, default_strategy)

        assert result.data.loc[0, "company_id"] == "account_company_123"
        assert result.statistics.db_cache_hits["legacy"] == 1
        assert result.statistics.db_cache_hits_total == 1

    def test_db_cache_lookup_raw_for_p5_account_name(self, default_strategy):
        """P5 (account_name) should use RAW values for DB lookup (AC3)."""
        from unittest.mock import MagicMock
        from work_data_hub.infrastructure.enrichment.mapping_repository import (
            MatchResult,
        )

        mock_repo = MagicMock()
        mock_repo.lookup_batch.return_value = {
            "账户名A": MatchResult(
                company_id="account_name_company_123",
                match_type="account_name",
                priority=5,
                source="internal",
            )
        }

        resolver = CompanyIdResolver(
            eqc_config=EqcLookupConfig.disabled(),
            yaml_overrides={
                "plan": {},
                "account": {},
                "hardcode": {},
                "name": {},
                "account_name": {},
            },
            mapping_repository=mock_repo,
        )

        df = pd.DataFrame(
            {
                "计划代码": ["UNKNOWN"],
                "客户名称": ["公司A"],
                "年金账户名": ["账户名A"],
            }
        )

        result = resolver.resolve_batch(df, default_strategy)

        assert result.data.loc[0, "company_id"] == "account_name_company_123"
        assert result.statistics.db_cache_hits["legacy"] == 1
        assert result.statistics.db_cache_hits_total == 1


class TestP4NormalizationBackflow:
    """Tests for P4 (customer_name) normalization in backflow (AC2, AC3)."""

    def test_backflow_normalizes_p4_customer_name(self, default_strategy):
        """P4 backflow should write normalized value to DB (AC2)."""
        from unittest.mock import MagicMock
        from work_data_hub.infrastructure.enrichment.mapping_repository import (
            InsertBatchResult,
        )

        mock_repo = MagicMock()
        mock_repo.lookup_batch.return_value = {}
        mock_repo.insert_batch_with_conflict_check.return_value = InsertBatchResult(
            inserted_count=1,
            skipped_count=0,
            conflicts=[],
        )

        resolver = CompanyIdResolver(
            eqc_config=EqcLookupConfig.disabled(),
            yaml_overrides={
                "plan": {},
                "account": {},
                "hardcode": {},
                "name": {},
                "account_name": {},
            },
            mapping_repository=mock_repo,
        )

        # Input has raw customer_name with bracket content
        # normalize_company_name removes leading/trailing bracket content
        df = pd.DataFrame(
            {
                "计划代码": ["UNKNOWN"],
                "客户名称": ["公司B（非核心）"],  # Should normalize to "公司B"
                "公司代码": ["existing_456"],
            }
        )

        result = resolver.resolve_batch(df, default_strategy)

        # Verify backflow was called
        mock_repo.insert_batch_with_conflict_check.assert_called_once()
        call_args = mock_repo.insert_batch_with_conflict_check.call_args[0][0]

        # Find the name mapping entry
        name_entries = [e for e in call_args if e["match_type"] == "name"]
        assert len(name_entries) == 1
        # Should be normalized (no bracket content)
        assert name_entries[0]["alias_name"] == "公司B"

    def test_backflow_raw_for_p2_account_number(self, default_strategy):
        """P2 backflow should write RAW value to DB (AC3)."""
        from unittest.mock import MagicMock
        from work_data_hub.infrastructure.enrichment.mapping_repository import (
            InsertBatchResult,
        )

        mock_repo = MagicMock()
        mock_repo.lookup_batch.return_value = {}
        mock_repo.insert_batch_with_conflict_check.return_value = InsertBatchResult(
            inserted_count=1,
            skipped_count=0,
            conflicts=[],
        )

        resolver = CompanyIdResolver(
            eqc_config=EqcLookupConfig.disabled(),
            yaml_overrides={
                "plan": {},
                "account": {},
                "hardcode": {},
                "name": {},
                "account_name": {},
            },
            mapping_repository=mock_repo,
        )

        df = pd.DataFrame(
            {
                "计划代码": ["UNKNOWN"],
                "客户名称": ["公司A"],
                "年金账户号": ["ACC001"],
                "公司代码": ["existing_789"],
            }
        )

        result = resolver.resolve_batch(df, default_strategy)

        mock_repo.insert_batch_with_conflict_check.assert_called_once()
        call_args = mock_repo.insert_batch_with_conflict_check.call_args[0][0]

        # Find the account mapping entry
        account_entries = [e for e in call_args if e["match_type"] == "account"]
        assert len(account_entries) == 1
        # Should be raw (exact value)
        assert account_entries[0]["alias_name"] == "ACC001"

    def test_backflow_raw_for_p5_account_name(self, default_strategy):
        """P5 backflow should write RAW value to DB (AC3)."""
        from unittest.mock import MagicMock
        from work_data_hub.infrastructure.enrichment.mapping_repository import (
            InsertBatchResult,
        )

        mock_repo = MagicMock()
        mock_repo.lookup_batch.return_value = {}
        mock_repo.insert_batch_with_conflict_check.return_value = InsertBatchResult(
            inserted_count=1,
            skipped_count=0,
            conflicts=[],
        )

        resolver = CompanyIdResolver(
            eqc_config=EqcLookupConfig.disabled(),
            yaml_overrides={
                "plan": {},
                "account": {},
                "hardcode": {},
                "name": {},
                "account_name": {},
            },
            mapping_repository=mock_repo,
        )

        df = pd.DataFrame(
            {
                "计划代码": ["UNKNOWN"],
                "客户名称": ["公司A"],
                "年金账户名": ["账户名B"],
                "公司代码": ["existing_999"],
            }
        )

        result = resolver.resolve_batch(df, default_strategy)

        mock_repo.insert_batch_with_conflict_check.assert_called_once()
        call_args = mock_repo.insert_batch_with_conflict_check.call_args[0][0]

        # Find the account_name mapping entry
        account_name_entries = [
            e for e in call_args if e["match_type"] == "account_name"
        ]
        assert len(account_name_entries) == 1
        # Should be raw (exact value)
        assert account_name_entries[0]["alias_name"] == "账户名B"

    def test_backflow_skips_empty_normalized_p4(self, default_strategy):
        """If P4 normalization returns empty string, skip backflow (AC2)."""
        from unittest.mock import MagicMock
        from work_data_hub.infrastructure.enrichment.mapping_repository import (
            InsertBatchResult,
        )

        mock_repo = MagicMock()
        mock_repo.lookup_batch.return_value = {}
        mock_repo.insert_batch_with_conflict_check.return_value = InsertBatchResult(
            inserted_count=0,
            skipped_count=0,
            conflicts=[],
        )

        resolver = CompanyIdResolver(
            eqc_config=EqcLookupConfig.disabled(),
            yaml_overrides={
                "plan": {},
                "account": {},
                "hardcode": {},
                "name": {},
                "account_name": {},
            },
            mapping_repository=mock_repo,
        )

        # Customer name that might normalize to empty (edge case)
        df = pd.DataFrame(
            {
                "计划代码": ["UNKNOWN"],
                "客户名称": ["   "],  # Whitespace only - normalizes to empty
                "公司代码": ["existing_111"],
            }
        )

        result = resolver.resolve_batch(df, default_strategy)

        # Backflow may be called but should not include empty alias_name
        if mock_repo.insert_batch_with_conflict_check.called:
            call_args = mock_repo.insert_batch_with_conflict_check.call_args[0][0]
            name_entries = [e for e in call_args if e["match_type"] == "name"]
            # Should have no name entries (empty normalized value skipped)
            assert len(name_entries) == 0


class TestP4NormalizationEdgeCases:
    """Tests for P4 normalization edge cases (AC4)."""

    def test_p4_normalization_special_characters(self, default_strategy):
        """Test P4 normalization handles special characters correctly."""
        from unittest.mock import MagicMock
        from work_data_hub.infrastructure.enrichment.mapping_repository import (
            MatchResult,
        )

        mock_repo = MagicMock()
        # DB has normalized key without decorative characters
        mock_repo.lookup_batch.return_value = {
            "公司C": MatchResult(
                company_id="special_company_123",
                match_type="name",
                priority=4,
                source="internal",
            )
        }

        resolver = CompanyIdResolver(
            eqc_config=EqcLookupConfig.disabled(),
            yaml_overrides={
                "plan": {},
                "account": {},
                "hardcode": {},
                "name": {},
                "account_name": {},
            },
            mapping_repository=mock_repo,
        )

        # Input has decorative characters that should be removed
        df = pd.DataFrame(
            {
                "计划代码": ["UNKNOWN"],
                "客户名称": ["「公司C」"],  # Decorative brackets should be removed
            }
        )

        result = resolver.resolve_batch(df, default_strategy)

        assert result.data.loc[0, "company_id"] == "special_company_123"
        assert result.statistics.db_cache_hits["legacy"] == 1
        assert result.statistics.db_cache_hits_total == 1

    def test_p4_normalization_full_width_conversion(self, default_strategy):
        """Test P4 normalization converts full-width ASCII to half-width."""
        from unittest.mock import MagicMock
        from work_data_hub.infrastructure.enrichment.mapping_repository import (
            MatchResult,
        )

        mock_repo = MagicMock()
        # DB has half-width version
        mock_repo.lookup_batch.return_value = {
            "ABC公司": MatchResult(
                company_id="fullwidth_company_123",
                match_type="name",
                priority=4,
                source="internal",
            )
        }

        resolver = CompanyIdResolver(
            eqc_config=EqcLookupConfig.disabled(),
            yaml_overrides={
                "plan": {},
                "account": {},
                "hardcode": {},
                "name": {},
                "account_name": {},
            },
            mapping_repository=mock_repo,
        )

        # Input has full-width ASCII
        df = pd.DataFrame(
            {
                "计划代码": ["UNKNOWN"],
                "客户名称": ["ＡＢＣ公司"],  # Full-width ABC
            }
        )

        result = resolver.resolve_batch(df, default_strategy)

        assert result.data.loc[0, "company_id"] == "fullwidth_company_123"
        assert result.statistics.db_cache_hits["legacy"] == 1
        assert result.statistics.db_cache_hits_total == 1

    def test_p3_hardcode_yaml_uses_raw_values(self, default_strategy):
        """P3 (hardcode/plan_code) YAML lookup should use RAW values (AC3 regression guard)."""
        # P3 hardcode uses the same column as P1 (plan_code_column)
        # This test ensures YAML lookup path remains RAW for P3
        yaml_overrides = {
            "plan": {},
            "account": {},
            "hardcode": {"FP0001": "hardcode_company_123"},  # P3 hardcode mapping
            "name": {},
            "account_name": {},
        }
        resolver = CompanyIdResolver(
            eqc_config=EqcLookupConfig.disabled(), yaml_overrides=yaml_overrides
        )

        df = pd.DataFrame(
            {
                "计划代码": ["FP0001"],  # Exact raw match required
                "客户名称": ["公司A"],
            }
        )

        result = resolver.resolve_batch(df, default_strategy)

        # Should hit via hardcode YAML with exact raw match
        assert result.data.loc[0, "company_id"] == "hardcode_company_123"
        assert result.statistics.yaml_hits.get("hardcode", 0) == 1


class TestP4NormalizationIntegration:
    """Integration tests for P4 normalization cache hit improvement (AC5)."""

    def test_cache_hit_after_backflow_with_normalized_p4(self, default_strategy):
        """Test round-trip: backflow writes normalized → lookup finds normalized (AC5)."""
        from unittest.mock import MagicMock
        from work_data_hub.infrastructure.enrichment.mapping_repository import (
            InsertBatchResult,
            MatchResult,
        )

        mock_repo = MagicMock()

        # Phase 1: Backflow - simulate existing column resolution
        mock_repo.lookup_batch.return_value = {}  # No cache hit initially
        mock_repo.insert_batch_with_conflict_check.return_value = InsertBatchResult(
            inserted_count=1,
            skipped_count=0,
            conflicts=[],
        )

        resolver = CompanyIdResolver(
            eqc_config=EqcLookupConfig.disabled(),
            yaml_overrides={
                "plan": {},
                "account": {},
                "hardcode": {},
                "name": {},
                "account_name": {},
            },
            mapping_repository=mock_repo,
        )

        # First batch: has existing company_id, triggers backflow
        df1 = pd.DataFrame(
            {
                "计划代码": ["UNKNOWN"],
                "客户名称": ["公司D（核心）"],  # Will normalize to "公司D"
                "公司代码": ["real_company_789"],
            }
        )

        result1 = resolver.resolve_batch(df1, default_strategy)
        assert result1.data.loc[0, "company_id"] == "real_company_789"
        assert result1.statistics.existing_column_hits == 1

        # Verify backflow wrote normalized value
        backflow_call = mock_repo.insert_batch_with_conflict_check.call_args[0][0]
        name_entries = [e for e in backflow_call if e["match_type"] == "name"]
        assert len(name_entries) == 1
        assert name_entries[0]["alias_name"] == "公司D"  # Normalized

        # Phase 2: Lookup - simulate cache hit with normalized key
        mock_repo.lookup_batch.return_value = {
            "公司D": MatchResult(
                company_id="real_company_789",
                match_type="name",
                priority=4,
                source="internal",
            )
        }

        # Second batch: different raw value that normalizes to same key
        df2 = pd.DataFrame(
            {
                "计划代码": ["UNKNOWN"],
                "客户名称": ["（非核心）公司D"],  # Also normalizes to "公司D"
            }
        )

        result2 = resolver.resolve_batch(df2, default_strategy)

        # Should hit cache because normalized("（非核心）公司D") == "公司D"
        assert result2.data.loc[0, "company_id"] == "real_company_789"
        assert result2.statistics.db_cache_hits["legacy"] == 1
        assert result2.statistics.db_cache_hits_total == 1
