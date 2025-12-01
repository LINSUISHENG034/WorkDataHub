# Migration Strategy

### Strangler Fig Execution Plan

**Phase 1: MVP (Epics 1-8)**

| Month | Deliverable | Parity Status |
|-------|-------------|---------------|
| M1 | Foundation + Validation + Discovery | N/A (infrastructure) |
| M2 | Annuity domain migration | ✅ 100% parity with legacy |
| M3 | Enrichment (stub), Testing, Orchestration | ✅ Stub validates parity |
| M4 | Monitoring, production readiness | ✅ Ongoing parity monitoring |

**Phase 2: Growth (Epics 9-10)**

| Month | Deliverable | Parity Status |
|-------|-------------|---------------|
| M5-M6 | 5 additional domains | ✅ Per-domain parity tests |
| M7 | Full enrichment service (Stories 5.3-5.8) | ⚠️ Backfill temporary IDs |
| M8 | Configuration & tooling | ✅ Maintain parity |

### Parallel Running Strategy

**M2-M4 (MVP Phase):**
- **New system:** Annuity pipeline runs in parallel with legacy
- **Outputs:** Both new and legacy write to separate database schemas
- **Validation:** CI parity tests compare outputs
- **Cutover:** After 3 months of 100% parity, switch traffic to new system

**M5-M8 (Growth Phase):**
- **Repeat:** Apply same parallel running to each new domain
- **Enrichment backfill:** Async job resolves MVP temporary IDs → real company IDs
- **Legacy decommission:** After 6 months of stable production, retire legacy system

---
