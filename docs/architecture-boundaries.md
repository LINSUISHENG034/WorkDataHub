---
title: "Clean Architecture Boundaries (Story 1.6)"
last-updated: 2025-11-13
sources:
  - docs/epics.md#story-16-clean-architecture-boundaries-enforcement
  - docs/tech-spec-epic-1.md#story-16-clean-architecture-boundary-enforcement
  - .bmad-ephemeral/stories/1-5-shared-pipeline-framework-core-simple.md
---

# Clean Architecture Boundaries

Story 1.6 codifies how WorkDataHub enforces the dependency direction
`domain ← io ← orchestration` while keeping medallion-stage ownership clear.
The goals are:

- protect Story 1.5 pipeline contracts from infrastructure coupling,
- ensure every I/O or Dagster concern is injected from the outside, and
- document how contributors verify the rules before landing code.

## Layer responsibilities and allowed dependencies

| Layer | Responsibilities | Allowed Dependencies | Representative modules |
| --- | --- | --- | --- |
| `domain/` | Pure business logic, TransformStep protocols, Pipeline executor, validation utilities. No knowledge of files, databases, or Dagster. | stdlib, `pandas`, `pydantic`, Story 1.5 pipeline modules inside `domain/`. | `src/work_data_hub/domain/pipelines/core.py`, `src/work_data_hub/domain/pipelines/types.py`, `src/work_data_hub/domain/reference_backfill/generic_service.py`. |
| `io/` | Filesystem, Excel readers, warehouse loaders, connectors, adapters that speak to Bronze data. May import `domain/` to reuse types, but never the other way around. | Everything the domain layer can use **plus** infrastructure SDKs (psycopg2, openpyxl, yaml, etc.). | `src/work_data_hub/io/readers/excel_reader.py`, `src/work_data_hub/io/loader/warehouse_loader.py`, `src/work_data_hub/io/connectors/file_connector.py`. |
| `orchestration/` | Dagster jobs/ops/schedules/sensors plus CLI entry points that stitch the system together. Performs dependency injection so domain logic stays pure. | May import domain + I/O modules, Dagster, config/logging helpers. | `src/work_data_hub/orchestration/jobs.py`, `ops.py`, `schedules.py`, `sensors.py`. |

> **Cross-story citation:** The pipeline executor and protocols listed in the
> domain column were implemented in Story 1.5 and live in
> `src/work_data_hub/domain/pipelines/{core,types}.py`. Keep referencing those
> modules instead of recreating infrastructure.

## Medallion alignment

| Medallion stage | Ownership | Notes |
| --- | --- | --- |
| Bronze | I/O layer (`work_data_hub.io`) | Handles discovery, file normalization, and landing zones. Uses Story 1.5 structlog + config helpers (`work_data_hub.utils.logging`, `work_data_hub.config.settings`). |
| Silver | Domain layer (`work_data_hub.domain`) | Hosts transformations, enrichment, cleansing, and pipeline orchestration via the Story 1.5 executor. Receives data through injected adapters. |
| Gold | Split between domain + orchestration | Domain defines projections; orchestration schedules DAGs that hydrate downstream consumers without bypassing domain APIs. |

Mapping the medallion model onto the Clean Architecture rings makes it clear why
domain logic must never open files or database connections directly.

## Dependency injection example

```python
from pathlib import Path

from work_data_hub.domain.annuity_performance.service import process_with_enrichment
from work_data_hub.domain.company_enrichment.service import CompanyEnrichmentService
from work_data_hub.io.readers.excel_reader import ExcelReader
from work_data_hub.io.loader import warehouse_loader


def transform_annuity_data(
    source_path: Path,
    reader: ExcelReader,
    enrichment: CompanyEnrichmentService,
) -> None:
    """
    Example (from the Story 1.6 epic snippet) showing orchestration injecting I/O
    services into the domain layer.
    """

    raw_rows = reader.read_rows(source_path, sheet_name="规模明细")
    result = process_with_enrichment(
        raw_rows,
        data_source=source_path.name,
        enrichment_service=enrichment,
        sync_lookup_budget=25,
    )

    warehouse_loader.load(
        table="gold.annuity_performance",
        rows=[model.model_dump() for model in result.records],
        mode="delete_insert",
        pk=["policy_number", "statement_date"],
    )
```

Key takeaways:

1. Domain logic (`process_with_enrichment`) has no knowledge of readers/loaders.
2. `ExcelReader` and `warehouse_loader.load` stay in the I/O layer and are
   injected by orchestration.
3. Orchestration supplies configuration (file path, table, keys) without making
   the domain depend on Dagster or psycopg2.

## Cross-story references

- **Story 1.5 – Shared pipeline framework**
  - `src/work_data_hub/domain/pipelines/types.py`
  - `src/work_data_hub/domain/pipelines/core.py`
- **Story 1.4 – Configuration singleton**
  - `src/work_data_hub/config/settings.py` (`get_settings`)
- **Story 1.3 – Structlog utilities**
  - `src/work_data_hub/utils/logging.py`

These assets remain the canonical entry points for new stories—cite them in
docs and reuse them in code to avoid duplication.

## Boundary guardrails

Ruff is configured (Story 1.6) with `TID251` banned-import rules so that any
`work_data_hub/domain` module that imports `work_data_hub.io` or
`work_data_hub.orchestration` will fail linting. Run `uv run ruff check`
locally—the CI workflow runs the same command.

## How to extend the document

1. When adding new I/O adapters, provide a short note in this file linking to
   the module plus the Story ID that introduced it.
2. When introducing a new domain pipeline, document the medallion stage it
   serves so future epics can reuse it.
3. Link any new dependency guards, scripts, or CI jobs that protect the clean
   boundaries described above.
