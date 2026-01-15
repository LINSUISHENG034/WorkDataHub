"""Annual Loss Domain Service Adapter.

实现 DomainServiceProtocol，使用 pipeline_builder 处理数据。
注意: annual_loss 使用 Pipeline 架构，与其他 domain 的简单 process() 接口不同。
"""

import time
from datetime import datetime, timezone
from typing import Any, Dict, List

import pandas as pd

from work_data_hub.domain.protocols import (
    DomainProcessingResult,
    ProcessingContext,
)


class AnnualLossService:
    """Annual Loss 领域服务适配器.

    注意: 此 domain 使用 Pipeline 架构处理数据，需要特殊适配。
    """

    @property
    def domain_name(self) -> str:
        return "annual_loss"

    @property
    def requires_enrichment(self) -> bool:
        return True

    @property
    def requires_backfill(self) -> bool:
        return False

    def process(
        self,
        rows: List[Dict[str, Any]],
        context: ProcessingContext,
    ) -> DomainProcessingResult:
        """委托给 pipeline_builder 处理.

        Annual Loss domain 使用 Pipeline 架构，需要：
        1. 将 rows 转换为 DataFrame
        2. 使用 build_bronze_to_silver_pipeline 创建流水线
        3. 执行流水线并转换结果
        """
        from work_data_hub.domain.annual_loss.helpers import (
            convert_dataframe_to_models,
        )
        from work_data_hub.domain.annual_loss.pipeline_builder import (
            build_bronze_to_silver_pipeline,
        )
        from work_data_hub.domain.pipelines.types import PipelineContext
        from work_data_hub.infrastructure.enrichment import EqcLookupConfig
        from work_data_hub.infrastructure.enrichment.mapping_repository import (
            CompanyMappingRepository,
        )

        start = time.perf_counter()

        # Create mapping repository if enrichment is enabled
        mapping_repository = None
        repo_connection = None

        if context.enrichment_service is not None:
            try:
                from sqlalchemy import create_engine

                from work_data_hub.config.settings import get_settings

                settings = get_settings()
                engine = create_engine(settings.get_database_connection_string())
                repo_connection = engine.connect()
                mapping_repository = CompanyMappingRepository(repo_connection)
            except Exception:
                # Continue without mapping repository
                pass

        try:
            # Convert rows to DataFrame
            df = pd.DataFrame(rows)

            # Build EQC config from context
            eqc_config = (
                context.eqc_config if context.eqc_config else EqcLookupConfig.disabled()
            )

            # Build and execute pipeline
            pipeline = build_bronze_to_silver_pipeline(
                eqc_config=eqc_config,
                mapping_repository=mapping_repository,
                db_connection=repo_connection,
            )

            pipeline_context = PipelineContext(
                pipeline_name="bronze_to_silver",
                execution_id=f"annual_loss-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
                timestamp=datetime.now(timezone.utc),
                config={"domain": "annual_loss"},
                domain="annual_loss",
                run_id=f"annual_loss-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
                extra={"data_source": context.data_source},
            )

            result_df = pipeline.execute(df, pipeline_context)

            # Convert to models
            records, failed_count = convert_dataframe_to_models(result_df)

            elapsed_ms = (time.perf_counter() - start) * 1000

            return DomainProcessingResult(
                records=records,
                total_input=len(rows),
                total_output=len(records),
                failed_count=failed_count,
                processing_time_ms=elapsed_ms,
            )

        finally:
            if repo_connection is not None:
                try:
                    repo_connection.commit()
                except Exception:
                    repo_connection.rollback()
                repo_connection.close()
