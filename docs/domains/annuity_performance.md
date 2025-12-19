# Annuity Performance

## Overview

This domain processes monthly annuity performance Excel data and loads the curated output to the warehouse.

## Input Format

- Source: Excel files discovered under the configured `base_path` for a given `{YYYYMM}`
- Primary sheet: `规模明细`

## Transformation

- Reads the discovered sheet into a dataframe
- Applies cleansing/normalization + enrichment (company_id resolution)
- Drops invalid rows and exports error artifacts when enabled

## Output Schema

- Target schema: `business`
- Target tables:
  - Validation mode: `annuity_performance_NEW`
  - Production mode: `annuity_performance`

## Configuration

- Source config: `config/data_sources.yml` → `domains.annuity_performance`
- Typical sheet: `规模明细`
- Output table (validation mode): `annuity_performance_NEW`
- Output table (production mode): `annuity_performance`

## Entry Points

- Service: `work_data_hub.domain.annuity_performance.service.process_annuity_performance`
- Orchestration: `work_data_hub.orchestration.ops.process_annuity_performance_op`
