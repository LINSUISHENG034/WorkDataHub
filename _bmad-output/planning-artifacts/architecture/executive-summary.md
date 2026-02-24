# Executive Summary

This architecture defines the technical foundation for WorkDataHub, a brownfield migration project transforming a monolithic legacy ETL system into a modern, declarative, testable data platform. The architecture supports **10+ epics with 100+ user stories** across MVP (Phase 1, completed) and Growth (Phase 2, in progress) phases.

**Key Architectural Decisions:**
1. **File-Pattern-Aware Version Detection** - Intelligent version selection scoped per domain
2. **Legacy-Compatible Temporary Company IDs** - HMAC-based stable IDs with normalization parity
3. **Hybrid Pipeline Step Protocol** - Support both DataFrame and row-level transformations
4. **Hybrid Error Context Standards** - Structured exceptions with required context fields
5. **Explicit Chinese Date Format Priority** - Predictable parsing without fallback surprises
6. **5-Layer Company Enrichment Architecture** - Full hierarchical resolution (YAML → DB Cache → Existing Column → EQC API → Temp ID)
7. **Comprehensive Naming Conventions** - Chinese Pydantic fields, English database columns
8. **structlog with Sanitization** - True structured logging with sensitive data protection
9. **Configuration-Driven Generic Steps** - Reusable DataFrame transformation steps with dict/lambda configuration
10. **Infrastructure Layer & Pipeline Composition** - Extracted reusable infrastructure with Python Code Composition pattern
11. **Hybrid Reference Data Management** - Two-layer model combining authoritative data with auto-derived backfill
12. **Customer MDM Post-ETL Hook Architecture** - Registry-based hooks for contract sync and snapshot refresh

**Architecture Type:** Brownfield - Strangler Fig migration pattern with 100% legacy parity requirement

---
