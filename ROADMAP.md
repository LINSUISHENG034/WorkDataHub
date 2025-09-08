# **Project: WorkDataHub**

## **Vision**

Build a reliable, declarative, and testable data processing platform that replaces the legacy monolithic ETL with isolated domain services, configuration-driven discovery, and orchestrated end-to-end pipelines. The platform prioritizes correctness, observability, and safety with CI gates, environment-based configuration, and vertically sliced, independently verifiable deliveries.

## **Milestone 0: Security & Quality Baseline**

| ID | Epic | Feature/Task | Status | Dependencies | PRP_Link |
| :---- | :---- | :---- | :---- | :---- | :---- |
| R-001 | M0 | Research and document secrets policy (env vars, .env.example, scanning) | COMPLETED | - | P-006 |
| C-001 | M0 | Add `.env.example` with `WDH_*` vars and docs on secrets handling | COMPLETED | R-001 | P-006 |
| C-002 | M0 | Set up GitHub Actions CI (ruff, mypy, pytest) | COMPLETED | - | P-006 |
| C-003 | M0 | Add optional secret scanning (e.g., pre-commit/gitleaks) | COMPLETED | R-001 | P-006 |
| F-001 | M0 | Establish end-to-end test baseline (plan-only path) | COMPLETED | - | P-001 |
| C-004 | M0 | Optional local dev via docker-compose (PostgreSQL + Dagster) | READY_FOR_PRP | C-002 | - |

<!--
PHILOSOPHY: Front-load uncertainty (R-001), then implement atomic chores/features with explicit dependencies. CI and secret policy enable fast, safe iteration for later milestones.
-->

## **Milestone 1: First Vertical Slice — Trustee Performance (E2E)**

| ID | Epic | Feature/Task | Status | Dependencies | PRP_Link |
| :---- | :---- | :---- | :---- | :---- | :---- |
| R-010 | M1 | Define JSON-serializable contracts and job shape for Dagster | COMPLETED | - | P-003 |
| F-010 | M1 | Implement `DataSourceConnector` (config-driven discovery) | COMPLETED | - | P-001 |
| F-011 | M1 | Implement robust `ExcelReader` with error handling | COMPLETED | - | P-001 |
| F-012 | M1 | Implement `trustee_performance` Pydantic models + service | COMPLETED | - | P-001 |
| F-013 | M1 | Implement transactional `DataWarehouseLoader` (plan-only + execute) | COMPLETED | - | P-002 |
| F-014 | M1 | Implement Dagster ops (discover/read/process/load) with dynamic domain validation | COMPLETED | F-010, F-011, F-012, F-013 | P-004 |
| F-015 | M1 | Implement Dagster jobs + CLI (`--execute`, multi-file accumulation) | COMPLETED | F-014 | P-003, P-005 |
| C-010 | M1 | Provide domain config (`data_sources.yml`) with table + pk | COMPLETED | - | P-003 |
| C-016 | M1 | Fix Pydantic v2 ValidationError misuse in trustee_performance.service | COMPLETED | F-012 | P-007 |
| C-011 | M1 | Validate local Dagster "hello-world" pipeline + runbook | READY_FOR_PRP | F-014, F-015 | - |
| C-012 | M1 | Convert legacy handler mappings (DB) to YAML config seeds | COMPLETED | F-010 | P-008 |

<!--
TASK BREAKDOWN PHILOSOPHY:
- Vertical slice: end-to-end from discovery → read → transform → load.
- Contextual isolation: each component has a single, testable responsibility.
- Dependencies: ops/jobs rely on connector, reader, service, and loader.
-->

## **Milestone 2: Second Vertical Slice — Domain B (E2E)**

| ID | Epic | Feature/Task | Status | Dependencies | PRP_Link |
| :---- | :---- | :---- | :---- | :---- | :---- |
| R-015 | M2 | Inventory legacy cleaners/domains and produce migration plan | READY_FOR_PRP | - | - |
| R-020 | M2 | Profile Domain B inputs; define data contract strategy | READY_FOR_PRP | - | - |
| F-020 | M2 | Add Pydantic models for Domain B | PENDING | R-020 | - |
| F-021 | M2 | Implement Domain B transformation service (pure, validated) | PENDING | F-020 | - |
| F-022 | M2 | Extend `data_sources.yml` with Domain B patterns/table/pk | PENDING | R-020 | - |
| F-023 | M2 | Unit/integration tests for Domain B models + service | PENDING | F-020, F-021 | - |
| F-024 | M2 | Execute Domain B via existing Dagster job + CLI example | PENDING | F-021, F-022 | - |
| F-025 | M2 | Migrate Annuity Income domain (收入明细) to new stack | PENDING | R-015 | - |
| F-026 | M2 | Migrate Group Retirement domain (团养缴费) | PENDING | R-015 | - |
| F-027 | M2 | Migrate Awards/Losses ledger (受托/投资 中标/流失) | PENDING | R-015 | - |
| F-028 | M2 | Migrate Health Coverage domains (企康/JK) | PENDING | R-015 | - |
| F-029 | M2 | Migrate Revenue Details/Budget (收入明细/预算) | PENDING | R-015 | - |
| R-016 | M2 | Research ingestion connectors (HTTP/SFTP) and auth strategy | READY_FOR_PRP | - | - |
| F-032 | M2 | Implement HTTP crawler connector + retries/auth + CLI | PENDING | R-016 | - |
| F-033 | M2 | Implement SFTP/FTP downloader connector | PENDING | R-016 | - |
| R-017 | M2 | Assess legacy MongoDB usage; propose deprecation/migration | READY_FOR_PRP | - | - |
| C-020 | M2 | Mongo→Postgres export utility and decommission plan | PENDING | R-017 | - |
| C-021 | M2 | Replace Flask API with read-only export/report script | PENDING | R-017 | - |
| R-025 | M2 | Evaluate Polars adoption for transform/loader performance | READY_FOR_PRP | F-012, F-013 | - |

<!--
Uncertainty segregation: R-020 precedes implementation to de-risk modeling and discovery patterns for the new domain.
-->

## **Milestone 3: Orchestration & Observability**

| ID | Epic | Feature/Task | Status | Dependencies | PRP_Link |
| :---- | :---- | :---- | :---- | :---- | :---- |
| R-030 | M3 | Research Dagster sensors/alerts and minimal SLOs | READY_FOR_PRP | - | - |
| F-030 | M3 | Add schedules for domain jobs | PENDING | R-030 | - |
| F-031 | M3 | Add sensors for data quality (record counts, null rates, latency) | PENDING | R-030 | - |
| C-030 | M3 | Configure alerting channel (env-based Slack/email) | PENDING | R-030 | - |

<!--
Explicit dependencies: Schedules/alerts depend on research outcomes to avoid misconfiguration and wasted cycles.
-->

## **Milestone 4: Data Parity & Cutover**

| ID | Epic | Feature/Task | Status | Dependencies | PRP_Link |
| :---- | :---- | :---- | :---- | :---- | :---- |
| R-040 | M4 | Research diffing approach for MySQL→Postgres parity (types, keys, tolerances) | READY_FOR_PRP | - | - |
| F-040 | M4 | Implement diff tool + report for domain outputs | PENDING | R-040 | - |
| F-041 | M4 | Dual-run on historical samples; capture mismatches and root causes | PENDING | F-040 | - |
| F-042 | M4 | Resolve mismatches; document reconciliation rules | PENDING | F-041 | - |
| C-040 | M4 | Draft cutover + rollback plan with acceptance gates | PENDING | F-041 | - |

<!--
Vertical value: Demonstrable parity with auditable reports is a tangible outcome that de-risks production cutover.
-->

## **Milestone 5: Deployment & Handover**

| ID | Epic | Feature/Task | Status | Dependencies | PRP_Link |
| :---- | :---- | :---- | :---- | :---- | :---- |
| C-050 | M5 | Deploy Dagster + Postgres to target environment (non-Docker) | PENDING | F-030, F-031 | - |
| C-051 | M5 | Operations + developer docs (runbooks, models, CLI) | PENDING | F-024, F-031 | - |
| C-052 | M5 | Archive legacy `annuity_hub` repository to read-only | PENDING | F-042, C-040 | - |

<!-- Add more milestones as needed -->

## **Key**

### **ID Prefix**

- **F-XXX**: Feature Implementation Task  
- **R-XXX**: Research / Spike Task  
- **C-XXX**: Chore / Refactoring Task

### **Status Lifecycle**

1. PENDING: Planned but not ready.  
2. READY_FOR_PRP: All dependencies are COMPLETED. Ready for PRP generation.  
3. PRP_GENERATED: PRP is created and linked. Ready for an execution agent.  
4. IN_PROGRESS: An agent is actively working on the task.  
5. VALIDATING: Code is complete, agent is running validation loops.  
6. COMPLETED: All validation gates passed.  
7. BLOCKED: Progress is impeded. Requires human review.
