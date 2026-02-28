"""Phase H: End-to-end slice flow contracts.

These tests validate full behavior contracts (not single constants) for:
1. Bronze->Silver pipelines of three core domains
2. FK backfill candidate derivation for real downstream effects
3. Orchestration chain: process -> backfill -> gate -> load(plan-only)
4. File discovery + read_data integration for single-sheet and multi-sheet inputs
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
import yaml
from dagster import build_op_context

from work_data_hub.domain.reference_backfill import (
    GenericBackfillService,
    load_foreign_keys_config,
)
from work_data_hub.infrastructure.enrichment import EqcLookupConfig
from work_data_hub.orchestration.ops.file_processing import (
    DiscoverFilesConfig,
    ReadDataOpConfig,
    discover_files_op,
    read_data_op,
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


def _write_excel(path: Path, sheets: dict[str, pd.DataFrame]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for sheet_name, sheet_df in sheets.items():
            sheet_df.to_excel(writer, sheet_name=sheet_name, index=False)


def test_h1_annuity_pipeline_contract(
    annuity_performance_slice_df: pd.DataFrame,
    make_pipeline_context,
) -> None:
    from work_data_hub.domain.annuity_performance.pipeline_builder import (
        build_bronze_to_silver_pipeline,
    )

    pipeline = build_bronze_to_silver_pipeline(eqc_config=EqcLookupConfig.disabled())
    result = pipeline.execute(
        annuity_performance_slice_df.copy(),
        make_pipeline_context(domain="annuity_performance"),
    )

    assert len(result) == len(annuity_performance_slice_df)
    assert "计划代码" in result.columns
    assert "机构名称" in result.columns
    assert "产品线代码" in result.columns
    assert "company_id" in result.columns
    assert "id" not in result.columns
    assert "备注" not in result.columns

    # Empty plan code defaults must be applied by plan type.
    collective_row = result[result["客户名称"] == "缺计划集合"].iloc[0]
    single_row = result[result["客户名称"] == "缺计划单一"].iloc[0]
    assert collective_row["计划代码"] == "AN001"
    assert single_row["计划代码"] == "AN002"

    # Group customer id cleaning + account number derivation must remain consistent.
    shared_row = result[result["客户名称"] == "共享客户"].iloc[0]
    assert shared_row["集团企业客户号"] == "10001"
    assert shared_row["年金账户号"] == "10001"

    # Fallback/derived fields should be present, not silently dropped.
    assert result["机构代码"].notna().all()
    assert result["产品线代码"].notna().all()
    assert result["company_id"].notna().all()


def test_h2_annual_award_pipeline_contract(
    annual_award_slice_df: pd.DataFrame,
    make_pipeline_context,
) -> None:
    from work_data_hub.domain.annual_award.pipeline_builder import (
        build_bronze_to_silver_pipeline,
    )

    pipeline = build_bronze_to_silver_pipeline(
        eqc_config=EqcLookupConfig.disabled(),
        db_connection=None,
    )
    result = pipeline.execute(
        annual_award_slice_df.copy(),
        make_pipeline_context(domain="annual_award"),
    )

    assert len(result) == len(annual_award_slice_df)
    assert "上报客户名称" in result.columns
    assert "客户全称" not in result.columns
    assert "机构代码" in result.columns
    assert "company_id" in result.columns

    # Business/plan normalization must be effective.
    assert set(result["业务类型"].dropna().unique()) <= {"企年受托", "企年投资"}
    assert set(result["计划类型"].dropna().unique()) <= {"集合计划", "单一计划"}

    # Missing plan code must be defaulted after enrichment stage.
    shared_collective = result[
        (result["上报客户名称"] == "共享客户（中标）")
        & (result["计划类型"] == "集合计划")
    ].iloc[0]
    shared_single = result[
        (result["上报客户名称"] == "共享客户（中标）")
        & (result["计划类型"] == "单一计划")
    ].iloc[0]
    assert shared_collective["年金计划号"] == "AN001"
    assert shared_single["年金计划号"] == "AN002"

    # Existing source plan code should not be overwritten by defaults.
    existing = result[result["上报客户名称"] == "新客中标"].iloc[0]
    assert existing["年金计划号"] == "P9001"
    assert existing["机构代码"] == "G00"  # unknown branch fallback


def test_h3_annual_loss_pipeline_contract(
    annual_loss_slice_df: pd.DataFrame,
    make_pipeline_context,
) -> None:
    from work_data_hub.domain.annual_loss.pipeline_builder import (
        build_bronze_to_silver_pipeline,
    )

    pipeline = build_bronze_to_silver_pipeline(
        eqc_config=EqcLookupConfig.disabled(),
        db_connection=None,
    )
    result = pipeline.execute(
        annual_loss_slice_df.copy(),
        make_pipeline_context(domain="annual_loss"),
    )

    assert len(result) == len(annual_loss_slice_df)
    assert "上报客户名称" in result.columns
    assert "客户全称" not in result.columns
    assert "机构代码" in result.columns
    assert "company_id" in result.columns

    assert set(result["业务类型"].dropna().unique()) <= {"企年受托", "企年投资"}
    assert set(result["计划类型"].dropna().unique()) <= {"集合计划", "单一计划"}

    shared_collective = result[
        (result["上报客户名称"] == "共享客户（流失）")
        & (result["计划类型"] == "集合计划")
    ].iloc[0]
    shared_single = result[
        (result["上报客户名称"] == "共享客户（流失）")
        & (result["计划类型"] == "单一计划")
    ].iloc[0]
    assert shared_collective["年金计划号"] == "AN001"
    assert shared_single["年金计划号"] == "AN002"

    existing = result[result["上报客户名称"] == "新客流失"].iloc[0]
    assert existing["年金计划号"] == "P9101"
    assert existing["机构代码"] == "G00"


def test_h4_backfill_annuity_customer_aggregation_contract(
    annuity_performance_slice_df: pd.DataFrame,
    make_pipeline_context,
) -> None:
    from work_data_hub.domain.annuity_performance.pipeline_builder import (
        build_bronze_to_silver_pipeline,
    )

    pipeline = build_bronze_to_silver_pipeline(eqc_config=EqcLookupConfig.disabled())
    transformed = pipeline.execute(
        annuity_performance_slice_df.copy(),
        make_pipeline_context(domain="annuity_performance"),
    )

    fk_configs = load_foreign_keys_config(domain="annuity_performance")
    fk_customer = next(c for c in fk_configs if c.name == "fk_customer")
    service = GenericBackfillService(domain="annuity_performance")
    candidates = service.derive_candidates(transformed, fk_customer)

    target = candidates[candidates["company_id"] == "COMP_SHARED"].iloc[0]
    shared_rows = transformed[transformed["company_id"] == "COMP_SHARED"]

    expected_main_code = shared_rows.loc[
        shared_rows["期末资产规模"].idxmax(), "机构代码"
    ]
    expected_plan_count = shared_rows["计划代码"].nunique(dropna=True)
    expected_qual_set = set(shared_rows["业务类型"].dropna().astype(str).unique())
    actual_qual_set = set(str(target["管理资格"]).split("+"))

    assert target["主拓机构代码"] == expected_main_code
    assert int(target["关联计划数"]) == int(expected_plan_count)
    assert actual_qual_set == expected_qual_set
    assert str(target["年金客户标签"]).endswith("新建")
    assert target["年金客户类型"] == "新客"


def test_h5_backfill_award_loss_tags_contract(
    annual_award_slice_df: pd.DataFrame,
    annual_loss_slice_df: pd.DataFrame,
    make_pipeline_context,
) -> None:
    from work_data_hub.domain.annual_award.pipeline_builder import (
        build_bronze_to_silver_pipeline as build_award_pipeline,
    )
    from work_data_hub.domain.annual_loss.pipeline_builder import (
        build_bronze_to_silver_pipeline as build_loss_pipeline,
    )

    award_df = build_award_pipeline(
        eqc_config=EqcLookupConfig.disabled(), db_connection=None
    ).execute(
        annual_award_slice_df.copy(),
        make_pipeline_context(domain="annual_award"),
    )
    loss_df = build_loss_pipeline(
        eqc_config=EqcLookupConfig.disabled(), db_connection=None
    ).execute(
        annual_loss_slice_df.copy(),
        make_pipeline_context(domain="annual_loss"),
    )

    award_fk = next(
        c
        for c in load_foreign_keys_config(domain="annual_award")
        if c.name == "fk_customer"
    )
    loss_fk = next(
        c
        for c in load_foreign_keys_config(domain="annual_loss")
        if c.name == "fk_customer"
    )

    service_award = GenericBackfillService(domain="annual_award")
    service_loss = GenericBackfillService(domain="annual_loss")
    award_candidates = service_award.derive_candidates(award_df, award_fk)
    loss_candidates = service_loss.derive_candidates(loss_df, loss_fk)

    award_target = award_candidates[
        award_candidates["年金客户类型"] == "中标客户"
    ].iloc[0]
    loss_target = loss_candidates[loss_candidates["年金客户类型"] == "流失客户"].iloc[0]

    award_tags = json.loads(award_target["tags"])
    loss_tags = json.loads(loss_target["tags"])

    assert "2510中标" in award_tags
    assert "2510流失" in loss_tags
    assert award_target["年金客户类型"] == "中标客户"
    assert loss_target["年金客户类型"] == "流失客户"


def test_h6_orchestration_chain_contract(
    annuity_performance_slice_df: pd.DataFrame,
) -> None:
    rows = annuity_performance_slice_df.to_dict("records")
    file_paths = ["slice_规模收入数据.xlsx"]

    process_ctx = build_op_context()
    processed_rows = process_domain_op_v2(
        process_ctx,
        GenericDomainOpConfig(domain="annuity_performance", plan_only=True),
        rows,
        file_paths,
    )
    assert processed_rows

    backfill_ctx = build_op_context()
    backfill_summary = generic_backfill_refs_op(
        backfill_ctx,
        GenericBackfillConfig(
            domain="annuity_performance",
            add_tracking_fields=False,
            plan_only=True,
        ),
        processed_rows,
    )
    assert "tables_processed" in backfill_summary
    assert backfill_summary["plan_only"] is True

    gate_ctx = build_op_context()
    gated_rows = gate_after_backfill(gate_ctx, processed_rows, backfill_summary)
    assert gated_rows == processed_rows

    load_ctx = build_op_context()
    load_result = load_op(
        load_ctx,
        LoadConfig(
            table='business."规模明细"',
            mode="delete_insert",
            pk=["月度", "业务类型", "计划类型"],
            plan_only=True,
        ),
        gated_rows,
    )

    assert "sql_plans" in load_result
    op_types = [plan[0] for plan in load_result["sql_plans"]]
    assert "DELETE" in op_types
    assert "INSERT" in op_types


def test_h7_discover_and_read_integration_contract(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "data_sources.yml"

    annuity_base = tmp_path / "data" / "real_data" / "202510" / "collect" / "perf"
    award_base = tmp_path / "data" / "real_data" / "202510" / "collect" / "award"

    v1_file = annuity_base / "V1" / "规模收入数据_v1.xlsx"
    v2_file = annuity_base / "V2" / "规模收入数据_v2.xlsx"
    _write_excel(
        v1_file, {"规模明细": pd.DataFrame([{"月度": "202509", "计划号": "P1"}])}
    )
    _write_excel(
        v2_file, {"规模明细": pd.DataFrame([{"月度": "202510", "计划号": "P2"}])}
    )

    award_file = award_base / "V1" / "台账登记_v1.xlsx"
    _write_excel(
        award_file,
        {
            "企年受托中标(空白)": pd.DataFrame(
                [{"业务类型": "受托", "客户全称": "客户A"}]
            ),
            "企年投资中标(空白)": pd.DataFrame(
                [{"业务类型": "投资", "客户全称": "客户B"}]
            ),
        },
    )

    cfg = {
        "schema_version": "1.2",
        "defaults": {"exclude_patterns": ["~$*"], "version_strategy": "highest_number"},
        "domains": {
            "annuity_performance": {
                "base_path": str(
                    tmp_path / "data" / "real_data" / "{YYYYMM}" / "collect" / "perf"
                ),
                "file_patterns": ["*规模收入数据*.xlsx"],
                "sheet_name": "规模明细",
            },
            "annual_award": {
                "base_path": str(
                    tmp_path / "data" / "real_data" / "{YYYYMM}" / "collect" / "award"
                ),
                "file_patterns": ["*台账登记*.xlsx"],
                "sheet_name": "企年受托中标(空白)",
                "sheet_names": ["企年受托中标(空白)", "企年投资中标(空白)"],
            },
        },
    }
    config_path.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")

    from work_data_hub.orchestration.ops import (
        file_processing as file_processing_module,
    )
    from work_data_hub.io.connectors.discovery import (
        service as discovery_service_module,
    )

    monkeypatch.setattr(
        file_processing_module,
        "get_settings",
        lambda: SimpleNamespace(data_sources_config=str(config_path)),
    )
    monkeypatch.setattr(
        discovery_service_module,
        "get_settings",
        lambda: SimpleNamespace(data_sources_config=str(config_path)),
    )

    discover_ctx = build_op_context()
    annuity_paths = discover_files_op(
        discover_ctx,
        DiscoverFilesConfig(domain="annuity_performance", period="202510"),
    )
    assert len(annuity_paths) == 1
    assert Path(annuity_paths[0]).name == "规模收入数据_v2.xlsx"

    read_ctx = build_op_context()
    annuity_rows = read_data_op(
        read_ctx,
        ReadDataOpConfig(domain="annuity_performance", sheet="规模明细"),
        annuity_paths,
    )
    assert len(annuity_rows) == 1
    assert annuity_rows[0]["计划号"] == "P2"

    award_paths = discover_files_op(
        discover_ctx,
        DiscoverFilesConfig(domain="annual_award", period="202510"),
    )
    award_rows = read_data_op(
        read_ctx,
        ReadDataOpConfig(
            domain="annual_award",
            sheet="企年受托中标(空白)",
            sheet_names=["企年受托中标(空白)", "企年投资中标(空白)"],
        ),
        award_paths,
    )
    assert len(award_rows) == 2
    assert {r["客户全称"] for r in award_rows} == {"客户A", "客户B"}
