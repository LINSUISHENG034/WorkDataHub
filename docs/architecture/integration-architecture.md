# Integration Architecture

### Epic Dependency Graph

```
Epic 1 (Foundation)
  ├─> Epic 2 (Validation)
  ├─> Epic 3 (File Discovery)
  ├─> Epic 5 (Enrichment - MVP stub only)
  ├─> Epic 6 (Testing)
  ├─> Epic 7 (Orchestration)
  └─> Epic 8 (Monitoring)

Epic 4 (Annuity Migration)
  ├─ depends on: Epic 1, 2, 3, 5 (stub), 6
  └─> Epic 9 (Growth Domains)

Epic 9 (Growth Domains)
  ├─ depends on: Epic 4 (pattern reference)
  └─> Epic 5 (full enrichment), Epic 10 (config/tooling)
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

**Epic 5 → Epic 4:**
- `EnrichmentGateway.enrich()` called in annuity pipeline (Story 4.3)
- MVP: Returns temporary IDs (Decision #2, Decision #6)
- Growth: Returns real company IDs (Epic 9)

**Epic 6 → All:**
- Parity tests enforce legacy compatibility (Strangler Fig pattern)
- CI blocks deployment if parity fails

**Epic 7 → All:**
- Dagster definitions wrap pipelines for UI monitoring (deferred to post-MVP)
- CLI remains primary execution method for MVP

**Epic 8 → All:**
- `structlog` (Decision #8) used by all modules
- `ErrorContext` (Decision #4) feeds structured logs

---
