# Cleansing Architecture & Enrichment Integration Plan

## 1. Shared Cleansing Pipeline Foundation (F-018, C-065)

- Deliver TransformStep interface, pipeline builder, config loader, reusable error/reporting hooks.
- Document canonical step categories (date, numeric, mapping, enrichment-input prep) referencing existing src/work_data_hub/cleansing/ rules.
- Provide sample pipeline configuration for quick adoption and extensibility guidelines for new domains.

## 2. Centralized Mapping/Default Rules (C-014)

- Consolidate cross-domain mapping sources and default fallback logic into a MappingService consumed by TransformSteps.
- Keep company_id matching under Company Enrichment; expose plan/portfolio/product defaults via the shared service.
- Supply migration notes for legacy mappings and extend registry tests accordingly.

## 3. Annuity Performance Pipeline Refactor (F-065)

- Rebuild annuity_performance service using the shared pipeline, MappingService, and enrichment adapter.
- Implement parity testing (golden dataset) and ensure CSV/log outputs remain compatible.
- Capture metrics such as processed rows, step timing, enrichment stats.

## 4. Golden Dataset Regression Suite (C-066)

- Curate representative legacy samples and persist
 legacy outputs as golden files.
- Build a regression harness comparing pipeline output versus legacy cleaner results with numeric tolerances.
- Automate execution in CI and document the workflow for refreshing golden data.

## 5. Company Enrichment Integration Baseline

- Define the canonical adapter contract (
esolve_company_id inputs/outputs, status metadata) for TransformSteps.
- Provide shared mocks/fixtures for enrichment tests; document temp-ID bootstrapping and queue behavior.
- Align logging/metrics (EnrichmentStats) with docs/company_id expectations.

## 6. Domain Invocation Guidelines

- Document how orchestration ops call the standard pipeline: discover → read → pipeline.execute() → enrichment → load.
- Outline configuration knobs (sheet selection, step toggles, enrichment budget) and reference .env/settings overrides.
- Update README/ROADMAP references once the new workflow is in place.
