# File Length Violations Audit

**Date:** 2025-12-21
**Scope:** All Python files in `src/` directory
**Constraint:** No file should exceed 500 lines (Hard Constraint from project-context.md)

## Executive Summary

Found **21 Python files** exceeding the 500-line limit, with **1 file exceeding 800 lines** (marked as Critical). The largest violation is `ops.py` at 2165 lines, which is more than 4 times the allowed limit.

## Violations Table

| File Path | Line Count | Primary Responsibility | Refactoring Priority |
|-----------|------------|-----------------------|----------------------|
| src/work_data_hub/orchestration/ops.py | 2165 | Dagster ops for dependency injection into domain services | **Critical** |
| src/work_data_hub/io/loader/warehouse_loader.py | 1404 | Warehouse data loading with database connectivity | High |
| src/work_data_hub/infrastructure/enrichment/company_id_resolver.py | 1342 | Company ID resolution with hierarchical strategies | High |
| src/work_data_hub/cli/etl.py | 1197 | ETL CLI for multi-domain batch processing | High |
| src/work_data_hub/io/connectors/eqc_client.py | 1163 | HTTP client for EQC API company data enrichment | High |
| src/work_data_hub/infrastructure/enrichment/mapping_repository.py | 1068 | Database operations for company_mapping table | High |
| src/work_data_hub/io/connectors/file_connector.py | 1051 | File discovery connector with version resolution | High |
| src/work_data_hub/domain/company_enrichment/service.py | 844 | Business logic for company ID resolution | High |
| src/work_data_hub/infrastructure/enrichment/domain_learning_service.py | 819 | Automatic company ID mapping extraction | High |
| src/work_data_hub/orchestration/jobs.py | 752 | Dagster jobs wiring I/O services into pipelines | High |
| src/work_data_hub/domain/company_enrichment/lookup_queue.py | 733 | Asynchronous EQC lookup queue operations | High |
| src/work_data_hub/domain/reference_backfill/generic_service.py | 682 | Configuration-driven reference data backfill | High |
| src/work_data_hub/infrastructure/enrichment/data_refresh_service.py | 676 | EQC data freshness maintenance service | High |
| src/work_data_hub/domain/reference_backfill/observability.py | 676 | Reference data quality monitoring | High |
| src/work_data_hub/domain/reference_backfill/sync_service.py | 671 | Pre-loading authoritative reference data | High |
| src/work_data_hub/domain/pipelines/core.py | 648 | Core pipeline execution framework | High |
| src/work_data_hub/domain/company_enrichment/models.py | 647 | Pydantic models for company enrichment | High |
| src/work_data_hub/cli/eqc_refresh.py | 602 | CLI for EQC data refresh operations | High |
| src/work_data_hub/io/loader/company_mapping_loader.py | 587 | Company mapping data migration loader | High |
| src/work_data_hub/config/settings.py | 580 | Environment-based configuration management | High |
| src/work_data_hub/io/auth/auto_eqc_auth.py | 553 | Automated QR code login for EQC | High |
| src/work_data_hub/domain/reference_backfill/hybrid_service.py | 544 | Combined pre-load and backfill strategies | High |
| src/work_data_hub/infrastructure/enrichment/eqc_provider.py | 531 | Synchronous EQC API provider | High |
| src/work_data_hub/io/loader/company_enrichment_loader.py | 527 | EQC result caching loader | High |
| src/work_data_hub/io/readers/excel_reader.py | 511 | Excel data reading utilities | High |

## Detailed Analysis

### Critical Violation (>800 lines)

#### src/work_data_hub/orchestration/ops.py - 2165 lines
This file is the most severe violation, exceeding the limit by 1665 lines (332% over).

### High Violations (500-800 lines)

The following files range from 511-844 lines, exceeding the limit by 11-344 lines:
- 3 files in orchestration layer
- 5 files in infrastructure/enrichment
- 4 files in io/connectors and loaders
- 3 files in domain services
- 2 files in domain/reference_backfill
- 1 file in config
- 1 file in cli
- 1 file in io/auth

## Refactoring Strategy for Critical File

### src/work_data_hub/orchestration/ops.py (2165 lines)

**Current Issue**: Contains multiple Dagster operations mixing different domain concerns.

**Proposed Split Strategy**:

1. **Extract to Domain-Specific Op Modules**:
   - `src/work_data_hub/orchestration/ops/company_enrichment.py` - Move all company enrichment related ops (~600 lines)
   - `src/work_data_hub/orchestration/ops/reference_backfill.py` - Move all reference backfill ops (~500 lines)
   - `src/work_data_hub/orchestration/ops/file_processing.py` - Move file reading/writing ops (~400 lines)
   - `src/work_data_hub/orchestration/ops/pipeline_ops.py` - Keep core pipeline execution ops (~300 lines)

2. **Create Shared Utilities**:
   - `src/work_data_hub/orchestration/utils/op_helpers.py` - Common op utilities and decorators (~200 lines)
   - `src/work_data_hub/orchestration/utils/io_factory.py` - I/O factory patterns used across ops (~150 lines)

3. **Expected Result**:
   - Main `ops.py` reduced to < 300 lines
   - Each domain module < 400 lines
   - Better separation of concerns
   - Improved testability and maintainability

## Recommendations

1. **Immediate Action Required**: Address the critical violation in `ops.py` as it impedes code maintainability.

2. **High-Priority Refactoring**: The following files should be refactored soon as they significantly exceed the limit:
   - `warehouse_loader.py` (1404 lines)
   - `company_id_resolver.py` (1342 lines)
   - `etl.py` (1197 lines)
   - `eqc_client.py` (1163 lines)
   - `mapping_repository.py` (1068 lines)
   - `file_connector.py` (1051 lines)

3. **Systematic Approach**: Implement a policy where new files exceeding 300 lines trigger an automatic review for potential refactoring.

4. **Code Review Integration**: Add a pre-commit hook that checks file length and fails the commit if files exceed 500 lines.

## Next Steps

1. Create stories for refactoring each critical and high-priority file
2. Implement file length checks in CI/CD pipeline
3. Establish regular code health reviews to prevent future violations
4. Consider adopting tools like `wily` for tracking code complexity over time