"""
Integration-style unit test for CompanyIdResolver using EqcProvider.

Ensures Resolver can drive EqcProvider path (without legacy enrichment_service),
consume budget, emit resolved company_id, and trigger EQC cache write to
company_name_index via mapping repository.
"""

from types import SimpleNamespace
from typing import Any, Dict, List

import pandas as pd
from pytest import fixture
from unittest.mock import patch

from work_data_hub.infrastructure.enrichment import (
    CompanyIdResolver,
    EqcLookupConfig,
    EqcProvider,
    ResolutionStrategy,
)
from work_data_hub.infrastructure.enrichment.mapping_repository import (
    EnqueueResult,
    InsertBatchResult,
)


class InMemoryMappingRepo:
    """Minimal stub for mapping repository used in integration test."""

    def __init__(self) -> None:
        self.name_index_payloads: List[List[Dict[str, Any]]] = []
        self.backflow_payloads: List[List[Dict[str, Any]]] = []
        self.async_enqueue_payloads: List[List[Dict[str, str]]] = []
        self.enrichment_index_payloads: List[List[Any]] = []

    def lookup_batch(self, alias_names, match_types=None):  # noqa: ANN001
        return {}

    def lookup_enrichment_index_batch(self, keys_by_type):  # noqa: ANN001
        return {}

    def update_hit_count(self, lookup_key, lookup_type):  # noqa: ANN001
        return False

    def insert_company_name_index_batch(
        self, rows: List[Dict[str, Any]]
    ) -> InsertBatchResult:
        self.name_index_payloads.append(rows)
        return InsertBatchResult(
            inserted_count=len(rows), skipped_count=0, conflicts=[]
        )

    def insert_enrichment_index_batch(self, records: List[Any]) -> InsertBatchResult:
        self.enrichment_index_payloads.append(records)
        return InsertBatchResult(
            inserted_count=len(records), skipped_count=0, conflicts=[]
        )

    def insert_batch_with_conflict_check(
        self, mappings: List[Dict[str, Any]]
    ) -> InsertBatchResult:
        self.backflow_payloads.append(mappings)
        return InsertBatchResult(
            inserted_count=len(mappings), skipped_count=0, conflicts=[]
        )

    def enqueue_for_enrichment(self, requests: List[Dict[str, str]]) -> EnqueueResult:
        self.async_enqueue_payloads.append(requests)
        return EnqueueResult(queued_count=len(requests), skipped_count=0)


@fixture
def eqc_provider_with_client() -> EqcProvider:
    """Create EqcProvider with mocked settings and in-memory repo."""
    repo = InMemoryMappingRepo()
    with patch(
        "work_data_hub.infrastructure.enrichment.eqc_provider.get_settings"
    ) as mock_settings:
        mock_settings.return_value.eqc_token = ""
        mock_settings.return_value.eqc_base_url = "https://eqc.test.com"
        mock_settings.return_value.company_sync_lookup_limit = 2
        mock_settings.return_value.eqc_rate_limit = 10

        provider = EqcProvider(
            token="test_token_12345678901234567890",
            budget=2,
            base_url="https://eqc.test.com",
            mapping_repository=repo,
        )

    # Replace EQC client with simple stub
    # Note: search_company_with_raw returns (results, raw_json) tuple
    provider.client = SimpleNamespace(
        search_company_with_raw=lambda name: (
            [
                SimpleNamespace(
                    company_id="C123",
                    official_name=f"{name}_official",
                    match_score=0.9,
                    unite_code=None,
                )
            ],
            {"list": [{"companyId": "C123"}]},  # raw_json
        )
    )
    return provider


def test_resolver_uses_eqc_provider_and_caches(
    eqc_provider_with_client: EqcProvider,
) -> None:
    """Resolver should call EqcProvider when provided, set output, and write cache."""
    repo = eqc_provider_with_client.mapping_repository  # type: ignore[assignment]
    assert isinstance(repo, InMemoryMappingRepo)

    resolver = CompanyIdResolver(
        eqc_config=EqcLookupConfig(
            enabled=True, sync_budget=1, auto_create_provider=False
        ),
        yaml_overrides={
            "plan": {},
            "account": {},
            "hardcode": {},
            "name": {},
            "account_name": {},
        },
        mapping_repository=repo,
        eqc_provider=eqc_provider_with_client,
    )

    df = pd.DataFrame({"客户名称": ["测试公司"]})
    strategy = ResolutionStrategy(
        use_enrichment_service=True,
        sync_lookup_budget=0,  # Legacy field (ignored by resolver)
        generate_temp_ids=False,
        enable_async_queue=False,
    )

    result = resolver.resolve_batch(df, strategy)

    # CompanyId should come from EQC
    assert result.data.loc[0, strategy.output_column] == "C123"
    # EQC hits recorded, budget decremented
    assert result.statistics.eqc_sync_hits == 1
    assert result.statistics.budget_remaining == 0
    # Cache write to enrichment_index was attempted
    assert repo.enrichment_index_payloads
    payload = repo.enrichment_index_payloads[0][0]
    assert payload.company_id == "C123"
    assert payload.source.value == "eqc_api"


def test_resolver_backflow_existing_column(monkeypatch) -> None:
    """Resolver should backflow mappings from existing company_id column."""
    repo = InMemoryMappingRepo()

    # Normalize customer name to a fixed value for deterministic backflow
    monkeypatch.setattr(
        "work_data_hub.infrastructure.enrichment.company_id_resolver.normalize_company_name",
        lambda v: "normalized_name",
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
        mapping_repository=repo,
        eqc_provider=None,
    )

    df = pd.DataFrame(
        {
            "计划代码": ["P1"],
            "客户名称": ["客户A"],
            "年金账户号": ["ACC1"],
            "年金账户名": ["账户A"],
            "公司代码": ["CID123"],
        }
    )
    strategy = ResolutionStrategy(
        use_enrichment_service=False,
        sync_lookup_budget=0,  # Legacy field (ignored by resolver)
        generate_temp_ids=False,
        enable_async_queue=False,
    )

    result = resolver.resolve_batch(df, strategy)

    assert result.statistics.existing_column_hits == 1
    assert repo.backflow_payloads, "Backflow payloads should be recorded"
    backflow = repo.backflow_payloads[0]
    # Should contain three entries: account (raw), name (normalized), account_name (raw)
    assert len(backflow) == 3
    # Check normalized entry
    normalized_entry = [m for m in backflow if m["match_type"] == "name"][0]
    assert normalized_entry["alias_name"] == "normalized_name"
    assert normalized_entry["canonical_id"] == "CID123"


def test_resolver_async_enqueue_temp_ids(monkeypatch) -> None:
    """Resolver should enqueue unresolved names after temp ID generation."""
    repo = InMemoryMappingRepo()

    # Ensure deterministic normalization
    monkeypatch.setattr(
        "work_data_hub.infrastructure.enrichment.company_id_resolver.normalize_for_temp_id",
        lambda v: "normalized_for_temp",
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
        mapping_repository=repo,
        eqc_provider=None,
    )

    df = pd.DataFrame({"客户名称": ["未解析公司"]})
    strategy = ResolutionStrategy(
        use_enrichment_service=False,
        sync_lookup_budget=0,
        generate_temp_ids=True,
        enable_async_queue=True,
    )

    result = resolver.resolve_batch(df, strategy)

    # Temp ID should be generated
    assert result.statistics.temp_ids_generated == 1
    # Async enqueue should have been called
    assert repo.async_enqueue_payloads
    enqueue_payload = repo.async_enqueue_payloads[0][0]
    assert enqueue_payload["normalized_name"] == "normalized_for_temp"


def test_no_enrichment_does_not_create_eqc_provider() -> None:
    """Story 6.2-P17 AC-5: --no-enrichment should result in zero EQC provider init."""
    repo = InMemoryMappingRepo()
    with patch(
        "work_data_hub.infrastructure.enrichment.eqc_provider.EqcProvider"
    ) as mock_provider:
        resolver = CompanyIdResolver(
            eqc_config=EqcLookupConfig.disabled(),
            yaml_overrides={
                "plan": {},
                "account": {},
                "hardcode": {},
                "name": {},
                "account_name": {},
            },
            mapping_repository=repo,
            eqc_provider=None,
        )

        assert resolver.eqc_provider is None
        mock_provider.assert_not_called()
