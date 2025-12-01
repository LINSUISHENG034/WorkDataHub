# Project Classification

**Technical Type:** Internal Data Platform / ETL Pipeline System
**Domain:** Enterprise Business Intelligence / Data Engineering
**Complexity:** Medium (Complex data transformations, but not regulated domain)

**Classification Rationale:**

- **Project Type**: This is an internal developer/data engineering tool - a Python-based data pipeline platform similar to modern ETL tools (Airflow, Prefect), but purpose-built for your specific enterprise data domains
- **Domain**: Enterprise Business Intelligence / Data Engineering (annuity performance, business metrics, portfolio analytics) - not high-regulation fintech/healthcare, but business-critical internal data
- **Complexity**: Medium - Multiple data sources with versioning, complex transformations, and critical BI dependencies, but manageable scope with modern frameworks

**Reference Context:**
- **Research Documents:**
  - `docs/deep_research/1.md` - Modern Data Processing Architectures (Gemini Deep Research, 2025-11-08)
  - `docs/deep_research/2.md` - Refactoring Strategy Comparison Matrix
  - `docs/deep_research/3.md` - Strangler Fig Implementation Guide
  - `docs/deep_research/4.md` - Data Contracts with Pandera (DataFrame Validation)
  - `docs/research-deep-prompt-2025-11-08.md` - Research Prompt for AI Platforms
- **Archive Documents:**
  - `docs/archive/prd.md` - Previous Annuity Performance Pipeline Migration PRD
  - `docs/archive/architecture.md` - Brownfield Enhancement Architecture
- **Existing Codebase:** `src/work_data_hub/` - Partially refactored with Dagster + Pydantic + Pipeline framework
- **Legacy System:** `legacy/annuity_hub/` - Original monolithic implementation (to be replaced)

---
