"""Deprecated per-domain ops (Phase 4 cleanup).

These ops are kept for backward compatibility with existing jobs.
New code should use process_domain_op_v2 from generic_ops.py instead.

DEPRECATED: Will be removed after jobs are migrated to generic_ops.
"""

import logging
from typing import Any, Dict, List

from dagster import OpExecutionContext, op

from work_data_hub.config.settings import get_settings
from work_data_hub.domain.annuity_income.service import (
    process_with_enrichment as process_annuity_income_with_enrichment,
)
from work_data_hub.domain.annuity_performance.service import (
    process_with_enrichment,
)
from work_data_hub.domain.sandbox_trustee_performance.service import process
from work_data_hub.io.loader.warehouse_loader import DataWarehouseLoaderError

from ._internal import _PSYCOPG2_NOT_LOADED, psycopg2
from .pipeline_ops import ProcessingConfig

logger = logging.getLogger(__name__)


@op
def process_sandbox_trustee_performance_op(
    context: OpExecutionContext, excel_rows: List[Dict[str, Any]], file_paths: List[str]
) -> List[Dict[str, Any]]:
    """DEPRECATED: Use process_domain_op_v2 with domain='sandbox_trustee_performance'."""  # noqa: E501
    file_path = file_paths[0] if file_paths else "unknown"
    try:
        processed_models = process(excel_rows, data_source=file_path)
        result_dicts = [
            model.model_dump(mode="json", by_alias=True, exclude_none=True)
            for model in processed_models
        ]
        context.log.info(
            "Domain processing completed - source: %s, input_rows: %s, "
            "output_records: %s, domain: sandbox_trustee_performance",
            file_path,
            len(excel_rows),
            len(result_dicts),
        )
        return result_dicts
    except Exception as e:
        context.log.error(f"Domain processing failed: {e}")
        raise


@op
def process_annuity_income_op(
    context: OpExecutionContext,
    config: ProcessingConfig,
    excel_rows: List[Dict[str, Any]],
    file_paths: List[str],
) -> List[Dict[str, Any]]:
    """DEPRECATED: Use process_domain_op_v2 with domain='annuity_income'."""
    file_path = file_paths[0] if file_paths else "unknown"
    try:
        processing_result = process_annuity_income_with_enrichment(
            excel_rows, data_source=file_path, session_id=config.session_id
        )
        result_dicts = [
            model.model_dump(mode="json", by_alias=True, exclude_none=True)
            for model in processing_result.records
        ]
        mode_text = "EXECUTED" if not config.plan_only else "PLAN-ONLY"
        context.log.info(
            "Domain processing completed (%s) - source: %s, input_rows: %s, "
            "output_records: %s, domain: annuity_income",
            mode_text,
            file_path,
            len(excel_rows),
            len(result_dicts),
        )
        return result_dicts
    except Exception as e:
        context.log.error(f"Domain processing failed: {e}")
        raise


@op
def process_annual_award_op(
    context: OpExecutionContext,
    config: ProcessingConfig,
    excel_rows: List[Dict[str, Any]],
    file_paths: List[str],
) -> List[Dict[str, Any]]:
    """DEPRECATED: Use process_domain_op_v2 with domain='annual_award'."""
    from datetime import datetime, timezone

    import pandas as pd

    from work_data_hub.domain.annual_award.helpers import convert_dataframe_to_models
    from work_data_hub.domain.annual_award.pipeline_builder import (
        build_bronze_to_silver_pipeline,
    )
    from work_data_hub.domain.pipelines.types import PipelineContext
    from work_data_hub.infrastructure.enrichment import EqcLookupConfig
    from work_data_hub.infrastructure.enrichment.mapping_repository import (
        CompanyMappingRepository,
    )

    file_path = file_paths[0] if file_paths else "unknown"
    mapping_repository = None
    repo_connection = None

    try:
        from sqlalchemy import create_engine

        settings = get_settings()
        engine = create_engine(settings.get_database_connection_string())
        repo_connection = engine.connect()
        mapping_repository = CompanyMappingRepository(repo_connection)
    except Exception as e:
        context.log.warning("Failed to initialize CompanyMappingRepository: %s", str(e))

    try:
        df = pd.DataFrame(excel_rows)
        if config.eqc_lookup_config is not None:
            eqc_config = EqcLookupConfig.from_dict(config.eqc_lookup_config)
        else:
            eqc_config = EqcLookupConfig(
                enabled=config.enrichment_enabled,
                sync_budget=max(config.enrichment_sync_budget, 0),
                auto_create_provider=config.enrichment_enabled,
                export_unknown_names=config.export_unknown_names,
                auto_refresh_token=True,
            )
        pipeline = build_bronze_to_silver_pipeline(
            eqc_config=eqc_config,
            mapping_repository=mapping_repository,
            db_connection=repo_connection,
        )
        pipeline_context = PipelineContext(
            pipeline_name="bronze_to_silver",
            execution_id=f"annual_award-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            timestamp=datetime.now(timezone.utc),
            config={"domain": "annual_award"},
            domain="annual_award",
            run_id=f"annual_award-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            extra={"data_source": file_path},
        )
        result_df = pipeline.execute(df, pipeline_context)
        records, failed_count = convert_dataframe_to_models(result_df)
        result_dicts = [
            model.model_dump(mode="json", by_alias=True, exclude_none=True)
            for model in records
        ]
        mode_text = "EXECUTED" if not config.plan_only else "PLAN-ONLY"
        context.log.info(
            "Domain processing completed (%s) - source: %s, input_rows: %s, "
            "output_records: %s, failed: %s, domain: annual_award",
            mode_text,
            file_path,
            len(excel_rows),
            len(result_dicts),
            failed_count,
        )
        return result_dicts
    except Exception as e:
        context.log.error(f"Domain processing failed: {e}")
        raise
    finally:
        if repo_connection is not None:
            try:
                repo_connection.commit()
            except Exception:
                repo_connection.rollback()
            repo_connection.close()


@op
def process_annuity_performance_op(
    context: OpExecutionContext,
    config: ProcessingConfig,
    excel_rows: List[Dict[str, Any]],
    file_paths: List[str],
) -> List[Dict[str, Any]]:
    """DEPRECATED: Use process_domain_op_v2 with domain='annuity_performance'."""
    global psycopg2
    file_path = file_paths[0] if file_paths else "unknown"
    enrichment_service = None
    observer = None
    conn = None
    settings = get_settings()

    try:
        use_enrichment = (
            (not config.plan_only)
            and config.enrichment_enabled
            and settings.enrich_enabled
        )

        if use_enrichment:
            from work_data_hub.domain.company_enrichment.lookup_queue import LookupQueue
            from work_data_hub.domain.company_enrichment.observability import (
                EnrichmentObserver,
            )
            from work_data_hub.domain.company_enrichment.service import (
                CompanyEnrichmentService,
            )
            from work_data_hub.io.connectors.eqc_client import EQCClient
            from work_data_hub.io.loader.company_enrichment_loader import (
                CompanyEnrichmentLoader,
            )

            if psycopg2 is _PSYCOPG2_NOT_LOADED:
                try:
                    import psycopg2 as _psycopg2

                    psycopg2 = _psycopg2
                except ImportError:
                    raise DataWarehouseLoaderError("psycopg2 not available")

            dsn = settings.get_database_connection_string()
            conn = psycopg2.connect(dsn)
            loader = CompanyEnrichmentLoader(conn)
            queue = LookupQueue(conn)
            eqc_client = EQCClient()
            observer = EnrichmentObserver()
            enrichment_service = CompanyEnrichmentService(
                loader=loader,
                queue=queue,
                eqc_client=eqc_client,
                sync_lookup_budget=config.enrichment_sync_budget,
                observer=observer,
                enrich_enabled=settings.enrich_enabled,
            )

        processing_result = process_with_enrichment(
            excel_rows,
            data_source=file_path,
            session_id=config.session_id,
            enrichment_service=enrichment_service,
        )
        result_dicts = [
            model.model_dump(mode="json", by_alias=True, exclude_none=True)
            for model in processing_result.records
        ]
        mode_text = "EXECUTED" if not config.plan_only else "PLAN-ONLY"
        context.log.info(
            "Domain processing completed (%s) - source: %s, input_rows: %s, "
            "output_records: %s, domain: annuity_performance",
            mode_text,
            file_path,
            len(excel_rows),
            len(result_dicts),
        )
        return result_dicts
    except Exception as e:
        context.log.error(f"Domain processing failed: {e}")
        raise
    finally:
        if conn is not None:
            try:
                conn.commit()
            except Exception:
                conn.rollback()
            conn.close()
