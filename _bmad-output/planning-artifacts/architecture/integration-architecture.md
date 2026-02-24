# Integration Architecture

### Epic Dependency Graph

```
Epic 1 (Foundation) ✅
  ├─> Epic 2 (Validation) ✅
  ├─> Epic 3 (File Discovery) ✅
  ├─> Epic 6 (Enrichment — full 5-layer architecture) ✅
  ├─> Epic 7 (Testing/Modularization) ✅
  └─> Epic 8 (Orchestration — Dagster active) ✅

Epic 4 (Annuity Migration) ✅
  ├─ depends on: Epic 1, 2, 3, 6
  └─> Epic 5 (Infrastructure Layer) ✅

Epic 5 (Infrastructure Layer) ✅
  ├─ depends on: Epic 4 (refactors annuity implementation)
  └─> Growth Domains (annual_award, annual_loss)

Epic 7.6 (Customer MDM) ✅
  ├─ depends on: Epic 4 (annuity_performance source data)
  └─> Post-ETL Hook pattern (contract sync, snapshot refresh)

Growth Domains (in progress)
  ├─ depends on: Epic 5 (infrastructure components)
  ├─ annual_award ✅, annual_loss ✅, sandbox_trustee_performance ✅
  └─> Additional domains TBD
```

### Key Integration Points

**Epic 1 → Epic 2:**
- Foundation provides `Pipeline` class
- Validation provides `BronzeSchema`, `GoldSchema` (pandera)
- Validation provides `PydanticValidator` (row-level)

**Epic 2 → Epic 4:**
- Annuity pipeline uses Bronze/Silver/Gold validation layers
- `utils/date_parser.py` (Decision #5) used in Pydantic validators

**Epic 3 → Epic 4:**
- File Discovery provides `VersionedPath` (Decision #1)
- `DataSourceConnector` configures annuity file patterns

**Epic 4 → Epic 5:**
- Epic 5 extracts infrastructure from Epic 4 implementation
- Refactors domain layer from 3,446 to <500 lines
- Establishes reusable infrastructure components

**Epic 5 → Epic 10:**
- Infrastructure layer enables rapid domain migration
- Reusable components (enrichment, validation, transforms)
- Python code composition pattern (Decision #10)

**Epic 6 → Epic 4:**
- `EnrichmentGateway.enrich()` called in annuity pipeline (Story 4.3)
- Full 5-layer resolution: YAML Config → DB Cache → Existing Column → EQC API → Temp ID
- EQC API with confidence scoring and budget control (Decision #6, updated)

**Epic 7 → All:**
- Parity tests enforce legacy compatibility (Strangler Fig pattern)
- CI blocks deployment if parity fails
- Epic 7 also covers package modularization (800-line limit enforcement)

**Epic 8 → All:**
- Dagster active — `JOB_REGISTRY` maps domains to Dagster JobDefinitions
- CLI and Dagster UI both serve as execution interfaces
- `DOMAIN_SERVICE_REGISTRY` enables dynamic domain dispatch in pipeline ops

**Epic 7.6 (Customer MDM) → Epic 4:**
- Post-ETL hooks triggered after `annuity_performance` ETL completion
- `contract_status_sync` → `customer.customer_plan_contract`
- `snapshot_refresh` → `customer.fct_customer_product_line_monthly`

**Epic 9 → All:**
- `structlog` (Decision #8) used by all modules
- `ErrorContext` (Decision #4) feeds structured logs

---
