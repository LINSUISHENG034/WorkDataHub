"""Phase J: Anti-fake behavior guards for core domain flows.

These tests focus on behavior contracts that are hard to satisfy with
placeholder implementations:
1. Company ID resolution priority chain (YAML -> DB cache -> existing -> EQC -> temp)
2. DB-driven plan-code enrichment for annual_award / annual_loss
3. Orchestration stage chain coverage for annual_award / annual_loss
"""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest
from dagster import build_op_context

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
from work_data_hub.orchestration.ops.generic_backfill import (
    GenericBackfillConfig,
    gate_after_backfill,
    generic_backfill_refs_op,
)
from work_data_hub.orchestration.ops.generic_ops import (
    GenericDomainOpConfig,
    process_domain_op_v2,
)
from work_data_hub.orchestration.ops.loading import LoadConfig, load_op

pytestmark = pytest.mark.slice_test


class _FakeMappingRepository:
    def __init__(self) -> None:
        self.lookup_calls: list[dict[LookupType, list[str]]] = []

    def lookup_enrichment_index_batch(self, keys_by_type):
        self.lookup_calls.append(keys_by_type)
        return {
            (LookupType.PLAN_CODE, "DB_PLAN"): EnrichmentIndexRecord(
                lookup_key="DB_PLAN",
                lookup_type=LookupType.PLAN_CODE,
                company_id="CID_DB",
                source=SourceType.MANUAL,
            )
        }

    def update_hit_count(self, key: str, lookup_type: LookupType) -> None:
        # No-op for test observability.
        return None


class _FakeEqcProvider:
    def __init__(self) -> None:
        self.is_available = True
        self.budget = 3
        self.remaining_budget = 3
        self.lookups: list[str] = []

    def lookup(self, company_name: str):
        self.lookups.append(company_name)
        self.remaining_budget -= 1
        if company_name == "EQC公司":
            return SimpleNamespace(company_id="CID_EQC")
        return None


class _CaptureConnection:
    """Minimal SQLAlchemy-like connection stub for PlanCodeEnrichmentStep."""

    def __init__(self, rows: list[SimpleNamespace]) -> None:
        self.rows = rows
        self.calls: list[dict[str, object]] = []

    def execute(self, query, params):
        self.calls.append({"sql": str(query), "params": params})
        return list(self.rows)


def test_j1_company_id_resolution_priority_chain_contract() -> None:
    mapping_repository = _FakeMappingRepository()
    eqc_provider = _FakeEqcProvider()

    resolver = CompanyIdResolver(
        eqc_config=EqcLookupConfig(
            enabled=True,
            sync_budget=3,
            auto_create_provider=False,
            export_unknown_names=False,
            auto_refresh_token=False,
        ),
        yaml_overrides={
            "plan": {"YAML_PLAN": "CID_YAML"},
            "hardcode": {},
            "name": {},
        },
        mapping_repository=mapping_repository,
        eqc_provider=eqc_provider,
    )

    input_df = pd.DataFrame(
        {
            "计划代码": ["YAML_PLAN", "DB_PLAN", "NO_HIT", "NO_EQC", "NO_TMP"],
            "客户名称": ["YAML公司", "DB公司", "已有公司", "EQC公司", "最终临时"],
            "源公司代码": [None, None, "CID_EXISTING", None, None],
        }
    )

    result = resolver.resolve_batch(
        input_df,
        ResolutionStrategy(
            plan_code_column="计划代码",
            customer_name_column="客户名称",
            company_id_column="源公司代码",
            output_column="company_id",
            generate_temp_ids=True,
            enable_backflow=False,
            enable_async_queue=False,
        ),
    )

    output = result.data["company_id"].tolist()
    assert output[0] == "CID_YAML"
    assert output[1] == "CID_DB"
    assert output[2] == "CID_EXISTING"
    assert output[3] == "CID_EQC"
    assert isinstance(output[4], str) and output[4].startswith("IN")

    stats = result.statistics
    assert stats.yaml_hits.get("plan", 0) == 1
    assert stats.db_cache_hits.get("plan_code", 0) == 1
    assert stats.existing_column_hits == 1
    assert stats.eqc_sync_hits == 1
    assert stats.temp_ids_generated == 1
    assert stats.unresolved == 0


def test_j2_annual_award_plan_code_enrichment_uses_db_lookup(
    make_pipeline_context,
) -> None:
    from work_data_hub.domain.annual_award.pipeline_builder import (
        PlanCodeEnrichmentStep,
    )

    connection = _CaptureConnection(
        rows=[
            SimpleNamespace(
                company_id="COMP_A", product_line_code="PL202", plan_code="S100"
            ),
            SimpleNamespace(
                company_id="COMP_A", product_line_code="PL202", plan_code="P200"
            ),
            SimpleNamespace(
                company_id="COMP_B", product_line_code="PL201", plan_code="P900"
            ),
        ]
    )

    df = pd.DataFrame(
        {
            "company_id": ["COMP_A", "COMP_A", "COMP_B"],
            "产品线代码": ["PL202", "PL202", "PL201"],
            "计划类型": ["集合计划", "单一计划", "集合计划"],
            "年金计划号": ["", None, "P_EXISTING"],
        }
    )

    result = PlanCodeEnrichmentStep(db_connection=connection).apply(
        df,
        make_pipeline_context(domain="annual_award"),
    )

    assert result.loc[0, "年金计划号"] == "P200"
    assert result.loc[1, "年金计划号"] == "S100"
    assert result.loc[2, "年金计划号"] == "P_EXISTING"

    assert len(connection.calls) == 1
    company_ids = connection.calls[0]["params"]["company_ids"]
    assert company_ids == ["COMP_A"]


def test_j3_annual_loss_plan_code_enrichment_uses_db_lookup(
    make_pipeline_context,
) -> None:
    from work_data_hub.domain.annual_loss.pipeline_builder import PlanCodeEnrichmentStep

    connection = _CaptureConnection(
        rows=[
            SimpleNamespace(
                company_id="COMP_X", product_line_code="PL201", plan_code="S800"
            ),
            SimpleNamespace(
                company_id="COMP_X", product_line_code="PL201", plan_code="P700"
            ),
        ]
    )

    df = pd.DataFrame(
        {
            "company_id": ["COMP_X", "COMP_X"],
            "产品线代码": ["PL201", "PL201"],
            "计划类型": ["集合计划", "单一计划"],
            "年金计划号": [None, ""],
        }
    )

    result = PlanCodeEnrichmentStep(db_connection=connection).apply(
        df,
        make_pipeline_context(domain="annual_loss"),
    )

    assert result.loc[0, "年金计划号"] == "P700"
    assert result.loc[1, "年金计划号"] == "S800"
    assert len(connection.calls) == 1


@pytest.mark.parametrize(
    ("domain", "table", "pk", "fixture_name"),
    [
        (
            "annual_award",
            'customer."中标客户明细"',
            ["上报月份", "业务类型"],
            "annual_award_slice_df",
        ),
        (
            "annual_loss",
            'customer."流失客户明细"',
            ["上报月份", "业务类型"],
            "annual_loss_slice_df",
        ),
    ],
)
def test_j4_orchestration_chain_contract_for_event_domains(
    request,
    domain: str,
    table: str,
    pk: list[str],
    fixture_name: str,
) -> None:
    rows = request.getfixturevalue(fixture_name).to_dict("records")
    file_paths = [f"slice_{domain}.xlsx"]

    process_ctx = build_op_context()
    processed_rows = process_domain_op_v2(
        process_ctx,
        GenericDomainOpConfig(domain=domain, plan_only=True),
        rows,
        file_paths,
    )
    assert processed_rows

    backfill_ctx = build_op_context()
    backfill_summary = generic_backfill_refs_op(
        backfill_ctx,
        GenericBackfillConfig(domain=domain, add_tracking_fields=False, plan_only=True),
        processed_rows,
    )
    assert backfill_summary["plan_only"] is True
    assert any(
        item["table"] == "客户明细" for item in backfill_summary["tables_processed"]
    )

    gated_rows = gate_after_backfill(
        build_op_context(), processed_rows, backfill_summary
    )
    assert gated_rows == processed_rows

    load_result = load_op(
        build_op_context(),
        LoadConfig(table=table, mode="delete_insert", pk=pk, plan_only=True),
        gated_rows,
    )
    assert "sql_plans" in load_result
    assert {plan[0] for plan in load_result["sql_plans"]} >= {"DELETE", "INSERT"}
