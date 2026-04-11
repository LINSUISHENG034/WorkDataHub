# Database Schema Panorama

> Source of truth: `src/work_data_hub/infrastructure/schema/definitions/`, `src/work_data_hub/customer_mdm/`, `config/customer_status_rules.yml`, `src/work_data_hub/infrastructure/enrichment/`, `src/work_data_hub/io/loader/company_enrichment_loader.py`
> Last verified: `2026-04-11`
> Scope: Current code-verified schema overview

## 1. Scope

This document is a code-verified overview of the active schemas and key tables referenced by the repository today. It is intentionally narrower than a full production inventory and avoids unverifiable row counts or environment-specific table totals.

## 2. Key Active Schemas

| Schema | Purpose | Representative active tables / objects |
|--------|---------|----------------------------------------|
| `business` | ETL fact-domain outputs | `规模明细`, `收入明细` |
| `customer` | customer lifecycle and snapshot outputs | `客户年金计划`, `中标客户明细`, `流失客户明细`, `客户业务月度快照`, `客户计划月度快照` |
| `mapping` | reference/master data | `年金计划`, `组合计划`, `产品线`, `客户明细` |
| `enterprise` | enrichment, EQC persistence, lookup cache | `enrichment_index`, `base_info`, `business_info`, `biz_label`, `enrichment_requests` |
| `sandbox` | non-production validation targets | `sandbox_trustee_performance` |

## 3. Domain-Managed Tables From Schema Definitions

The domain schema registry under `src/work_data_hub/infrastructure/schema/definitions/` currently defines these domain tables:

| Domain schema | Schema | Table | Notes |
|---------------|--------|-------|-------|
| `annuity_performance` | `business` | `规模明细` | managed by ETL domain schema definition |
| `annuity_income` | `business` | `收入明细` | managed by ETL domain schema definition |
| `annuity_plans` | `mapping` | `年金计划` | mapping/reference schema definition |
| `portfolio_plans` | `mapping` | `组合计划` | mapping/reference schema definition |

These definitions are the authoritative source for composite keys, delete scopes, and generated DDL in the schema registry layer.

## 4. Customer MDM Tables

Current `customer_mdm` code references and maintains:

- `customer."客户年金计划"` as the contract-status and annual-status base table
- `customer."客户业务月度快照"` as the ProductLine-level snapshot output
- `customer."客户计划月度快照"` as the Plan-level snapshot output
- `customer."中标客户明细"` and `customer."流失客户明细"` as status-evaluation sources

Code paths:

- `src/work_data_hub/customer_mdm/contract_sync.py`
- `src/work_data_hub/customer_mdm/snapshot_refresh.py`
- `src/work_data_hub/customer_mdm/year_init.py`
- `config/customer_status_rules.yml`

## 5. Enrichment Tables

Current enrichment code uses:

- `enterprise.enrichment_index` as the main lookup cache
- `enterprise.base_info` as the primary EQC persistence table
- `enterprise.business_info` for normalized business detail persistence
- `enterprise.biz_label` for flattened EQC label persistence
- `enterprise.enrichment_requests` for queued enrichment work

Important current-state note:

- `enterprise.company_mapping` is no longer the active cache path in code
- new cache writes and lookups are implemented against `enterprise.enrichment_index`

## 6. Status-Evaluation Sources

`config/customer_status_rules.yml` currently defines:

- `business."规模明细"` as the annuity performance source
- `customer."中标客户明细"` as the winning-status source
- `customer."流失客户明细"` as the loss-status source

Those rules feed SQL generation in `work_data_hub.customer_mdm.status_evaluator`.

## 7. Operator Reference Commands

```bash
uv run --env-file .wdh_env python -m work_data_hub.cli etl --check-db
uv run --env-file .wdh_env alembic upgrade head
```

## 8. Non-Goals Of This Document

This document does not attempt to be:

- a production row-count report
- a live database introspection dump
- a complete history of deprecated tables

Historical schema discussions belong under `docs/archive/`.
