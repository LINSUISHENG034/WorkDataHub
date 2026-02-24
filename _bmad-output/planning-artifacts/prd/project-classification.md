# Project Classification

**Technical Type:** Internal Data Platform / ETL Pipeline System
**Domain:** Enterprise Business Intelligence / Data Engineering
**Complexity:** Medium (Complex data transformations, but not regulated domain)

**Classification Rationale:**

- **Project Type**: This is an internal developer/data engineering tool - a Python-based data pipeline platform similar to modern ETL tools (Airflow, Prefect), but purpose-built for your specific enterprise data domains. Includes Customer MDM capabilities and desktop GUI tools for operational use.
- **Domain**: Enterprise Business Intelligence / Data Engineering (annuity performance, annuity income, annual awards/losses, customer MDM, company enrichment) - not high-regulation fintech/healthcare, but business-critical internal data
- **Complexity**: Medium-High - Multiple data sources with versioning, complex transformations, EQC API integration with browser automation (Playwright + CAPTCHA solving), Customer MDM lifecycle management, and critical BI dependencies

**Reference Context:**
- **Research Documents:**
  - `docs/initial/research-deep-prompt*.md` - Original Research Prompt for AI Platforms
- **Architecture Documentation:**
  - `docs/architecture-patterns/` - Pipeline integration guide, tiered retry, error message quality
  - `docs/guides/infrastructure/` - Company enrichment, DB connection, EQC token, schemas deep-dive, transforms
  - `docs/guides/domain-migration/` - Code mapping, development guide, workflow, troubleshooting
- **Business Context:**
  - `docs/business-background/` - Annuity plan types, customer MDM analysis, 战客身份定义
- **Planning Artifacts:**
  - `_bmad-output/planning-artifacts/architecture/` - Full architecture documentation (12 files)
  - `_bmad-output/planning-artifacts/epics/` - Epic 1-6 + Epic 5.5
- **Existing Codebase:** `src/work_data_hub/` - 8 business domains, infrastructure layer, CLI, GUI, orchestration
- **Legacy System:** `legacy/annuity_hub/` - Original monolithic implementation (quarantined, linting/typing disabled)

---
