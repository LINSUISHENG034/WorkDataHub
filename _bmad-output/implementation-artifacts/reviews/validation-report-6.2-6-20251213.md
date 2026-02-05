# Validation Report: Story 6.2.6 – Reference Data Observability

**Document:** `docs/sprint-artifacts/stories/6.2-6-reference-data-observability.md`  
**Checklist:** `.bmad/bmm/workflows/4-implementation/create-story/checklist.md`  
**Date:** 2025-12-13

---

## Summary

- Overall: 6/12 items passed (50%)
- Critical Issues: 1 fail, 5 partials

---

## Section Results

### 1) Story Structure (4/4 ✅)
- ✓ PASS – Story statement and status present (`ready-for-dev`), lines 1-31.
- ✓ PASS – Acceptance criteria cover functional, risk, and verification scopes, lines 34-85.
- ✓ PASS – Tasks/subtasks mapped to ACs with IDs, lines 86-118.
- ✓ PASS – Dev notes and prior-story references captured with file pointers, lines 120-165.

### 2) Technical Coverage (2/6 ✅ / 1✗ / 3⚠)
- ✓ PASS – Core observability features (metrics, alerts, CSV export, audit log) enumerated, lines 36-60.
- ✓ PASS – Non-functional/perf/privacy and test plans listed (perf targets, privacy notes, unit/integration tests, commands), lines 64-84, 467-475.
- ✗ FAIL – Config-driven table discovery missing: AC forbids hardcoding (line 41) but dev plan uses constant `REFERENCE_TABLES` (lines 230-234) with no binding to `config/data_sources.yml` or schema introspection.
- ⚠ PARTIAL – HybridReferenceService integration unspecified: constraint says “Must integrate with existing HybridReferenceService metrics” (line 10) but no hook/contract for ingesting `HybridResult` metrics into dashboard/alerts.
- ⚠ PARTIAL – Sensitive-field governance unclear: AC mentions “if any defined in config” (line 70) but CSV export only accepts ad-hoc `exclude_columns` (lines 340-394) with no source-of-truth or retention/ACL guidance.
- ⚠ PARTIAL – Audit logging scope underspecified: AC requires instrumenting `GenericBackfillService`/`ReferenceSyncService` (lines 56-60) yet dev notes only show stubs (lines 396-405) without event schema, job/domain context, or hook points.

### 3) Disaster Prevention & Ops (0/2 ✅ / 0✗ / 2⚠)
- ⚠ PARTIAL – Alert routing/resilience: story confines alerts to structlog WARN (lines 44-47) but lacks sink/forwarding (pager/metrics), dedupe, or degraded-mode toggles to avoid noise regressions.
- ⚠ PARTIAL – CSV export governance: default `exports/` path (lines 49-55, 340-394) has no retention/ACL/encryption guidance, backpressure limits, or concurrent run handling; risks PII leakage and disk churn.

---

## Failed Items
- Config-driven table discovery absent; violates “no hardcoding” requirement and risks drift when tables change. Need to load table list from `config/data_sources.yml` (or schema introspection) and drive all query generation from it.

---

## Partial Items
- HybridReferenceService integration not defined; unclear how `HybridResult` metrics or degraded-mode flags feed dashboard/alerts.
- Sensitive-field governance unspecified; no authoritative list or control for CSV exports and audit payloads.
- Audit logging lacks event schema, context fields, and explicit hook locations in `GenericBackfillService`/`ReferenceSyncService`.
- Alert routing lacks sink/SLO integration and noise controls.
- CSV export lacks retention/ACL/backpressure guidance.

---

## Recommendations
1. **Must Fix**
   - Drive table discovery from `config/data_sources.yml` (or schema introspection) and forbid hardcoded lists in `ObservabilityService`; ensure AC #1 is test-backed.
2. **Should Improve**
   - Define `HybridReferenceService` → observability contract: which `HybridResult` metrics surface in dashboards/alerts, and how thresholds relate to service-level warnings.
   - Establish sensitive-field source-of-truth (config key) and apply to CSV export + audit payloads; document retention/ACL/encryption.
   - Specify audit event schema (fields, event name, log level) and exact hook points in `GenericBackfillService`/`ReferenceSyncService`.
3. **Consider**
   - Route structlog alerts to monitoring (metrics/log shipper) with dedupe/toggle; add backpressure and cleanup rules for `exports/` directory.

