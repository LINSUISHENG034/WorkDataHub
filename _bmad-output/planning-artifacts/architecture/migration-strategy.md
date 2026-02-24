# Migration Strategy

> **Last updated:** 2026-02 | **Status:** MVP complete, Growth phase in progress

### Strangler Fig Execution Plan

**Phase 1: MVP (Epics 1-7) — ✅ COMPLETED (2025-11 ~ 2025-12)**

| Period | Deliverable | Status |
|--------|-------------|--------|
| 2025-11 | Epic 1: Foundation + Validation + File Discovery | ✅ Complete |
| 2025-11 | Epic 2-3: Data Quality Framework + File Discovery | ✅ Complete |
| 2025-11 | Epic 4: Annuity Performance domain migration | ✅ 100% parity |
| 2025-12 | Epic 5: Infrastructure Layer extraction | ✅ Complete |
| 2025-12 | Epic 6: Full 5-layer Enrichment (YAML → DB → Existing → EQC API → Temp ID) | ✅ Complete |
| 2025-12 | Epic 7: Package modularization + Domain Registry | ✅ Complete |

**Phase 2: Growth — In Progress (2026-01 ~)**

| Period | Deliverable | Status |
|--------|-------------|--------|
| 2026-01 | Epic 7.6: Customer MDM (Post-ETL Hooks) | ✅ Complete |
| 2026-01 | Growth domains: annual_award, annual_loss | ✅ Complete |
| 2026-01 | Growth domains: annuity_income | ✅ Complete |
| 2026-02 | sandbox_trustee_performance | ✅ Complete |
| TBD | Additional domains | Pending |
| TBD | Legacy decommission | Pending |

### Parallel Running Strategy

**MVP Phase (completed):**
- New system ran in parallel with legacy for annuity_performance domain
- CI parity tests validated 100% output match
- Cutover completed for annuity_performance

**Growth Phase (in progress):**
- Same parallel running pattern applied to each new domain
- 5-layer enrichment resolves company IDs (no longer stub-only)
- Legacy decommission planned after all domains migrated and stable

---
