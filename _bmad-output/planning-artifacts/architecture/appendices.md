# Appendices

### Appendix A: Decision Summary Table

| # | Decision | Impact | MVP/Growth |
|---|----------|--------|------------|
| 1 | File-Pattern-Aware Version Detection | Epic 3 (Discovery) | MVP |
| 2 | Legacy-Compatible Temporary Company IDs | Epic 6 (Enrichment) | MVP |
| 3 | Hybrid Pipeline Step Protocol | Epic 1, 4, 9 (All pipelines) | MVP |
| 4 | Hybrid Error Context Standards | Epic 2, 8 (Validation, Monitoring) | MVP |
| 5 | Explicit Chinese Date Format Priority | Epic 2, 4 (Validation, Annuity) | MVP |
| 6 | 5-Layer Company Enrichment Architecture | Epic 6 (Enrichment) | MVP+Growth (fully implemented) |
| 7 | Comprehensive Naming Conventions | All epics | MVP |
| 8 | structlog with Sanitization | Epic 1, 8 (Foundation, Monitoring) | MVP |
| 9 | Configuration-Driven Generic Steps | Epic 1, 4, 9 (All pipelines) | MVP |
| 10 | Infrastructure Layer & Pipeline Composition | Epic 5 (Infrastructure), Epic 9 (Growth) | MVP |
| 11 | Hybrid Reference Data Management | Epic 5 (Reference backfill) | MVP |
| 12 | Customer MDM Post-ETL Hook Architecture | Epic 7.6 (Customer MDM) | Growth |

### Appendix B: Technology Dependency Matrix

| Technology | Used By | Justification |
|------------|---------|---------------|
| Python 3.10+ | All modules | Corporate standard, type system maturity |
| uv | All dependencies | 10-100x faster than pip, reproducible builds |
| Dagster | Orchestration (active) | JOB_REGISTRY pattern, CLI + Dagster UI execution |
| Pydantic v2 | Row-level validation | 5-50x faster than v1, better error messages |
| pandas | DataFrame operations | Team expertise, ecosystem maturity |
| pandera | Bronze/Gold schemas | DataFrame validation, complements Pydantic |
| structlog | All logging | True structured logging, context binding |
| pytest | All testing | Industry standard, rich plugin ecosystem |
| mypy (strict) | All type checking | NFR requirement: 100% type coverage |
| ruff | All linting/formatting | 10-100x faster than black + flake8 + isort |

### Appendix C: Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `WDH_ALIAS_SALT` | ✅ MVP | N/A | HMAC salt for temporary company IDs (Decision #2) |
| `WDH_ENRICH_COMPANY_ID` | ❌ | `0` | Enable enrichment service (5-layer architecture) |
| `WDH_COMPANY_ENRICHMENT_ENABLED` | ❌ | `0` | Simplified enrichment toggle |
| `WDH_PROVIDER_EQC_TOKEN` | ✅ (if enrichment enabled) | N/A | EQC API token (30-min validity, auto-refresh via Playwright) |
| `WDH_ENRICH_SYNC_BUDGET` | ❌ | `0` | Max sync API calls per run (budget control) |
| `LOG_LEVEL` | ❌ | `INFO` | Logging level (Decision #8: DEBUG/INFO/WARNING/ERROR) |
| `LOG_TO_FILE` | ❌ | `1` | Enable file logging (Decision #8) |
| `LOG_FILE_PATH` | ❌ | `logs/workdatahub.log` | Log file path (Decision #8) |

### Appendix D: Glossary

| Term | Definition |
|------|------------|
| **Bronze Layer** | Raw data with structural validation only (pandera) |
| **Silver Layer** | Cleansed data with per-row business validation (Pydantic) |
| **Gold Layer** | Business-ready data with final projections and schemas (pandera) |
| **Strangler Fig** | Migration pattern: gradually replace legacy with parallel running |
| **Parity Test** | CI-enforced test comparing new vs legacy outputs (100% match required) |
| **Temporary Company ID** | Stable ID (`IN<16-char-Base32>`) for unresolved companies (Decision #2) |
| **Version Detection** | Algorithm selecting correct V1/V2/V3 folder per domain (Decision #1) |
| **DataFrame Step** | Bulk transformation operating on entire DataFrame (Decision #3) |
| **Row Step** | Per-row transformation with detailed validation/enrichment (Decision #3) |
| **ErrorContext** | Structured error metadata for debugging (Decision #4) |

---

**End of Architecture Document**

_This architecture has been approved for implementation. All 100+ user stories across Epics 1-10 must adhere to the decisions, patterns, and standards defined in this document._

_For questions or clarification, refer to the architecture documents in `_bmad-output/planning-artifacts/architecture/`._
