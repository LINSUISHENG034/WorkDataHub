# Integration Architecture

### Epic Dependency Graph

```
Epic 1 (Foundation)
  ├─> Epic 2 (Validation)
  ├─> Epic 3 (File Discovery)
  ├─> Epic 6 (Enrichment - MVP stub only)
  ├─> Epic 7 (Testing)
  ├─> Epic 8 (Orchestration)
  └─> Epic 9 (Monitoring)

Epic 4 (Annuity Migration)
  ├─ depends on: Epic 1, 2, 3, 6 (stub), 7
  └─> Epic 5 (Infrastructure Layer)

Epic 5 (Infrastructure Layer)
  ├─ depends on: Epic 4 (refactors annuity implementation)
  └─> Epic 10 (Growth Domains)

Epic 10 (Growth Domains)
  ├─ depends on: Epic 5 (infrastructure components)
  └─> Epic 6 (full enrichment), Epic 11 (config/tooling)
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
- MVP: Returns temporary IDs (Decision #2, Decision #6)
- Growth: Returns real company IDs (Epic 10)

**Epic 7 → All:**
- Parity tests enforce legacy compatibility (Strangler Fig pattern)
- CI blocks deployment if parity fails

**Epic 8 → All:**
- Dagster definitions wrap pipelines for UI monitoring (deferred to post-MVP)
- CLI remains primary execution method for MVP

**Epic 9 → All:**
- `structlog` (Decision #8) used by all modules
- `ErrorContext` (Decision #4) feeds structured logs

---
