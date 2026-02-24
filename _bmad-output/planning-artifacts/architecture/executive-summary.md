# Executive Summary

This architecture defines the technical foundation for WorkDataHub, a brownfield migration project transforming a monolithic legacy ETL system into a modern, declarative, testable data platform. The architecture supports **10 epics with 100+ user stories** across MVP (Phase 1) and Growth (Phase 2) phases.

**Key Architectural Decisions:**
1. **File-Pattern-Aware Version Detection** - Intelligent version selection scoped per domain
2. **Legacy-Compatible Temporary Company IDs** - HMAC-based stable IDs with normalization parity
3. **Hybrid Pipeline Step Protocol** - Support both DataFrame and row-level transformations
4. **Hybrid Error Context Standards** - Structured exceptions with required context fields
5. **Explicit Chinese Date Format Priority** - Predictable parsing without fallback surprises
6. **Stub-Only Enrichment MVP** - Defer complex enrichment to Growth phase
7. **Comprehensive Naming Conventions** - Chinese Pydantic fields, English database columns
8. **structlog with Sanitization** - True structured logging with sensitive data protection

**Architecture Type:** Brownfield - Strangler Fig migration pattern with 100% legacy parity requirement

---
